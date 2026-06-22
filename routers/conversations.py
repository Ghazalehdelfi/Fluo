"""Conversation routes: topics, lesson start, scenario start, turn handling, end."""

import json
import uuid
import logging
from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    File,
    Form,
    BackgroundTasks,
)
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import (
    User,
    Language,
    Vocabulary,
    Grammar,
    Conversation,
    ConversationTopic,
    SessionLocal,
)
from auth import get_current_user
from cost_tracker import TrackedOpenAI, check_sufficient_credits
from dependencies import (
    get_db,
    get_api_key,
    get_native_language,
    get_user_level,
    get_elevenlabs_client,
)
import time
from session_store import active_sessions, SESSION_TTL_SECONDS
from tasks import rebuild_topics
from agents.dialogue_agent import DialogueAgent
from agents.analysis_agent import AnalysisAgent
from agents.logging_utils import Colors, get_logger, log_api_call as _log_api_call
from rate_limiter import user_limiter

logger = get_logger(__name__)
router = APIRouter()


def _log(method: str, endpoint: str, details: str = ""):
    _log_api_call(logger, method, endpoint, details)


# ── Topics ────────────────────────────────────────────────────────


@router.get("/api/topics/{language_id}")
async def get_conversation_topics(
    language_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return pre-computed conversation topics grouped by cluster."""
    _log("GET", f"/api/topics/{language_id}")

    lang = (
        db.query(Language)
        .filter(Language.id == language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    topics = (
        db.query(ConversationTopic)
        .filter(
            ConversationTopic.language_id == language_id,
            ConversationTopic.is_active == True,
        )
        .order_by(ConversationTopic.cluster_id, ConversationTopic.id)
        .all()
    )

    clusters: dict = {}
    for t in topics:
        cid = t.cluster_id
        if cid not in clusters:
            clusters[cid] = {"cluster_id": cid, "theme": t.theme, "topics": []}

        vocab_ids = json.loads(t.vocab_ids)
        vocab_items = db.query(Vocabulary).filter(Vocabulary.id.in_(vocab_ids)).all()

        clusters[cid]["topics"].append(
            {
                "id": t.id,
                "topic": t.topic,
                "vocab": [
                    {
                        "id": v.id,
                        "target_word": v.target_word,
                        "native_translation": v.native_translation,
                        "fluency_level": v.fluency_level,
                    }
                    for v in vocab_items
                ],
            }
        )

    return list(clusters.values())


@router.post("/api/topics/rebuild/{language_id}")
async def rebuild_conversation_topics(
    language_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger a topic re-clustering for a language."""
    lang = (
        db.query(Language)
        .filter(Language.id == language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    background_tasks.add_task(rebuild_topics, language_id, lang.name)
    return {"message": f"Topic clustering queued for {lang.name}"}


# ── Lesson start ──────────────────────────────────────────────────


@router.post("/api/start-lesson/{language_id}")
@user_limiter.limit("10/minute")
async def start_lesson(
    request: Request,
    language_id: int,
    topic_id: Optional[int] = None,
    num_vocab: int = 5,
    num_grammar: int = 1,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a new lesson and initialise a conversation session."""
    if not check_sufficient_credits(user, min_credits=1):
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please purchase more credits to continue.",
        )

    lang = (
        db.query(Language)
        .filter(Language.id == language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    logger.info(f"\n{Colors.GREEN}🎓 STARTING NEW LESSON{Colors.END}")
    logger.info(f"   Language: {Colors.BOLD}{lang.name}{Colors.END}")

    api_key = get_api_key()
    native_lang = get_native_language(db, user.id)
    target_lang = lang.name
    level = get_user_level(db, user.id)

    _log(
        "POST",
        f"/api/start-lesson/{language_id}",
        f"topic_id={topic_id}, vocab={num_vocab}, grammar={num_grammar}, level={level}",
    )

    session_id = str(uuid.uuid4())
    tracked_client = TrackedOpenAI(
        api_key, user_id=user.id, session_id=session_id, db_factory=SessionLocal
    )

    vocab_count = (
        db.query(Vocabulary).filter(Vocabulary.language_id == language_id).count()
    )
    grammar_count = db.query(Grammar).filter(Grammar.language_id == language_id).count()

    if vocab_count < 1:
        raise HTTPException(
            status_code=400,
            detail=f"Please upload some {lang.name} notes first to add vocabulary",
        )

    num_vocab = min(num_vocab, vocab_count)
    num_grammar = min(num_grammar, grammar_count)

    dialogue = DialogueAgent(
        tracked_client,
        target_lang,
        native_lang,
        elevenlabs_client=get_elevenlabs_client(),
    )
    all_known_items = dialogue.get_all_known_items(db, language_id)

    if topic_id is not None:
        logger.info(
            f"\n{Colors.YELLOW}📋 LESSON PLANNER: Using pre-computed topic id={topic_id}{Colors.END}"
        )
        db_topic = (
            db.query(ConversationTopic)
            .filter(
                ConversationTopic.id == topic_id,
                ConversationTopic.language_id == language_id,
                ConversationTopic.is_active == True,
            )
            .first()
        )
        if not db_topic:
            raise HTTPException(status_code=404, detail="Conversation topic not found")

        vocab_ids = json.loads(db_topic.vocab_ids)
        vocab_objs = db.query(Vocabulary).filter(Vocabulary.id.in_(vocab_ids)).all()
        vocab_list = [
            {
                "id": v.id,
                "target_word": v.target_word,
                "native_translation": v.native_translation,
                "example_sentence": v.example_sentence,
                "fluency_level": v.fluency_level,
            }
            for v in vocab_objs
        ]

        selected_items = dialogue.select_items_for_practice(
            db, 0, num_grammar, language_id
        )
        selected_items["vocabulary"] = vocab_list

        lesson_plan = {
            "theme": f"{db_topic.theme} — {db_topic.topic}",
            "conversation_goals": [
                f"Practice {db_topic.theme} vocabulary",
                f"Discuss: {db_topic.topic}",
                "Use the target words naturally in context",
            ],
            "suggested_topics": [db_topic.topic],
            "target_vocab_usage": {
                v["target_word"]: f"Use naturally in the context of '{db_topic.topic}'"
                for v in vocab_list
            },
            "target_grammar_usage": {},
            "difficulty_level": level,
            "grammar_allowed": [],
            "grammar_forbidden": [],
            "selected_items": selected_items,
        }
    else:
        logger.info(f"\n{Colors.YELLOW}📋 Selecting items on the fly...{Colors.END}")
        selected_items = dialogue.select_items_for_practice(
            db, num_vocab, num_grammar, language_id
        )
        lesson_plan = None

    theme_hint = lesson_plan["theme"] if lesson_plan is not None else None
    opening_message = dialogue.initialize_conversation(
        selected_items, all_known_items, level, theme_hint=theme_hint
    )
    lesson_plan = dialogue.lesson_plan

    logger.info(f"\n{Colors.BLUE}🔊 Generating TTS for opening message...{Colors.END}")
    audio_bytes = dialogue.text_to_speech(opening_message)
    opening_translation = dialogue.translate_to_native(opening_message)

    active_sessions[(user.id, session_id)] = {
        "dialogue": dialogue,
        "lesson_plan": lesson_plan,
        "target_language": target_lang,
        "native_language": native_lang,
        "language_id": language_id,
        "all_known_items": all_known_items,
        "tracked_client": tracked_client,
        "user_id": user.id,
        "_expires_at": time.time() + SESSION_TTL_SECONDS,
    }

    logger.info(f"\n{Colors.GREEN}✅ Session created: {session_id[:8]}...{Colors.END}")

    return {
        "session_id": session_id,
        "lesson_plan": lesson_plan,
        "opening_message": opening_message,
        "opening_translation": opening_translation,
        "audio": audio_bytes.hex(),
        "vocab_info": "Conversations are generated using at least 70% of vocabulary from your personal database.",
    }


# ── Scenario start ────────────────────────────────────────────────


class ScenarioRequest(BaseModel):
    scenario: str


@router.post("/api/start-scenario/{language_id}")
@user_limiter.limit("10/minute")
async def start_scenario(
    request: Request,
    language_id: int,
    body: ScenarioRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a free-form scenario conversation (no lesson plan)."""
    _log("POST", f"/api/start-scenario/{language_id}", f"scenario={body.scenario[:60]}")

    if not check_sufficient_credits(user, min_credits=1):
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please purchase more credits to continue.",
        )

    lang = (
        db.query(Language)
        .filter(Language.id == language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    logger.info(f"\n{Colors.GREEN}🎭 STARTING SCENARIO{Colors.END}")
    logger.info(f"   Language: {Colors.BOLD}{lang.name}{Colors.END}")

    api_key = get_api_key()
    native_lang = get_native_language(db, user.id)
    target_lang = lang.name
    level = get_user_level(db, user.id)

    session_id = str(uuid.uuid4())
    tracked_client = TrackedOpenAI(
        api_key, user_id=user.id, session_id=session_id, db_factory=SessionLocal
    )

    dialogue = DialogueAgent(
        tracked_client,
        target_lang,
        native_lang,
        elevenlabs_client=get_elevenlabs_client(),
    )
    all_known_items = dialogue.get_all_known_items(db, language_id)
    opening_message = dialogue.initialize_scenario(
        body.scenario, all_known_items, level
    )

    audio_bytes = dialogue.text_to_speech(opening_message)
    opening_translation = dialogue.translate_to_native(opening_message)

    active_sessions[(user.id, session_id)] = {
        "dialogue": dialogue,
        "lesson_plan": dialogue.lesson_plan,
        "target_language": target_lang,
        "native_language": native_lang,
        "language_id": language_id,
        "all_known_items": all_known_items,
        "tracked_client": tracked_client,
        "user_id": user.id,
        "_expires_at": time.time() + SESSION_TTL_SECONDS,
    }

    logger.info(
        f"\n{Colors.GREEN}✅ Scenario session created: {session_id[:8]}...{Colors.END}"
    )

    return {
        "session_id": session_id,
        "scenario": body.scenario,
        "opening_message": opening_message,
        "opening_translation": opening_translation,
        "audio": audio_bytes.hex(),
        "vocab_info": "Conversations are generated using at least 70% of vocabulary from your personal database.",
    }


# ── Conversation turns ────────────────────────────────────────────


@router.post("/api/conversation/{session_id}/respond")
@user_limiter.limit("60/minute")
async def respond_to_conversation(
    request: Request,
    session_id: str,
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
):
    """Send a response in the conversation (audio or text)."""
    _log(
        "POST",
        f"/api/conversation/{session_id[:8]}../respond",
        f"input={'audio' if audio else 'text'}",
    )

    session_key = (user.id, session_id)
    if session_key not in active_sessions:
        raise HTTPException(
            status_code=404,
            detail="Session expired or not found. Please start a new practice session.",
        )

    session = active_sessions[session_key]
    dialogue: DialogueAgent = session["dialogue"]

    if audio:
        logger.info(f"{Colors.CYAN}🎤 Processing audio input...{Colors.END}")
        audio_bytes = await audio.read()
        user_message = dialogue.speech_to_text(
            audio_bytes, audio.filename or "audio.webm"
        )
    elif text:
        logger.info(f"{Colors.CYAN}⌨️  Processing text input...{Colors.END}")
        user_message = text
    else:
        raise HTTPException(status_code=400, detail="No audio or text provided")

    response_text, is_ended = dialogue.generate_response(user_message)
    audio_bytes = dialogue.text_to_speech(response_text)
    translation = dialogue.translate_to_native(response_text)

    return {
        "user_message": user_message,
        "response": response_text,
        "translation": translation,
        "audio": audio_bytes.hex(),
        "is_ended": is_ended,
    }


@router.post("/api/conversation/{session_id}/end")
async def end_conversation(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """End the conversation and get analysis."""
    _log("POST", f"/api/conversation/{session_id[:8]}../end")

    session_key = (user.id, session_id)
    if session_key not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_key]
    dialogue: DialogueAgent = session["dialogue"]
    lesson_plan = session["lesson_plan"]
    target_lang = session.get("target_language", "Turkish")
    native_lang = session.get("native_language", "English")
    language_id = session.get("language_id")

    transcript = dialogue.get_transcript_text()
    tracked_client = session.get("tracked_client")
    analyzer = AnalysisAgent(tracked_client, target_lang, native_lang)
    practice_grammar = lesson_plan.get("selected_items", {}).get("grammar", [])
    analysis = analyzer.analyze_conversation(transcript, practice_grammar)
    overall_feedback = analyzer.get_overall_feedback(transcript)

    updates = analyzer.update_fluency_scores(db, analysis, language_id)

    total_cost = tracked_client.total_cost if tracked_client else 0.0

    conversation_id = analyzer.save_conversation(
        db,
        transcript,
        analysis,
        overall_feedback,
        user_id=user.id,
        language_id=language_id,
        total_cost_usd=total_cost,
    )

    del active_sessions[session_key]

    return {
        "conversation_id": conversation_id,
        "transcript": transcript,
        "analysis": {**analysis, "overall_feedback": overall_feedback},
        "fluency_updates": updates,
    }
