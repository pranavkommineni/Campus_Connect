from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import services as S
from ..core import get_db, require_roles
from ..models import AuditLog, Category, Club, Event, Feedback, Registration, User, Venue
from .events import csv_response

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_roles("admin"))])
admin = require_roles("admin")


@router.get("/users")
def users(role: str = "", db: Session = Depends(get_db)):
    q = select(User).order_by(User.id)
    if role:
        q = q.where(User.role == role)
    return [{"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active,
             "club": {"id": u.club.id, "name": u.club.name, "status": u.club.status} if u.club else None}
            for u in db.scalars(q)]


class Active(BaseModel):
    is_active: bool


@router.patch("/users/{uid}")
def set_active(uid: int, b: Active, db: Session = Depends(get_db), me=Depends(admin)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == me.id or u.role == "admin":
        raise HTTPException(400, "Admin accounts cannot be suspended here")
    u.is_active = b.is_active
    S.audit(db, me, "user.activate" if b.is_active else "user.suspend", "user", u.id, u.email)
    db.commit()
    return {"id": u.id, "is_active": u.is_active}


class ClubStatus(BaseModel):
    status: str = Field(pattern="^(approved|suspended|pending)$")


@router.patch("/clubs/{cid}")
def club_status(cid: int, b: ClubStatus, db: Session = Depends(get_db), me=Depends(admin)):
    c = db.get(Club, cid)
    if not c:
        raise HTTPException(404, "Club not found")
    c.status = b.status
    S.notify(db, c.user_id, f"Your club '{c.name}' is now {b.status}.")
    S.audit(db, me, f"club.{b.status}", "club", c.id, c.name)
    db.commit()
    return {"id": c.id, "status": c.status}


class VenueIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    location: str = ""
    capacity: int = Field(ge=1, le=100000)


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)


def _add(db, obj, me, action):
    db.add(obj)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Already exists")
    S.audit(db, me, action, obj.__tablename__, obj.id, obj.name)
    db.commit()
    return {"id": obj.id, "name": obj.name}


@router.post("/venues", status_code=201)
def add_venue(b: VenueIn, db: Session = Depends(get_db), me=Depends(admin)):
    return _add(db, Venue(**b.model_dump()), me, "venue.create")


@router.put("/venues/{vid}")
def edit_venue(vid: int, b: VenueIn, db: Session = Depends(get_db), me=Depends(admin)):
    v = db.get(Venue, vid)
    if not v:
        raise HTTPException(404, "Venue not found")
    for k, val in b.model_dump().items():
        setattr(v, k, val)
    S.audit(db, me, "venue.update", "venues", v.id, v.name)
    db.commit()
    return {"id": v.id, "name": v.name}


@router.post("/categories", status_code=201)
def add_category(b: CategoryIn, db: Session = Depends(get_db), me=Depends(admin)):
    return _add(db, Category(name=b.name), me, "category.create")


@router.get("/audit")
def audit_logs(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500))).all()
    return [{"id": a.id, "actor_id": a.actor_id, "action": a.action, "entity": a.entity, "entity_id": a.entity_id,
             "detail": a.detail, "created_at": S.iso(a.created_at)} for a in rows]


@router.get("/analytics")
def analytics(db: Session = Depends(get_db)):
    count = lambda m, *w: db.scalar(select(func.count()).select_from(m).where(*w)) or 0
    by_status = dict(db.execute(select(Event.status, func.count()).group_by(Event.status)).all())
    by_cat = db.execute(select(Category.name, func.count(Registration.id))
                        .select_from(Category).join(Event, Event.category_id == Category.id, isouter=True)
                        .join(Registration, (Registration.event_id == Event.id) & (Registration.status == "registered"), isouter=True)
                        .group_by(Category.name)).all()
    top = db.execute(select(Event.title, func.count(Registration.id).label("n")).join(Registration, Registration.event_id == Event.id)
                     .where(Registration.status == "registered").group_by(Event.id, Event.title)
                     .order_by(func.count(Registration.id).desc()).limit(5)).all()
    avg = db.scalar(select(func.avg(Feedback.rating)))
    return {"students": count(User, User.role == "student"), "clubs": count(Club), "pending_clubs": count(Club, Club.status == "pending"),
            "events": count(Event), "pending_events": count(Event, Event.status == "pending_approval"),
            "registrations": count(Registration, Registration.status == "registered"),
            "attended": count(Registration, Registration.attended.is_(True)),
            "avg_rating": round(float(avg), 2) if avg else None,
            "events_by_status": [{"status": k, "count": v} for k, v in by_status.items()],
            "registrations_by_category": [{"category": n, "count": c} for n, c in by_cat],
            "top_events": [{"title": t, "count": n} for t, n in top]}


@router.get("/reports/events.csv")
def events_report(db: Session = Depends(get_db), me=Depends(admin)):
    rows = [["id", "title", "club", "category", "venue", "start_at", "status", "capacity", "registered"]]
    for e in db.scalars(select(Event).order_by(Event.id)):
        rows.append([e.id, S.csv_safe(e.title), S.csv_safe(e.club.name), e.category.name, e.venue.name, S.iso(e.start_at), e.status, e.capacity, S.seats_taken(db, e.id)])
    S.audit(db, me, "export.events", "event")
    db.commit()
    return csv_response(rows, "events_report.csv")


@router.get("/reports/registrations.csv")
def regs_report(db: Session = Depends(get_db), me=Depends(admin)):
    rows = [["registration_id", "event", "student", "email", "status", "attended"]]
    for r in db.scalars(select(Registration).order_by(Registration.id)):
        rows.append([r.id, S.csv_safe(r.event.title), S.csv_safe(r.student.full_name), r.student.email, r.status, r.attended])
    S.audit(db, me, "export.registrations", "registration")
    db.commit()
    return csv_response(rows, "registrations_report.csv")


@router.get("/reports/attendance.csv")
def attendance_report(db: Session = Depends(get_db), me=Depends(admin)):
    rows = [["event", "registered", "attended", "attendance_rate_pct"]]
    for e in db.scalars(select(Event).order_by(Event.id)):
        reg = S.seats_taken(db, e.id)
        att = db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == e.id, Registration.attended.is_(True))) or 0
        rows.append([S.csv_safe(e.title), reg, att, round(100 * att / reg, 1) if reg else 0])
    return csv_response(rows, "attendance_report.csv")
