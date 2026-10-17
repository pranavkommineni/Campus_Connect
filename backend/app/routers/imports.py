import csv
import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services as S
from ..core import get_db, require_roles
from ..models import Club, ImportJob, ImportRowError
from .events import csv_response

router = APIRouter(prefix="/api/imports", tags=["imports"])
staff = require_roles("club", "admin")

TEMPLATE = [S.EVENT_COLUMNS,
            ["Intro to Cloud Computing", "Hands-on AWS workshop", "Workshop", "Seminar Hall A",
             "2030-03-10 10:00", "2030-03-10 13:00", "80", "2030-03-09 18:00", "Open to all students",
             "CSE", "2", "club@college.edu", "(admin only: club name)", "yes"]]


@router.get("/template.csv")
def template():
    return csv_response(TEMPLATE, "campusconnect_events_template.csv")


def _process(db: Session, user, raw: bytes, commit: bool):
    club = None
    if user.role == "club":
        club = S.acting_club(db, user)
    _, rows = S.read_csv(raw)
    results, seen = [], set()
    for rownum, row in rows:
        try:
            c, data, submit = S.row_to_event_data(db, user, row, club)
            key = (c.id, data["title"].lower(), data["start_at"])
            if key in seen:
                raise ValueError(["duplicate of an earlier row in this file"])
            seen.add(key)
            sp = db.begin_nested()  # per-row savepoint: one bad row never poisons the rest
            try:
                ev = S.create_event(db, user, c, data, submit)
                sp.commit()  # preview: whole transaction is rolled back by the caller, but rows still see each other
            except Exception:
                sp.rollback()
                raise
            results.append({"row": rownum, "ok": True, "title": data["title"], "status": ev.status if commit else "valid"})
        except ValueError as ex:
            results.append({"row": rownum, "ok": False, "title": row.get("title", ""), "errors": ex.args[0]})
    return results


@router.post("/preview")
async def preview(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(staff)):
    raw = await file.read(S.MAX_CSV_BYTES + 1)
    results = _process(db, user, raw, commit=False)
    db.rollback()  # preview never writes
    ok = sum(r["ok"] for r in results)
    return {"total": len(results), "valid": ok, "invalid": len(results) - ok, "rows": results}


@router.post("/commit")
async def commit(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(staff)):
    raw = await file.read(S.MAX_CSV_BYTES + 1)
    results = _process(db, user, raw, commit=True)
    job = ImportJob(user_id=user.id, filename=(file.filename or "upload.csv")[:255], total_rows=len(results),
                    success_rows=sum(r["ok"] for r in results), failed_rows=sum(not r["ok"] for r in results))
    for r in results:
        if not r["ok"]:
            job.errors.append(ImportRowError(row_number=r["row"], message="; ".join(r["errors"])[:500], raw=r["title"][:200]))
    db.add(job)
    db.flush()
    S.audit(db, user, "import.commit", "import_job", job.id, f"{job.success_rows} ok / {job.failed_rows} failed")
    db.commit()
    return {"job_id": job.id, "total": job.total_rows, "success": job.success_rows, "failed": job.failed_rows, "rows": results}


def _job(db, user, job_id):
    job = db.get(ImportJob, job_id)
    if not job or (user.role != "admin" and job.user_id != user.id):
        raise HTTPException(404, "Import job not found")
    return job


@router.get("/jobs")
def jobs(db: Session = Depends(get_db), user=Depends(staff)):
    q = select(ImportJob).order_by(ImportJob.id.desc()).limit(50)
    if user.role != "admin":
        q = q.where(ImportJob.user_id == user.id)
    return [{"id": j.id, "filename": j.filename, "total": j.total_rows, "success": j.success_rows,
             "failed": j.failed_rows, "created_at": S.iso(j.created_at)} for j in db.scalars(q)]


@router.get("/jobs/{job_id}/errors")
def job_errors(job_id: int, db: Session = Depends(get_db), user=Depends(staff)):
    job = _job(db, user, job_id)
    return [{"row": e.row_number, "message": e.message, "title": e.raw} for e in job.errors]


@router.get("/jobs/{job_id}/errors.csv")
def job_errors_csv(job_id: int, db: Session = Depends(get_db), user=Depends(staff)):
    job = _job(db, user, job_id)
    rows = [["row_number", "title", "error"]] + [[e.row_number, S.csv_safe(e.raw), S.csv_safe(e.message)] for e in job.errors]
    return csv_response(rows, f"import_{job.id}_errors.csv")
