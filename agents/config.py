"""
Central configuration for all agent models and language defaults.
Change settings here to control LLM, TTS, and STT models used across the app.
"""

# ── LLM Models ──────────────────────────────────────────────────
LLM_MODEL = "gpt-4o"

# ── Speech Models ────────────────────────────────────────────────
TTS_MODEL = "tts-1"
TTS_VOICE = "nova"
STT_MODEL = "whisper-1"

# ── Language Defaults ────────────────────────────────────────────
DEFAULT_TARGET_LANGUAGE = "Turkish"
DEFAULT_NATIVE_LANGUAGE = "English"
