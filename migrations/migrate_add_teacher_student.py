#!/usr/bin/env python3
"""
Migration: Add teacher/student roles and homework system tables.

Run once:
    python migrate_add_teacher_student.py
"""

from dotenv import load_dotenv
load_dotenv()

from aws_config import load_secrets
load_secrets()

from database import engine
from sqlalchemy import text

MIGRATIONS = [
    # 1. Add role column to users
    """
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'student';
    """,

    # 2. Classes
    """
    CREATE TABLE IF NOT EXISTS classes (
        id SERIAL PRIMARY KEY,
        teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        language_id INTEGER REFERENCES languages(id) ON DELETE SET NULL,
        class_code VARCHAR(12) NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
    """,

    # 3. Class ↔ student join
    """
    CREATE TABLE IF NOT EXISTS class_students (
        class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
        student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        joined_at TIMESTAMP NOT NULL DEFAULT NOW(),
        PRIMARY KEY (class_id, student_id)
    );
    """,

    # 4. Homework
    """
    CREATE TABLE IF NOT EXISTS homework (
        id SERIAL PRIMARY KEY,
        class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
        teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        language_id INTEGER REFERENCES languages(id) ON DELETE SET NULL,
        due_date DATE,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
    """,

    # 5. Homework vocab refs (FK into teacher's vocabulary)
    """
    CREATE TABLE IF NOT EXISTS homework_vocab_refs (
        homework_id INTEGER NOT NULL REFERENCES homework(id) ON DELETE CASCADE,
        vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE,
        PRIMARY KEY (homework_id, vocabulary_id)
    );
    """,

    # 6. Homework grammar refs (FK into teacher's grammar)
    """
    CREATE TABLE IF NOT EXISTS homework_grammar_refs (
        homework_id INTEGER NOT NULL REFERENCES homework(id) ON DELETE CASCADE,
        grammar_id INTEGER NOT NULL REFERENCES grammar(id) ON DELETE CASCADE,
        PRIMARY KEY (homework_id, grammar_id)
    );
    """,

    # 7. Homework grammar questions (teacher-refined, persistent)
    """
    CREATE TABLE IF NOT EXISTS homework_grammar_questions (
        id SERIAL PRIMARY KEY,
        homework_id INTEGER NOT NULL REFERENCES homework(id) ON DELETE CASCADE,
        grammar_id INTEGER NOT NULL REFERENCES grammar(id) ON DELETE CASCADE,
        question_type VARCHAR(30) NOT NULL,
        question_text TEXT NOT NULL,
        english_prompt TEXT,
        wrong_sentence TEXT,
        correct_answer TEXT NOT NULL,
        explanation TEXT,
        highlighted_segments TEXT,
        order_index INTEGER NOT NULL DEFAULT 0
    );
    """,

    # 8. Homework conversation topics
    """
    CREATE TABLE IF NOT EXISTS homework_topics (
        id SERIAL PRIMARY KEY,
        homework_id INTEGER NOT NULL REFERENCES homework(id) ON DELETE CASCADE,
        topic_text TEXT NOT NULL,
        source VARCHAR(20) NOT NULL DEFAULT 'custom',
        cluster_topic_id INTEGER REFERENCES conversation_topics(id) ON DELETE SET NULL
    );
    """,

    # 9. Homework completions (per student, per exercise type)
    """
    CREATE TABLE IF NOT EXISTS homework_completions (
        id SERIAL PRIMARY KEY,
        student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        homework_id INTEGER NOT NULL REFERENCES homework(id) ON DELETE CASCADE,
        exercise_type VARCHAR(30) NOT NULL,
        completed_at TIMESTAMP NOT NULL DEFAULT NOW(),
        score FLOAT,
        UNIQUE (student_id, homework_id, exercise_type)
    );
    """,
]


def run():
    with engine.connect() as conn:
        for sql in MIGRATIONS:
            conn.execute(text(sql.strip()))
        conn.commit()
    print("Migration complete.")


if __name__ == "__main__":
    run()
