"""Vocabulary and grammar management routes, including flashcard results."""

import json
import uuid
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import User, Language, Vocabulary, Grammar, SessionLocal
from auth import get_current_user
from cost_tracker import TrackedOpenAI, check_sufficient_credits
from dependencies import get_db, get_api_key, get_native_language, get_user_level
from grammar_utils import (
    GRAMMAR_SIMILARITY_HIGH,
    GRAMMAR_SIMILARITY_LOW,
    embed_text,
    grammar_embed_text,
    find_most_similar_grammar,
)
from agents.logging_utils import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ── Vocabulary ───────────────────────────────────────────────────


@router.get("/api/vocabulary/{language_id}")
async def get_vocabulary(
    language_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all vocabulary items for a specific language."""
    lang = (
        db.query(Language)
        .filter(Language.id == language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")
    items = db.query(Vocabulary).filter(Vocabulary.language_id == language_id).all()
    return [
        {
            "id": v.id,
            "target_word": v.target_word,
            "native_translation": v.native_translation,
            "example_sentence": v.example_sentence,
            "fluency_level": v.fluency_level,
            "times_practiced": v.times_practiced,
            "times_correct": v.times_correct,
        }
        for v in items
    ]


@router.delete("/api/vocabulary/{vocab_id}")
async def delete_vocabulary(
    vocab_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a vocabulary item."""
    item = (
        db.query(Vocabulary)
        .join(Language)
        .filter(Vocabulary.id == vocab_id, Language.user_id == user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")
    db.delete(item)
    db.commit()
    return {"message": "Vocabulary item deleted"}


# ── Grammar ──────────────────────────────────────────────────────


@router.get("/api/grammar/{language_id}")
async def get_grammar(
    language_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all grammar concepts for a specific language."""
    lang = (
        db.query(Language)
        .filter(Language.id == language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")
    items = db.query(Grammar).filter(Grammar.language_id == language_id).all()
    return [
        {
            "id": g.id,
            "concept_name": g.concept_name,
            "description": g.description,
            "examples": g.examples,
            "fluency_level": g.fluency_level,
            "times_practiced": g.times_practiced,
            "times_correct": g.times_correct,
            "has_detail_card": bool(g.detail_card),
        }
        for g in items
    ]


@router.delete("/api/grammar/{grammar_id}")
async def delete_grammar(
    grammar_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a grammar concept."""
    item = (
        db.query(Grammar)
        .join(Language)
        .filter(Grammar.id == grammar_id, Language.user_id == user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Grammar concept not found")
    db.delete(item)
    db.commit()
    return {"message": "Grammar concept deleted"}


# ── Pending grammar resolution ────────────────────────────────────


class GrammarCandidateModel(BaseModel):
    concept_name: str
    description: str = ""
    examples: str = ""


class GrammarResolvePendingModel(BaseModel):
    action: str  # "merge" | "create_new"
    candidate: GrammarCandidateModel
    existing_id: Optional[int] = None  # required when action == "merge"
    language_id: int


@router.post("/api/grammar/resolve-pending")
async def resolve_pending_grammar(
    body: GrammarResolvePendingModel,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve a pending grammar card held for user confirmation.

    action = "create_new" — insert candidate as a brand-new card.
    action = "merge"      — merge candidate into the existing card via LLM.
    """
    lang = (
        db.query(Language)
        .filter(Language.id == body.language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    api_key = get_api_key()

    if body.action == "create_new":
        candidate_text = grammar_embed_text(
            body.candidate.concept_name, body.candidate.description
        )
        vec = embed_text(api_key, candidate_text)
        new_item = Grammar(
            language_id=body.language_id,
            concept_name=body.candidate.concept_name,
            description=body.candidate.description,
            examples=body.candidate.examples,
            fluency_level="low",
            embedding=json.dumps(vec),
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return {
            "action": "created",
            "grammar_id": new_item.id,
            "concept_name": new_item.concept_name,
        }

    if body.action == "merge":
        if body.existing_id is None:
            raise HTTPException(
                status_code=422, detail="existing_id is required for action='merge'"
            )
        existing = (
            db.query(Grammar)
            .join(Language)
            .filter(Grammar.id == body.existing_id, Language.user_id == user.id)
            .first()
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Existing grammar card not found")

        if not check_sufficient_credits(user, min_credits=1):
            raise HTTPException(
                status_code=402,
                detail="Insufficient credits. Please purchase more credits to continue.",
            )

        user_level = get_user_level(db, user.id)
        session_id = str(uuid.uuid4())
        tracked_client = TrackedOpenAI(
            api_key, user_id=user.id, session_id=session_id, db_factory=SessionLocal
        )

        if existing.detail_card:
            existing_card_json = existing.detail_card
        else:
            existing_card_json = json.dumps(
                {
                    "concept": existing.concept_name,
                    "tagline": existing.description or "",
                    "examples": existing.examples or "",
                }
            )

        merge_prompt = f"""You are updating an existing grammar card with new evidence from a learner's notes.

You will be given the existing card and a new trigger phrase that relates to the same concept.
Your job is to enrich the card — add to it without duplicating what is already there.

Rules:
- Do not repeat examples, nuances, or errors already in the card.
- If the new trigger phrase reveals a specific use case not already covered, add it as a new example or nuance.
- If the new trigger adds nothing new, return the card unchanged.
- Never remove existing content.
- Return the full updated card JSON in the same schema.

Existing card:
{existing_card_json}

New trigger phrase / description: {body.candidate.description or body.candidate.concept_name}
New examples: {body.candidate.examples or "(none)"}

Target language: {lang.name}
Learner level: {user_level}"""

        response = tracked_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": merge_prompt}],
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
            raw = raw.strip()

        try:
            merged_card = json.loads(raw)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=502, detail="AI returned malformed JSON — please retry"
            )

        if existing.detail_card:
            existing.detail_card = json.dumps(merged_card)
        else:
            existing.description = merged_card.get("tagline", existing.description)
            existing.examples = merged_card.get("examples", existing.examples)

        new_desc = (
            merged_card.get("tagline", existing.description) or existing.description or ""
        )
        new_text = grammar_embed_text(existing.concept_name, new_desc)
        existing.embedding = json.dumps(embed_text(api_key, new_text))

        db.commit()
        return {
            "action": "merged",
            "grammar_id": existing.id,
            "concept_name": existing.concept_name,
            "updated_card": merged_card,
        }

    raise HTTPException(
        status_code=422,
        detail="action must be 'merge' or 'create_new'",
    )


@router.post("/api/grammar/{grammar_id}/detail-card")
async def get_grammar_detail_card(
    grammar_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the detailed grammar study card for a concept (cached or generated)."""
    item = (
        db.query(Grammar)
        .join(Language)
        .filter(Grammar.id == grammar_id, Language.user_id == user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Grammar concept not found")

    if item.detail_card:
        try:
            return json.loads(item.detail_card)
        except json.JSONDecodeError:
            pass  # fall through to regenerate

    if not check_sufficient_credits(user, min_credits=1):
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please purchase more credits to continue.",
        )

    api_key = get_api_key()
    native_lang = get_native_language(db, user.id)
    user_level = get_user_level(db, user.id)
    lang = item.language

    session_id = str(uuid.uuid4())
    tracked_client = TrackedOpenAI(
        api_key, user_id=user.id, session_id=session_id, db_factory=SessionLocal
    )

    prompt = f"""You are an expert language tutor creating a focused grammar study card for a language learner.

You will be given a grammar concept name, the phrase from the learner's notes that triggered it, the target language, and the learner's level.

Return only this JSON — no preamble, no markdown fences:

{{
  "concept": "Concept name",
  "tagline": "One sentence: what this concept does in plain English",
  "breakdown": {{
    "structure": "The abstract pattern e.g. [subject] + [auxiliary] + [past participle]",
    "components": [
      {{ "part": "element of the structure", "role": "what it does", "from_trigger": "the word from the trigger phrase that fills this slot" }}
    ]
  }},
  "core_rules": [
    "Rule stated simply",
    "..."
  ],
  "nuances": [
    {{ "observation": "A subtle point, exception, or register note", "example": "Sentence illustrating it" }}
  ],
  "examples": [
    {{ "sentence": "...", "translation": "...", "highlight": "the part that demonstrates the concept" }}
  ],
  "common_errors": [
    {{ "wrong": "...", "right": "...", "why": "Why learners get this wrong" }}
  ],
  "related_concepts": ["..."]
}}

Rules:
- "core_rules" and at least one "examples" entry should almost always be present.
- All other fields — "nuances", "common_errors", "related_concepts" — should be null if you are not confident in the content. Do not invent entries to fill them.
- Never fabricate examples, rules, or errors. If a concept is simple, a short card is correct.
- Write for a learner, not a linguist. Avoid technical jargon unless you define it immediately.
- Examples should feel natural and varied, not clones of the trigger phrase.
- "highlight" should pinpoint the exact word or clause that demonstrates the concept, not summarize the whole sentence.

Concept: {item.concept_name}
Trigger phrase: {item.examples or item.description or "(none provided)"}
Target language: {lang.name}
Learner level: {user_level}"""

    response = tracked_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

    try:
        card = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502, detail="AI returned malformed JSON — please retry"
        )

    item.detail_card = json.dumps(card)
    db.commit()
    return card


# ── Flashcard practice ────────────────────────────────────────────


class FlashcardResult(BaseModel):
    correct: bool


@router.post("/api/flashcard-result/{vocab_id}")
async def submit_flashcard_result(
    vocab_id: int,
    body: FlashcardResult,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a flashcard result (correct/wrong) and update fluency scores."""
    item = (
        db.query(Vocabulary)
        .join(Language)
        .filter(Vocabulary.id == vocab_id, Language.user_id == user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Vocabulary item not found")

    item.times_practiced += 1
    if body.correct:
        item.times_correct += 1
    item.last_practiced_at = datetime.utcnow()

    if item.times_practiced > 0:
        success_rate = item.times_correct / item.times_practiced
        if success_rate >= 0.8 and item.times_practiced >= 3:
            item.fluency_level = "high"
        elif success_rate >= 0.5 and item.times_practiced >= 2:
            item.fluency_level = "medium"
        else:
            item.fluency_level = "low"

    db.commit()
    db.refresh(item)

    return {
        "id": item.id,
        "target_word": item.target_word,
        "fluency_level": item.fluency_level,
        "times_practiced": item.times_practiced,
        "times_correct": item.times_correct,
    }
