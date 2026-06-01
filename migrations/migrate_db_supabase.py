"""
Migrate to Supabase
───────────────────
Creates all tables on a Supabase Postgres database and optionally copies
data from the local SQLite database.

Usage:
    python migrate_to_supabase.py <SUPABASE_DATABASE_URL>

Example:
    python migrate_to_supabase.py "postgresql://postgres.xxx:password@aws-0-region.pooler.supabase.com:6543/postgres"

The script will:
  1. Connect to Supabase and create all tables
  2. Ask if you want to copy data from your local SQLite DB
  3. Copy users, settings, languages, vocabulary, grammar, conversations, usage_logs
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
import dotenv

# Import all models so Base.metadata knows about them
from database import (
    Base,
    User,
    Settings,
    Language,
    Vocabulary,
    Grammar,
    Conversation,
    UsageLog,
)

LOCAL_DB_PATH = Path(__file__).parent / "language_learning.db"
LOCAL_DB_URL = f"sqlite:///{LOCAL_DB_PATH}"

# Table creation order (respects foreign key dependencies)
ORDERED_MODELS = [User, Settings, Language, Vocabulary, Grammar, Conversation, UsageLog]


def create_supabase_engine(url: str):
    return create_engine(url, connect_args={"sslmode": "require"}, pool_pre_ping=True)


def create_tables(engine):
    """Create all tables on the target database."""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"✓ Tables on Supabase: {', '.join(tables)}")


def copy_data(source_url: str, target_engine):
    """Copy all rows from the local SQLite DB to Supabase.

    Uses raw SQL to read from the source so that missing columns in the
    old SQLite schema don't cause errors.
    """
    source_engine = create_engine(source_url, connect_args={"check_same_thread": False})
    TargetSession = sessionmaker(bind=target_engine)
    tgt = TargetSession()

    try:
        src_inspector = inspect(source_engine)
        for model in ORDERED_MODELS:
            table_name = model.__tablename__

            # Skip if table doesn't exist in source
            if table_name not in src_inspector.get_table_names():
                print(f"  ⏭  {table_name}: not in local DB (skipped)")
                continue

            # Get columns that exist in BOTH source and target
            source_cols = {c["name"] for c in src_inspector.get_columns(table_name)}
            target_cols = {c.key for c in model.__table__.columns}
            common_cols = sorted(source_cols & target_cols)

            if not common_cols:
                print(f"  ⏭  {table_name}: no matching columns (skipped)")
                continue

            # Read raw rows from source using only the columns that exist
            with source_engine.connect() as src_conn:
                col_list = ", ".join(f'"{c}"' for c in common_cols)
                result = src_conn.execute(
                    text(f'SELECT {col_list} FROM "{table_name}"')
                )
                rows = result.fetchall()

            if not rows:
                print(f"  ⏭  {table_name}: 0 rows (skipped)")
                continue

            # Check if target already has data
            existing = tgt.query(model).count()
            if existing > 0:
                print(
                    f"  ⚠  {table_name}: target already has {existing} rows — skipping to avoid duplicates"
                )
                continue

            # Detect NOT NULL columns missing from the source that need defaults
            not_null_cols = {
                c.key
                for c in model.__table__.columns
                if not c.nullable and c.key not in common_cols and not c.primary_key
            }

            # Insert into target
            for row in rows:
                data = dict(zip(common_cols, row))
                # Fill NOT NULL foreign keys that are missing from old schema
                if "user_id" in not_null_cols and "user_id" not in data:
                    data["user_id"] = 1  # assign to first user
                tgt.execute(model.__table__.insert().values(**data))

            tgt.commit()
            missing = target_cols - source_cols
            note = f" (missing cols filled with defaults: {missing})" if missing else ""
            print(f"  ✓  {table_name}: {len(rows)} rows copied{note}")

    except Exception as e:
        tgt.rollback()
        print(f"\n✗ Error during data copy: {e}")
        raise
    finally:
        tgt.close()


def main():
    dotenv.load_dotenv()
    supabase_url = os.getenv("DATABASE_URL")
    if not supabase_url:
        print(
            "Usage: python migrate_to_supabase.py add your Supabase DATABASE_URL in the .env file"
        )
        sys.exit(1)

    print(f"\n🔌 Connecting to Supabase...")
    engine = create_supabase_engine(supabase_url)

    # Test connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Connected successfully\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)

    # Step 1: Create tables
    print("📦 Creating tables...")
    create_tables(engine)
    print()

    # Step 2: Optionally copy data
    if LOCAL_DB_PATH.exists():
        answer = (
            input(
                f"📋 Local SQLite DB found ({LOCAL_DB_PATH.name}). Copy data to Supabase? [y/N] "
            )
            .strip()
            .lower()
        )
        if answer == "y":
            print("\n📋 Copying data...")
            copy_data(LOCAL_DB_URL, engine)
            print("\n✓ Data migration complete!")
        else:
            print("⏭  Skipping data copy.")
    else:
        print("ℹ  No local SQLite database found — only tables were created.")

    print("\n✅ Done! Set your DATABASE_URL env var to switch the app to Supabase.")


if __name__ == "__main__":
    main()
