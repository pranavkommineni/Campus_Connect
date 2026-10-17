import csv
import io
from datetime import datetime
from typing import Optional

import qrcode
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from .. import services as S
from ..aws import get_storage
from ..core import current_user, get_db, require_roles, settings
from ..models import (Bookmark, Certificate, Event, Feedback, Notification, Registration, User, now)

router = APIRouter(prefix="/api", tags=["events"])


class EventIn(BaseModel):
    title: str = Field(max_length=200)
    description: str = ""
    category_id: int
    venue_id: int
    start_at: datetime
    end_at: datetime
    capacity: int
    registration_deadline: datetime
    eligibility: str = Field("Open to all students", max_length=300)
    department: str = Field("", max_length=100)
    academic_year: str = Field("", max_length=30)
    contact_info: str = Field("", max_length=200)
    club_id: Optional[int] = None  # admin only
    submit: bool = False


def sweep_completed(db: Session):
    db.execute(update(Event).where(Event.status == "published", Event.end_at < now()).values(status="completed"))
    db.commit()


def ev_out(db: Session, e: Event, user=None, full=False):
    taken = S.seats_taken(db, e.id)
    d = {"id": e.id, "title": e.title, "description": e.description, "category": e.category.name,
         "category_id": e.category_id, "club": e.club.name, "club_id": e.club_id, "venue": e.venue.name,
         "venue_id": e.venue_id, "start_at": S.iso(e.start_at), "end_at": S.iso(e.end_at),
         "capacity": e.capacity, "seats_left": max(e.capacity - taken, 0), "registered": taken,
         "registration_deadline": S.iso(e.registration_deadline), "poster_url": e.poster_url,
         "eligibility": e.eligibility, "department": e.department, "academic_year": e.academic_year,
         "contact_info": e.contact_info, "status": e.status, "review_note": e.review_note}
    if user and user.role == "student":
        reg = db.scalars(select(Registration).where(Registration.event_id == e.id,
                                                    Registration.student_id == user.id)).first()
        d["my_registration"] = ({"id": reg.id, "status": reg.status, "attended": reg.attended}
                                if reg and reg.status != "cancelled" else None)
        d["bookmarked"] = bool(db.get(Bookmark, (user.id, e.id)))
    return d


def get_event(db, event_id) -> Event:
    e = db.get(Event, event_id)
    if not e:
        raise HTTPException(404, "Event not found")
    return e


def optional_user(db: Session = Depends(get_db), creds=Depends(__import__("app.core", fromlist=["bearer"]).bearer)):
    if not creds:
        return None
    try:
        return current_user(creds, db)
    except HTTPException:
        return None


