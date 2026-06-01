"""Placement test routes: /api/placement-test/*."""

import json
import uuid
import logging
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import User, Language, Settings, Vocabulary, Grammar, SessionLocal
from auth import get_current_user
from cost_tracker import TrackedOpenAI, check_sufficient_credits
from dependencies import get_db, get_api_key, get_native_language
from session_store import active_sessions
from agents.placement_agent import (
    PlacementTestAgent,
    CEFR_LEVELS,
    QUESTIONS_PER_LEVEL,
    ADVANCE_THRESHOLD,
    LEVEL_DESCRIPTIONS,
)
from grammar_utils import (
    GRAMMAR_SIMILARITY_HIGH,
    cosine_similarity,
    embed_text,
    grammar_embed_text,
    find_most_similar_grammar,
)
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
    }

    logger.info(
        f"{Colors.GREEN}🎯 PLACEMENT TEST started for {lang.name} "
        f"(session {session_id[:8]}...){Colors.END}"
    )

    return {
        "session_id": session_id,
        "question": {
            "question": first_question["question"],
            "type": first_question["type"],
            "options": first_question.get("options"),
            "hint": first_question.get("hint", ""),
            "level": first_question["level"],
        },
        "question_number": 1,
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
            determined = agent.determine_level(session["results"])
            session["determined_level"] = determined

            lang_code = session["language_name"].lower()
            setting_key = f"{lang_code}_level"
            existing = (
                db.query(Settings)
                .filter(Settings.user_id == user.id, Settings.key == setting_key)
                .first()
            )
            if existing:
                existing.value = determined
            else:
                db.add(Settings(user_id=user.id, key=setting_key, value=determined))
            db.commit()

            logger.info(
                f"{Colors.GREEN}✅ PLACEMENT TEST complete: {determined} "
                f"({LEVEL_DESCRIPTIONS[determined]}){Colors.END}"
            )

            return {
                "correct": is_correct,
                "explanation": evaluation.get("explanation", ""),
                "completed": True,
                "determined_level": determined,
                "level_name": LEVEL_DESCRIPTIONS[determined],
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
        "question": {
            "question": next_question["question"],
            "type": next_question["type"],
            "options": next_question.get("options"),
            "hint": next_question.get("hint", ""),
            "level": next_question["level"],
        },
        "question_number": total_asked + 1,
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
    determined = session.get("determined_level")
    if not determined:
        raise HTTPException(status_code=400, detail="Test not yet completed")

    agent: PlacementTestAgent = session["agent"]

    logger.info(
        f"{Colors.CYAN}📚 Generating starter content at {determined} for "
        f"{session['language_name']}...{Colors.END}"
    )

    content = agent.generate_starter_content(determined)
    session["generated_content"] = content

    return {
        "level": determined,
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
    lang_id = session["language_id"]
    api_key = get_api_key()

    # Deduplicate vocabulary
    seen_vocab = set()
    vocabulary = []
    for v in body.vocabulary:
        key = v.get("target_word", "").lower()
        if key and key not in seen_vocab:
            seen_vocab.add(key)
            vocabulary.append(v)

    # Deduplicate grammar
    seen_grammar = set()
    grammar = []
    for g in body.grammar:
        key = g.get("concept_name", "").lower()
        if key and key not in seen_grammar:
            seen_grammar.add(key)
            grammar.append(g)

    # Save vocabulary
    added_vocab = 0
    for vocab in vocabulary:
        existing = (
            db.query(Vocabulary)
            .filter(
                Vocabulary.language_id == lang_id,
                Vocabulary.target_word.ilike(vocab.get("target_word", "")),
            )
            .first()
        )
        if not existing and vocab.get("target_word"):
            db.add(
                Vocabulary(
                    language_id=lang_id,
                    target_word=vocab["target_word"],
                    native_translation=vocab.get("native_translation", ""),
                    example_sentence=vocab.get("example_sentence", ""),
                    fluency_level="low",
                )
            )
            added_vocab += 1

    # Save grammar with semantic deduplication
    added_grammar = 0
    all_existing_grammar = (
        db.query(Grammar).filter(Grammar.language_id == lang_id).all()
    )
    accepted_in_batch: list = []  # (concept_name_lower, embedding_vec)

    for gram in grammar:
        if not gram.get("concept_name"):
            continue

        existing_exact = (
            db.query(Grammar)
            .filter(
                Grammar.language_id == lang_id,
                Grammar.concept_name.ilike(gram["concept_name"]),
            )
            .first()
        )
        if existing_exact:
            continue

        concept_lower = gram["concept_name"].lower()
        if any(concept_lower == name for name, _ in accepted_in_batch):
            continue

        candidate_text = grammar_embed_text(
            gram["concept_name"], gram.get("description", "")
        )
        candidate_vec = embed_text(api_key, candidate_text)

        most_similar, similarity = find_most_similar_grammar(
            candidate_vec, all_existing_grammar, api_key, db
        )
        if similarity >= GRAMMAR_SIMILARITY_HIGH:
            continue

        batch_best = max(
            (cosine_similarity(candidate_vec, vec) for _, vec in accepted_in_batch),
            default=0.0,
        )
        if batch_best >= GRAMMAR_SIMILARITY_HIGH:
            continue

        accepted_in_batch.append((concept_lower, candidate_vec))
        db.add(
            Grammar(
                language_id=lang_id,
                concept_name=gram["concept_name"],
                description=gram.get("description", ""),
                examples=gram.get("examples", ""),
                fluency_level="low",
                embedding=json.dumps(candidate_vec),
            )
        )
        added_grammar += 1

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
