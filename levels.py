"""Shared learner-level definitions.

A level is a CEFR band (A1–C2) combined with a sub-level (beginner /
intermediate / advanced), stored as e.g. ``"B1-intermediate"``.
"""

from typing import Optional

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

CEFR_DESCRIPTIONS = {
    "A1": "Beginner",
    "A2": "Elementary",
    "B1": "Intermediate",
    "B2": "Upper Intermediate",
    "C1": "Advanced",
    "C2": "Proficient",
}

SUB_LEVELS = ["beginner", "intermediate", "advanced"]
DEFAULT_SUB_LEVEL = "intermediate"

ALL_LEVELS = [f"{c}-{s}" for c in CEFR_LEVELS for s in SUB_LEVELS]
DEFAULT_LEVEL = "A1-beginner"


def normalize_level(value: Optional[str]) -> Optional[str]:
    """Coerce ``"B1"``, ``"b1 intermediate"``, ``"B1-Advanced"`` etc. to the
    canonical ``"B1-intermediate"`` form. Returns None if unparseable."""
    if not value:
        return None
    parts = str(value).strip().replace("_", " ").replace("-", " ").split()
    if not parts:
        return None
    cefr = parts[0].upper()
    if cefr not in CEFR_LEVELS:
        return None
    sub = parts[1].lower() if len(parts) > 1 else DEFAULT_SUB_LEVEL
    if sub not in SUB_LEVELS:
        return None
    return f"{cefr}-{sub}"


def split_level(level: str):
    """Return (cefr, sub_level) for a level string (falls back to the default)."""
    cefr, sub = (normalize_level(level) or DEFAULT_LEVEL).split("-")
    return cefr, sub


def level_label(level: str) -> str:
    """Human-readable label, e.g. ``"B1 · Intermediate"``."""
    norm = normalize_level(level)
    if not norm:
        return level or "—"
    cefr, sub = norm.split("-")
    return f"{cefr} · {sub.capitalize()}"


def level_prompt_text(level: str) -> str:
    """Rich description suitable for LLM prompts, e.g.
    ``"B1 (Intermediate) — advanced end of the band"``."""
    norm = normalize_level(level) or DEFAULT_LEVEL
    cefr, sub = norm.split("-")
    position = {
        "beginner": "just entering this band; keep to its easier, most common material",
        "intermediate": "solidly within this band",
        "advanced": "at the upper end of this band, approaching the next CEFR level",
    }[sub]
    return f"CEFR {cefr} ({CEFR_DESCRIPTIONS[cefr]}), {sub} sub-level — {position}"


def level_index(level: str) -> int:
    norm = normalize_level(level)
    return ALL_LEVELS.index(norm) if norm in ALL_LEVELS else -1
