"""Language management routes: /api/languages."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import User, Language, Settings, SUPPORTED_LANGUAGES, NATIVE_LANGUAGES
from auth import get_current_user
from dependencies import get_db, get_native_language, get_user_level

logger = logging.getLogger(__name__)
router = APIRouter()


class LanguageCreate(BaseModel):
    name: str


@router.get("/api/languages")
async def get_languages(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all user's languages and available languages to add."""
    user_languages = (
        db.query(Language)
        .filter(Language.user_id == user.id, Language.is_active == True)
        .all()
    )
    native_lang = get_native_language(db, user.id)
    user_level = get_user_level(db, user.id)

    user_lang_names = {lang.name for lang in user_languages}
    available = [
        name for name in SUPPORTED_LANGUAGES.keys() if name not in user_lang_names
    ]

    default_lang_setting = (
        db.query(Settings)
        .filter(Settings.user_id == user.id, Settings.key == "default_language_id")
        .first()
    )
    default_language_id = (
        int(default_lang_setting.value) if default_lang_setting else None
    )

    return {
        "user_languages": [
            {"id": lang.id, "name": lang.name, "code": lang.code}
            for lang in user_languages
        ],
        "available_languages": available,
        "native_language": native_lang,
        "native_language_options": NATIVE_LANGUAGES,
        "default_language_id": default_language_id,
        "user_level": user_level,
    }


@router.post("/api/languages")
async def add_language(
    language: LanguageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a new language to learn."""
    if language.name not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {language.name}. Available: {list(SUPPORTED_LANGUAGES.keys())}",
        )

    existing = (
        db.query(Language)
        .filter(Language.user_id == user.id, Language.name == language.name)
        .first()
    )
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="Language already added")
        existing.is_active = True
        db.commit()
        return {"message": f"{language.name} reactivated", "id": existing.id}

    new_lang = Language(
        user_id=user.id,
        name=language.name,
        code=SUPPORTED_LANGUAGES[language.name],
    )
    db.add(new_lang)
    db.commit()
    db.refresh(new_lang)
    return {"message": f"{language.name} added", "id": new_lang.id}


@router.delete("/api/languages/{language_id}")
async def remove_language(
    language_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a language and all associated data (vocab, grammar, conversations, level)."""
    lang = (
        db.query(Language)
        .filter(Language.id == language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    lang_name = lang.name
    lang_code = lang.code

    # Clear CEFR level setting for this language
    setting_key = f"{lang_code}_level"
    db.query(Settings).filter(
        Settings.user_id == user.id, Settings.key == setting_key
    ).delete()

    # Clear default language setting if it pointed to this language
    default_setting = (
        db.query(Settings)
        .filter(
            Settings.user_id == user.id,
            Settings.key == "default_language_id",
            Settings.value == str(language_id),
        )
        .first()
    )
    if default_setting:
        db.delete(default_setting)

    # Delete language row — cascades to vocabulary, grammar, conversations
    db.delete(lang)
    db.commit()
    return {"message": f"{lang_name} and all associated data removed"}
