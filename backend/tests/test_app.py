import io
from datetime import datetime, timedelta, timezone

from .conftest import login


def ev_body(**kw):
    s = datetime.now(timezone.utc) + timedelta(days=60)
    b = dict(title="Test Event", description="d", category_id=1, venue_id=3, start_at=s.isoformat(),
             end_at=(s + timedelta(hours=2)).isoformat(), capacity=2,
             registration_deadline=(s - timedelta(hours=2)).isoformat(), submit=True)
    b.update(kw)
    return b


def make_published(client, admin, **kw):
    r = client.post("/api/events", json=ev_body(club_id=1, **kw), headers=admin)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "published"
    return r.json()


# ---- auth / RBAC ----
def test_register_login_and_password_hashed(client):
    r = client.post("/api/auth/register", json={"email": "new@x.com", "password": "longenough1", "full_name": "New Kid"})
    assert r.status_code == 201 and r.json()["user"]["role"] == "student"
    assert client.post("/api/auth/register", json={"email": "new@x.com", "password": "longenough1", "full_name": "New Kid"}).status_code == 409
    from app.core import SessionLocal
    from app.models import User
    with SessionLocal() as db:
        assert db.query(User).filter_by(email="new@x.com").one().password_hash != "longenough1"


def test_bad_login_and_missing_token(client):
    assert client.post("/api/auth/login", json={"email": "admin@campusconnect.dev", "password": "nope"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_role_boundaries(client, s1, club1):
    assert client.get("/api/admin/users", headers=s1).status_code == 403
    assert client.get("/api/admin/users", headers=club1).status_code == 403
    assert client.post("/api/events", json=ev_body(), headers=s1).status_code == 403
    assert client.post("/api/events/1/register", headers=club1).status_code == 403


def test_pending_club_cannot_create_events(client):
    h = login(client, "newclub@campusconnect.dev")
    assert client.post("/api/events", json=ev_body(), headers=h).status_code == 403


# ---- events ----
def test_club_submit_needs_approval_then_admin_publishes(client, club1, admin, s1):
    r = client.post("/api/events", json=ev_body(), headers=club1)
    assert r.status_code == 201 and r.json()["status"] == "pending_approval"
    eid = r.json()["id"]
    assert eid not in [e["id"] for e in client.get("/api/events").json()["items"]]
    assert client.post(f"/api/events/{eid}/approve", headers=club1).status_code == 403
    assert client.post(f"/api/events/{eid}/approve", headers=admin).json()["status"] == "published"
    assert eid in [e["id"] for e in client.get("/api/events?page_size=50").json()["items"]]


def test_venue_conflict_and_validation(client, admin):
    make_published(client, admin)
    r = client.post("/api/events", json=ev_body(title="Clash", club_id=1), headers=admin)
    assert r.status_code == 422 and "venue" in str(r.json())
    bad = client.post("/api/events", json=ev_body(title="Bad", club_id=1, venue_id=1, capacity=0), headers=admin)
    assert bad.status_code == 422
    big = client.post("/api/events", json=ev_body(title="Too big", club_id=1, venue_id=3, capacity=999), headers=admin)
    assert big.status_code == 422 and "venue capacity" in str(big.json())


def test_club_cannot_touch_other_clubs_event(client, club1, club2):
    eid = client.post("/api/events", json=ev_body(), headers=club1).json()["id"]
    for method, path in [("put", f"/api/events/{eid}"), ]:
        assert client.put(path, json=ev_body(), headers=club2).status_code == 403
    assert client.post(f"/api/events/{eid}/cancel", headers=club2).status_code == 403
    assert client.get(f"/api/events/{eid}/attendees", headers=club2).status_code == 403
    assert client.get(f"/api/events/{eid}", headers=club2).status_code == 403  # unpublished -> not visible to others
    r = client.post("/api/events", json=ev_body(title="Spoof", club_id=1, venue_id=2), headers=club2)
    assert r.status_code == 403  # club_id spoofing blocked


def test_poster_upload_validation(client, club1):
    eid = client.post("/api/events", json=ev_body(), headers=club1).json()["id"]
    bad = client.post(f"/api/events/{eid}/poster", files={"file": ("x.png", io.BytesIO(b"<script>"), "image/png")}, headers=club1)
    assert bad.status_code == 400
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
    ok = client.post(f"/api/events/{eid}/poster", files={"file": ("p.png", io.BytesIO(png), "image/png")}, headers=club1)
    assert ok.status_code == 200 and ok.json()["poster_url"].startswith("/uploads/")


# ---- registration ----
def test_capacity_waitlist_promotion_and_duplicates(client, admin, s1, s4):
    e = make_published(client, admin, capacity=1)
    s2 = login(client, "student2@campusconnect.dev")
    assert client.post(f"/api/events/{e['id']}/register", headers=s1).json()["status"] == "registered"
    assert client.post(f"/api/events/{e['id']}/register", headers=s1).status_code == 409
    assert client.post(f"/api/events/{e['id']}/register", headers=s2).json()["status"] == "waitlisted"
    assert client.get(f"/api/events/{e['id']}").json()["seats_left"] == 0
    assert client.delete(f"/api/events/{e['id']}/register", headers=s1).status_code == 204
    regs = client.get("/api/me/registrations", headers=s2).json()
    assert regs[0]["status"] == "registered"  # promoted
    notes = client.get("/api/notifications", headers=s2).json()
    assert any("promoted" in n["message"] for n in notes)
    assert client.post(f"/api/events/{e['id']}/register", headers=s1).json()["status"] == "waitlisted"  # re-register


def test_qr_checkin_and_idor(client, admin, club1, club2, s1, s4):
    e = make_published(client, admin, capacity=5)
    club_event = e["id"]
    rid = client.post(f"/api/events/{club_event}/register", headers=s1).json()["id"]
    assert client.get(f"/api/registrations/{rid}/qr.png", headers=s1).headers["content-type"] == "image/png"
    assert client.get(f"/api/registrations/{rid}/qr.png", headers=s4).status_code == 404  # other student
    code = client.get("/api/me/registrations", headers=s1).json()[0]["ticket_code"]
    assert len(code) >= 30
    assert client.post("/api/checkin", json={"ticket_code": code}, headers=club2).status_code == 403
    assert client.post("/api/checkin", json={"ticket_code": code}, headers=club1).status_code == 200
    assert client.post("/api/checkin", json={"ticket_code": code}, headers=club1).status_code == 409
    assert client.post("/api/checkin", json={"ticket_code": "x" * 30}, headers=club1).status_code == 404


def test_feedback_only_for_attendees(client, s1, s4):
    assert client.post("/api/events/6/feedback", json={"rating": 4}, headers=s4).status_code == 403
    assert client.post("/api/events/6/feedback", json={"rating": 5}, headers=s1).status_code == 409  # seeded already
    assert client.post("/api/events/6/feedback", json={"rating": 9}, headers=s1).status_code == 422
    regs = client.get("/api/me/registrations", headers=s1).json()
    past = next(r for r in regs if r["event"]["id"] == 6)
    pdf = client.get(f"/api/registrations/{past['id']}/certificate", headers=s1)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_registration_closed_for_unpublished(client, s1):
    assert client.post("/api/events/5/register", headers=s1).status_code == 404  # draft
    assert client.post("/api/events/4/register", headers=s1).status_code == 404  # pending


# ---- CSV ----
HDR = "title,description,category,venue,start_at,end_at,capacity,registration_deadline,eligibility,department,academic_year,contact_info,club,submit\n"


def csv_file(body):
    return {"file": ("events.csv", io.BytesIO((HDR + body).encode("utf-8-sig")), "text/csv")}


def test_csv_preview_commit_and_error_report(client, club1):
    y = datetime.now(timezone.utc).year + 2
    body = (f"Good Event,desc,Technical,Innovation Lab,{y}-05-01 10:00,{y}-05-01 12:00,20,{y}-04-30 10:00,,,,,,yes\n"
            f"Bad Date,desc,Technical,Innovation Lab,not-a-date,{y}-05-02 12:00,20,{y}-04-30 10:00,,,,,,yes\n"
            f"Bad Venue,desc,Technical,Nowhere,{y}-06-01 10:00,{y}-06-01 12:00,20,{y}-05-30 10:00,,,,,,no\n"
            f"Café Düsseldorf Meet,ünï,Social,Seminar Hall A,{y}-07-01 10:00,{y}-07-01 12:00,20,{y}-06-30 10:00,,,,,,no\n"
            f"Good Event,dup,Technical,Innovation Lab,{y}-05-01 10:00,{y}-05-01 12:00,20,{y}-04-30 10:00,,,,,,yes\n"
            f"Other Club,x,Technical,Seminar Hall A,{y}-08-01 10:00,{y}-08-01 12:00,20,{y}-07-30 10:00,,,,Arts & Culture Society,no\n")
    p = client.post("/api/imports/preview", files=csv_file(body), headers=club1).json()
    assert (p["total"], p["valid"], p["invalid"]) == (6, 2, 4)
    assert client.get("/api/events/manage", headers=club1).json().__len__() == 4  # preview wrote nothing (seeded 4)
    c = client.post("/api/imports/commit", files=csv_file(body), headers=club1).json()
    assert (c["success"], c["failed"]) == (2, 4)
    errs = client.get(f"/api/imports/jobs/{c['job_id']}/errors", headers=club1).json()
    assert sorted(e["row"] for e in errs) == [3, 4, 6, 7]  # row numbers match file lines
    rep = client.get(f"/api/imports/jobs/{c['job_id']}/errors.csv", headers=club1)
    assert "row_number" in rep.text and "invalid date" in rep.text


def test_csv_missing_columns_and_encoding_and_access(client, club1, club2, admin):
    bad = {"file": ("e.csv", io.BytesIO(b"title,venue\nA,B\n"), "text/csv")}
    assert client.post("/api/imports/preview", files=bad, headers=club1).status_code == 400
    latin = {"file": ("e.csv", io.BytesIO(HDR.encode() + "caf\xe9,,,,,,,,,,,,,\n".encode("latin-1")), "text/csv")}
    assert client.post("/api/imports/preview", files=latin, headers=club1).status_code == 400
    c = client.post("/api/imports/commit", files=csv_file(""), headers=club1).json()
    assert client.get(f"/api/imports/jobs/{c['job_id']}/errors", headers=club2).status_code == 404
    assert client.get(f"/api/imports/jobs/{c['job_id']}/errors", headers=admin).status_code == 200
    assert client.get("/api/imports/template.csv").status_code == 200  # public template


def test_admin_csv_requires_club_and_publishes(client, admin):
    y = datetime.now(timezone.utc).year + 2
    row = f"Admin Event,d,Technical,Innovation Lab,{y}-05-01 10:00,{y}-05-01 12:00,20,{y}-04-30 10:00,,,,,Code Club,yes\n"
    c = client.post("/api/imports/commit", files=csv_file(row), headers=admin).json()
    assert c["success"] == 1 and c["rows"][0]["status"] == "published"
    c2 = client.post("/api/imports/commit", files=csv_file(row.replace("Code Club", "")), headers=admin).json()
    assert c2["failed"] == 1


# ---- admin ----
def test_admin_controls(client, admin):
    assert client.patch("/api/admin/clubs/3", json={"status": "approved"}, headers=admin).status_code == 200
    h = login(client, "newclub@campusconnect.dev")
    assert client.post("/api/events", json=ev_body(), headers=h).status_code == 201
    assert client.patch("/api/admin/users/5", json={"is_active": False}, headers=admin).status_code == 200
    assert client.post("/api/auth/login", json={"email": "student1@campusconnect.dev", "password": "Password123!"}).status_code == 403
    a = client.get("/api/admin/analytics", headers=admin).json()
    assert a["students"] == 4 and a["events"] >= 6
    assert any(x["action"] == "club.approved" for x in client.get("/api/admin/audit", headers=admin).json())
    assert client.get("/api/admin/reports/events.csv", headers=admin).status_code == 200
