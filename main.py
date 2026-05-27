"""
Language Learning App - Main FastAPI Application
Supports multiple target languages with separate vocabulary/grammar per language.
Multi-user with JWT auth, per-user data isolation, cost tracking, and Stripe billing.
"""

import os
import json
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Optional
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException,
    Depends,
    Request,
    BackgroundTasks,
)
from typing import List
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from pydantic import BaseModel

# Load secrets: SSM Parameter Store in production, .env locally
from aws_config import load_secrets

load_secrets()

from database import (
    init_db,
    SessionLocal,
    Vocabulary,
    Grammar,
    Conversation,
    ConversationTopic,
    Settings,
    Language,
    User,
    UsageLog,
    Class,
    ClassStudent,
    Homework,
    HomeworkVocabRef,
    HomeworkGrammarRef,
    HomeworkGrammarQuestion,
    HomeworkTopic,
    HomeworkCompletion,
    SUPPORTED_LANGUAGES,
    NATIVE_LANGUAGES,
)
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_teacher,
    require_student,
)
from cost_tracker import TrackedOpenAI, check_sufficient_credits, SessionCostTracker
from agents.note_extractor import NoteExtractorAgent
from agents.lesson_planner import LessonPlannerAgent
from agents.cluster_topic_agent import ClusterTopicAgent
from agents.dialogue_agent import DialogueAgent
from agents.analysis_agent import AnalysisAgent
from agents.grammar_practice_agent import GrammarPracticeAgent
from agents.placement_agent import (
    PlacementTestAgent,
    CEFR_LEVELS,
    QUESTIONS_PER_LEVEL,
    ADVANCE_THRESHOLD,
    LEVEL_DESCRIPTIONS,
)
from agents.logging_utils import (
    Colors,
    setup_logging,
    get_logger,
    log_api_call as _log_api_call,
    print_startup_banner,
)

# ============== Logging Setup ==============
setup_logging()
logger = get_logger(__name__)


def log_api_call(method: str, endpoint: str, details: str = ""):
    """Log API calls with visual formatting."""
    _log_api_call(logger, method, endpoint, details)


load_dotenv()

app = FastAPI(title="Language Learning App")

# CORS middleware — restrict in production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stripe (optional — only active when keys are set)
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")

# Cached Stripe Price ID — resolved lazily by ensure_stripe_price()
_stripe_price_id: Optional[str] = os.getenv("STRIPE_PRICE_ID", "") or None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Initialize database
init_db()

# Store active dialogue sessions (in production, use Redis or similar)
active_sessions = {}

# Store active grammar practice sessions
grammar_practice_sessions = {}


def get_api_key():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    return api_key


def get_native_language(db: Session, user_id: int) -> str:
    """Get native language from per-user settings."""
    native = (
        db.query(Settings)
        .filter(Settings.user_id == user_id, Settings.key == "native_language")
        .first()
    )
    return native.value if native else "English"


def get_user_level(db: Session, user_id: int) -> str:
    """Get the user's default CEFR level from settings (default A1)."""
    setting = (
        db.query(Settings)
        .filter(Settings.user_id == user_id, Settings.key == "user_level")
        .first()
    )
    return setting.value if setting else "A1"


def _rebuild_topics(language_id: int, language_name: str) -> None:
    """
    Background task: re-cluster vocabulary embeddings and regenerate conversation topics.
    Opens its own DB session so it is safe to run after the request has returned.
    """
    db = SessionLocal()
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("ClusterTopicAgent: OPENAI_API_KEY not set — skipping")
            return
        from openai import OpenAI as _OpenAI

        client = _OpenAI(api_key=api_key)
        agent = ClusterTopicAgent(client)
        agent.run(language_id, db, language_name)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"ClusterTopicAgent failed (language_id={language_id}): {exc}")
    finally:
        db.close()


# ============== Grammar Similarity Helpers ==============

# Cosine-similarity thresholds for grammar deduplication
# score >= HIGH  → treat as duplicate, skip silently
# LOW <= score < HIGH → surface to user for merge-or-new decision
# score < LOW    → treat as a new concept, insert immediately
GRAMMAR_SIMILARITY_HIGH: float = 0.92
GRAMMAR_SIMILARITY_LOW: float = 0.60

_EMBEDDING_MODEL = "text-embedding-3-small"


def _cosine_similarity(a: list, b: list) -> float:
    """Return cosine similarity in [0, 1] between two equal-length float vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _embed_text(api_key: str, text: str) -> list:
    """Embed *text* with text-embedding-3-small and return the float vector."""
    from openai import OpenAI as _OpenAI

    client = _OpenAI(api_key=api_key)
    response = client.embeddings.create(model=_EMBEDDING_MODEL, input=text[:8192])
    return response.data[0].embedding


def _grammar_embed_text(item_concept: str, item_description: str) -> str:
    """Build the text to embed for a grammar item (concept + description)."""
    return f"{item_concept} {item_description}".strip()


def _ensure_grammar_embedding(item: "Grammar", api_key: str, db: "Session") -> list:
    """Return the embedding for an existing Grammar row, generating it if absent."""
    if item.embedding:
        try:
            return json.loads(item.embedding)
        except (json.JSONDecodeError, ValueError):
            pass
    vec = _embed_text(
        api_key, _grammar_embed_text(item.concept_name, item.description or "")
    )
    item.embedding = json.dumps(vec)
    db.add(item)
    db.flush()
    return vec


def _find_most_similar_grammar(
    candidate_vec: list,
    existing_items: list,
    api_key: str,
    db: "Session",
) -> "tuple[Grammar | None, float]":
    """Return (most_similar_Grammar, score) or (None, 0.0) if no items exist."""
    best_item = None
    best_score = 0.0
    for item in existing_items:
        vec = _ensure_grammar_embedding(item, api_key, db)
        score = _cosine_similarity(candidate_vec, vec)
        if score > best_score:
            best_score = score
            best_item = item
    return best_item, best_score


# ============== Auth Endpoints ==============


class AuthRegister(BaseModel):
    email: str
    password: str


class AuthLogin(BaseModel):
    email: str
    password: str


@app.post("/api/auth/register")
async def register(body: AuthRegister, db: Session = Depends(get_db)):
    """Create a new account and return a JWT for immediate access."""
    email = body.email.strip()
    if len(email) < 3:
        raise HTTPException(status_code=400, detail="Email/username is too short")
    if len(body.password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )

    exists = db.query(User).filter(User.email == email).first()
    if exists:
        raise HTTPException(status_code=409, detail="Account already exists")

    welcome_bonus = float(os.getenv("WELCOME_BONUS_CREDITS", "5.0"))
    user = User(
        email=email,
        hashed_password=hash_password(body.password),
        credits_balance=welcome_bonus,
        role="student",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email, user.role)
    return {
        "token": token,
        "email": user.email,
        "credits": user.credits_balance,
        "role": user.role,
    }


@app.post("/api/auth/login")
async def login(body: AuthLogin, db: Session = Depends(get_db)):
    """Login and receive a JWT."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user.id, user.email, user.role)
    return {
        "token": token,
        "email": user.email,
        "credits": user.credits_balance,
        "role": user.role,
    }


@app.get("/api/user/me")
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
    return {
        "id": user.id,
        "email": user.email,
        "credits": user.credits_balance,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "default_language_id": default_language_id,
    }


# ============== Language Management ==============


class LanguageCreate(BaseModel):
    name: str


class SettingsUpdate(BaseModel):
    native_language: str


@app.get("/api/languages")
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

    # Get languages user hasn't added yet
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


@app.post("/api/languages")
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

    # Check if already exists for this user
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


@app.delete("/api/languages/{language_id}")
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


@app.get("/api/settings")
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


@app.put("/api/settings/default-language")
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
            Settings(user_id=user.id, key="default_language_id", value=str(language_id))
        )
    db.commit()
    return {"message": "Default language updated", "default_language_id": language_id}


@app.post("/api/settings")
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
                user_id=user.id, key="native_language", value=settings.native_language
            )
        )

    db.commit()
    return {"message": "Settings updated", "native_language": settings.native_language}


