from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import create_token, current_user, get_db, hash_password, verify_password
from ..models import Club, StudentProfile, User
from ..services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


class StudentReg(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=2, max_length=150)
    department: str = ""
    academic_year: int = Field(1, ge=1, le=6)
    roll_no: str = ""


class ClubReg(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=2, max_length=150)
    club_name: str = Field(min_length=2, max_length=150)
    description: str = ""


class Login(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=150)
    department: str | None = None
    academic_year: int | None = Field(None, ge=1, le=6)
    description: str | None = None


def user_out(u: User):
    d = {"id": u.id, "email": u.email, "role": u.role, "full_name": u.full_name}
    if u.student:
        d["profile"] = {"department": u.student.department, "academic_year": u.student.academic_year,
                        "roll_no": u.student.roll_no}
    if u.club:
        d["club"] = {"id": u.club.id, "name": u.club.name, "status": u.club.status,
                     "description": u.club.description}
    return d


def _check_email(db, email):
    if db.scalar(select(User.id).where(User.email == email.lower())):
        raise HTTPException(409, "Email already registered")


@router.post("/register", status_code=201)
def register_student(b: StudentReg, db: Session = Depends(get_db)):
    _check_email(db, b.email)
    u = User(email=b.email.lower(), password_hash=hash_password(b.password), role="student", full_name=b.full_name)
    u.student = StudentProfile(department=b.department, academic_year=b.academic_year, roll_no=b.roll_no)
    db.add(u)
    db.commit()
    return {"token": create_token(u.id, u.role), "user": user_out(u)}


@router.post("/register-club", status_code=201)
def register_club(b: ClubReg, db: Session = Depends(get_db)):
    _check_email(db, b.email)
    if db.scalar(select(Club.id).where(Club.name == b.club_name)):
        raise HTTPException(409, "Club name already taken")
    u = User(email=b.email.lower(), password_hash=hash_password(b.password), role="club", full_name=b.full_name)
    u.club = Club(name=b.club_name, description=b.description, contact_email=b.email.lower(), status="pending")
    db.add(u)
    db.commit()
    return {"token": create_token(u.id, u.role), "user": user_out(u)}


@router.post("/login")
def login(b: Login, db: Session = Depends(get_db)):
    u = db.scalars(select(User).where(User.email == b.email.lower())).first()
    if not u or not verify_password(b.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not u.is_active:
        raise HTTPException(403, "Account suspended")
    return {"token": create_token(u.id, u.role), "user": user_out(u)}


@router.get("/me")
def me(u: User = Depends(current_user)):
    return user_out(u)


@router.patch("/me")
def update_me(b: ProfileUpdate, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if b.full_name:
        u.full_name = b.full_name
    if u.student:
        if b.department is not None:
            u.student.department = b.department
        if b.academic_year:
            u.student.academic_year = b.academic_year
    if u.club and b.description is not None:
        u.club.description = b.description
    db.commit()
    return user_out(u)
