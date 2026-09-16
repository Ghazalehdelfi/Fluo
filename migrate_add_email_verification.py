#!/usr/bin/env python3
"""
Migration: Add email_verification_codes table for email confirmation
at registration and password-reset codes.

Run once:
    python migrate_add_email_verification.py
"""

from dotenv import load_dotenv
load_dotenv()

from aws_config import load_secrets
load_secrets()

from database import engine
from sqlalchemy import text

MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS email_verification_codes (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        code_hash VARCHAR(64) NOT NULL,
        purpose VARCHAR(20) NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        consumed_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_email_verification_codes_email
    ON email_verification_codes (email);
    """,
]


def run():
    with engine.begin() as conn:
        for i, stmt in enumerate(MIGRATIONS, 1):
            conn.execute(text(stmt))
            print(f"  ✓ step {i}/{len(MIGRATIONS)}")
    print("Migration complete.")


if __name__ == "__main__":
    run()
