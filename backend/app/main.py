from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .core import SessionLocal, log, settings
from .routers import admin, auth, events, imports

app = FastAPI(title="CampusConnect API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                   allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type"])
for r in (auth.router, events.router, imports.router, admin.router):
    app.include_router(r)
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.exception_handler(HTTPException)
async def http_exc(_: Request, exc: HTTPException):
    d = exc.detail
    body = d if isinstance(d, dict) else {"detail": d}
    return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def val_exc(_: Request, exc: RequestValidationError):
    msgs = [f"{'.'.join(str(x) for x in e['loc'][1:])}: {e['msg']}" for e in exc.errors()]
    return JSONResponse({"detail": "Validation failed", "errors": msgs}, status_code=422)


@app.exception_handler(Exception)
async def any_exc(_: Request, exc: Exception):
    log.exception("Unhandled error")  # details stay in logs, never in the response
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


@app.get("/api/health")
def health():
    with SessionLocal() as db:
        db.execute(text("select 1"))
    return {"status": "ok"}
