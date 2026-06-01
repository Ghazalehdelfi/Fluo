"""Grammar practice session routes."""

import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import User, Language, Grammar, SessionLocal
from auth import get_current_user
from cost_tracker import TrackedOpenAI, check_sufficient_credits
from dependencies import get_db, get_api_key, get_native_language, get_user_level
from session_store import grammar_practice_sessions
from agents.grammar_practice_agent import GrammarPracticeAgent
from agents.logging_utils import get_logger, log_api_call as _log_api_call

logger = get_logger(__name__)
router = APIRouter()


def _log(method: str, endpoint: str, details: str = ""):
    _log_api_call(logger, method, endpoint, details)


class GrammarPracticeAnswerBody(BaseModel):
    question_index: int
    user_answer: str


@router.post("/api/grammar/{grammar_id}/start-practice")
async def start_grammar_practice(
    grammar_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate 10 grammar practice exercises and start a session."""
    _log("POST", f"/api/grammar/{grammar_id}/start-practice")

    item = (
        db.query(Grammar)
        .join(Language)
        .filter(Grammar.id == grammar_id, Language.user_id == user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Grammar concept not found")

    if not check_sufficient_credits(user, min_credits=1):
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please purchase more credits to continue.",
        )

    import json

    api_key = get_api_key()
    native_lang = get_native_language(db, user.id)
    user_level = get_user_level(db, user.id)
    lang = item.language

    if item.detail_card:
        try:
            grammar_card = json.loads(item.detail_card)
        except json.JSONDecodeError:
            grammar_card = {
                "concept": item.concept_name,
                "tagline": item.description or "",
                "examples": item.examples or "",
            }
    else:
        grammar_card = {
            "concept": item.concept_name,
            "tagline": item.description or "",
            "examples": item.examples or "",
        }

    session_id = str(uuid.uuid4())
    tracked_client = TrackedOpenAI(
        api_key, user_id=user.id, session_id=session_id, db_factory=SessionLocal
    )

    agent = GrammarPracticeAgent(
        client=tracked_client,
        target_language=lang.name,
        native_language=native_lang,
        level=user_level,
        fluency_level=item.fluency_level or "low",
    )

    questions = agent.generate_questions(grammar_card)

    grammar_practice_sessions[(user.id, session_id)] = {
        "grammar_id": grammar_id,
        "language_name": lang.name,
        "questions": questions,
        "answers": {},
        "correct_count": 0,
    }

    return {
        "session_id": session_id,
        "grammar_concept": item.concept_name,
        "total_questions": len(questions),
        "questions": questions,
    }


@router.post("/api/grammar-practice/{session_id}/submit-answer")
async def submit_grammar_practice_answer(
    session_id: str,
    body: GrammarPracticeAnswerBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evaluate a single answer in a grammar practice session."""
    _log("POST", f"/api/grammar-practice/{session_id}/submit-answer")

    session = grammar_practice_sessions.get((user.id, session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Grammar practice session not found")

    questions = session["questions"]
    if body.question_index < 0 or body.question_index >= len(questions):
        raise HTTPException(status_code=422, detail="Invalid question_index")

    question = questions[body.question_index]

    api_key = get_api_key()
    lang_name = session["language_name"]

    tracked_client = TrackedOpenAI(
        api_key, user_id=user.id, session_id=session_id, db_factory=SessionLocal
    )

    agent = GrammarPracticeAgent(client=tracked_client, target_language=lang_name)
    result = agent.evaluate_answer(question, body.user_answer)

    # Only count the first submission per question
    if body.question_index not in session["answers"]:
        session["answers"][body.question_index] = result["is_correct"]
        if result["is_correct"]:
            session["correct_count"] += 1

    return {
        "is_correct": result["is_correct"],
        "feedback": result["feedback"],
        "correct_answer": question["correct_answer"],
        "highlighted_segments": question.get("highlighted_segments", []),
        "explanation": question.get("explanation", ""),
    }


@router.post("/api/grammar-practice/{session_id}/end")
async def end_grammar_practice(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """End a grammar practice session, update fluency, and flush costs."""
    _log("POST", f"/api/grammar-practice/{session_id}/end")

    session = grammar_practice_sessions.get((user.id, session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Grammar practice session not found")

    correct_count = session["correct_count"]
    total = len(session["questions"])
    score = correct_count / total if total > 0 else 0

    item = (
        db.query(Grammar)
        .join(Language)
        .filter(Grammar.id == session["grammar_id"], Language.user_id == user.id)
        .first()
    )

    if item:
        item.times_practiced += 1
        if score >= 0.7:
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
        new_fluency = item.fluency_level
    else:
        new_fluency = None

    del grammar_practice_sessions[(user.id, session_id)]

    return {
        "correct_count": correct_count,
        "total_questions": total,
        "score": round(score, 2),
        "fluency_level": new_fluency,
    }
