"""Shared FastAPI dependencies used across multiple routers."""

import os
import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal

logger = logging.getLogger(__name__)

try:
    from elevenlabs import ElevenLabs as _ElevenLabs
except ImportError:
    _ElevenLabs = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    return api_key


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
