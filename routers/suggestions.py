"""Level-aware content suggestions: /api/languages/{id}/suggest-*.

Lets a learner keep growing their knowledge base after the placement test by
generating more vocabulary / grammar at their current level, excluding what
they already have.
"""

import uuid
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from database import User, Language, Vocabulary, Grammar, SessionLocal
from auth import get_current_user
from cost_tracker import TrackedOpenAI, check_sufficient_credits
from dependencies import get_db, get_api_key, get_native_language, get_user_level
from agents.placement_agent import PlacementTestAgent
from agents.logging_utils import Colors, get_logger, log_api_call as _log_api_call
from content_utils import save_generated_content
from levels import level_label

logger = get_logger(__name__)
router = APIRouter()

MAX_VOCAB_SUGGESTIONS = 50
MAX_GRAMMAR_SUGGESTIONS = 10


class SuggestBody(BaseModel):
    count: int = Field(default=20, ge=1, le=MAX_VOCAB_SUGGESTIONS)


class SuggestGrammarBody(BaseModel):
    count: int = Field(default=5, ge=1, le=MAX_GRAMMAR_SUGGESTIONS)


class SaveSuggestionsBody(BaseModel):
    vocabulary: List[Dict] = []
    grammar: List[Dict] = []


def _get_language(db: Session, user: User, language_id: int) -> Language:
    lang = (
        db.query(Language)
        .filter(Language.id == language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")
    return lang


def _make_agent(db: Session, user: User, lang: Language) -> PlacementTestAgent:
    if not check_sufficient_credits(user, min_credits=1):
        raise HTTPException(status_code=402, detail="Insufficient credits.")
    client = TrackedOpenAI(
        get_api_key(),
        user_id=user.id,
        session_id=str(uuid.uuid4()),
        db_factory=SessionLocal,
    )
    return PlacementTestAgent(client, lang.name, get_native_language(db, user.id))


@router.post("/api/languages/{language_id}/suggest-vocabulary")
async def suggest_vocabulary(
    language_id: int,
    body: SuggestBody = SuggestBody(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate new vocabulary at the learner's level, excluding known words."""
    _log_api_call(logger, "POST", f"/api/languages/{language_id}/suggest-vocabulary")
    lang = _get_language(db, user, language_id)
    level = get_user_level(db, user.id, lang)
    known = [
        w
        for (w,) in db.query(Vocabulary.target_word)
        .filter(Vocabulary.language_id == language_id)
        .all()
    ]
    agent = _make_agent(db, user, lang)
    logger.info(
        f"{Colors.CYAN}📚 Suggesting {body.count} vocab at {level} for {lang.name} "
        f"(excluding {len(known)} known){Colors.END}"
    )
    vocabulary = agent.generate_vocabulary(level, count=body.count, exclude=known)
    return {"level": level, "level_label": level_label(level), "vocabulary": vocabulary}


@router.post("/api/languages/{language_id}/suggest-grammar")
async def suggest_grammar(
    language_id: int,
    body: SuggestGrammarBody = SuggestGrammarBody(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate new grammar concepts at the learner's level, excluding known ones."""
    _log_api_call(logger, "POST", f"/api/languages/{language_id}/suggest-grammar")
    lang = _get_language(db, user, language_id)
    level = get_user_level(db, user.id, lang)
    known = [
        c
        for (c,) in db.query(Grammar.concept_name)
        .filter(Grammar.language_id == language_id)
        .all()
    ]
    agent = _make_agent(db, user, lang)
    logger.info(
        f"{Colors.CYAN}📚 Suggesting {body.count} grammar at {level} for {lang.name} "
        f"(excluding {len(known)} known){Colors.END}"
    )
    grammar = agent.generate_grammar(level, count=body.count, exclude=known)
    return {"level": level, "level_label": level_label(level), "grammar": grammar}


@router.post("/api/languages/{language_id}/save-suggestions")
async def save_suggestions(
    language_id: int,
    body: SaveSuggestionsBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist user-approved suggestions into the knowledge base."""
    _get_language(db, user, language_id)
    added_vocab, added_grammar = save_generated_content(
        db, get_api_key(), language_id, body.vocabulary, body.grammar
    )
    db.commit()
    logger.info(
        f"{Colors.GREEN}✅ Suggestions saved: {added_vocab} vocab, "
        f"{added_grammar} grammar{Colors.END}"
    )
    return {
        "message": "Suggestions saved",
        "vocabulary_added": added_vocab,
        "grammar_added": added_grammar,
    }
