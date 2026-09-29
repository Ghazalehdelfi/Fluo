"""History, stats, and dashboard routes."""

import json
import logging
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import (
    User,
    Language,
    Vocabulary,
    Grammar,
    Conversation,
    Settings,
)
from auth import get_current_user
from dependencies import get_db, get_native_language

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/conversations")
async def get_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get conversation history."""
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "created_at": c.created_at.isoformat(),
            "transcript": c.transcript,
            "analysis": json.loads(c.analysis) if c.analysis else None,
            "total_cost_usd": c.total_cost_usd,
        }
        for c in conversations
    ]


@router.get("/api/stats/{language_id}")
async def get_language_stats(
    language_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get learning statistics for a specific language."""
    lang = (
        db.query(Language)
        .filter(Language.id == language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    vocab_count = (
        db.query(Vocabulary).filter(Vocabulary.language_id == language_id).count()
    )
    grammar_count = db.query(Grammar).filter(Grammar.language_id == language_id).count()
    conversation_count = (
        db.query(Conversation).filter(Conversation.language_id == language_id).count()
    )

    vocab_by_fluency = {
        level: db.query(Vocabulary)
        .filter(
            Vocabulary.language_id == language_id, Vocabulary.fluency_level == level
        )
        .count()
        for level in ("low", "medium", "high")
    }
    grammar_by_fluency = {
        level: db.query(Grammar)
        .filter(Grammar.language_id == language_id, Grammar.fluency_level == level)
        .count()
        for level in ("low", "medium", "high")
    }

    return {
        "language": lang.name,
        "total_vocabulary": vocab_count,
        "total_grammar": grammar_count,
        "total_conversations": conversation_count,
        "vocabulary_by_fluency": vocab_by_fluency,
        "grammar_by_fluency": grammar_by_fluency,
    }


@router.get("/api/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get overall learning statistics across all languages."""
    native_lang = get_native_language(db, user.id)
    user_languages = (
        db.query(Language)
        .filter(Language.user_id == user.id, Language.is_active == True)
        .all()
    )

    languages_stats = []
    for lang in user_languages:
        vocab_count = (
            db.query(Vocabulary).filter(Vocabulary.language_id == lang.id).count()
        )
        grammar_count = db.query(Grammar).filter(Grammar.language_id == lang.id).count()
        languages_stats.append(
            {
                "id": lang.id,
                "name": lang.name,
                "vocab_count": vocab_count,
                "grammar_count": grammar_count,
            }
        )

    return {
        "languages": languages_stats,
        "native_language": native_lang,
    }


@router.get("/api/dashboard")
async def get_dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    language_id: Optional[int] = None,
):
    """Get dashboard data. If language_id is provided, returns per-language stats."""
    from sqlalchemy import func

    if language_id:
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
        user_lang_ids = [language_id]
    else:
        user_lang_ids = [
            lid
            for (lid,) in db.query(Language.id)
            .filter(Language.user_id == user.id, Language.is_active == True)
            .all()
        ]

    total_vocab = (
        db.query(func.count(Vocabulary.id))
        .filter(Vocabulary.language_id.in_(user_lang_ids))
        .scalar()
        if user_lang_ids
        else 0
    )
    total_grammar = (
        db.query(func.count(Grammar.id))
        .filter(Grammar.language_id.in_(user_lang_ids))
        .scalar()
        if user_lang_ids
        else 0
    )

    fluency_level = "Beginner"
    high = medium = 0
    if total_vocab > 0:
        high = (
            db.query(func.count(Vocabulary.id))
            .filter(
                Vocabulary.language_id.in_(user_lang_ids),
                Vocabulary.fluency_level == "high",
            )
            .scalar()
        )
        medium = (
            db.query(func.count(Vocabulary.id))
            .filter(
                Vocabulary.language_id.in_(user_lang_ids),
                Vocabulary.fluency_level == "medium",
            )
            .scalar()
        )
        high_ratio = high / total_vocab
        med_ratio = medium / total_vocab
        if high_ratio >= 0.5:
            fluency_level = "Advanced"
        elif high_ratio + med_ratio >= 0.4:
            fluency_level = "Intermediate"

    if language_id:
        lang_obj = db.query(Language).filter(Language.id == language_id).first()
        cefr_key = f"{lang_obj.code}_level" if lang_obj else None
        cefr_settings = (
            db.query(Settings)
            .filter(Settings.user_id == user.id, Settings.key == cefr_key)
            .all()
            if cefr_key
            else []
        )
    else:
        cefr_settings = (
            db.query(Settings)
            .filter(Settings.user_id == user.id, Settings.key.like("%_level"))
            .all()
        )

    if cefr_settings:
        cefr_order = ["A1", "A2", "B1", "B2", "C1", "C2"]
        best = max(
            cefr_settings,
            key=lambda s: cefr_order.index(s.value) if s.value in cefr_order else -1,
        )
        if best.value in cefr_order:
            fluency_level = best.value

    # Daily streak: count consecutive days with any activity
    activity_dates = set()

    for (d,) in (
        db.query(func.date(Conversation.created_at))
        .filter(Conversation.user_id == user.id)
        .distinct()
        .all()
    ):
        if d:
            activity_dates.add(
                d
                if isinstance(d, date)
                else d.date() if hasattr(d, "date") else date.fromisoformat(str(d))
            )

    if user_lang_ids:
        for (d,) in (
            db.query(func.date(Vocabulary.last_practiced_at))
            .filter(
                Vocabulary.language_id.in_(user_lang_ids),
                Vocabulary.last_practiced_at.isnot(None),
            )
            .distinct()
            .all()
        ):
            if d:
                activity_dates.add(
                    d
                    if isinstance(d, date)
                    else d.date() if hasattr(d, "date") else date.fromisoformat(str(d))
                )

        for (d,) in (
            db.query(func.date(Grammar.last_practiced_at))
            .filter(
                Grammar.language_id.in_(user_lang_ids),
                Grammar.last_practiced_at.isnot(None),
            )
            .distinct()
            .all()
        ):
            if d:
                activity_dates.add(
                    d
                    if isinstance(d, date)
                    else d.date() if hasattr(d, "date") else date.fromisoformat(str(d))
                )

    today = date.today()
    streak = 0
    check = today
    while check in activity_dates:
        streak += 1
        check -= timedelta(days=1)

    # Last 7 days, oldest -> today, for the weekly activity strip
    week_activity = [
        (today - timedelta(days=offset)) in activity_dates for offset in range(6, -1, -1)
    ]

    return {
        "credits": user.credits_balance,
        "total_vocab": total_vocab,
        "total_grammar": total_grammar,
        "vocab_by_fluency": {
            "high": high,
            "medium": medium,
            "low": max(total_vocab - high - medium, 0),
        },
        "fluency_level": fluency_level,
        "daily_streak": streak,
        "practiced_today": today in activity_dates,
        "week_activity": week_activity,
        "language_id": language_id,
    }
