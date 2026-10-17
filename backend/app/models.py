from datetime import datetime, timezone

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .core import Base


def now():
    return datetime.now(timezone.utc)


class TS:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base, TS):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)  # student | club | admin
    full_name: Mapped[str] = mapped_column(String(150))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("role in ('student','club','admin')", name="ck_user_role"),)
    student: Mapped["StudentProfile"] = relationship(back_populates="user", uselist=False)
    club: Mapped["Club"] = relationship(back_populates="user", uselist=False)


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    department: Mapped[str] = mapped_column(String(100), default="")
    academic_year: Mapped[int] = mapped_column(Integer, default=1)
    roll_no: Mapped[str] = mapped_column(String(50), default="")
    user: Mapped[User] = relationship(back_populates="student")


class Club(Base, TS):
    __tablename__ = "clubs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    contact_email: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending|approved|suspended
    user: Mapped[User] = relationship(back_populates="club")


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class Venue(Base):
    __tablename__ = "venues"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    location: Mapped[str] = mapped_column(String(200), default="")
    capacity: Mapped[int] = mapped_column(Integer, default=100)


class Event(Base, TS):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="RESTRICT"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int] = mapped_column(Integer)
    registration_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    poster_url: Mapped[str] = mapped_column(String(500), default="")
    eligibility: Mapped[str] = mapped_column(String(300), default="Open to all students")
    department: Mapped[str] = mapped_column(String(100), default="")
    academic_year: Mapped[str] = mapped_column(String(30), default="")
    contact_info: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    # draft|pending_approval|published|rejected|completed|cancelled
    review_note: Mapped[str] = mapped_column(String(500), default="")
    club: Mapped[Club] = relationship()
    category: Mapped[Category] = relationship()
    venue: Mapped[Venue] = relationship()
    __table_args__ = (
        UniqueConstraint("club_id", "title", "start_at", name="uq_event_club_title_start"),
        CheckConstraint("capacity > 0", name="ck_event_capacity"),
        CheckConstraint("end_at > start_at", name="ck_event_times"),
        Index("ix_event_venue_time", "venue_id", "start_at", "end_at"),
    )


class Registration(Base, TS):
    __tablename__ = "registrations"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="registered")  # registered|waitlisted|cancelled
    ticket_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    attended: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    event: Mapped[Event] = relationship()
    student: Mapped[User] = relationship()
    __table_args__ = (UniqueConstraint("event_id", "student_id", name="uq_registration_event_student"),)


class Bookmark(Base):
    __tablename__ = "bookmarks"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)


class Notification(Base, TS):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message: Mapped[str] = mapped_column(String(500))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)


class Feedback(Base, TS):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("event_id", "student_id", name="uq_feedback_once"),
                      CheckConstraint("rating between 1 and 5", name="ck_rating"))


class Certificate(Base, TS):
    __tablename__ = "certificates"
    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("registrations.id", ondelete="CASCADE"), unique=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)


class ImportJob(Base, TS):
    __tablename__ = "import_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    success_rows: Mapped[int] = mapped_column(Integer, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    errors: Mapped[list["ImportRowError"]] = relationship(cascade="all, delete-orphan")


class ImportRowError(Base):
    __tablename__ = "import_row_errors"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(String(500))
    raw: Mapped[str] = mapped_column(Text, default="")


class AuditLog(Base, TS):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity: Mapped[str] = mapped_column(String(50), default="")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(String(500), default="")
