# CampusConnect - college event management

React + Vite + TypeScript + Tailwind frontend · FastAPI backend · PostgreSQL (SQLAlchemy + Alembic) · JWT auth with three roles: **student, club, admin**.

## Verification status (be aware)
- Backend: **16 pytest tests pass** (auth, RBAC, IDOR/cross-club access, venue conflicts, capacity, waitlist promotion, QR check-in, uploads, CSV preview/commit/error reports, admin) - run against **SQLite**.
- Frontend: TypeScript strict typecheck, `vite build` and 3 Vitest tests pass. The UI was **not clicked through in a browser** in the environment that produced this repo - expect small visual/UX fixes.
- **Not verified:** a live PostgreSQL run (the Alembic migration was generated and applied on SQLite; models use portable types), real concurrent-registration load tests (overbooking protection relies on `SELECT … FOR UPDATE` row locks, which SQLite ignores), and **all AWS integrations** (nothing deployed; see `docs/AWS.md`).

## Quick start (local)
```bash
# 1. PostgreSQL
cp .env.example .env            # (root: for docker-compose)  -> set POSTGRES_PASSWORD
docker compose up -d db
# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set DATABASE_URL password + a long random JWT_SECRET
alembic upgrade head            # create schema
python -m app.seed              # demo data (python -m app.seed --reset drops and re-creates everything)
uvicorn app.main:app --reload   # http://localhost:8000  (interactive API docs: /docs)
# 3. Frontend
cd ../frontend && npm install && npm run dev    # http://localhost:5173 (proxies /api to :8000)
```
Without a `.env` the backend falls back to a local SQLite file, handy for a quick look.

**Demo accounts** (password `Password123!` - demo only, never deploy them): `admin@campusconnect.dev`, `codeclub@campusconnect.dev`, `artsclub@campusconnect.dev`, `newclub@campusconnect.dev` (pending approval), `student1..4@campusconnect.dev`.

## Tests
```bash
cd backend && pytest -q          # uses a temp SQLite DB
cd frontend && npm test && npm run build
```

## What's implemented
- **Student:** register/profile, discover (search, category/club/date filters, sort, pagination), bookmarks, register/cancel, waitlist with automatic promotion, QR passes, calendar view, notifications, feedback (attendees only), PDF certificates (after the event ends).
- **Club:** profile, create/edit/submit/cancel events, poster upload (magic-byte validated), attendee list + CSV export, waitlist visibility, QR check-in, CSV import wizard. Clubs can only touch their own events; an unapproved club cannot publish.
- **Admin:** approve/reject events, approve/suspend clubs, disable users, venues and categories, analytics charts, audit log, CSV reports (events/registrations/attendance), CSV import for any club.
- **Rules (one code path for form and CSV):** date/capacity validation, venue-capacity and overlapping-venue checks, duplicate detection, club submissions go to `pending_approval` while admin submissions publish directly.
- **CSV:** template download, required-column docs, UTF-8 only (BOM tolerated), 2 MB / 1000-row limits, preview (nothing saved), per-row savepoints with explicit row-numbered errors, downloadable error report, CSV-injection-safe exports. Samples in `samples/`.

## Security notes
Backend enforces every permission (frontend guards are cosmetic). Pydantic schemas whitelist writable fields (no mass assignment); club identity comes from the token, never the request; ticket codes are 192-bit random; QR images only for the ticket owner; uploads limited by type/size; ORM-only queries; consistent JSON errors with no stack traces; passwords bcrypt-hashed; CORS restricted to `CORS_ORIGINS`.
**Not included (add before production):** login rate limiting / lockout, email verification and password reset, refresh tokens (JWT lives 8 h in `localStorage`), HTTPS termination config, malware scanning of uploads.
Naive datetimes (e.g. from CSV) are interpreted as **UTC**.

## Layout
`backend/app` (core, models, services, routers, aws adapters, worker, seed) · `backend/alembic` · `backend/tests` · `frontend/src` · `infra/` · `docs/AWS.md` · `docs/API.md` · `samples/`

## Troubleshooting
- *`password authentication failed`*: `DATABASE_URL` password must match `POSTGRES_PASSWORD` used when the volume was first created (`docker compose down -v` to reset).
- *CORS errors*: add your frontend origin to `CORS_ORIGINS`.
- *Poster not showing in production*: set `S3_PUBLIC_BASE_URL` to the CloudFront domain serving the posters bucket.
- *Reset database*: `python -m app.seed --reset` (destroys all data).
