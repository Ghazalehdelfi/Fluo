"""Placement test routes: /api/placement-test/*."""

import time
import uuid
import logging
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import User, Language, SessionLocal
from auth import get_current_user
from cost_tracker import TrackedOpenAI, check_sufficient_credits
from dependencies import (
    get_db,
    get_api_key,
    get_native_language,
    get_user_level,
    set_user_level,
)
from session_store import active_sessions, SESSION_TTL_SECONDS
from agents.placement_agent import (
    PlacementTestAgent,
    CEFR_LEVELS,
    QUESTIONS_PER_LEVEL,
    ADVANCE_THRESHOLD,
    LEVEL_DESCRIPTIONS,
)
from agents.romanization_utils import is_persian, romanize_question_finglish
from content_utils import save_generated_content
from levels import ALL_LEVELS, level_label
from agents.logging_utils import Colors, get_logger, log_api_call as _log_api_call

logger = get_logger(__name__)
router = APIRouter()


def _log(method: str, endpoint: str, details: str = ""):
    _log_api_call(logger, method, endpoint, details)


class PlacementAnswerBody(BaseModel):
    answer: str


class PlacementSaveBody(BaseModel):
    vocabulary: List[Dict]
    grammar: List[Dict]


def _build_results_summary(results: List[Dict]) -> List[Dict]:
    """Build a per-level summary of placement test results."""
    level_data: Dict = {}
    for r in results:
        lvl = r["level"]
        if lvl not in level_data:
            level_data[lvl] = {"correct": 0, "total": 0}
        level_data[lvl]["total"] += 1
        if r["correct"]:
            level_data[lvl]["correct"] += 1
    return [
        {
            "level": lvl,
            "name": LEVEL_DESCRIPTIONS.get(lvl, lvl),
            "correct": d["correct"],
            "total": d["total"],
        }
        for lvl, d in level_data.items()
    ]


def _question_payload(session: Dict, question: Dict) -> Dict:
    """Build the question payload for the client, adding Finglish
    romanization for Persian questions."""
    payload = {
        "question": question["question"],
        "type": question["type"],
        "options": question.get("options"),
        "hint": question.get("hint", ""),
        "level": question["level"],
    }
    if is_persian(session["language_name"]):
        rom = romanize_question_finglish(
            session["tracked_client"],
            session["agent"].model,
            question["question"],
            question.get("options"),
        )
        payload["romanization"] = rom.get("question_finglish")
        payload["option_romanizations"] = rom.get("options_finglish")
    return payload


