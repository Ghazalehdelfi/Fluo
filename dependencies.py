"""Shared FastAPI dependencies used across multiple routers."""

import os
import logging
import threading
from fastapi import HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal

logger = logging.getLogger(__name__)

try:
    from elevenlabs import ElevenLabs as _ElevenLabs
except ImportError:
    _ElevenLabs = None


# ── OpenAI API key rotation ───────────────────────────────────────
# Set OPENAI_API_KEYS as a comma-separated list of keys to enable rotation.
# Falls back to OPENAI_API_KEY (single key) for backwards compatibility.

def _load_openai_keys() -> list[str]:
    multi = os.getenv("OPENAI_API_KEYS", "")
    if multi:
        keys = [k.strip() for k in multi.split(",") if k.strip()]
        if keys:
            return keys
    single = os.getenv("OPENAI_API_KEY", "")
    return [single] if single else []


_openai_keys: list[str] = _load_openai_keys()
_key_index: int = 0
_key_lock = threading.Lock()


def get_api_key() -> str:
    """Return the next OpenAI API key in round-robin order.

    Configure multiple keys via OPENAI_API_KEYS (comma-separated) or a single
    key via OPENAI_API_KEY.  Keys are refreshed from the environment on the
    first call; restart the process to pick up new keys.
    """
    global _key_index
    if not _openai_keys:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    with _key_lock:
        key = _openai_keys[_key_index % len(_openai_keys)]
        _key_index = (_key_index + 1) % len(_openai_keys)
    return key


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_elevenlabs_client():
    """Return an ElevenLabs client if the SDK is installed and the API key is set."""
    if _ElevenLabs is None:
        logger.warning(
            "elevenlabs package not installed — TTS/STT will fall back to OpenAI"
        )
        return None
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        logger.warning("ELEVENLABS_API_KEY not set — TTS/STT will fall back to OpenAI")
        return None
    return _ElevenLabs(api_key=api_key)


def get_native_language(db: Session, user_id: int) -> str:
    """Get native language from per-user settings."""
    from database import Settings

    native = (
        db.query(Settings)
        .filter(Settings.user_id == user_id, Settings.key == "native_language")
        .first()
    )
    return native.value if native else "English"


def get_user_level(db: Session, user_id: int) -> str:
    """Get the user's default CEFR level from settings (default A1)."""
    from database import Settings

    setting = (
        db.query(Settings)
        .filter(Settings.user_id == user_id, Settings.key == "user_level")
        .first()
    )
    return setting.value if setting else "A1"
