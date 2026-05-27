-- Supabase Schema for Language Learning App
-- Run this in the Supabase SQL Editor to create all tables.

-- ── 1. Users ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    credits_balance DOUBLE PRECISION DEFAULT 0.0,
    stripe_customer_id TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- ── 2. Settings (per-user key/value) ───────────────────────────
CREATE TABLE IF NOT EXISTS settings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT,
    updated_at TIMESTAMP DEFAULT now(),
    CONSTRAINT uq_user_setting UNIQUE (user_id, key)
);

CREATE INDEX IF NOT EXISTS idx_settings_key ON settings (key);

-- ── 3. Languages ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS languages (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT now(),
    CONSTRAINT uq_user_language UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_languages_name ON languages (name);

-- ── 4. Vocabulary ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vocabulary (
    id SERIAL PRIMARY KEY,
    language_id INTEGER NOT NULL REFERENCES languages(id) ON DELETE CASCADE,
    target_word TEXT NOT NULL,
    native_translation TEXT,
    example_sentence TEXT,
    fluency_level TEXT DEFAULT 'low',
    times_practiced INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    last_practiced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_vocabulary_target_word ON vocabulary (target_word);

-- Add embedding column if it doesn't exist (run separately on existing DBs)
-- ALTER TABLE vocabulary ADD COLUMN IF NOT EXISTS embedding TEXT;

-- ── 8. Conversation Topics (pre-computed cluster topics) ────────
CREATE TABLE IF NOT EXISTS conversation_topics (
    id SERIAL PRIMARY KEY,
    language_id INTEGER NOT NULL REFERENCES languages(id) ON DELETE CASCADE,
    cluster_id INTEGER NOT NULL,
    theme TEXT NOT NULL,
    topic TEXT NOT NULL,
    vocab_ids TEXT NOT NULL,
    generated_at TIMESTAMP DEFAULT now(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_conversation_topics_language ON conversation_topics (language_id);

-- ── 5. Grammar ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS grammar (
    id SERIAL PRIMARY KEY,
    language_id INTEGER NOT NULL REFERENCES languages(id) ON DELETE CASCADE,
    concept_name TEXT NOT NULL,
    description TEXT,
    examples TEXT,
    fluency_level TEXT DEFAULT 'low',
    times_practiced INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    last_practiced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_grammar_concept_name ON grammar (concept_name);

-- ── 6. Conversations ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    language_id INTEGER REFERENCES languages(id) ON DELETE CASCADE,
    lesson_plan TEXT,
    transcript TEXT,
    analysis TEXT,
    vocab_used TEXT,
    grammar_used TEXT,
    total_cost_usd DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT now()
);

-- ── 7. Usage Logs (billing) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS usage_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT,
    model TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    audio_seconds DOUBLE PRECISION DEFAULT 0.0,
    characters INTEGER DEFAULT 0,
    cost_usd DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);
