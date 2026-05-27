"""
Migration: Add detail_card column to grammar table
───────────────────────────────────────────────────
Run this once against your existing Supabase database to bring the schema
up to date before deploying the grammar detail card feature.

Usage:
    python migrate_add_grammar_detail_card.py

The DATABASE_URL environment variable (or .env file) must be set.

What it does:
  1. Adds  grammar.detail_card  TEXT column (idempotent — skips if already present)
     This column stores the JSON-serialised detailed grammar study card generated
     by the AI, so it only needs to be generated once per concept.
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is not set.")
    sys.exit(1)

engine = create_engine(
    DATABASE_URL, connect_args={"sslmode": "require"}, pool_pre_ping=True
)


def column_exists(conn, table: str, column: str) -> bool:
    insp = inspect(conn)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def run():
    with engine.begin() as conn:
        if not column_exists(conn, "grammar", "detail_card"):
            conn.execute(text("ALTER TABLE grammar ADD COLUMN detail_card TEXT"))
            print("✓ Added grammar.detail_card column")
        else:
            print("⏭  grammar.detail_card already exists — skipped")


if __name__ == "__main__":
    run()
    print("\nMigration complete.")
