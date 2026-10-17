"""Seed demo data.  python -m app.seed [--reset]"""
import sys
from datetime import timedelta

from sqlalchemy import select

from .core import Base, SessionLocal, engine, hash_password
from .models import (Category, Club, Event, Feedback, Registration, StudentProfile, User, Venue, now)

DEMO_PASSWORD = "Password123!"  # demo accounts only - change/delete before any real deployment


def main(reset: bool = False):
    pw_hash = hash_password(DEMO_PASSWORD)  # hashed once; every demo account shares the demo password
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)  # no-op when Alembic already created the schema
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)):
            print("Database already seeded (use --reset to start over).")
            return
        cats = [Category(name=n) for n in ["Technical", "Cultural", "Sports", "Workshop", "Career", "Social"]]
        venues = [Venue(name="Main Auditorium", location="Admin Block", capacity=500),
                  Venue(name="Seminar Hall A", location="CSE Block", capacity=120),
                  Venue(name="Innovation Lab", location="Tech Park", capacity=40),
                  Venue(name="Sports Ground", location="South Campus", capacity=800)]
        db.add_all(cats + venues)
        admin = User(email="admin@campusconnect.dev", password_hash=pw_hash, role="admin", full_name="Campus Admin")
        db.add(admin)
        clubs = []
        for email, name, desc in [("codeclub@campusconnect.dev", "Code Club", "Hackathons, workshops and open-source."),
                                  ("artsclub@campusconnect.dev", "Arts & Culture Society", "Music, dance and drama.")]:
            u = User(email=email, password_hash=pw_hash, role="club", full_name=name + " Lead")
            u.club = Club(name=name, description=desc, contact_email=email, status="approved")
            db.add(u)
            clubs.append(u.club)
        pend = User(email="newclub@campusconnect.dev", password_hash=pw_hash, role="club", full_name="Robotics Lead")
        pend.club = Club(name="Robotics Club", description="Awaiting approval.", contact_email=pend.email, status="pending")
        db.add(pend)
        students = []
        for i, (n, d) in enumerate([("Asha Rao", "CSE"), ("Vikram Singh", "ECE"), ("Meera Nair", "IT"), ("Rohan Das", "ME")], 1):
            u = User(email=f"student{i}@campusconnect.dev", password_hash=pw_hash, role="student", full_name=n)
            u.student = StudentProfile(department=d, academic_year=(i % 4) + 1, roll_no=f"23{i:03d}")
            db.add(u)
            students.append(u)
        db.flush()
        t = now().replace(minute=0, second=0, microsecond=0)
        spec = [(clubs[0], cats[0], venues[1], 5, "HackSprint 24h Hackathon", 100, "published"),
                (clubs[0], cats[3], venues[2], 9, "Intro to Cloud Computing on AWS", 3, "published"),
                (clubs[1], cats[1], venues[0], 14, "Annual Cultural Night", 400, "published"),
                (clubs[1], cats[5], venues[3], 20, "Campus Fun Run", 200, "pending_approval"),
                (clubs[0], cats[4], venues[1], 28, "Placement Prep Bootcamp", 80, "draft"),
                (clubs[0], cats[0], venues[1], -10, "AI/ML Bootcamp (past)", 60, "completed")]
        evs = []
        for club, cat, ven, days, title, cap, st in spec:
            start = t + timedelta(days=days, hours=2)
            e = Event(club_id=club.id, category_id=cat.id, venue_id=ven.id, title=title, capacity=cap,
                      description=f"{title} - hosted by {club.name}. Open to curious students from every department.",
                      start_at=start, end_at=start + timedelta(hours=3), registration_deadline=start - timedelta(hours=12),
                      status=st, contact_info=club.contact_email, department="All", academic_year="All")
            db.add(e)
            evs.append(e)
        db.flush()
        for i, s in enumerate(students[:3]):  # fills the 3-seat cloud workshop partly
            db.add(Registration(event_id=evs[1].id, student_id=s.id, status="registered", ticket_code=f"DEMO-CLOUD-{i}-" + "x" * 20))
        past = Registration(event_id=evs[5].id, student_id=students[0].id, status="registered", attended=True,
                            checked_in_at=t - timedelta(days=10), ticket_code="DEMO-PAST-" + "y" * 24)
        db.add(past)
        db.add(Feedback(event_id=evs[5].id, student_id=students[0].id, rating=5, comment="Great session!"))
        db.commit()
        print("Seeded. All demo accounts use password:", DEMO_PASSWORD)
        print("  admin@campusconnect.dev | codeclub@campusconnect.dev | student1@campusconnect.dev")


if __name__ == "__main__":
    main("--reset" in sys.argv)
