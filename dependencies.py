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


def _level_setting_keys(language) -> list[str]:
    """Candidate settings keys for a language's level, most preferred first.

    Historically the placement test wrote ``{name.lower()}_level`` while other
    code read ``{code}_level``; we accept both and write the code-based key.
    """
    keys = []
    if language is not None:
        if getattr(language, "code", None):
            keys.append(f"{language.code}_level")
        if getattr(language, "name", None):
            keys.append(f"{language.name.lower()}_level")
    return keys


def get_user_level(db: Session, user_id: int, language=None) -> str:
    """Get the learner's level for ``language`` (a ``Language`` row or id),
    falling back to the account-wide ``user_level`` and then the default.

    Always returns a canonical ``"B1-intermediate"`` style string.
    """
    from database import Settings, Language
    from levels import normalize_level, DEFAULT_LEVEL

    if isinstance(language, int):
        language = db.query(Language).filter(Language.id == language).first()

    for key in _level_setting_keys(language) + ["user_level"]:
        setting = (
            db.query(Settings)
            .filter(Settings.user_id == user_id, Settings.key == key)
            .first()
        )
        norm = normalize_level(setting.value) if setting else None
        if norm:
            return norm
    return DEFAULT_LEVEL


def set_user_level(db: Session, user_id: int, language, level: str) -> str:
    """Persist a canonical level for ``language`` (writes ``{code}_level`` and
    removes any legacy name-based key). Caller commits."""
    from database import Settings
    from levels import normalize_level

    norm = normalize_level(level)
    if not norm:
        raise ValueError(f"Invalid level: {level}")

    keys = _level_setting_keys(language)
    primary, legacy = keys[0], keys[1:]
    for key in legacy:
        db.query(Settings).filter(
            Settings.user_id == user_id, Settings.key == key
        ).delete()
    setting = (
        db.query(Settings)
        .filter(Settings.user_id == user_id, Settings.key == primary)
        .first()
    )
    if setting:
        setting.value = norm
    else:
        db.add(Settings(user_id=user_id, key=primary, value=norm))
    return norm
