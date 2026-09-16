"""Auth routes: /api/auth/register, /api/auth/login, email verification, password reset."""

import hashlib
import os
import re
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import User, ClassStudent, EmailVerificationCode
from auth import hash_password, verify_password, create_access_token
from dependencies import get_db
from email_utils import send_verification_code_email, VERIFICATION_CODE_TTL_MINUTES
from rate_limiter import limiter
import feature_flags

logger = logging.getLogger(__name__)
router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_CODE_ATTEMPTS = 5


class AuthRegister(BaseModel):
    email: str
    password: str
    role: str = "student"  # "student" | "teacher"
    code: str  # 6-digit email verification code


class AuthLogin(BaseModel):
    email: str
    password: str


class RequestCode(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    email: str
    code: str
    new_password: str


# ── Verification code helpers ───────────────────────────────────


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _create_and_send_code(db: Session, email: str, purpose: str) -> None:
    """Invalidate previous codes, create a new one, and email it."""
    db.query(EmailVerificationCode).filter(
        EmailVerificationCode.email == email,
        EmailVerificationCode.purpose == purpose,
        EmailVerificationCode.consumed_at.is_(None),
    ).update({"consumed_at": datetime.utcnow()}, synchronize_session=False)

    code = f"{secrets.randbelow(900000) + 100000}"  # 6 digits
    record = EmailVerificationCode(
        email=email,
        code_hash=_hash_code(code),
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=VERIFICATION_CODE_TTL_MINUTES),
    )
    db.add(record)
    db.commit()

    if not send_verification_code_email(email, code, purpose):
        logger.error("Could not send verification email to %s", email)
        raise HTTPException(
            status_code=500,
            detail="Could not send the verification email. Please try again later.",
        )


def _verify_code(db: Session, email: str, code: str, purpose: str) -> None:
    """Validate a code and consume it. Raises HTTPException on any failure."""
    record = (
        db.query(EmailVerificationCode)
        .filter(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.consumed_at.is_(None),
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .first()
    )
    if record is None:
        raise HTTPException(
            status_code=400,
            detail="No verification code found for this email — please request a new one",
        )
    if record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="Verification code has expired — please request a new one",
        )
    if record.attempts >= MAX_CODE_ATTEMPTS:
        raise HTTPException(
            status_code=400,
            detail="Too many incorrect attempts — please request a new code",
        )
    if record.code_hash != _hash_code(code.strip()):
        record.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect verification code")

    record.consumed_at = datetime.utcnow()
    db.commit()


def _auth_response(user: User, db: Session) -> dict:
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


# ── Registration (with email verification) ──────────────────────


@router.post("/api/auth/register/request-code")
@limiter.limit("5/minute")
async def register_request_code(
    request: Request, body: RequestCode, db: Session = Depends(get_db)
):
    """Send a 6-digit verification code to the email the user wants to register with."""
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")

    exists = db.query(User).filter(User.email == email).first()
    if exists:
        raise HTTPException(status_code=409, detail="Account already exists")

    _create_and_send_code(db, email, "register")
    return {"ok": True, "message": "Verification code sent"}


@router.post("/api/auth/register")
@limiter.limit("5/minute")
async def register(request: Request, body: AuthRegister, db: Session = Depends(get_db)):
    """Verify the email code, create the account, and return a JWT."""
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")
    if len(body.password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )
    if not body.code or not body.code.strip():
        raise HTTPException(status_code=400, detail="Verification code is required")

    role = body.role if body.role in ("student", "teacher") else "student"
    if not feature_flags.ENABLE_TEACHER_FEATURES:
        role = "student"

    exists = db.query(User).filter(User.email == email).first()
    if exists:
        raise HTTPException(status_code=409, detail="Account already exists")

    _verify_code(db, email, body.code, "register")

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

    return _auth_response(user, db)


# ── Login ───────────────────────────────────────────────────────


@router.post("/api/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, body: AuthLogin, db: Session = Depends(get_db)):
    """Login and receive a JWT."""
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return _auth_response(user, db)


# ── Password reset ──────────────────────────────────────────────


@router.post("/api/auth/password-reset/request")
@limiter.limit("5/minute")
async def password_reset_request(
    request: Request, body: RequestCode, db: Session = Depends(get_db)
):
    """Email a password-reset code. Always returns ok to avoid revealing accounts."""
    email = body.email.strip().lower()
    if EMAIL_RE.match(email):
        user = db.query(User).filter(User.email == email).first()
        if user:
            _create_and_send_code(db, email, "password_reset")
    return {"ok": True, "message": "If an account exists for this email, a code is on its way"}


@router.post("/api/auth/password-reset/confirm")
@limiter.limit("10/minute")
async def password_reset_confirm(
    request: Request, body: PasswordResetConfirm, db: Session = Depends(get_db)
):
    """Verify the reset code, set the new password, and log the user in."""
    email = body.email.strip().lower()
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

    _verify_code(db, email, body.code, "password_reset")

    user.hashed_password = hash_password(body.new_password)
    db.commit()
    db.refresh(user)

    return _auth_response(user, db)