@router.get("/events")
def list_events(q: str = "", category_id: int | None = None, club_id: int | None = None,
                date_from: datetime | None = None, date_to: datetime | None = None,
                sort: str = "start", page: int = Query(1, ge=1), page_size: int = Query(9, ge=1, le=50),
                db: Session = Depends(get_db), user=Depends(optional_user)):
    sweep_completed(db)
    f = [Event.status == "published"]
    if q:
        like = f"%{q.strip()}%"
        f.append(or_(Event.title.ilike(like), Event.description.ilike(like)))
    if category_id:
        f.append(Event.category_id == category_id)
    if club_id:
        f.append(Event.club_id == club_id)
    if date_from:
        f.append(Event.start_at >= S.utc(date_from))
    if date_to:
        f.append(Event.start_at <= S.utc(date_to))
    order = {"start": Event.start_at.asc(), "-start": Event.start_at.desc(), "title": Event.title.asc()}.get(sort, Event.start_at.asc())
    total = db.scalar(select(func.count()).select_from(Event).where(and_(*f)))
    rows = db.scalars(select(Event).where(and_(*f)).order_by(order).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [ev_out(db, e, user) for e in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/events/manage")
def manage_events(status: str = "", db: Session = Depends(get_db), user=Depends(require_roles("club", "admin"))):
    sweep_completed(db)
    q = select(Event).order_by(Event.start_at.desc())
    if user.role == "club":
        q = q.where(Event.club_id == (user.club.id if user.club else -1))
    if status:
        q = q.where(Event.status == status)
    return [ev_out(db, e) for e in db.scalars(q).all()]


@router.get("/events/{event_id}")
def event_detail(event_id: int, db: Session = Depends(get_db), user=Depends(optional_user)):
    e = get_event(db, event_id)
    if e.status not in ("published", "completed", "cancelled"):
        if not user or user.role not in ("club", "admin"):
            raise HTTPException(404, "Event not found")
        S.assert_event_access(user, e)
    out = ev_out(db, e, user)
    avg = db.scalar(select(func.avg(Feedback.rating)).where(Feedback.event_id == e.id))
    out["avg_rating"] = round(float(avg), 2) if avg else None
    return out


def _payload(b: EventIn) -> dict:
    return b.model_dump(exclude={"club_id", "submit"}) | {
        "start_at": S.utc(b.start_at), "end_at": S.utc(b.end_at),
        "registration_deadline": S.utc(b.registration_deadline)}


@router.post("/events", status_code=201)
def create_event(b: EventIn, db: Session = Depends(get_db), user=Depends(require_roles("club", "admin"))):
    club = S.acting_club(db, user, b.club_id)
    try:
        ev = S.create_event(db, user, club, _payload(b), b.submit)
    except ValueError as ex:
        raise HTTPException(422, {"errors": ex.args[0]})
    db.commit()
    return ev_out(db, ev)


@router.put("/events/{event_id}")
def update_event(event_id: int, b: EventIn, db: Session = Depends(get_db), user=Depends(require_roles("club", "admin"))):
    ev = db.scalars(select(Event).where(Event.id == event_id).with_for_update()).first()
    if not ev:
        raise HTTPException(404, "Event not found")
    S.assert_event_access(user, ev)
    if ev.status in ("completed", "cancelled"):
        raise HTTPException(400, f"Cannot edit a {ev.status} event")
    d = _payload(b)
    errs = S.validate_event_fields(d, existing=ev)
    venue = db.get(__import__("app.models", fromlist=["Venue"]).Venue, b.venue_id)
    if not venue:
        errs.append("unknown venue")
    elif b.capacity > 0:
        errs += S.check_venue_capacity(venue, b.capacity)
    taken = S.seats_taken(db, ev.id)
    if b.capacity < taken:
        errs.append(f"capacity cannot be below current registrations ({taken})")
    if not errs and ev.status in ("published", "pending_approval") and S.venue_conflict(db, b.venue_id, d["start_at"], d["end_at"], ev.id):
        errs.append("venue is already booked for an overlapping event")
    if errs:
        raise HTTPException(422, {"errors": errs})
    changed = any(getattr(ev, k) != d[k] for k in ("start_at", "end_at", "venue_id"))
    for k, v in d.items():  # explicit field whitelist via EventIn
        setattr(ev, k, v)
    if user.role == "club" and ev.status in ("published", "rejected"):
        ev.status = "pending_approval" if b.submit or ev.status == "rejected" else ev.status
    elif b.submit and ev.status in ("draft", "rejected"):
        S.apply_submit(user, ev, True)
    db.flush()
    if changed:
        for r in db.scalars(select(Registration).where(Registration.event_id == ev.id, Registration.status != "cancelled")):
            S.notify(db, r.student_id, f"'{ev.title}' was updated - please check the new time/venue.")
    S.audit(db, user, "event.update", "event", ev.id, ev.title)
    db.commit()
    return ev_out(db, ev)


@router.post("/events/{event_id}/submit")
def submit_event(event_id: int, db: Session = Depends(get_db), user=Depends(require_roles("club", "admin"))):
    ev = get_event(db, event_id)
    S.assert_event_access(user, ev)
    if ev.status not in ("draft", "rejected"):
        raise HTTPException(400, "Only drafts or rejected events can be submitted")
    if S.venue_conflict(db, ev.venue_id, ev.start_at, ev.end_at, ev.id):
        raise HTTPException(422, {"errors": ["venue is already booked for an overlapping event"]})
    if S.utc(ev.start_at) < now():
        raise HTTPException(422, {"errors": ["start_at is in the past"]})
    S.apply_submit(user, ev, True)
    S.audit(db, user, "event.submit", "event", ev.id, ev.status)
    db.commit()
    return ev_out(db, ev)


class Review(BaseModel):
    note: str = Field("", max_length=500)


@router.post("/events/{event_id}/approve")
def approve(event_id: int, db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    ev = get_event(db, event_id)
    if ev.status != "pending_approval":
        raise HTTPException(400, "Event is not pending approval")
    if S.venue_conflict(db, ev.venue_id, ev.start_at, ev.end_at, ev.id) and \
       db.scalar(select(Event.id).where(Event.venue_id == ev.venue_id, Event.status == "published",
                                         Event.start_at < ev.end_at, Event.end_at > ev.start_at, Event.id != ev.id)):
        raise HTTPException(422, {"errors": ["venue conflict with a published event"]})
    ev.status, ev.review_note = "published", ""
    S.notify(db, ev.club.user_id, f"Your event '{ev.title}' was approved and is now live.")
    S.audit(db, user, "event.approve", "event", ev.id, ev.title)
    db.commit()
    return ev_out(db, ev)


@router.post("/events/{event_id}/reject")
def reject(event_id: int, b: Review, db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    ev = get_event(db, event_id)
    if ev.status != "pending_approval":
        raise HTTPException(400, "Event is not pending approval")
    ev.status, ev.review_note = "rejected", b.note
    S.notify(db, ev.club.user_id, f"Your event '{ev.title}' was rejected. {b.note}")
    S.audit(db, user, "event.reject", "event", ev.id, b.note)
    db.commit()
    return ev_out(db, ev)


@router.post("/events/{event_id}/cancel")
def cancel_event(event_id: int, db: Session = Depends(get_db), user=Depends(require_roles("club", "admin"))):
    ev = get_event(db, event_id)
    S.assert_event_access(user, ev)
    if ev.status in ("cancelled", "completed"):
        raise HTTPException(400, f"Event already {ev.status}")
    ev.status = "cancelled"
    for r in db.scalars(select(Registration).where(Registration.event_id == ev.id, Registration.status != "cancelled")):
        S.notify(db, r.student_id, f"'{ev.title}' has been cancelled.")
    S.audit(db, user, "event.cancel", "event", ev.id, ev.title)
    db.commit()
    return ev_out(db, ev)


@router.post("/events/{event_id}/poster")
async def upload_poster(event_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                        user=Depends(require_roles("club", "admin"))):
    ev = get_event(db, event_id)
    S.assert_event_access(user, ev)
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Poster too large (max {settings.max_upload_mb} MB)")
    sig = {b"\x89PNG\r\n\x1a\n": ".png", b"\xff\xd8\xff": ".jpg"}
    ext = next((x for s, x in sig.items() if data.startswith(s)), ".webp" if data[:4] == b"RIFF" and data[8:12] == b"WEBP" else None)
    if not ext:  # magic bytes, not the client's filename or content-type
        raise HTTPException(400, "Only PNG, JPEG or WebP images are allowed")
    ev.poster_url = get_storage().save(data, ext)
    S.audit(db, user, "event.poster", "event", ev.id)
    db.commit()
    return {"poster_url": ev.poster_url}


# ---------- organizer views ----------
@router.get("/events/{event_id}/attendees")
def attendees(event_id: int, db: Session = Depends(get_db), user=Depends(require_roles("club", "admin"))):
    ev = get_event(db, event_id)
    S.assert_event_access(user, ev)
    rows = db.scalars(select(Registration).where(Registration.event_id == ev.id).order_by(Registration.id)).all()
    return [{"id": r.id, "name": r.student.full_name, "email": r.student.email, "status": r.status,
             "attended": r.attended, "registered_at": S.iso(r.created_at)} for r in rows]


@router.get("/events/{event_id}/attendees.csv")
def attendees_csv(event_id: int, db: Session = Depends(get_db), user=Depends(require_roles("club", "admin"))):
    ev = get_event(db, event_id)
    S.assert_event_access(user, ev)
    S.audit(db, user, "export.attendees", "event", ev.id)
    db.commit()
    rows = [["name", "email", "status", "attended", "checked_in_at"]]
    for r in db.scalars(select(Registration).where(Registration.event_id == ev.id).order_by(Registration.id)):
        rows.append([S.csv_safe(r.student.full_name), r.student.email, r.status, r.attended, S.iso(r.checked_in_at) or ""])
    return csv_response(rows, f"attendees_event_{ev.id}.csv")


@router.get("/events/{event_id}/feedback")
def event_feedback(event_id: int, db: Session = Depends(get_db), user=Depends(require_roles("club", "admin"))):
    ev = get_event(db, event_id)
    S.assert_event_access(user, ev)
    fb = db.scalars(select(Feedback).where(Feedback.event_id == ev.id).order_by(Feedback.id.desc())).all()
    return [{"rating": f.rating, "comment": f.comment, "created_at": S.iso(f.created_at)} for f in fb]


def csv_response(rows, filename):
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


class CheckIn(BaseModel):
    ticket_code: str = Field(min_length=10, max_length=64)


@router.post("/checkin")
def checkin(b: CheckIn, db: Session = Depends(get_db), user=Depends(require_roles("club", "admin"))):
    r = S.check_in(db, user, b.ticket_code.strip())
    return {"student": r.student.full_name, "event": r.event.title, "checked_in_at": S.iso(r.checked_in_at)}


# ---------- student actions ----------
student_only = require_roles("student")


@router.post("/events/{event_id}/register", status_code=201)
def register(event_id: int, db: Session = Depends(get_db), user=Depends(student_only)):
    r = S.register_student(db, event_id, user)
    return {"id": r.id, "status": r.status}


@router.delete("/events/{event_id}/register", status_code=204)
def unregister(event_id: int, db: Session = Depends(get_db), user=Depends(student_only)):
    S.cancel_registration(db, event_id, user)


@router.post("/events/{event_id}/bookmark", status_code=204)
def bookmark(event_id: int, db: Session = Depends(get_db), user=Depends(student_only)):
    get_event(db, event_id)
    if not db.get(Bookmark, (user.id, event_id)):
        db.add(Bookmark(user_id=user.id, event_id=event_id))
        db.commit()


@router.delete("/events/{event_id}/bookmark", status_code=204)
def unbookmark(event_id: int, db: Session = Depends(get_db), user=Depends(student_only)):
    b = db.get(Bookmark, (user.id, event_id))
    if b:
        db.delete(b)
        db.commit()


@router.get("/me/bookmarks")
def my_bookmarks(db: Session = Depends(get_db), user=Depends(student_only)):
    ids = db.scalars(select(Bookmark.event_id).where(Bookmark.user_id == user.id)).all()
    return [ev_out(db, db.get(Event, i), user) for i in ids]


@router.get("/me/registrations")
def my_registrations(db: Session = Depends(get_db), user=Depends(student_only)):
    rows = db.scalars(select(Registration).where(Registration.student_id == user.id, Registration.status != "cancelled")
                      .order_by(Registration.id.desc())).all()
    return [{"id": r.id, "status": r.status, "attended": r.attended, "ticket_code": r.ticket_code,
             "event": ev_out(db, r.event),
             "feedback_given": bool(db.scalar(select(Feedback.id).where(Feedback.event_id == r.event_id, Feedback.student_id == user.id)))}
            for r in rows]


@router.get("/registrations/{reg_id}/qr.png")
def qr(reg_id: int, db: Session = Depends(get_db), user=Depends(student_only)):
    r = db.get(Registration, reg_id)
    if not r or r.student_id != user.id or r.status != "registered":  # owner only: prevents IDOR
        raise HTTPException(404, "Ticket not found")
    buf = io.BytesIO()
    qrcode.make(r.ticket_code).save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field("", max_length=2000)


@router.post("/events/{event_id}/feedback", status_code=201)
def give_feedback(event_id: int, b: FeedbackIn, db: Session = Depends(get_db), user=Depends(student_only)):
    r = db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.student_id == user.id)).first()
    if not r or not r.attended:
        raise HTTPException(403, "Only attendees can leave feedback")
    if db.scalar(select(Feedback.id).where(Feedback.event_id == event_id, Feedback.student_id == user.id)):
        raise HTTPException(409, "Feedback already submitted")
    db.add(Feedback(event_id=event_id, student_id=user.id, rating=b.rating, comment=b.comment))
    db.commit()
    return {"ok": True}


@router.get("/registrations/{reg_id}/certificate")
def certificate(reg_id: int, db: Session = Depends(get_db), user=Depends(student_only)):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    import secrets
    r = db.get(Registration, reg_id)
    if not r or r.student_id != user.id:
        raise HTTPException(404, "Not found")
    if not r.attended:
        raise HTTPException(403, "Certificates are issued to attendees only")
    if S.utc(r.event.end_at) > now():
        raise HTTPException(403, "Certificate available after the event ends")
    cert = db.scalars(select(Certificate).where(Certificate.registration_id == r.id)).first()
    if not cert:
        cert = Certificate(registration_id=r.id, code=secrets.token_hex(8).upper())
        db.add(cert)
        db.commit()
    buf = io.BytesIO()
    w, h = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.setFillColorRGB(0.07, 0.09, 0.25)
    c.rect(0, 0, w, h, fill=1)
    c.setStrokeColorRGB(0.55, 0.6, 1)
    c.rect(25, 25, w - 50, h - 50)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(w / 2, h - 120, "Certificate of Participation")
    c.setFont("Helvetica", 16)
    c.drawCentredString(w / 2, h - 175, "This is to certify that")
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(w / 2, h - 225, r.student.full_name)
    c.setFont("Helvetica", 16)
    c.drawCentredString(w / 2, h - 275, "participated in")
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(w / 2, h - 315, r.event.title[:70])
    c.setFont("Helvetica", 14)
    c.drawCentredString(w / 2, h - 350, f"organised by {r.event.club.name} on {S.utc(r.event.start_at):%d %B %Y}")
    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, 50, f"CampusConnect - Verification code {cert.code}")
    c.save()
    return Response(buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="certificate_{cert.code}.pdf"'})


# ---------- notifications ----------
@router.get("/notifications")
def notifications(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(100)).all()
    return [{"id": n.id, "message": n.message, "is_read": n.is_read, "created_at": S.iso(n.created_at)} for n in rows]


@router.post("/notifications/read-all", status_code=204)
def read_all(db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.execute(update(Notification).where(Notification.user_id == user.id).values(is_read=True))
    db.commit()


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    from ..models import Category, Club, Venue
    return {"categories": [{"id": c.id, "name": c.name} for c in db.scalars(select(Category).order_by(Category.name))],
            "venues": [{"id": v.id, "name": v.name, "capacity": v.capacity} for v in db.scalars(select(Venue).order_by(Venue.name))],
            "clubs": [{"id": c.id, "name": c.name} for c in db.scalars(select(Club).where(Club.status == "approved").order_by(Club.name))]}
