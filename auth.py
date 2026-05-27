"""
Authentication module — JWT + bcrypt
Provides password hashing, JWT token creation/verification, and a FastAPI
dependency (`get_current_user`) for protecting routes.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import User, get_db, SessionLocal

# ── Configuration ───────────────────────────────────────────────

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-to-a-real-secret-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "72"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


# ── Password helpers ────────────────────────────────────────────


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ─────────────────────────────────────────────────


def create_access_token(user_id: int, email: str, role: str = "student") -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# ── FastAPI dependency ──────────────────────────────────────────


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency that extracts the JWT from the Authorization header,
    validates it, and returns the corresponding User ORM object.
    Raises 401 if anything is wrong.
    """
    payload = decode_access_token(credentials.credentials)
    user_id = int(payload["sub"])

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def require_teacher(
    user: User = Depends(get_current_user),
) -> User:
    """Dependency: only allows users with role='teacher'."""
    if user.role != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher access required",
        )
    return user


def require_student(
    user: User = Depends(get_current_user),
) -> User:
    """Dependency: only allows users with role='student'."""
    if user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required",
        )
    return user
