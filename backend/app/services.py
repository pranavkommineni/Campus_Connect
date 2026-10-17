"""Business rules shared by manual creation, CSV import and the API."""
import csv
import io
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .aws import get_queue
from .models import (AuditLog, Category, Club, Event, Notification, Registration, Venue, now)


def utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def iso(dt):
    return utc(dt).isoformat() if dt else None


def audit(db: Session, actor, action: str, entity: str = "", entity_id: int | None = None, detail: str = ""):
    db.add(AuditLog(actor_id=getattr(actor, "id", None), action=action, entity=entity,
                    entity_id=entity_id, detail=detail[:500]))


def notify(db: Session, user_id: int, message: str):
    db.add(Notification(user_id=user_id, message=message[:500]))
    get_queue().publish("notification", {"user_id": user_id, "message": message})


def acting_club(db: Session, user, club_id: int | None = None) -> Club:
    """Resolve which club an actor may act for. Clubs: only their own. Admin: must name one."""
    if user.role == "club":
        club = user.club
        if not club or club.status != "approved":
            raise HTTPException(403, "Your club account is not approved")
        if club_id and club_id != club.id:
            raise HTTPException(403, "You cannot act for another club")
        return club
    club = db.get(Club, club_id) if club_id else None
    if not club:
        raise HTTPException(422, "club_id is required for admin")
    return club


def assert_event_access(user, event: Event):
    if user.role == "admin":
        return
    if user.role == "club" and user.club and event.club_id == user.club.id:
        return
    raise HTTPException(403, "Not your event")


def validate_event_fields(d: dict, existing: Event | None = None) -> list[str]:
    errs = []
    if not str(d.get("title", "")).strip():
        errs.append("title is required")
    if len(str(d.get("title", ""))) > 200:
        errs.append("title too long (max 200)")
    s, e, dl = d.get("start_at"), d.get("end_at"), d.get("registration_deadline")
    if not (s and e and dl):
        errs.append("start_at, end_at and registration_deadline are required")
    else:
        if e <= s:
            errs.append("end_at must be after start_at")
        if dl > s:
            errs.append("registration_deadline must be on or before start_at")
        if s < now() and not existing:
            errs.append("start_at must be in the future")
    cap = d.get("capacity")
    if not isinstance(cap, int) or cap < 1:
        errs.append("capacity must be a positive integer")
    return errs


def venue_conflict(db: Session, venue_id: int, start, end, exclude_id: int | None = None) -> Event | None:
    q = select(Event).where(Event.venue_id == venue_id,
                            Event.status.in_(["pending_approval", "published"]),
                            Event.start_at < end, Event.end_at > start)
    if exclude_id:
        q = q.where(Event.id != exclude_id)
    return db.scalars(q).first()


def check_venue_capacity(venue: Venue, capacity: int) -> list[str]:
    return [f"capacity {capacity} exceeds venue capacity {venue.capacity}"] if capacity > venue.capacity else []


def seats_taken(db: Session, event_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Registration)
                     .where(Registration.event_id == event_id, Registration.status == "registered")) or 0


def apply_submit(user, event: Event, submit: bool):
    """Shared approval rule: admin events publish directly, club events go to review."""
    if not submit:
        event.status = "draft"
    else:
        event.status = "published" if user.role == "admin" else "pending_approval"


def create_event(db: Session, user, club: Club, d: dict, submit: bool) -> Event:
    """Single creation path used by the API form and CSV import. Raises ValueError(list) on invalid data."""
    errs = validate_event_fields(d)
    venue = db.get(Venue, d.get("venue_id"))
    cat = db.get(Category, d.get("category_id"))
    if not venue:
        errs.append("unknown venue")
    if not cat:
        errs.append("unknown category")
    if venue and isinstance(d.get("capacity"), int):
        errs += check_venue_capacity(venue, d["capacity"])
    if not errs and submit and venue_conflict(db, venue.id, d["start_at"], d["end_at"]):
        errs.append("venue is already booked for an overlapping event")
    if not errs:
        dup = db.scalar(select(Event.id).where(Event.club_id == club.id, Event.title == d["title"].strip(),
                                               Event.start_at == d["start_at"]))
        if dup:
            errs.append("duplicate event (same club, title and start time)")
    if errs:
        raise ValueError(errs)
    ev = Event(club_id=club.id, category_id=cat.id, venue_id=venue.id, title=d["title"].strip(),
               description=d.get("description", ""), start_at=d["start_at"], end_at=d["end_at"],
               capacity=d["capacity"], registration_deadline=d["registration_deadline"],
               poster_url=d.get("poster_url", ""), eligibility=d.get("eligibility") or "Open to all students",
               department=d.get("department", ""), academic_year=d.get("academic_year", ""),
               contact_info=d.get("contact_info", ""))
    apply_submit(user, ev, submit)
    db.add(ev)
    db.flush()
    audit(db, user, "event.create", "event", ev.id, f"{ev.title} [{ev.status}]")
    return ev


# ---------- registrations ----------
def promote_waitlist(db: Session, event: Event):
    """Fill free seats from the waitlist in FIFO order. Caller holds the event row lock."""
    while seats_taken(db, event.id) < event.capacity:
        nxt = db.scalars(select(Registration).where(Registration.event_id == event.id,
                                                    Registration.status == "waitlisted")
                         .order_by(Registration.queued_at, Registration.id).limit(1)).first()
        if not nxt:
            break
        nxt.status = "registered"
        db.flush()  # autoflush is off: without this the loop would re-read the same row forever
        notify(db, nxt.student_id, f"You got a seat for '{event.title}' - promoted from the waitlist!")