@app.put("/api/settings/level")
async def set_user_level(
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set the user's default CEFR level."""
    level = body.get("level", "A1").upper()
    valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    if level not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level. Must be one of: {', '.join(valid_levels)}",
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


# ============== Note Upload & Extraction ==============


@app.post("/api/upload-notes")
async def upload_notes(
    language_id: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    text: Optional[str] = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """Upload notes (multiple images or text) and extract vocabulary and grammar for a specific language."""
    log_api_call("POST", "/api/upload-notes", f"language_id={language_id}")

    # Check credits before making API calls
    if not check_sufficient_credits(user, min_credits=0.01):
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please purchase more credits to continue.",
        )

    api_key = get_api_key()
    native_lang = get_native_language(db, user.id)

    # Create tracked client for cost tracking + immediate credit deduction
    session_id = str(uuid.uuid4())
    tracked_client = TrackedOpenAI(
        api_key, user_id=user.id, session_id=session_id, db_factory=SessionLocal
    )

    # Convert language_id to int
    try:
        lang_id = int(language_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid language_id")

    # Get the target language (scoped to user)
    lang = (
        db.query(Language)
        .filter(Language.id == lang_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    logger.info(
        f"{Colors.GREEN}📝 NOTE EXTRACTOR: Processing upload for {lang.name}{Colors.END}"
    )
    logger.info(f"   Native language: {native_lang}")

    extractor = NoteExtractorAgent(tracked_client, lang.name, native_lang)

    all_vocabulary = []
    all_grammar = []
    if files and len(files) > 0 and files[0].filename:
        # Handle multiple image uploads
        logger.info(f"   Processing {len(files)} image(s)...")
        for i, file in enumerate(files):
            logger.info(f"      Image {i+1}: {file.filename} ({file.content_type})")
            contents = await file.read()
            mime_type = file.content_type or "image/jpeg"
            vocabulary, grammar = extractor.extract_from_image(contents, mime_type)
            all_vocabulary.extend(vocabulary)
            all_grammar.extend(grammar)
    elif text:
        # Handle text input
        logger.info(f"   Processing text input ({len(text)} chars)...")
        all_vocabulary, all_grammar = extractor.extract_from_text(text)
    else:
        raise HTTPException(status_code=400, detail="No files or text provided")

    # Deduplicate vocabulary by target_word (case-insensitive)
    seen_vocab = set()
    vocabulary = []
    for v in all_vocabulary:
        key = v.get("target_word", "").lower()
        if key and key not in seen_vocab:
            seen_vocab.add(key)
            vocabulary.append(v)

    # Deduplicate grammar by concept_name (case-insensitive)
    seen_grammar = set()
    grammar = []
    for g in all_grammar:
        key = g.get("concept_name", "").lower()
        if key and key not in seen_grammar:
            seen_grammar.add(key)
            grammar.append(g)

    # Store extracted items in database
    added_vocab = []
    added_grammar = []
    grammar_pending = []  # items needing user merge-or-new decision

    for vocab in vocabulary:
        # Check if word already exists for this language
        existing = (
            db.query(Vocabulary)
            .filter(
                Vocabulary.language_id == lang_id,
                Vocabulary.target_word.ilike(vocab.get("target_word", "")),
            )
            .first()
        )

        if not existing and vocab.get("target_word"):
            new_vocab = Vocabulary(
                language_id=lang_id,
                target_word=vocab["target_word"],
                native_translation=vocab.get("native_translation", ""),
                example_sentence=vocab.get("example_sentence", ""),
                fluency_level="low",
            )
            db.add(new_vocab)
            added_vocab.append(vocab)

    for gram in grammar:
        if not gram.get("concept_name"):
            continue

        # ── Exact name match (case-insensitive) ─────────────────────────────
        existing_exact = (
            db.query(Grammar)
            .filter(
                Grammar.language_id == lang_id,
                Grammar.concept_name.ilike(gram["concept_name"]),
            )
            .first()
        )
        if existing_exact:
            continue  # already stored verbatim — nothing to do

        # ── Semantic similarity check against all cards for this language ────
        api_key = get_api_key()
        all_existing = db.query(Grammar).filter(Grammar.language_id == lang_id).all()
        candidate_text = _grammar_embed_text(
            gram["concept_name"], gram.get("description", "")
        )
        candidate_vec = _embed_text(api_key, candidate_text)

        most_similar, similarity = _find_most_similar_grammar(
            candidate_vec, all_existing, api_key, db
        )

        if similarity >= GRAMMAR_SIMILARITY_HIGH:
            # Near-duplicate — skip silently
            logger.info(
                f"   ⏭ Grammar '{gram['concept_name']}' skipped "
                f"(similarity={similarity:.2f} with '{most_similar.concept_name}')"
            )
            continue

        if similarity >= GRAMMAR_SIMILARITY_LOW and most_similar is not None:
            # Ambiguous — surface to user for resolution
            grammar_pending.append(
                {
                    "candidate": gram,
                    "similar_card": {
                        "id": most_similar.id,
                        "concept_name": most_similar.concept_name,
                        "description": most_similar.description,
                        "examples": most_similar.examples,
                        "has_detail_card": bool(most_similar.detail_card),
                    },
                    "similarity": round(similarity, 4),
                }
            )
            logger.info(
                f"   ❓ Grammar '{gram['concept_name']}' pending user decision "
                f"(similarity={similarity:.2f} with '{most_similar.concept_name}')"
            )
            continue

        # ── New concept — insert with embedding ─────────────────────────────
        new_grammar = Grammar(
            language_id=lang_id,
            concept_name=gram["concept_name"],
            description=gram.get("description", ""),
            examples=gram.get("examples", ""),
            fluency_level="low",
            embedding=json.dumps(candidate_vec),
        )
        db.add(new_grammar)
        added_grammar.append(gram)

    db.commit()

    logger.info(f"\n{Colors.GREEN}✅ Note extraction complete:{Colors.END}")
    logger.info(f"   Vocabulary: {len(vocabulary)} extracted, {len(added_vocab)} new")
    logger.info(f"   Grammar: {len(grammar)} extracted, {len(added_grammar)} new")

    if added_vocab:
        logger.info(f"   {Colors.CYAN}New vocabulary added:{Colors.END}")
        for v in added_vocab[:5]:
            logger.info(
                f"      • {v['target_word']} → {v.get('native_translation', '')}"
            )
        if len(added_vocab) > 5:
            logger.info(f"      ... and {len(added_vocab) - 5} more")

    # Re-cluster vocab and regenerate conversation topics in the background
    if added_vocab and background_tasks is not None:
        background_tasks.add_task(_rebuild_topics, lang_id, lang.name)
        logger.info(
            f"   {Colors.CYAN}⚙ Topic clustering queued as background task{Colors.END}"
        )

    return {
        "message": "Notes processed successfully",
        "language": lang.name,
        "vocabulary_extracted": len(vocabulary),
        "vocabulary_added": len(added_vocab),
        "grammar_extracted": len(grammar),
        "grammar_added": len(added_grammar),
        "grammar_pending": grammar_pending,
        "vocabulary": vocabulary,
        "grammar": grammar,
    }


# ============== Vocabulary & Grammar Management ==============


@app.get("/api/vocabulary/{language_id}")
async def get_vocabulary(
    language_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all vocabulary items for a specific language."""
    # Verify language belongs to user
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


@app.get("/api/grammar/{language_id}")
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


@app.delete("/api/vocabulary/{vocab_id}")
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


@app.delete("/api/grammar/{grammar_id}")
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


# ── Models for pending-grammar resolution ───────────────────────────────────


class GrammarCandidateModel(BaseModel):
    concept_name: str
    description: str = ""
    examples: str = ""


class GrammarResolvePendingModel(BaseModel):
    action: str  # "merge" | "create_new"
    candidate: GrammarCandidateModel
    existing_id: Optional[int] = None  # required when action == "merge"
    language_id: int


@app.post("/api/grammar/resolve-pending")
async def resolve_pending_grammar(
    body: GrammarResolvePendingModel,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve a pending grammar card that was held for user confirmation.

    action = "create_new" — insert the candidate as a brand-new card.
    action = "merge"      — merge the candidate into the existing card using the
                            LLM merge prompt, then update the stored card.
    """
    # Verify language ownership
    lang = (
        db.query(Language)
        .filter(Language.id == body.language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    api_key = get_api_key()

    if body.action == "create_new":
        # Embed and insert
        candidate_text = _grammar_embed_text(
            body.candidate.concept_name, body.candidate.description
        )
        vec = _embed_text(api_key, candidate_text)
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
            raise HTTPException(
                status_code=404, detail="Existing grammar card not found"
            )

        if not check_sufficient_credits(user, min_credits=0.01):
            raise HTTPException(
                status_code=402,
                detail="Insufficient credits. Please purchase more credits to continue.",
            )

        user_level = get_user_level(db, user.id)
        session_id = str(uuid.uuid4())
        tracked_client = TrackedOpenAI(
            api_key, user_id=user.id, session_id=session_id, db_factory=SessionLocal
        )

        # Build the existing card representation for the prompt
        if existing.detail_card:
            try:
                existing_card_json = existing.detail_card
            except Exception:
                existing_card_json = json.dumps(
                    {
                        "concept": existing.concept_name,
                        "tagline": existing.description or "",
                        "examples": existing.examples or "",
                    }
                )
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

        # Update the existing record
        if existing.detail_card:
            existing.detail_card = json.dumps(merged_card)
        else:
            # Persist any enrichment back to the basic fields as well
            existing.description = merged_card.get("tagline", existing.description)
            existing.examples = merged_card.get("examples", existing.examples)

        # Re-embed with potentially richer content (concept + new description)
        new_desc = (
            merged_card.get("tagline", existing.description)
            or existing.description
            or ""
        )
        new_text = _grammar_embed_text(existing.concept_name, new_desc)
        existing.embedding = json.dumps(_embed_text(api_key, new_text))

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


@app.post("/api/grammar/{grammar_id}/detail-card")
async def get_grammar_detail_card(
    grammar_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the detailed grammar study card for a concept.

    If a cached card already exists in the database it is returned immediately.
    Otherwise the card is generated via GPT-4o, persisted, and returned.
    """
    item = (
        db.query(Grammar)
        .join(Language)
        .filter(Grammar.id == grammar_id, Language.user_id == user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Grammar concept not found")

    # Return cached card if available
    if item.detail_card:
        try:
            return json.loads(item.detail_card)
        except json.JSONDecodeError:
            pass  # fall through to regenerate

    if not check_sufficient_credits(user, min_credits=0.01):
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
    # Strip markdown fences if the model includes them despite instructions
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


# ============== Flashcard Practice ==============


class FlashcardResult(BaseModel):
    correct: bool


@app.post("/api/flashcard-result/{vocab_id}")
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

    # Update fluency level using same logic as AnalysisAgent
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


# ============== Grammar Practice ==============


class GrammarPracticeAnswerBody(BaseModel):
    question_index: int
    user_answer: str


@app.post("/api/grammar/{grammar_id}/start-practice")
async def start_grammar_practice(
    grammar_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate 10 grammar practice exercises from a grammar card and start a session."""
    log_api_call("POST", f"/api/grammar/{grammar_id}/start-practice")

    item = (
        db.query(Grammar)
        .join(Language)
        .filter(Grammar.id == grammar_id, Language.user_id == user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Grammar concept not found")

    if not check_sufficient_credits(user, min_credits=0.01):
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please purchase more credits to continue.",
        )

    api_key = get_api_key()
    native_lang = get_native_language(db, user.id)
    user_level = get_user_level(db, user.id)
    lang = item.language

    # Ensure detail card exists; generate it if not
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

    cost_tracker = SessionCostTracker(user_id=user.id, session_id=session_id)

    agent = GrammarPracticeAgent(
        client=tracked_client,
        target_language=lang.name,
        native_language=native_lang,
        level=user_level,
        fluency_level=item.fluency_level or "low",
        cost_tracker=cost_tracker,
    )

    questions = agent.generate_questions(grammar_card)

    grammar_practice_sessions[(user.id, session_id)] = {
        "grammar_id": grammar_id,
        "language_name": lang.name,
        "questions": questions,
        "answers": {},
        "correct_count": 0,
        "cost_tracker": cost_tracker,
    }

    return {
        "session_id": session_id,
        "grammar_concept": item.concept_name,
        "total_questions": len(questions),
        "questions": questions,
    }


@app.post("/api/grammar-practice/{session_id}/submit-answer")
async def submit_grammar_practice_answer(
    session_id: str,
    body: GrammarPracticeAnswerBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evaluate a single answer in a grammar practice session."""
    log_api_call("POST", f"/api/grammar-practice/{session_id}/submit-answer")

    session = grammar_practice_sessions.get((user.id, session_id))
    if not session:
        raise HTTPException(
            status_code=404, detail="Grammar practice session not found"
        )

    questions = session["questions"]
    if body.question_index < 0 or body.question_index >= len(questions):
        raise HTTPException(status_code=422, detail="Invalid question_index")

    question = questions[body.question_index]

    api_key = get_api_key()
    lang_name = session["language_name"]

    tracked_client = TrackedOpenAI(
        api_key, user_id=user.id, session_id=session_id, db_factory=SessionLocal
    )

    agent = GrammarPracticeAgent(
        client=tracked_client,
        target_language=lang_name,
        cost_tracker=session["cost_tracker"],
    )

    result = agent.evaluate_answer(question, body.user_answer)

    # Track score (only count first submission per question)
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


@app.post("/api/grammar-practice/{session_id}/end")
async def end_grammar_practice(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """End a grammar practice session, update fluency, and flush costs."""
    log_api_call("POST", f"/api/grammar-practice/{session_id}/end")

    session = grammar_practice_sessions.get((user.id, session_id))
    if not session:
        raise HTTPException(
            status_code=404, detail="Grammar practice session not found"
        )

    correct_count = session["correct_count"]
    total = len(session["questions"])
    score = correct_count / total if total > 0 else 0

    # Update grammar card fluency
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

        # Recalculate fluency level (same logic as vocabulary flashcards)
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

    # Flush costs to DB
    try:
        session["cost_tracker"].flush_to_db(db)
    except Exception:
        pass

    del grammar_practice_sessions[(user.id, session_id)]

    return {
        "correct_count": correct_count,
        "total_questions": total,
        "score": round(score, 2),
        "fluency_level": new_fluency,
    }


# ============== Lesson Planning ==============


@app.get("/api/topics/{language_id}")
async def get_conversation_topics(
    language_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return pre-computed conversation topics for a language, grouped by cluster.

    Topics are generated in the background whenever new vocabulary is uploaded.
    Each topic includes the vocabulary words in that cluster so the frontend can
    display them before the user starts a conversation.
    """
    log_api_call("GET", f"/api/topics/{language_id}")

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

    # Group by cluster and hydrate vocab details
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


@app.post("/api/topics/rebuild/{language_id}")
async def rebuild_conversation_topics(
    language_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger a topic re-clustering for a language (e.g. after bulk import)."""
    lang = (
        db.query(Language)
        .filter(Language.id == language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    background_tasks.add_task(_rebuild_topics, language_id, lang.name)
    return {"message": f"Topic clustering queued for {lang.name}"}


@app.post("/api/start-lesson/{language_id}")
async def start_lesson(
    language_id: int,
    topic_id: Optional[int] = None,
    num_vocab: int = 5,
    num_grammar: int = 1,
    level: str = "A1",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a new lesson and initialize a conversation session.

    Args:
        language_id: The language to practice
        topic_id: Pre-computed ConversationTopic ID (preferred). When provided,
                  the lesson plan is built from the stored cluster data without
                  any on-the-fly LLM generation.
        num_vocab: (legacy) Number of vocab words when topic_id is not given
        num_grammar: Number of grammar concepts to sample (always weighted-random)
        level: CEFR level (A1, A2, B1, B2, C1, C2)
    """
    log_api_call(
        "POST",
        f"/api/start-lesson/{language_id}",
        f"topic_id={topic_id}, vocab={num_vocab}, grammar={num_grammar}, level={level}",
    )

    # Check credits
    if not check_sufficient_credits(user, min_credits=0.01):
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please purchase more credits to continue.",
        )

    # Get the language (scoped to user)
    lang = (
        db.query(Language)
        .filter(Language.id == language_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    # Validate level
    valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    if level.upper() not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level. Must be one of: {', '.join(valid_levels)}",
        )
    level = level.upper()

    logger.info(f"\n{Colors.GREEN}🎓 STARTING NEW LESSON{Colors.END}")
    logger.info(f"   Language: {Colors.BOLD}{lang.name}{Colors.END}")
    logger.info(f"   CEFR Level: {Colors.BOLD}{level}{Colors.END}")
    logger.info(f"   Vocabulary items: {num_vocab}")
    logger.info(f"   Grammar concepts: {num_grammar}")

    api_key = get_api_key()
    native_lang = get_native_language(db, user.id)
    target_lang = lang.name

    logger.info(f"   Native language: {native_lang}")

    # Create tracked OpenAI client for cost tracking + immediate credit deduction
    session_id = str(uuid.uuid4())
    tracked_client = TrackedOpenAI(
        api_key, user_id=user.id, session_id=session_id, db_factory=SessionLocal
    )

    # Check if there's enough content for this language
    vocab_count = (
        db.query(Vocabulary).filter(Vocabulary.language_id == language_id).count()
    )
    grammar_count = db.query(Grammar).filter(Grammar.language_id == language_id).count()

    logger.info(f"\n{Colors.CYAN}📊 Database Content:{Colors.END}")
    logger.info(f"   Available vocabulary: {vocab_count} words")
    logger.info(f"   Available grammar: {grammar_count} concepts")

    if vocab_count < 1:
        raise HTTPException(
            status_code=400,
            detail=f"Please upload some {lang.name} notes first to add vocabulary",
        )

    # Adjust numbers if not enough content
    num_vocab = min(num_vocab, vocab_count)
    num_grammar = min(num_grammar, grammar_count)

    planner = LessonPlannerAgent(tracked_client, target_lang, native_lang)
    all_known_items = planner.get_all_known_items(db, language_id)
    logger.info(
        f"   Total known vocabulary: {len(all_known_items.get('all_vocabulary', []))}"
    )
    logger.info(
        f"   Total known grammar: {len(all_known_items.get('all_grammar', []))}"
    )

    if topic_id is not None:
        # ── Pre-computed path: use stored cluster topic ──────────
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

        # Hydrate vocab from stored IDs
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

        # Sample grammar with the usual weighted-random approach
        selected_items = planner.select_items_for_practice(
            db, 0, num_grammar, language_id
        )
        selected_items["vocabulary"] = vocab_list

        # Build a synthetic lesson plan (no extra LLM calls needed)
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
        logger.info(
            f"\n{Colors.GREEN}✅ Lesson plan built from pre-computed topic:{Colors.END}"
        )
        logger.info(f"   Theme: {lesson_plan['theme']}")

    else:
        # ── On-the-fly path (legacy / fallback) ─────────────────
        logger.info(
            f"\n{Colors.YELLOW}📋 LESSON PLANNER: Creating lesson plan on the fly...{Colors.END}"
        )

        # Select items to practice (prioritizing low fluency)
        selected_items = planner.select_items_for_practice(
            db, num_vocab, num_grammar, language_id
        )
        logger.info(f"\n   Selected for practice:")
        for v in selected_items["vocabulary"]:
            logger.info(
                f"      📝 {v['target_word']} (fluency: {v.get('fluency_level', 'low')})"
            )
        for g in selected_items["grammar"]:
            logger.info(f"      📐 {g['concept_name']}")

        # Generate lesson plan with level awareness
        lesson_plan = planner.generate_lesson_plan(
            selected_items, all_known_items, level
        )
        logger.info(f"\n{Colors.GREEN}✅ Lesson plan generated:{Colors.END}")
        logger.info(f"   Theme: {lesson_plan.get('theme', 'N/A')}")

    # Initialize dialogue agent with full knowledge context
    logger.info(f"\n{Colors.CYAN}🎭 Initializing dialogue agent...{Colors.END}")
    dialogue = DialogueAgent(tracked_client, target_lang, native_lang)
    opening_message = dialogue.initialize_conversation(
        lesson_plan, all_known_items, level
    )

    # Generate audio for opening
    logger.info(f"\n{Colors.BLUE}🔊 Generating TTS for opening message...{Colors.END}")
    audio_bytes = dialogue.text_to_speech(opening_message)
    logger.info(f"   Audio size: {len(audio_bytes) / 1024:.1f} KB")

    # Generate translation for opening message
    opening_translation = dialogue.translate_to_native(opening_message)

    # Store session (keyed by user+session for isolation)
    active_sessions[(user.id, session_id)] = {
        "dialogue": dialogue,
        "lesson_plan": lesson_plan,
        "target_language": target_lang,
        "native_language": native_lang,
        "language_id": language_id,
        "all_known_items": all_known_items,  # Store for analysis
        "tracked_client": tracked_client,
        "user_id": user.id,
    }

    logger.info(f"\n{Colors.GREEN}✅ Session created: {session_id[:8]}...{Colors.END}")
    logger.info(f"   Active sessions: {len(active_sessions)}")

    return {
        "session_id": session_id,
        "lesson_plan": lesson_plan,
        "opening_message": opening_message,
        "opening_translation": opening_translation,
        "audio": audio_bytes.hex(),  # Send as hex string
    }


class ScenarioRequest(BaseModel):
    scenario: str
    level: str = "A1"


@app.post("/api/start-scenario/{language_id}")
async def start_scenario(
    language_id: int,
    body: ScenarioRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a free-form scenario conversation (no lesson plan)."""
    log_api_call(
        "POST",
        f"/api/start-scenario/{language_id}",
        f"scenario={body.scenario[:60]}, level={body.level}",
    )

    if not check_sufficient_credits(user, min_credits=0.01):
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

    valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    level = body.level.upper()
    if level not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level. Must be one of: {', '.join(valid_levels)}",
        )

    logger.info(f"\n{Colors.GREEN}🎭 STARTING SCENARIO{Colors.END}")
    logger.info(f"   Language: {Colors.BOLD}{lang.name}{Colors.END}")
    logger.info(f"   Level: {Colors.BOLD}{level}{Colors.END}")
    logger.info(f"   Scenario: {body.scenario[:100]}")

    api_key = get_api_key()
    native_lang = get_native_language(db, user.id)
    target_lang = lang.name

    session_id = str(uuid.uuid4())
    tracked_client = TrackedOpenAI(
        api_key, user_id=user.id, session_id=session_id, db_factory=SessionLocal
    )

    # Gather student knowledge for level control (optional, may have none)
    planner = LessonPlannerAgent(tracked_client, target_lang, native_lang)
    all_known_items = planner.get_all_known_items(db, language_id)

    dialogue = DialogueAgent(tracked_client, target_lang, native_lang)
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
    }


# ============== Conversation ==============


@app.post("/api/conversation/{session_id}/respond")
async def respond_to_conversation(
    session_id: str,
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
):
    """Send a response in the conversation (audio or text)."""
    log_api_call(
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

    # Get user's message
    if audio:
        logger.info(f"{Colors.CYAN}🎤 Processing audio input...{Colors.END}")
        audio_bytes = await audio.read()
        logger.info(f"   Audio size: {len(audio_bytes) / 1024:.1f} KB")
        user_message = dialogue.speech_to_text(
            audio_bytes, audio.filename or "audio.webm"
        )
    elif text:
        logger.info(f"{Colors.CYAN}⌨️  Processing text input...{Colors.END}")
        user_message = text
    else:
        raise HTTPException(status_code=400, detail="No audio or text provided")

    # Generate response
    response_text, is_ended = dialogue.generate_response(user_message)

    # Generate audio
    audio_bytes = dialogue.text_to_speech(response_text)

    # Generate translation for the tutor's response
    translation = dialogue.translate_to_native(response_text)

    logger.info(f"\n{Colors.GREEN}✅ Response generated:{Colors.END}")
    logger.info(f"   Conversation ended: {is_ended}")

    return {
        "user_message": user_message,
        "response": response_text,
        "translation": translation,
        "audio": audio_bytes.hex(),
        "is_ended": is_ended,
    }


@app.post("/api/conversation/{session_id}/end")
async def end_conversation(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """End the conversation and get analysis."""
    log_api_call("POST", f"/api/conversation/{session_id[:8]}../end")

    session_key = (user.id, session_id)
    if session_key not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_key]
    dialogue: DialogueAgent = session["dialogue"]
    lesson_plan = session["lesson_plan"]
    target_lang = session.get("target_language", "Turkish")
    native_lang = session.get("native_language", "English")
    language_id = session.get("language_id")
    all_known_items = session.get("all_known_items", {})

    # Get transcript
    transcript = dialogue.get_transcript_text()
    logger.info(f"\n{Colors.YELLOW}📝 Conversation transcript:{Colors.END}")
    for line in transcript.split("\n\n"):
        if line.strip():
            logger.info(f"   {line[:100]}{'...' if len(line) > 100 else ''}")

    # Analyze conversation — pass practiced grammar for targeted evaluation
    tracked_client = session.get("tracked_client")
    analyzer = AnalysisAgent(tracked_client, target_lang, native_lang)
    practice_grammar = lesson_plan.get("selected_items", {}).get("grammar", [])
    analysis = analyzer.analyze_conversation(transcript, practice_grammar)

    # Get overall feedback (separate LLM call)
    overall_feedback = analyzer.get_overall_feedback(transcript)

    logger.info(f"   {Colors.GREEN}✅ Analysis complete{Colors.END}")
    logger.info(f"   Correct words: {len(analysis.get('correct_words', []))}")
    logger.info(f"   Incorrect words: {len(analysis.get('incorrect_words', []))}")

    # Update fluency scores
    logger.info(f"\n{Colors.CYAN}📊 Updating fluency scores...{Colors.END}")
    updates = analyzer.update_fluency_scores(db, analysis, language_id)
    logger.info(f"   Vocabulary updated: {len(updates.get('vocabulary_updated', []))}")
    logger.info(f"   Vocabulary added: {len(updates.get('vocabulary_added', []))}")

    # Get total cost from tracked client (already deducted per-call)
    total_cost = 0.0
    if tracked_client:
        total_cost = tracked_client.total_cost

    # Save conversation
    conversation_id = analyzer.save_conversation(
        db,
        transcript,
        analysis,
        overall_feedback,
        user_id=user.id,
        language_id=language_id,
        total_cost_usd=total_cost,
    )
    logger.info(f"   Conversation saved with ID: {conversation_id}")

    # Clean up session
    del active_sessions[session_key]
    logger.info(
        f"\n{Colors.GREEN}✅ Session cleaned up. Active sessions: {len(active_sessions)}{Colors.END}"
    )

    return {
        "conversation_id": conversation_id,
        "transcript": transcript,
        "analysis": analysis,
        "fluency_updates": updates,
    }


# ============== History ==============


@app.get("/api/conversations")
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


@app.get("/api/stats/{language_id}")
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
        "low": db.query(Vocabulary)
        .filter(
            Vocabulary.language_id == language_id, Vocabulary.fluency_level == "low"
        )
        .count(),
        "medium": db.query(Vocabulary)
        .filter(
            Vocabulary.language_id == language_id, Vocabulary.fluency_level == "medium"
        )
        .count(),
        "high": db.query(Vocabulary)
        .filter(
            Vocabulary.language_id == language_id, Vocabulary.fluency_level == "high"
        )
        .count(),
    }

    grammar_by_fluency = {
        "low": db.query(Grammar)
        .filter(Grammar.language_id == language_id, Grammar.fluency_level == "low")
        .count(),
        "medium": db.query(Grammar)
        .filter(Grammar.language_id == language_id, Grammar.fluency_level == "medium")
        .count(),
        "high": db.query(Grammar)
        .filter(Grammar.language_id == language_id, Grammar.fluency_level == "high")
        .count(),
    }

    return {
        "language": lang.name,
        "total_vocabulary": vocab_count,
        "total_grammar": grammar_count,
        "total_conversations": conversation_count,
        "vocabulary_by_fluency": vocab_by_fluency,
        "grammar_by_fluency": grammar_by_fluency,
    }


@app.get("/api/stats")
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

    # Per-language stats
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


@app.get("/api/dashboard")
async def get_dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    language_id: Optional[int] = None,
):
    """Get dashboard data. If language_id is provided, returns per-language stats."""
    from sqlalchemy import func, cast, Date

    if language_id:
        # Verify the language belongs to this user
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

    # Fluency level: aggregate across all vocab items
    fluency_level = "Beginner"
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

    # Also check placement-test CEFR levels stored in settings
    if language_id:
        # Per-language: look up the specific language code's level
        lang_obj = db.query(Language).filter(Language.id == language_id).first()
        cefr_key = f"{lang_obj.code}_level" if lang_obj else None
        cefr_settings = (
            (
                db.query(Settings)
                .filter(Settings.user_id == user.id, Settings.key == cefr_key)
                .all()
            )
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

    # Daily streak: count consecutive days ending today with any activity
    # Activity = conversation created OR vocab/grammar last_practiced_at
    activity_dates = set()

    conv_dates = (
        db.query(func.date(Conversation.created_at))
        .filter(Conversation.user_id == user.id)
        .distinct()
        .all()
    )
    for (d,) in conv_dates:
        if d:
            activity_dates.add(
                d
                if isinstance(d, date)
                else d.date() if hasattr(d, "date") else date.fromisoformat(str(d))
            )

    vocab_dates = (
        (
            db.query(func.date(Vocabulary.last_practiced_at))
            .filter(
                Vocabulary.language_id.in_(user_lang_ids),
                Vocabulary.last_practiced_at.isnot(None),
            )
            .distinct()
            .all()
        )
        if user_lang_ids
        else []
    )
    for (d,) in vocab_dates:
        if d:
            activity_dates.add(
                d
                if isinstance(d, date)
                else d.date() if hasattr(d, "date") else date.fromisoformat(str(d))
            )

    grammar_dates = (
        (
            db.query(func.date(Grammar.last_practiced_at))
            .filter(
                Grammar.language_id.in_(user_lang_ids),
                Grammar.last_practiced_at.isnot(None),
            )
            .distinct()
            .all()
        )
        if user_lang_ids
        else []
    )
    for (d,) in grammar_dates:
        if d:
            activity_dates.add(
                d
                if isinstance(d, date)
                else d.date() if hasattr(d, "date") else date.fromisoformat(str(d))
            )

    streak = 0
    check = date.today()
    while check in activity_dates:
        streak += 1
        check -= timedelta(days=1)

    return {
        "credits": user.credits_balance,
        "total_vocab": total_vocab,
        "total_grammar": total_grammar,
        "fluency_level": fluency_level,
        "daily_streak": streak,
        "language_id": language_id,
    }


# ============== Placement Test ==============


class PlacementAnswerBody(BaseModel):
    answer: str


class PlacementSaveBody(BaseModel):
    vocabulary: List[Dict]
    grammar: List[Dict]


@app.post("/api/placement-test/start/{language_id}")
async def placement_test_start(
    language_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start an adaptive placement test for a language."""
    log_api_call("POST", f"/api/placement-test/start/{language_id}")

    if not check_sufficient_credits(user, min_credits=0.01):
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
        api_key, user_id=user.id, session_id=str(uuid.uuid4()), db_factory=SessionLocal
    )

    agent = PlacementTestAgent(tracked_client, lang.name, native_lang)

    # Generate the first question at A1
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


@app.post("/api/placement-test/{session_id}/answer")
async def placement_test_answer(
    session_id: str,
    body: PlacementAnswerBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit an answer, get evaluation + next question or final results."""
    session_key = (user.id, f"placement_{session_id}")
    if session_key not in active_sessions:
        raise HTTPException(status_code=404, detail="Placement test session not found")

    session = active_sessions[session_key]
    agent: PlacementTestAgent = session["agent"]

    # Evaluate the answer
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

    # Decide what happens next
    level_index = session["level_index"]
    questions_at_level = session["questions_at_level"]

    if questions_at_level >= QUESTIONS_PER_LEVEL:
        # Finished this level — check if we advance
        accuracy = session["correct_at_level"] / questions_at_level
        if accuracy >= ADVANCE_THRESHOLD and level_index < len(CEFR_LEVELS) - 1:
            # Advance to next level
            session["level_index"] = level_index + 1
            session["questions_at_level"] = 0
            session["correct_at_level"] = 0
        else:
            # Test complete
            determined = agent.determine_level(session["results"])
            session["determined_level"] = determined

            # Store CEFR level in user settings
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

    # Generate next question
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


def _build_results_summary(results: List[Dict]) -> List[Dict]:
    """Build a per-level summary of placement test results."""
    level_data = {}
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


@app.post("/api/placement-test/{session_id}/generate-content")
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


@app.post("/api/placement-test/{session_id}/save-content")
async def placement_test_save_content(
    session_id: str,
    body: PlacementSaveBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save user-approved (and possibly edited) starter content to the database."""
    session_key = (user.id, f"placement_{session_id}")
    if session_key not in active_sessions:
        raise HTTPException(status_code=404, detail="Placement test session not found")

    session = active_sessions[session_key]
    lang_id = session["language_id"]

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

    # Save vocabulary (skip duplicates already in DB)
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

    # Save grammar (with semantic deduplication)
    added_grammar = 0
    api_key = get_api_key()
    all_existing_grammar = (
        db.query(Grammar).filter(Grammar.language_id == lang_id).all()
    )

    # Track newly-accepted items within this batch to deduplicate against each other
    accepted_in_batch: list = []  # list of (concept_name_lower, embedding_vec)

    for gram in grammar:
        if not gram.get("concept_name"):
            continue

        # Exact name check against DB
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

        # Exact name check within current batch
        concept_lower = gram["concept_name"].lower()
        if any(
            concept_lower == accepted_name for accepted_name, _ in accepted_in_batch
        ):
            continue

        # Semantic similarity check against DB
        candidate_text = _grammar_embed_text(
            gram["concept_name"], gram.get("description", "")
        )
        candidate_vec = _embed_text(api_key, candidate_text)
        most_similar, similarity = _find_most_similar_grammar(
            candidate_vec, all_existing_grammar, api_key, db
        )

        if similarity >= GRAMMAR_SIMILARITY_HIGH:
            # Treat as duplicate of existing DB entry — skip
            continue

        # Semantic similarity check within current batch
        batch_best_score = 0.0
        for _, batch_vec in accepted_in_batch:
            score = _cosine_similarity(candidate_vec, batch_vec)
            if score > batch_best_score:
                batch_best_score = score
        if batch_best_score >= GRAMMAR_SIMILARITY_HIGH:
            # Too similar to another concept already accepted in this batch — skip
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

    # Clean up session
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


# ============== Billing (Stripe) ==============

# ── Stripe helpers ──────────────────────────────────────────────

CREDIT_PACK_NAME = "Fluō Credit Pack"
CREDIT_PACK_AMOUNT_CENTS = 2000  # $20.00 per pack
CREDIT_PACK_CREDITS = 20.0  # credits added per purchase


def ensure_stripe_price() -> str:
    """Ensure a Stripe Product + Price exist for the credit pack.

    Looks up the cached/env value first, then searches Stripe for an existing
    product named *CREDIT_PACK_NAME*, and finally creates a new product+price
    if nothing is found.  Returns the Price ID.
    """
    global _stripe_price_id
    if _stripe_price_id:
        return _stripe_price_id

    # Search for an existing product by name
    products = stripe.Product.list(limit=100, active=True)
    for product in products.data:
        if product.name == CREDIT_PACK_NAME and product.default_price:
            _stripe_price_id = (
                product.default_price
                if isinstance(product.default_price, str)
                else product.default_price.id
            )
            logger.info(f"Stripe: reusing existing price {_stripe_price_id}")
            return _stripe_price_id

    # Nothing found — create product with an embedded price
    product = stripe.Product.create(
        name=CREDIT_PACK_NAME,
        default_price_data={
            "currency": "usd",
            "unit_amount": CREDIT_PACK_AMOUNT_CENTS,
        },
    )
    _stripe_price_id = product.default_price  # type: ignore[assignment]
    logger.info(f"Stripe: created product {product.id} with price {_stripe_price_id}")
    return _stripe_price_id


def get_or_create_stripe_customer(user: User, db: Session) -> str:
    """Return the Stripe Customer ID for *user*, creating one if needed."""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe.Customer.create(
        email=user.email,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer.id
    db.commit()
    logger.info(f"Stripe: created customer {customer.id} for {user.email}")
    return customer.id


# ── Billing endpoints ───────────────────────────────────────────


class CheckoutRequest(BaseModel):
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@app.post("/api/billing/create-checkout-session")
async def create_checkout_session(
    body: CheckoutRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout Session for a one-time credit pack payment."""
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    try:
        price_id = ensure_stripe_price()
        customer_id = get_or_create_stripe_customer(user, db)

        # Derive sensible default URLs from the incoming request
        origin = str(request.base_url).rstrip("/")
        success = body.success_url or f"{origin}/?purchase=success"
        cancel = body.cancel_url or f"{origin}/?purchase=cancel"

        session = stripe.checkout.Session.create(
            customer=customer_id,
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success,
            cancel_url=cancel,
            client_reference_id=str(user.id),
            metadata={
                "user_id": str(user.id),
                "credits": str(CREDIT_PACK_CREDITS),
            },
        )
        return {"checkout_url": session.url}
    except stripe.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Checkout error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/billing/webhook")
async def handle_stripe_webhook(request: Request):
    """Handle Stripe webhook events.

    Listens for *checkout.session.completed* to credit the user's account.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session_data = event["data"]["object"]
        client_ref = session_data.get("client_reference_id")
        metadata = session_data.get("metadata", {})
        credits_to_add = float(metadata.get("credits", str(CREDIT_PACK_CREDITS)))

        if not client_ref:
            logger.warning(
                "Webhook: checkout.session.completed without client_reference_id"
            )
            return {"status": "ignored"}

        user_id = int(client_ref)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.credits_balance += credits_to_add
                # Persist customer ID if it was set during checkout
                stripe_customer = session_data.get("customer")
                if stripe_customer and not user.stripe_customer_id:
                    user.stripe_customer_id = stripe_customer
                db.commit()
                logger.info(
                    f"{Colors.GREEN}💳 Added ${credits_to_add:.2f} credits to "
                    f"{user.email} (balance: ${user.credits_balance:.2f}){Colors.END}"
                )
            else:
                logger.warning(f"Webhook: user {user_id} not found")
        finally:
            db.close()

    return {"status": "ok"}


@app.get("/api/billing/usage")
async def get_usage_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's API usage history."""
    logs = (
        db.query(UsageLog)
        .filter(UsageLog.user_id == user.id)
        .order_by(UsageLog.created_at.desc())
        .limit(100)
        .all()
    )
    total_spent = sum(log.cost_usd for log in logs)
    return {
        "credits_balance": user.credits_balance,
        "total_api_cost": round(total_spent, 4),
        "recent_usage": [
            {
                "model": log.model,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "cost_usd": log.cost_usd,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs[:20]
        ],
    }


# ============================================================
# ============== Teacher / Student / Homework API ============
# ============================================================

import secrets as _secrets
import string as _string


def _generate_class_code(length: int = 8) -> str:
    """Generate a random uppercase alphanumeric class code."""
    alphabet = _string.ascii_uppercase + _string.digits
    return "".join(_secrets.choice(alphabet) for _ in range(length))


# ── Pydantic models ─────────────────────────────────────────────


class ClassCreate(BaseModel):
    name: str
    language_id: Optional[int] = None


class HomeworkCreate(BaseModel):
    class_id: int
    name: str
    description: Optional[str] = None
    language_id: Optional[int] = None
    due_date: Optional[str] = None  # ISO date string


class HomeworkUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None


class VocabRefsBody(BaseModel):
    vocabulary_ids: List[int]


class GrammarRefsBody(BaseModel):
    grammar_ids: List[int]


class HomeworkQuestionItem(BaseModel):
    question_type: str
    question_text: str
    english_prompt: Optional[str] = None
    wrong_sentence: Optional[str] = None
    correct_answer: str
    explanation: Optional[str] = None
    highlighted_segments: Optional[str] = None  # JSON string
    order_index: int = 0


class HomeworkQuestionsBody(BaseModel):
    questions: List[HomeworkQuestionItem]


class HomeworkTopicBody(BaseModel):
    topic_text: str
    source: str = "custom"
    cluster_topic_id: Optional[int] = None


class HomeworkCompleteBody(BaseModel):
    exercise_type: str  # 'flashcards' | 'grammar' | 'conversation'
    score: Optional[float] = None


class AddStudentByEmailBody(BaseModel):
    email: str


class JoinClassBody(BaseModel):
    class_code: str


# ── Helper ──────────────────────────────────────────────────────


def _homework_belongs_to_teacher(
    homework_id: int, teacher_id: int, db: Session
) -> Homework:
    hw = (
        db.query(Homework)
        .filter(Homework.id == homework_id, Homework.teacher_id == teacher_id)
        .first()
    )
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")
    return hw


def _class_belongs_to_teacher(class_id: int, teacher_id: int, db: Session) -> Class:
    cls = (
        db.query(Class)
        .filter(Class.id == class_id, Class.teacher_id == teacher_id)
        .first()
    )
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    return cls


# ── Class endpoints (teacher) ────────────────────────────────────


@app.post("/api/classes")
async def create_class(
    body: ClassCreate,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    # Verify language belongs to teacher if provided
    if body.language_id:
        lang = (
            db.query(Language)
            .filter(Language.id == body.language_id, Language.user_id == teacher.id)
            .first()
        )
        if not lang:
            raise HTTPException(status_code=404, detail="Language not found")

    code = _generate_class_code()
    # Ensure uniqueness
    while db.query(Class).filter(Class.class_code == code).first():
        code = _generate_class_code()

    cls = Class(
        teacher_id=teacher.id,
        name=body.name,
        language_id=body.language_id,
        class_code=code,
    )
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return {
        "id": cls.id,
        "name": cls.name,
        "class_code": cls.class_code,
        "language_id": cls.language_id,
        "created_at": cls.created_at.isoformat(),
    }


@app.get("/api/classes")
async def list_classes(
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    classes = db.query(Class).filter(Class.teacher_id == teacher.id).all()
    result = []
    for cls in classes:
        student_count = (
            db.query(ClassStudent).filter(ClassStudent.class_id == cls.id).count()
        )
        result.append(
            {
                "id": cls.id,
                "name": cls.name,
                "class_code": cls.class_code,
                "language_id": cls.language_id,
                "student_count": student_count,
                "created_at": cls.created_at.isoformat(),
            }
        )
    return result


@app.get("/api/classes/{class_id}")
async def get_class(
    class_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    cls = _class_belongs_to_teacher(class_id, teacher.id, db)
    student_rows = (
        db.query(ClassStudent).filter(ClassStudent.class_id == class_id).all()
    )
    students = []
    for row in student_rows:
        student = db.query(User).filter(User.id == row.student_id).first()
        if student:
            students.append(
                {
                    "id": student.id,
                    "email": student.email,
                    "joined_at": row.joined_at.isoformat(),
                }
            )
    homework_list = db.query(Homework).filter(Homework.class_id == class_id).all()
    return {
        "id": cls.id,
        "name": cls.name,
        "class_code": cls.class_code,
        "language_id": cls.language_id,
        "students": students,
        "homework": [
            {
                "id": hw.id,
                "name": hw.name,
                "due_date": hw.due_date.isoformat() if hw.due_date else None,
            }
            for hw in homework_list
        ],
    }


@app.post("/api/classes/{class_id}/students")
async def add_student_to_class(
    class_id: int,
    body: AddStudentByEmailBody,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _class_belongs_to_teacher(class_id, teacher.id, db)
    student = db.query(User).filter(User.email == body.email).first()
    if not student:
        raise HTTPException(status_code=404, detail="No user found with that email")
    if student.role != "student":
        raise HTTPException(status_code=400, detail="That user is not a student")
    existing = (
        db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == class_id, ClassStudent.student_id == student.id
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Student already in this class")
    db.add(ClassStudent(class_id=class_id, student_id=student.id))
    db.commit()
    return {"message": f"{student.email} added to class"}


@app.delete("/api/classes/{class_id}/students/{student_id}")
async def remove_student_from_class(
    class_id: int,
    student_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _class_belongs_to_teacher(class_id, teacher.id, db)
    row = (
        db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == class_id, ClassStudent.student_id == student_id
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Student not in this class")
    db.delete(row)
    db.commit()
    return {"message": "Student removed from class"}


@app.post("/api/classes/join")
async def join_class(
    body: JoinClassBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Student joins a class using a class code."""
    cls = db.query(Class).filter(Class.class_code == body.class_code.upper()).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Invalid class code")
    existing = (
        db.query(ClassStudent)
        .filter(ClassStudent.class_id == cls.id, ClassStudent.student_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already enrolled in this class")
    db.add(ClassStudent(class_id=cls.id, student_id=user.id))
    db.commit()
    return {
        "message": f"Joined class '{cls.name}'",
        "class_id": cls.id,
        "class_name": cls.name,
    }


# ── Homework CRUD (teacher) ──────────────────────────────────────


@app.post("/api/homework")
async def create_homework(
    body: HomeworkCreate,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _class_belongs_to_teacher(body.class_id, teacher.id, db)
    due = None
    if body.due_date:
        try:
            due = datetime.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid due_date format (use ISO 8601)"
            )
    hw = Homework(
        class_id=body.class_id,
        teacher_id=teacher.id,
        name=body.name,
        description=body.description,
        language_id=body.language_id,
        due_date=due,
    )
    db.add(hw)
    db.commit()
    db.refresh(hw)
    return {
        "id": hw.id,
        "name": hw.name,
        "class_id": hw.class_id,
        "language_id": hw.language_id,
        "due_date": hw.due_date.isoformat() if hw.due_date else None,
        "created_at": hw.created_at.isoformat(),
    }


@app.get("/api/homework")
async def list_homework(
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    hws = db.query(Homework).filter(Homework.teacher_id == teacher.id).all()
    result = []
    for hw in hws:
        cls = db.query(Class).filter(Class.id == hw.class_id).first()
        vocab_count = (
            db.query(HomeworkVocabRef)
            .filter(HomeworkVocabRef.homework_id == hw.id)
            .count()
        )
        grammar_count = (
            db.query(HomeworkGrammarRef)
            .filter(HomeworkGrammarRef.homework_id == hw.id)
            .count()
        )
        topic_count = (
            db.query(HomeworkTopic).filter(HomeworkTopic.homework_id == hw.id).count()
        )
        result.append(
            {
                "id": hw.id,
                "name": hw.name,
                "description": hw.description,
                "class_id": hw.class_id,
                "class_name": cls.name if cls else None,
                "language_id": hw.language_id,
                "due_date": hw.due_date.isoformat() if hw.due_date else None,
                "created_at": hw.created_at.isoformat(),
                "vocab_count": vocab_count,
                "grammar_count": grammar_count,
                "topic_count": topic_count,
            }
        )
    return result


@app.get("/api/homework/{homework_id}")
async def get_homework(
    homework_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    hw = _homework_belongs_to_teacher(homework_id, teacher.id, db)
    cls = db.query(Class).filter(Class.id == hw.class_id).first()

    # Vocab items (from teacher's own vocabulary table)
    vocab_refs = (
        db.query(HomeworkVocabRef)
        .filter(HomeworkVocabRef.homework_id == homework_id)
        .all()
    )
    vocab_items = []
    for ref in vocab_refs:
        v = db.query(Vocabulary).filter(Vocabulary.id == ref.vocabulary_id).first()
        if v:
            vocab_items.append(
                {
                    "id": v.id,
                    "target_word": v.target_word,
                    "native_translation": v.native_translation,
                    "example_sentence": v.example_sentence,
                    "fluency_level": v.fluency_level,
                }
            )

    # Grammar items
    grammar_refs = (
        db.query(HomeworkGrammarRef)
        .filter(HomeworkGrammarRef.homework_id == homework_id)
        .all()
    )
    grammar_items = []
    for ref in grammar_refs:
        g = db.query(Grammar).filter(Grammar.id == ref.grammar_id).first()
        if g:
            # Get saved questions for this grammar concept within this homework
            questions = (
                db.query(HomeworkGrammarQuestion)
                .filter(
                    HomeworkGrammarQuestion.homework_id == homework_id,
                    HomeworkGrammarQuestion.grammar_id == ref.grammar_id,
                )
                .order_by(HomeworkGrammarQuestion.order_index)
                .all()
            )
            grammar_items.append(
                {
                    "id": g.id,
                    "concept_name": g.concept_name,
                    "description": g.description,
                    "examples": g.examples,
                    "fluency_level": g.fluency_level,
                    "questions_saved": len(questions),
                    "questions": [
                        {
                            "id": q.id,
                            "question_type": q.question_type,
                            "question_text": q.question_text,
                            "english_prompt": q.english_prompt,
                            "wrong_sentence": q.wrong_sentence,
                            "correct_answer": q.correct_answer,
                            "explanation": q.explanation,
                            "highlighted_segments": (
                                json.loads(q.highlighted_segments)
                                if q.highlighted_segments
                                else []
                            ),
                            "order_index": q.order_index,
                        }
                        for q in questions
                    ],
                }
            )

    # Topics
    topics = (
        db.query(HomeworkTopic).filter(HomeworkTopic.homework_id == homework_id).all()
    )

    # Completions summary
    completions = (
        db.query(HomeworkCompletion)
        .filter(HomeworkCompletion.homework_id == homework_id)
        .all()
    )
    completion_summary = {}
    for c in completions:
        key = c.exercise_type
        if key not in completion_summary:
            completion_summary[key] = 0
        completion_summary[key] += 1

    return {
        "id": hw.id,
        "name": hw.name,
        "description": hw.description,
        "class_id": hw.class_id,
        "class_name": cls.name if cls else None,
        "language_id": hw.language_id,
        "due_date": hw.due_date.isoformat() if hw.due_date else None,
        "created_at": hw.created_at.isoformat(),
        "vocab": vocab_items,
        "grammar": grammar_items,
        "topics": [
            {
                "id": t.id,
                "topic_text": t.topic_text,
                "source": t.source,
                "cluster_topic_id": t.cluster_topic_id,
            }
            for t in topics
        ],
        "completion_summary": completion_summary,
    }


@app.put("/api/homework/{homework_id}")
async def update_homework(
    homework_id: int,
    body: HomeworkUpdate,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    hw = _homework_belongs_to_teacher(homework_id, teacher.id, db)
    if body.name is not None:
        hw.name = body.name
    if body.description is not None:
        hw.description = body.description
    if body.due_date is not None:
        try:
            hw.due_date = datetime.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due_date format")
    db.commit()
    return {"message": "Homework updated"}


@app.delete("/api/homework/{homework_id}")
async def delete_homework(
    homework_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    hw = _homework_belongs_to_teacher(homework_id, teacher.id, db)
    db.delete(hw)
    db.commit()
    return {"message": "Homework deleted"}


# ── Homework content refs (teacher) ─────────────────────────────


@app.post("/api/homework/{homework_id}/vocab-refs")
async def add_vocab_refs(
    homework_id: int,
    body: VocabRefsBody,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    hw = _homework_belongs_to_teacher(homework_id, teacher.id, db)
    added = 0
    for vid in body.vocabulary_ids:
        # Verify vocab belongs to teacher
        vocab = db.query(Vocabulary).filter(Vocabulary.id == vid).first()
        if not vocab:
            continue
        lang = (
            db.query(Language)
            .filter(Language.id == vocab.language_id, Language.user_id == teacher.id)
            .first()
        )
        if not lang:
            continue
        existing = (
            db.query(HomeworkVocabRef)
            .filter(
                HomeworkVocabRef.homework_id == homework_id,
                HomeworkVocabRef.vocabulary_id == vid,
            )
            .first()
        )
        if not existing:
            db.add(HomeworkVocabRef(homework_id=homework_id, vocabulary_id=vid))
            added += 1
    db.commit()
    return {"message": f"{added} vocab item(s) attached"}


@app.delete("/api/homework/{homework_id}/vocab-refs/{vocab_id}")
async def remove_vocab_ref(
    homework_id: int,
    vocab_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    row = (
        db.query(HomeworkVocabRef)
        .filter(
            HomeworkVocabRef.homework_id == homework_id,
            HomeworkVocabRef.vocabulary_id == vocab_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Vocab ref not found")
    db.delete(row)
    db.commit()
    return {"message": "Vocab ref removed"}


@app.post("/api/homework/{homework_id}/grammar-refs")
async def add_grammar_refs(
    homework_id: int,
    body: GrammarRefsBody,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    added = 0
    for gid in body.grammar_ids:
        grammar = db.query(Grammar).filter(Grammar.id == gid).first()
        if not grammar:
            continue
        lang = (
            db.query(Language)
            .filter(Language.id == grammar.language_id, Language.user_id == teacher.id)
            .first()
        )
        if not lang:
            continue
        existing = (
            db.query(HomeworkGrammarRef)
            .filter(
                HomeworkGrammarRef.homework_id == homework_id,
                HomeworkGrammarRef.grammar_id == gid,
            )
            .first()
        )
        if not existing:
            db.add(HomeworkGrammarRef(homework_id=homework_id, grammar_id=gid))
            added += 1
    db.commit()
    return {"message": f"{added} grammar concept(s) attached"}


@app.delete("/api/homework/{homework_id}/grammar-refs/{grammar_id}")
async def remove_grammar_ref(
    homework_id: int,
    grammar_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    row = (
        db.query(HomeworkGrammarRef)
        .filter(
            HomeworkGrammarRef.homework_id == homework_id,
            HomeworkGrammarRef.grammar_id == grammar_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Grammar ref not found")
    db.delete(row)
    # Also delete saved questions for that concept in this homework
    db.query(HomeworkGrammarQuestion).filter(
        HomeworkGrammarQuestion.homework_id == homework_id,
        HomeworkGrammarQuestion.grammar_id == grammar_id,
    ).delete()
    db.commit()
    return {"message": "Grammar ref removed"}


@app.post("/api/homework/{homework_id}/grammar/{grammar_id}/generate-questions")
async def generate_homework_questions(
    homework_id: int,
    grammar_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Generate draft questions for a grammar concept (not saved yet)."""
    _homework_belongs_to_teacher(homework_id, teacher.id, db)

    # Verify grammar ref exists
    ref = (
        db.query(HomeworkGrammarRef)
        .filter(
            HomeworkGrammarRef.homework_id == homework_id,
            HomeworkGrammarRef.grammar_id == grammar_id,
        )
        .first()
    )
    if not ref:
        raise HTTPException(
            status_code=404, detail="Grammar concept not attached to this homework"
        )

    grammar = db.query(Grammar).filter(Grammar.id == grammar_id).first()
    if not grammar:
        raise HTTPException(status_code=404, detail="Grammar concept not found")

    api_key = get_api_key()
    native_lang = get_native_language(db, teacher.id)
    user_level = get_user_level(db, teacher.id)

    # Get language name
    lang = db.query(Language).filter(Language.id == grammar.language_id).first()
    target_language = lang.name if lang else "Unknown"

    # Auto-generate detail card if missing (same logic as GET /api/grammar/{id}/detail-card)
    if not grammar.detail_card:
        session_id = str(uuid.uuid4())
        tracked_client = TrackedOpenAI(
            api_key, user_id=teacher.id, session_id=session_id, db_factory=SessionLocal
        )
        dc_prompt = f"""You are an expert language tutor creating a focused grammar study card for a language learner.

Return only this JSON — no preamble, no markdown fences:

{{
  "concept": "Concept name",
  "tagline": "One sentence: what this concept does in plain English",
  "breakdown": {{
    "structure": "The abstract pattern",
    "components": [
      {{ "part": "element", "role": "what it does", "from_trigger": "word from trigger" }}
    ]
  }},
  "core_rules": ["Rule stated simply"],
  "nuances": [{{ "observation": "A subtle point", "example": "Sentence illustrating it" }}],
  "examples": [{{ "sentence": "...", "translation": "...", "highlight": "..." }}],
  "common_errors": [{{ "wrong": "...", "right": "...", "why": "..." }}],
  "related_concepts": ["..."]
}}

Rules: If a field has no confident content set it to null. Never fabricate entries.

Concept: {grammar.concept_name}
Trigger phrase: {grammar.examples or grammar.description or "(none provided)"}
Target language: {target_language}
Learner level: {user_level}"""

        dc_response = tracked_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": dc_prompt}],
            temperature=0.3,
        )
        raw = dc_response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
            raw = raw.strip()
        try:
            generated_card = json.loads(raw)
            grammar.detail_card = json.dumps(generated_card)
            db.commit()
        except json.JSONDecodeError:
            # Fall back to a minimal card so question generation can still proceed
            grammar.detail_card = json.dumps(
                {
                    "concept": grammar.concept_name,
                    "description": grammar.description or "",
                }
            )
            db.commit()

    from openai import OpenAI as _OpenAI

    client = _OpenAI(api_key=api_key)
    agent = GrammarPracticeAgent(
        client,
        target_language=target_language,
        native_language=native_lang,
        level=user_level,
        fluency_level=grammar.fluency_level or "low",
    )

    try:
        detail_card = json.loads(grammar.detail_card)
    except (json.JSONDecodeError, ValueError):
        detail_card = {
            "concept": grammar.concept_name,
            "description": grammar.description,
        }

    questions = agent.generate_questions(detail_card)
    # Normalise field names and add order_index
    for i, q in enumerate(questions):
        q["order_index"] = i
        # Agent returns "type"; frontend/Pydantic expect "question_type"
        if "type" in q and "question_type" not in q:
            q["question_type"] = q.pop("type")
    return {"questions": questions}


@app.put("/api/homework/{homework_id}/grammar/{grammar_id}/questions")
async def save_homework_questions(
    homework_id: int,
    grammar_id: int,
    body: HomeworkQuestionsBody,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Save teacher-refined questions for a grammar concept within a homework."""
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    # Verify ref exists
    ref = (
        db.query(HomeworkGrammarRef)
        .filter(
            HomeworkGrammarRef.homework_id == homework_id,
            HomeworkGrammarRef.grammar_id == grammar_id,
        )
        .first()
    )
    if not ref:
        raise HTTPException(
            status_code=404, detail="Grammar concept not attached to this homework"
        )

    # Delete existing questions for this concept in this homework
    db.query(HomeworkGrammarQuestion).filter(
        HomeworkGrammarQuestion.homework_id == homework_id,
        HomeworkGrammarQuestion.grammar_id == grammar_id,
    ).delete()

    for item in body.questions:
        db.add(
            HomeworkGrammarQuestion(
                homework_id=homework_id,
                grammar_id=grammar_id,
                question_type=item.question_type,
                question_text=item.question_text,
                english_prompt=item.english_prompt,
                wrong_sentence=item.wrong_sentence,
                correct_answer=item.correct_answer,
                explanation=item.explanation,
                highlighted_segments=item.highlighted_segments,
                order_index=item.order_index,
            )
        )
    db.commit()
    return {"message": f"{len(body.questions)} question(s) saved"}


@app.post("/api/homework/{homework_id}/topics")
async def add_homework_topic(
    homework_id: int,
    body: HomeworkTopicBody,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    topic = HomeworkTopic(
        homework_id=homework_id,
        topic_text=body.topic_text,
        source=body.source,
        cluster_topic_id=body.cluster_topic_id,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return {"id": topic.id, "topic_text": topic.topic_text, "source": topic.source}


@app.delete("/api/homework/{homework_id}/topics/{topic_id}")
async def remove_homework_topic(
    homework_id: int,
    topic_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    _homework_belongs_to_teacher(homework_id, teacher.id, db)
    topic = (
        db.query(HomeworkTopic)
        .filter(HomeworkTopic.id == topic_id, HomeworkTopic.homework_id == homework_id)
        .first()
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    db.delete(topic)
    db.commit()
    return {"message": "Topic removed"}


@app.get("/api/homework/{homework_id}/completions")
async def get_homework_completions(
    homework_id: int,
    teacher: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Get per-student completion status for a homework (teacher monitoring)."""
    hw = _homework_belongs_to_teacher(homework_id, teacher.id, db)
    cls = db.query(Class).filter(Class.id == hw.class_id).first()
    student_rows = (
        db.query(ClassStudent).filter(ClassStudent.class_id == hw.class_id).all()
    )

    result = []
    for row in student_rows:
        student = db.query(User).filter(User.id == row.student_id).first()
        if not student:
            continue
        completions = (
            db.query(HomeworkCompletion)
            .filter(
                HomeworkCompletion.homework_id == homework_id,
                HomeworkCompletion.student_id == student.id,
            )
            .all()
        )
        completion_map = {
            c.exercise_type: {
                "score": c.score,
                "completed_at": c.completed_at.isoformat(),
            }
            for c in completions
        }
        result.append(
            {
                "student_id": student.id,
                "student_email": student.email,
                "completions": completion_map,
            }
        )
    return {"homework_name": hw.name, "students": result}


# ── Student homework endpoints ───────────────────────────────────


@app.get("/api/student/homework")
async def list_student_homework(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all homework assigned to the student via their class enrollments."""
    enrollments = (
        db.query(ClassStudent).filter(ClassStudent.student_id == user.id).all()
    )
    result = []
    for enrollment in enrollments:
        cls = db.query(Class).filter(Class.id == enrollment.class_id).first()
        if not cls:
            continue
        homework_list = db.query(Homework).filter(Homework.class_id == cls.id).all()
        for hw in homework_list:
            completions = (
                db.query(HomeworkCompletion)
                .filter(
                    HomeworkCompletion.homework_id == hw.id,
                    HomeworkCompletion.student_id == user.id,
                )
                .all()
            )
            completion_map = {c.exercise_type: True for c in completions}

            vocab_count = (
                db.query(HomeworkVocabRef)
                .filter(HomeworkVocabRef.homework_id == hw.id)
                .count()
            )
            grammar_count = (
                db.query(HomeworkGrammarRef)
                .filter(HomeworkGrammarRef.homework_id == hw.id)
                .count()
            )
            topic_count = (
                db.query(HomeworkTopic)
                .filter(HomeworkTopic.homework_id == hw.id)
                .count()
            )

            result.append(
                {
                    "id": hw.id,
                    "name": hw.name,
                    "description": hw.description,
                    "class_name": cls.name,
                    "language_id": hw.language_id,
                    "due_date": hw.due_date.isoformat() if hw.due_date else None,
                    "created_at": hw.created_at.isoformat(),
                    "vocab_count": vocab_count,
                    "grammar_count": grammar_count,
                    "topic_count": topic_count,
                    "completions": completion_map,
                }
            )
    return result


@app.get("/api/student/homework/{homework_id}")
async def get_student_homework_detail(
    homework_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get homework detail for a student. Verifies enrollment."""
    hw = db.query(Homework).filter(Homework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")
    # Verify student is enrolled in the class
    enrollment = (
        db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == hw.class_id, ClassStudent.student_id == user.id
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=403, detail="Not enrolled in this class")

    cls = db.query(Class).filter(Class.id == hw.class_id).first()

    # Vocab (teacher's vocabulary rows)
    vocab_refs = (
        db.query(HomeworkVocabRef)
        .filter(HomeworkVocabRef.homework_id == homework_id)
        .all()
    )
    vocab_items = []
    for ref in vocab_refs:
        v = db.query(Vocabulary).filter(Vocabulary.id == ref.vocabulary_id).first()
        if v:
            vocab_items.append(
                {
                    "id": v.id,
                    "target_word": v.target_word,
                    "native_translation": v.native_translation,
                    "example_sentence": v.example_sentence,
                }
            )

    # Grammar (teacher's grammar rows + saved questions)
    grammar_refs = (
        db.query(HomeworkGrammarRef)
        .filter(HomeworkGrammarRef.homework_id == homework_id)
        .all()
    )
    grammar_items = []
    for ref in grammar_refs:
        g = db.query(Grammar).filter(Grammar.id == ref.grammar_id).first()
        if g:
            questions = (
                db.query(HomeworkGrammarQuestion)
                .filter(
                    HomeworkGrammarQuestion.homework_id == homework_id,
                    HomeworkGrammarQuestion.grammar_id == ref.grammar_id,
                )
                .order_by(HomeworkGrammarQuestion.order_index)
                .all()
            )
            grammar_items.append(
                {
                    "id": g.id,
                    "concept_name": g.concept_name,
                    "description": g.description,
                    "questions_count": len(questions),
                    "questions": [
                        {
                            "id": q.id,
                            "question_type": q.question_type,
                            "question_text": q.question_text,
                            "english_prompt": q.english_prompt,
                            "wrong_sentence": q.wrong_sentence,
                            "correct_answer": q.correct_answer,
                            "explanation": q.explanation,
                            "highlighted_segments": (
                                json.loads(q.highlighted_segments)
                                if q.highlighted_segments
                                else []
                            ),
                            "order_index": q.order_index,
                        }
                        for q in questions
                    ],
                }
            )

    # Topics
    topics = (
        db.query(HomeworkTopic).filter(HomeworkTopic.homework_id == homework_id).all()
    )

    # Student's completions for this homework
    completions = (
        db.query(HomeworkCompletion)
        .filter(
            HomeworkCompletion.homework_id == homework_id,
            HomeworkCompletion.student_id == user.id,
        )
        .all()
    )
    completion_map = {
        c.exercise_type: {"score": c.score, "completed_at": c.completed_at.isoformat()}
        for c in completions
    }

    return {
        "id": hw.id,
        "name": hw.name,
        "description": hw.description,
        "class_name": cls.name if cls else None,
        "language_id": hw.language_id,
        "due_date": hw.due_date.isoformat() if hw.due_date else None,
        "vocab": vocab_items,
        "grammar": grammar_items,
        "topics": [
            {"id": t.id, "topic_text": t.topic_text, "source": t.source} for t in topics
        ],
        "completions": completion_map,
    }


@app.post("/api/student/homework/{homework_id}/start-flashcards")
async def student_start_flashcards(
    homework_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Copy teacher's homework vocab into student's own vocabulary library (skip duplicates),
    then return the deck for flashcard practice.
    """
    hw = db.query(Homework).filter(Homework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")
    enrollment = (
        db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == hw.class_id, ClassStudent.student_id == user.id
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=403, detail="Not enrolled in this class")
    if not hw.language_id:
        raise HTTPException(status_code=400, detail="Homework has no language set")

    # Ensure student has this language in their account
    student_lang = (
        db.query(Language)
        .filter(Language.user_id == user.id, Language.id == hw.language_id)
        .first()
    )
    if not student_lang:
        # Try to find by name
        teacher_lang = db.query(Language).filter(Language.id == hw.language_id).first()
        if teacher_lang:
            student_lang = (
                db.query(Language)
                .filter(Language.user_id == user.id, Language.name == teacher_lang.name)
                .first()
            )
            if not student_lang:
                student_lang = Language(
                    user_id=user.id,
                    name=teacher_lang.name,
                    code=teacher_lang.code,
                )
                db.add(student_lang)
                db.flush()

    if not student_lang:
        raise HTTPException(
            status_code=400, detail="Could not determine student language"
        )

    vocab_refs = (
        db.query(HomeworkVocabRef)
        .filter(HomeworkVocabRef.homework_id == homework_id)
        .all()
    )
    deck = []
    for ref in vocab_refs:
        teacher_vocab = (
            db.query(Vocabulary).filter(Vocabulary.id == ref.vocabulary_id).first()
        )
        if not teacher_vocab:
            continue
        # Skip duplicates by target_word (case-insensitive) within student's language
        existing = (
            db.query(Vocabulary)
            .filter(
                Vocabulary.language_id == student_lang.id,
                Vocabulary.target_word.ilike(teacher_vocab.target_word),
            )
            .first()
        )
        if not existing:
            new_vocab = Vocabulary(
                language_id=student_lang.id,
                target_word=teacher_vocab.target_word,
                native_translation=teacher_vocab.native_translation,
                example_sentence=teacher_vocab.example_sentence,
                fluency_level="low",
            )
            db.add(new_vocab)
            db.flush()
            deck.append(
                {
                    "id": new_vocab.id,
                    "target_word": new_vocab.target_word,
                    "native_translation": new_vocab.native_translation,
                    "example_sentence": new_vocab.example_sentence,
                    "fluency_level": new_vocab.fluency_level,
                }
            )
        else:
            deck.append(
                {
                    "id": existing.id,
                    "target_word": existing.target_word,
                    "native_translation": existing.native_translation,
                    "example_sentence": existing.example_sentence,
                    "fluency_level": existing.fluency_level,
                }
            )
    db.commit()
    return {"deck": deck, "language_id": student_lang.id}


@app.post("/api/student/homework/{homework_id}/complete")
async def student_complete_exercise(
    homework_id: int,
    body: HomeworkCompleteBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a student's completion of an exercise type within a homework."""
    hw = db.query(Homework).filter(Homework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")
    enrollment = (
        db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == hw.class_id, ClassStudent.student_id == user.id
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=403, detail="Not enrolled in this class")

    valid_types = {"flashcards", "grammar", "conversation"}
    if body.exercise_type not in valid_types:
        raise HTTPException(
            status_code=400, detail=f"exercise_type must be one of {valid_types}"
        )

    existing = (
        db.query(HomeworkCompletion)
        .filter(
            HomeworkCompletion.student_id == user.id,
            HomeworkCompletion.homework_id == homework_id,
            HomeworkCompletion.exercise_type == body.exercise_type,
        )
        .first()
    )
    if existing:
        existing.score = body.score
        existing.completed_at = datetime.utcnow()
    else:
        db.add(
            HomeworkCompletion(
                student_id=user.id,
                homework_id=homework_id,
                exercise_type=body.exercise_type,
                score=body.score,
            )
        )
    db.commit()
    return {"message": f"{body.exercise_type} marked as complete"}


# ============== Serve Frontend ==============
# Must be registered AFTER all API routes so the catch-all doesn't shadow them.


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the frontend HTML."""
    with open("static/index.html", "r") as f:
        return f.read()


@app.get("/favicon.svg")
async def serve_favicon():
    return FileResponse("static/favicon.svg", media_type="image/svg+xml")


# Mount static asset directories BEFORE the catch-all route so Vite-built
# assets (/assets/...) are served with correct MIME types instead of being
# intercepted by the SPA catch-all and returned as text/html.
os.makedirs("static/assets", exist_ok=True)
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Catch-all route for SPA routing - must be after static mounts
@app.get("/{path:path}", response_class=HTMLResponse)
async def serve_spa(path: str):
    """Serve the frontend for any non-API route (SPA routing)."""
    # Don't serve HTML for API routes or static files
    if (
        path.startswith("api/")
        or path.startswith("static/")
        or path.startswith("assets/")
    ):
        raise HTTPException(status_code=404, detail="Not found")
    with open("static/index.html", "r") as f:
        return f.read()


if __name__ == "__main__":
    import uvicorn

    print_startup_banner()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
