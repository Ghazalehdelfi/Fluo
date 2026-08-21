"""
Shared text romanization helpers.

Currently supports Finglish — the informal phonetic Latin-alphabet
romanization used by Persian (Farsi) speakers online.
"""

import re
from typing import Dict, List, Optional

from agents.logging_utils import Colors, get_logger, call_llm_with_json

logger = get_logger(__name__)

PERSIAN_LANGUAGE_NAMES = {"persian", "farsi"}

# Arabic/Persian script Unicode ranges (includes Persian-specific letters,
# presentation forms and superscript alef)
_PERSIAN_SCRIPT_RE = re.compile(
    "[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]"
)


def contains_persian_script(text: str) -> bool:
    """Return True if the text contains any Arabic/Persian-script characters."""
    return bool(text) and bool(_PERSIAN_SCRIPT_RE.search(text))


def is_persian(language_name: str) -> bool:
    """Return True if the language name refers to Persian/Farsi."""
    return (language_name or "").strip().lower() in PERSIAN_LANGUAGE_NAMES


def romanize_to_finglish(client, model: str, text: str) -> str:
    """Romanize Persian text to Finglish (phonetic Latin representation)."""
    logger.info(f"\n{Colors.BLUE}🔤 FINGLISH ROMANIZATION:{Colors.END}")
    logger.info(f"   Input: {text[:60]}{'...' if len(text) > 60 else ''}")

    prompt = f"""Transliterate the following Persian (Farsi) text into Finglish — the informal phonetic romanization used by Persian speakers online (e.g. سلام → salam, چطوری → chetori, ممنون → mamnoon).

Rules:
- Write each word as it sounds phonetically using the Latin alphabet
- Do NOT translate, only transliterate sound by sound
- Preserve punctuation and sentence structure
- Use common Finglish conventions (e.g. kh, gh, sh, ch)

Persian text:
{text}

Finglish:"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=300,
    )

    romanized = response.choices[0].message.content.strip()
    logger.info(f"   {Colors.GREEN}✓ Finglish:{Colors.END} {romanized}")

    return romanized


def romanize_question_finglish(
    client,
    model: str,
    question_text: str,
    options: Optional[List[str]] = None,
) -> Dict:
    """Romanize a placement-test question (and its options) into Finglish.

    Handles mixed-language content: only Persian parts are transliterated,
    other text (e.g. English instructions) is kept unchanged.

    Returns dict with: question_finglish (str|None), options_finglish (list|None)
    """
    options = [o for o in (options or []) if o]

    # Nothing to romanize if there is no Persian script at all (e.g. the
    # question is fully in English) — skip the LLM call entirely.
    if not contains_persian_script(question_text) and not any(
        contains_persian_script(o) for o in options
    ):
        return {"question_finglish": None, "options_finglish": None}

    logger.info(
        f"\n{Colors.BLUE}🔤 FINGLISH ROMANIZATION (placement question):{Colors.END}"
    )
    logger.info(f"   Input: {question_text[:60]}{'...' if len(question_text) > 60 else ''}")

    options_block = ""
    options_schema = ""
    if options:
        numbered = "\n".join(f"{i + 1}. {o}" for i, o in enumerate(options))
        options_block = f"\n\nAnswer options:\n{numbered}"
        options_schema = """,
    "options_finglish": ["Finglish for option 1", "..."]  // same order and count as the options above"""

    prompt = f"""Transliterate the Persian (Farsi) parts of the following placement-test content into Finglish — the informal phonetic romanization used by Persian speakers online (e.g. سلام → salam, چطوری → chetori, ممنون → mamnoon).

Rules:
- Write each Persian word as it sounds phonetically using the Latin alphabet
- Do NOT translate, only transliterate sound by sound
- Keep any non-Persian text (e.g. English instructions) unchanged
- Preserve punctuation and sentence structure
- Use common Finglish conventions (e.g. kh, gh, sh, ch)

Question text:
{question_text}{options_block}

Return valid JSON:
{{
    "question_finglish": "The question text with Persian parts in Finglish"{options_schema}
}}

Return ONLY the JSON, no extra text."""

    result = call_llm_with_json(
        client.chat.completions.create,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=600,
        response_format={"type": "json_object"},
    )

    question_finglish = (result.get("question_finglish") or "").strip() or None
    options_finglish = result.get("options_finglish")
    if not isinstance(options_finglish, list) or len(options_finglish) != len(options):
        options_finglish = None

    logger.info(f"   {Colors.GREEN}✓ Finglish:{Colors.END} {question_finglish}")

    return {
        "question_finglish": question_finglish,
        "options_finglish": options_finglish,
    }