def register_student(db: Session, event_id: int, student) -> Registration:
    # Row lock serialises concurrent registrations for one event on PostgreSQL (no-op on SQLite).
    ev = db.scalars(select(Event).where(Event.id == event_id).with_for_update()).first()
    if not ev or ev.status != "published":
        raise HTTPException(404, "Event not found")
    if utc(ev.registration_deadline) < now() or utc(ev.start_at) < now():
        raise HTTPException(400, "Registration is closed")
    reg = db.scalars(select(Registration).where(Registration.event_id == ev.id,
                                                Registration.student_id == student.id)).first()
    if reg and reg.status != "cancelled":
        raise HTTPException(409, "Already registered")
    full = seats_taken(db, ev.id) >= ev.capacity
    status = "waitlisted" if full else "registered"
    if reg:  # re-registering after a cancel reuses the row (unique constraint)
        reg.status, reg.queued_at = status, now()
    else:
        reg = Registration(event_id=ev.id, student_id=student.id, status=status,
                           ticket_code=secrets.token_urlsafe(24))
        db.add(reg)
    notify(db, student.id, f"You are {'on the waitlist for' if full else 'registered for'} '{ev.title}'.")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Already registered")
    return reg


def cancel_registration(db: Session, event_id: int, student) -> None:
    ev = db.scalars(select(Event).where(Event.id == event_id).with_for_update()).first()
    reg = db.scalars(select(Registration).where(Registration.event_id == event_id,
                                                Registration.student_id == student.id)).first()
    if not ev or not reg or reg.status == "cancelled":
        raise HTTPException(404, "Registration not found")
    if reg.attended:
        raise HTTPException(400, "Already attended")
    was_seat = reg.status == "registered"
    reg.status = "cancelled"
    db.flush()
    if was_seat:
        promote_waitlist(db, ev)
    notify(db, student.id, f"Your registration for '{ev.title}' was cancelled.")
    db.commit()


def check_in(db: Session, user, ticket_code: str) -> Registration:
    reg = db.scalars(select(Registration).where(Registration.ticket_code == ticket_code)
                     .with_for_update()).first()
    if not reg:
        raise HTTPException(404, "Invalid ticket")
    assert_event_access(user, reg.event)
    if reg.status != "registered":
        raise HTTPException(400, f"Ticket is {reg.status}, not valid for entry")
    if reg.attended:
        raise HTTPException(409, "Ticket already used")
    if reg.event.status not in ("published", "completed"):
        raise HTTPException(400, "Event is not active")
    reg.attended, reg.checked_in_at = True, now()
    audit(db, user, "attendance.checkin", "registration", reg.id)
    db.commit()
    return reg


# ---------- CSV ----------
EVENT_COLUMNS = ["title", "description", "category", "venue", "start_at", "end_at", "capacity",
                 "registration_deadline", "eligibility", "department", "academic_year", "contact_info",
                 "club", "submit"]
REQUIRED_COLUMNS = ["title", "category", "venue", "start_at", "end_at", "capacity", "registration_deadline"]
MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_CSV_ROWS = 1000


def csv_safe(v) -> str:
    """Neutralise spreadsheet formula injection in exported cells."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def parse_dt(v: str) -> datetime:
    v = v.strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M"):
        try:
            d = datetime.fromisoformat(v) if fmt is None else datetime.strptime(v, fmt)
            return utc(d)
        except ValueError:
            continue
    raise ValueError(f"invalid date '{v}' (use YYYY-MM-DD HH:MM, UTC)")


def read_csv(raw: bytes) -> tuple[list[str], list[tuple[int, dict]]]:
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(413, "CSV too large (max 2 MB)")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be UTF-8 encoded")
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise HTTPException(400, f"Missing required column(s): {', '.join(missing)}")
    rows = []
    for i, r in enumerate(reader, start=2):  # row 1 is the header
        if i - 1 > MAX_CSV_ROWS:
            raise HTTPException(413, f"Too many rows (max {MAX_CSV_ROWS})")
        rows.append((i, {(k or "").strip().lower(): (v or "").strip() for k, v in r.items() if k}))
    return headers, rows


def row_to_event_data(db: Session, user, row: dict, default_club: Club | None):
    """Returns (club, data, submit). Raises ValueError(list[str])."""
    errs = []
    club = default_club
    if user.role == "admin":
        club = db.scalars(select(Club).where(Club.name == row.get("club", ""))).first()
        if not club:
            errs.append("admin imports need a valid 'club' name")
    elif row.get("club") and row["club"] != club.name:
        errs.append("you can only import events for your own club")
    cat = db.scalars(select(Category).where(func.lower(Category.name) == row.get("category", "").lower())).first()
    ven = db.scalars(select(Venue).where(func.lower(Venue.name) == row.get("venue", "").lower())).first()
    if not cat:
        errs.append(f"unknown category '{row.get('category', '')}'")
    if not ven:
        errs.append(f"unknown venue '{row.get('venue', '')}'")
    d = {k: row.get(k, "") for k in ("title", "description", "eligibility", "department", "academic_year", "contact_info")}
    d["category_id"], d["venue_id"] = cat.id if cat else None, ven.id if ven else None
    for f in ("start_at", "end_at", "registration_deadline"):
        try:
            d[f] = parse_dt(row.get(f, ""))
        except ValueError as ex:
            errs.append(f"{f}: {ex}")
    try:
        d["capacity"] = int(row.get("capacity", ""))
    except ValueError:
        d["capacity"] = None
    if errs:
        raise ValueError(errs)
    return club, d, row.get("submit", "").lower() in ("yes", "true", "1", "y")