@router.post("/api/placement-test/start/{language_id}")
async def placement_test_start(
    language_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start an adaptive placement test for a language."""
    _log("POST", f"/api/placement-test/start/{language_id}")

    if not check_sufficient_credits(user, min_credits=1):
        raise HTTPException(status_code=402, detail="Insufficient credits.")

    lang = (
        db.query(Language)
        .filter(Language.id == language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    api_key = get_api_key()
    native_lang = get_native_language(db, user.id)

    tracked_client = TrackedOpenAI(
        api_key,
        user_id=user.id,
        session_id=str(uuid.uuid4()),
        db_factory=SessionLocal,
    )

    agent = PlacementTestAgent(tracked_client, lang.name, native_lang)
    first_question = agent.generate_question("A1", [])

    session_id = str(uuid.uuid4())
    active_sessions[(user.id, f"placement_{session_id}")] = {
        "agent": agent,
        "tracked_client": tracked_client,
        "language_id": language_id,
        "language_name": lang.name,
        "level_index": 0,
        "questions_at_level": 1,
        "correct_at_level": 0,
        "questions": [first_question],
        "results": [],
        "determined_level": None,
        "generated_content": None,
        "_expires_at": time.time() + SESSION_TTL_SECONDS,
    }

    logger.info(
        f"{Colors.GREEN}🎯 PLACEMENT TEST started for {lang.name} "
        f"(session {session_id[:8]}...){Colors.END}"
    )

    return {
        "session_id": session_id,
        "question": _question_payload(
            active_sessions[(user.id, f"placement_{session_id}")], first_question
        ),
        "question_number": 1,
        "level_index": 0,
        "questions_at_level": 1,
        "questions_per_level": QUESTIONS_PER_LEVEL,
        "total_levels": len(CEFR_LEVELS),
    }


@router.post("/api/placement-test/{session_id}/answer")
async def placement_test_answer(
    session_id: str,
    body: PlacementAnswerBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit an answer; get evaluation + next question or final results."""
    session_key = (user.id, f"placement_{session_id}")
    if session_key not in active_sessions:
        raise HTTPException(status_code=404, detail="Placement test session not found")

    session = active_sessions[session_key]
    agent: PlacementTestAgent = session["agent"]

    current_question = session["questions"][-1]
    evaluation = agent.evaluate_answer(current_question, body.answer)

    is_correct = evaluation.get("correct", False)
    session["results"].append(
        {
            "level": current_question["level"],
            "question": current_question["question"],
            "user_answer": body.answer,
            "correct_answer": current_question["correct_answer"],
            "correct": is_correct,
            "explanation": evaluation.get("explanation", ""),
        }
    )

    if is_correct:
        session["correct_at_level"] += 1

    level_index = session["level_index"]
    questions_at_level = session["questions_at_level"]

    if questions_at_level >= QUESTIONS_PER_LEVEL:
        accuracy = session["correct_at_level"] / questions_at_level
        if accuracy >= ADVANCE_THRESHOLD and level_index < len(CEFR_LEVELS) - 1:
            session["level_index"] = level_index + 1
            session["questions_at_level"] = 0
            session["correct_at_level"] = 0
        else:
            suggested = agent.suggest_full_level(session["results"])
            determined = suggested.split("-")[0]
            session["determined_level"] = suggested

            lang = db.query(Language).filter(Language.id == session["language_id"]).first()
            set_user_level(db, user.id, lang, suggested)
            db.commit()

            logger.info(
                f"{Colors.GREEN}✅ PLACEMENT TEST complete: {suggested} "
                f"({LEVEL_DESCRIPTIONS[determined]}){Colors.END}"
            )

            return {
                "correct": is_correct,
                "explanation": evaluation.get("explanation", ""),
                "completed": True,
                "determined_level": determined,
                "suggested_level": suggested,
                "suggested_level_label": level_label(suggested),
                "level_name": LEVEL_DESCRIPTIONS[determined],
                "available_levels": ALL_LEVELS,
                "results_summary": _build_results_summary(session["results"]),
            }

    next_level = CEFR_LEVELS[session["level_index"]]
    next_question = agent.generate_question(next_level, session["questions"])
    session["questions"].append(next_question)
    session["questions_at_level"] += 1

    total_asked = len(session["results"])

    return {
        "correct": is_correct,
        "explanation": evaluation.get("explanation", ""),
        "completed": False,
        "question": _question_payload(session, next_question),
        "question_number": total_asked + 1,
        "level_index": session["level_index"],
        "questions_at_level": session["questions_at_level"],
        "questions_per_level": QUESTIONS_PER_LEVEL,
        "total_levels": len(CEFR_LEVELS),
    }


@router.post("/api/placement-test/{session_id}/generate-content")
async def placement_test_generate_content(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate starter vocabulary + grammar based on determined level."""
    session_key = (user.id, f"placement_{session_id}")
    if session_key not in active_sessions:
        raise HTTPException(status_code=404, detail="Placement test session not found")

    session = active_sessions[session_key]
    if not session.get("determined_level"):
        raise HTTPException(status_code=400, detail="Test not yet completed")

    # Use the language's current level — the user may have adjusted the
    # suggestion on the results screen.
    level = get_user_level(db, user.id, session["language_id"])
    agent: PlacementTestAgent = session["agent"]

    logger.info(
        f"{Colors.CYAN}📚 Generating starter content at {level} for "
        f"{session['language_name']}...{Colors.END}"
    )

    content = agent.generate_starter_content(level)
    session["generated_content"] = content

    return {
        "level": level,
        "level_label": level_label(level),
        "vocabulary": content["vocabulary"],
        "grammar": content["grammar"],
        "vocabulary_count": len(content["vocabulary"]),
        "grammar_count": len(content["grammar"]),
    }


@router.post("/api/placement-test/{session_id}/save-content")
async def placement_test_save_content(
    session_id: str,
    body: PlacementSaveBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save user-approved starter content to the database."""
    session_key = (user.id, f"placement_{session_id}")
    if session_key not in active_sessions:
        raise HTTPException(status_code=404, detail="Placement test session not found")

    session = active_sessions[session_key]
    added_vocab, added_grammar = save_generated_content(
        db, get_api_key(), session["language_id"], body.vocabulary, body.grammar
    )
    db.commit()
    del active_sessions[session_key]

    logger.info(
        f"{Colors.GREEN}✅ Starter content saved: {added_vocab} vocab, "
        f"{added_grammar} grammar{Colors.END}"
    )

    return {
        "message": "Starter content saved successfully",
        "vocabulary_added": added_vocab,
        "grammar_added": added_grammar,
    }
