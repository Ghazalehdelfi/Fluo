"""
Central configuration for all agent models and language defaults.
Change settings here to control LLM, TTS, and STT models used across the app.
"""

# ── LLM Models ──────────────────────────────────────────────────
LLM_MODEL = "gpt-4.1"

# ── ElevenLabs Speech Models ─────────────────────────────────────
# TTS: eleven_multilingual_v2 supports all target languages with high naturalness
TTS_MODEL = "eleven_multilingual_v2"
# Default voice ID — can be overridden per deployment.
# "Sarah" (EXAVITQu4vr4xnSDxMaL) is a multilingual voice that works well for language tutoring.
TTS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"
# Per-language voice overrides (takes priority over TTS_VOICE_ID when matched)
TTS_VOICE_ID_BY_LANGUAGE: dict = {
    "Turkish": "Q5n6GDIjpN0pLOlycRFT",
    "Spanish": "FXGrCtY3PEyfqczBAlqm",
    "French": "aQROLel5sQbj1vuIVi6B",
    "Korean": "uyVNoMrnUku1dZyVEXwD",
    "Japanese": "3JDquces8E8bkmvbh6Bc",
    "German": "FTNCalFNG5bRnkkaP5Ug",
}
# STT: Scribe v1 — ElevenLabs speech-to-text with strong multilingual accuracy
STT_MODEL = "scribe_v1"

# ── Language Defaults ────────────────────────────────────────────
DEFAULT_TARGET_LANGUAGE = "Turkish"
DEFAULT_NATIVE_LANGUAGE = "English"
