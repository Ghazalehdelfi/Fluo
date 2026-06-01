"""Note upload and extraction route: POST /api/upload-notes."""

import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from database import User, Language, Vocabulary, Grammar, SessionLocal
from auth import get_current_user
from cost_tracker import TrackedOpenAI, check_sufficient_credits
from dependencies import get_db, get_api_key, get_native_language
from grammar_utils import (
    GRAMMAR_SIMILARITY_HIGH,
    GRAMMAR_SIMILARITY_LOW,
    embed_text,
    grammar_embed_text,
    find_most_similar_grammar,
)
from tasks import rebuild_topics
from agents.note_extractor import NoteExtractorAgent
from agents.logging_utils import Colors, get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/api/upload-notes")
async def upload_notes(
    language_id: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    text: Optional[str] = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """Upload notes (images or text) and extract vocabulary and grammar."""
    if not check_sufficient_credits(user, min_credits=1):
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please purchase more credits to continue.",
        )

    api_key = get_api_key()
    native_lang = get_native_language(db, user.id)

    session_id = str(uuid.uuid4())
    tracked_client = TrackedOpenAI(
        api_key, user_id=user.id, session_id=session_id, db_factory=SessionLocal
    )

    try:
        lang_id = int(language_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid language_id")

    lang = (
        db.query(Language)
        .filter(Language.id == lang_id, Language.user_id == user.id)
        .first()
    )
    if not lang:
        raise HTTPException(status_code=404, detail="Language not found")

    logger.info(f"{Colors.GREEN}📝 NOTE EXTRACTOR: Processing upload for {lang.name}{Colors.END}")
    logger.info(f"   Native language: {native_lang}")

    extractor = NoteExtractorAgent(tracked_client, lang.name, native_lang)

    all_vocabulary = []
    all_grammar = []
    if files and len(files) > 0 and files[0].filename:
        logger.info(f"   Processing {len(files)} image(s)...")
        for i, file in enumerate(files):
            logger.info(f"      Image {i+1}: {file.filename} ({file.content_type})")
            contents = await file.read()
            mime_type = file.content_type or "image/jpeg"
            vocabulary, grammar = extractor.extract_from_image(contents, mime_type)
            all_vocabulary.extend(vocabulary)
            all_grammar.extend(grammar)
    elif text:
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
    grammar_pending = []

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

        all_existing = db.query(Grammar).filter(Grammar.language_id == lang_id).all()
        candidate_text = grammar_embed_text(gram["concept_name"], gram.get("description", ""))
        candidate_vec = embed_text(api_key, candidate_text)

        most_similar, similarity = find_most_similar_grammar(
            candidate_vec, all_existing, api_key, db
        )

        if similarity >= GRAMMAR_SIMILARITY_HIGH:
            logger.info(
                f"   ⏭ Grammar '{gram['concept_name']}' skipped "
                f"(similarity={similarity:.2f} with '{most_similar.concept_name}')"
            )
            continue

        if similarity >= GRAMMAR_SIMILARITY_LOW and most_similar is not None:
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

        import json
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
            logger.info(f"      • {v['target_word']} → {v.get('native_translation', '')}")
        if len(added_vocab) > 5:
            logger.info(f"      ... and {len(added_vocab) - 5} more")

    if added_vocab and background_tasks is not None:
        background_tasks.add_task(rebuild_topics, lang_id, lang.name)
        logger.info(f"   {Colors.CYAN}⚙ Topic clustering queued as background task{Colors.END}")

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
