"""Auth routes: /api/auth/register, /api/auth/login."""

import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import User, ClassStudent
from auth import hash_password, verify_password, create_access_token
from dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class AuthRegister(BaseModel):
    email: str
    password: str
    role: str = "student"  # "student" | "teacher"


class AuthLogin(BaseModel):
    email: str
    password: str


@router.post("/api/auth/register")
async def register(body: AuthRegister, db: Session = Depends(get_db)):
    """Create a new account and return a JWT for immediate access."""
    email = body.email.strip()
    if len(email) < 3:
        raise HTTPException(status_code=400, detail="Email/username is too short")
    if len(body.password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )

    role = body.role if body.role in ("student", "teacher") else "student"

    exists = db.query(User).filter(User.email == email).first()
    if exists:
        raise HTTPException(status_code=409, detail="Account already exists")

    welcome_bonus = float(os.getenv("WELCOME_BONUS_CREDITS", "100"))
    user = User(
        email=email,
        hashed_password=hash_password(body.password),
        credits_balance=welcome_bonus,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email, user.role)
    enrolled_in_class = (
        db.query(ClassStudent).filter(ClassStudent.student_id == user.id).first()
        is not None
    )
    return {
        "token": token,
        "email": user.email,
        "credits": user.credits_balance,
        "role": user.role,
        "enrolled_in_class": enrolled_in_class,
    }


@router.post("/api/auth/login")
async def login(body: AuthLogin, db: Session = Depends(get_db)):
    """Login and receive a JWT."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    enrolled_in_class = (
        db.query(ClassStudent).filter(ClassStudent.student_id == user.id).first()
        is not None
    )
    token = create_access_token(user.id, user.email, user.role)
    return {
        "token": token,
        "email": user.email,
        "credits": user.credits_balance,
        "role": user.role,
        "enrolled_in_class": enrolled_in_class,
    }
