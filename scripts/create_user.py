#!/usr/bin/env python3
"""Create a new user with a random password and assigned credits.

Usage:
    python create_user.py <username> [--credits N]

Examples:
    python create_user.py alice                  # 100 credits (default)
    python create_user.py bob --credits 200       # 200 credits
"""

import argparse
import secrets
import string

from dotenv import load_dotenv

load_dotenv()

from database import SessionLocal, User, DATABASE_URL
from auth import hash_password


def generate_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_user(
    username: str, credits: float, role: str = "student"
) -> tuple[str, float, str]:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == username).first()
        if existing:
            raise SystemExit(f"Error: user '{username}' already exists.")

        password = generate_password()
        user = User(
            email=username,
            hashed_password=hash_password(password),
            credits_balance=credits,
            role=role,
        )
        db.add(user)
        db.commit()
        return password, credits, role
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new Fluō user")
    parser.add_argument("username", help="Username for the new account")
    parser.add_argument(
        "--credits", type=float, default=100, help="Credits to assign (default: 100)"
    )
    parser.add_argument(
        "--role",
        choices=["student", "teacher"],
        default="student",
        help="User role (default: student)",
    )
    args = parser.parse_args()

    password, credits, role = create_user(args.username, args.credits, args.role)
    print(f"User created successfully!")
    print(f"  Username: {args.username}")
    print(f"  Password: {password}")
    print(f"  Role:     {role}")
    print(f"  Credits:  ${credits:.2f}")
