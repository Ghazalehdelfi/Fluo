"""Note upload and extraction route: POST /api/upload-notes."""

import io
import logging
import uuid
from typing import List, Optional
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
from rate_limiter import user_limiter

try:
    from pypdf import PdfReader

    _HAS_PYPDF = True
except ImportError:
    _HAS_PYPDF = False

try:
    import pymupdf  # PyMuPDF — renders PDF pages to images

    _HAS_PYMUPDF = True
except ImportError:
    _HAS_PYMUPDF = False

logger = get_logger(__name__)
router = APIRouter()

# Minimum chars of extractable text before a PDF is treated as text-based.
# Below this, the PDF is assumed scanned/handwritten → vision fallback.
_MIN_PDF_TEXT_CHARS = 20
# Max pages to send through vision extraction (cost guard).
_MAX_VISION_PAGES = 10


def _process_pdf(
    filename: str, contents: bytes, extractor: NoteExtractorAgent
):
    """Extract vocabulary/grammar from a PDF.

    Uses the embedded text layer when present; falls back to rendering pages
    as images and using vision extraction for scanned/handwritten PDFs.
    """
    if not _HAS_PYPDF:
        raise HTTPException(status_code=500, detail="PDF support not available")

    pdf_text = ""
    try:
        reader = PdfReader(io.BytesIO(contents))
        pdf_text = "\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()
    except Exception as exc:
        logger.warning(f"      pypdf text extraction failed for {filename}: {exc}")
    logger.info(f"      Extracted {len(pdf_text)} chars from PDF")

    if len(pdf_text) >= _MIN_PDF_TEXT_CHARS:
        return extractor.extract_from_text(pdf_text)

    # No usable text layer → scanned/handwritten PDF → vision fallback
    if not _HAS_PYMUPDF:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not extract text from PDF: {filename}. It may be "
                "scanned or handwritten, and PDF image support is not installed."
            ),
        )

    logger.info(
        "      No text layer found — falling back to vision extraction (page images)"
    )
    all_vocab: list = []
    all_grammar: list = []
    with pymupdf.open(stream=contents, filetype="pdf") as doc:
        page_count = min(len(doc), _MAX_VISION_PAGES)
        if len(doc) > _MAX_VISION_PAGES:
            logger.warning(
                f"      PDF has {len(doc)} pages; processing first {_MAX_VISION_PAGES} only"
            )
        for page_num in range(page_count):
            pix = doc[page_num].get_pixmap(dpi=200)
            png_bytes = pix.tobytes("png")
            logger.info(
                f"      Vision extraction: page {page_num + 1}/{page_count} "
                f"({len(png_bytes)} bytes)"
            )
            vocab, grammar = extractor.extract_from_image(png_bytes, "image/png")
            all_vocab.extend(vocab)
            all_grammar.extend(grammar)

    if not all_vocab and not all_grammar:
        raise HTTPException(
            status_code=400,
            detail=f"Could not extract any content from PDF: {filename}",
        )
    return all_vocab, all_grammar


@router.post("/api/upload-notes")
@user_limiter.limit("30/minute")
async def upload_notes(
    request: Request,
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

    logger.info(
        f"{Colors.GREEN}📝 NOTE EXTRACTOR: Processing upload for {lang.name}{Colors.END}"
    )
    logger.info(f"   Native language: {native_lang}")

    extractor = NoteExtractorAgent(tracked_client, lang.name, native_lang)

    all_vocabulary = []
    all_grammar = []
    if files and len(files) > 0 and files[0].filename:
        logger.info(f"   Processing {len(files)} file(s)...")
        for i, file in enumerate(files):
            logger.info(f"      File {i+1}: {file.filename} ({file.content_type})")
            contents = await file.read()
            mime_type = file.content_type or "application/octet-stream"
            try:
                if mime_type == "application/pdf":
                    vocabulary, grammar = _process_pdf(
                        file.filename, contents, extractor
                    )
                else:
                    vocabulary, grammar = extractor.extract_from_image(
                        contents, mime_type
                    )
            except HTTPException:
                raise
            except Exception as exc:
                logger.error(
                    f"      Error processing file {file.filename}: {exc}", exc_info=True
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing {file.filename}: {str(exc)}",
                )
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
        candidate_text = grammar_embed_text(
            gram["concept_name"], gram.get("description", "")
        )
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
            logger.info(
                f"      • {v['target_word']} → {v.get('native_translation', '')}"
            )
        if len(added_vocab) > 5:
            logger.info(f"      ... and {len(added_vocab) - 5} more")

    if added_vocab and background_tasks is not None:
        background_tasks.add_task(rebuild_topics, lang_id, lang.name)
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
