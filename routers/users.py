"""User profile and settings routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import User, Settings, Language, NATIVE_LANGUAGES, ClassStudent
from auth import get_current_user
from dependencies import get_db, get_native_language

logger = logging.getLogger(__name__)
router = APIRouter()


class SettingsUpdate(BaseModel):
    native_language: str


@router.get("/api/user/me")
async def get_current_user_info(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user profile + credit balance."""
    default_lang_setting = (
        db.query(Settings)
        .filter(Settings.user_id == user.id, Settings.key == "default_language_id")
        .first()
    )
    default_language_id = (
        int(default_lang_setting.value) if default_lang_setting else None
    )
    enrolled_in_class = (
        db.query(ClassStudent).filter(ClassStudent.student_id == user.id).first()
        is not None
    )
    return {
        "id": user.id,
        "email": user.email,
        "credits": user.credits_balance,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "default_language_id": default_language_id,
        "enrolled_in_class": enrolled_in_class,
    }


@router.get("/api/settings")
async def get_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current settings."""
    native_lang = get_native_language(db, user.id)
    default_lang_setting = (
        db.query(Settings)
        .filter(Settings.user_id == user.id, Settings.key == "default_language_id")
        .first()
    )
    default_language_id = (
        int(default_lang_setting.value) if default_lang_setting else None
    )
    return {
        "native_language": native_lang,
        "native_language_options": NATIVE_LANGUAGES,
        "default_language_id": default_language_id,
    }


@router.put("/api/settings/default-language")
async def set_default_language(
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set the user's default language."""
    language_id = body.get("language_id")
    if language_id is not None:
        lang = (
            db.query(Language)
            .filter(
                Language.id == language_id,
                Language.user_id == user.id,
                Language.is_active == True,
            )
            .first()
        )
        if not lang:
            raise HTTPException(status_code=404, detail="Language not found")

    setting = (
        db.query(Settings)
        .filter(Settings.user_id == user.id, Settings.key == "default_language_id")
        .first()
    )
    if setting:
        setting.value = str(language_id) if language_id else None
    else:
        db.add(
            Settings(
                user_id=user.id,
                key="default_language_id",
                value=str(language_id),
            )
        )
    db.commit()
    return {"message": "Default language updated", "default_language_id": language_id}


@router.post("/api/settings")
async def update_settings(
    settings: SettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update settings."""
    native_setting = (
        db.query(Settings)
        .filter(Settings.user_id == user.id, Settings.key == "native_language")
        .first()
    )
    if native_setting:
        native_setting.value = settings.native_language
    else:
        db.add(
            Settings(
                user_id=user.id,
                key="native_language",
                value=settings.native_language,
            )
        )
    db.commit()
    return {"message": "Settings updated", "native_language": settings.native_language}


@router.put("/api/settings/level")
async def set_user_level(
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set the user's default CEFR level."""
    from levels import normalize_level, ALL_LEVELS

    level = normalize_level(body.get("level"))
    if not level:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level. Must be one of: {', '.join(ALL_LEVELS)}",
        )
    setting = (
        db.query(Settings)
        .filter(Settings.user_id == user.id, Settings.key == "user_level")
        .first()
    )
    if setting:
        setting.value = level
    else:
        db.add(Settings(user_id=user.id, key="user_level", value=level))
    db.commit()
    return {"message": "Level updated", "user_level": level}
