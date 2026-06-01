"""
Migration: Add vocabulary embeddings + conversation_topics table
───────────────────────────────────────────────────────────────
Run this once against your existing Supabase database to bring the schema
up to date before deploying the new clustering feature.

Usage:
    python migrate_add_topics.py

The DATABASE_URL environment variable (or .env file) must be set.

What it does:
  1. Adds  vocabulary.embedding  TEXT column (idempotent — skips if already present)
  2. Creates conversation_topics table (idempotent — skips if already present)
  3. Creates indexes for fast lookups
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


def table_exists(conn, table: str) -> bool:
    insp = inspect(conn)
    return table in insp.get_table_names()


def run():
    with engine.begin() as conn:
        # 1. Add embedding column to vocabulary
        if not column_exists(conn, "vocabulary", "embedding"):
            conn.execute(text("ALTER TABLE vocabulary ADD COLUMN embedding TEXT"))
            print("✓ Added vocabulary.embedding column")
        else:
            print("⏭  vocabulary.embedding already exists — skipped")

        # 2. Create conversation_topics table
        if not table_exists(conn, "conversation_topics"):
            conn.execute(
                text(
                    """
                    CREATE TABLE conversation_topics (
                        id SERIAL PRIMARY KEY,
                        language_id INTEGER NOT NULL
                            REFERENCES languages(id) ON DELETE CASCADE,
                        cluster_id INTEGER NOT NULL,
                        theme TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        vocab_ids TEXT NOT NULL,
                        generated_at TIMESTAMP DEFAULT now(),
                        is_active BOOLEAN DEFAULT TRUE
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_conversation_topics_language "
                    "ON conversation_topics (language_id)"
                )
            )
            print("✓ Created conversation_topics table + index")
        else:
            print("⏭  conversation_topics already exists — skipped")

    print("\nMigration complete.")


if __name__ == "__main__":
    run()
