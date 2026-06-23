"""
OpenAI Cost Tracker
Calculates per-call API cost based on model and token/audio/character usage.
Accumulates costs per session and persists UsageLogs to the database.

Pricing as of March 2026 — update the PRICING dict when OpenAI changes rates.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict

from sqlalchemy.orm import Session

from database import UsageLog, User
from agents.logging_utils import Colors, get_logger

logger = get_logger(__name__)

# ── Langfuse observability ──────────────────────────────────────
# Uses the langfuse.openai drop-in replacement for automatic tracing.
# Credentials are read from LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY /
# LANGFUSE_BASE_URL environment variables (set via .env or AWS SSM).


# 100 credits costs $5 (purchase price), but internally equals $4 of API budget.
# Deduction rate: 1 USD of raw API cost = 25 credits charged to user.
CREDITS_PER_API_USD: float = 25.0

# ── Pricing table (USD) ────────────────────────────────────────
# Source: https://openai.com/pricing  (update periodically)

PRICING: Dict[str, dict] = {
    # Chat completion models — price per 1 000 tokens
    # Source: https://developers.openai.com/api/docs/pricing (updated June 2026)
    "gpt-4o": {
        "input_per_1k": 0.0025,
        "output_per_1k": 0.0100,
    },
    "gpt-4o-mini": {
        "input_per_1k": 0.00015,
        "output_per_1k": 0.0006,
    },
    "gpt-4.1": {
        "input_per_1k": 0.002,
        "output_per_1k": 0.008,
    },
    "gpt-4.1-mini": {
        "input_per_1k": 0.0004,
        "output_per_1k": 0.0016,
    },
    # OpenAI Speech-to-text (Whisper) — price per minute of audio (fallback only)
    "whisper-1": {
        "per_minute": 0.006,
    },
    # OpenAI Text-to-speech — price per 1 000 characters (fallback only)
    "tts-1": {
        "per_1k_chars": 0.015,
    },
    "tts-1-hd": {
        "per_1k_chars": 0.030,
    },
}

# ── ElevenLabs pricing (USD) ───────────────────────────────────
# Source: https://elevenlabs.io/pricing/api (updated June 2026)
ELEVENLABS_TTS_PER_1K_CHARS: Dict[str, float] = {
    "eleven_multilingual_v2": 0.10,  # $0.10 / 1k chars
    "eleven_multilingual_v3": 0.10,
    "eleven_flash_v2": 0.05,
    "eleven_turbo_v2": 0.05,
}
ELEVENLABS_TTS_DEFAULT_PER_1K: float = 0.10

# Scribe v1/v2: $0.22 / hour  →  $0.22 / 3600 s  ≈  $0.0000611 / s
ELEVENLABS_STT_PER_SECOND: Dict[str, float] = {
    "scribe_v1": 0.22 / 3600,
    "scribe_v2": 0.22 / 3600,
    "scribe_v2_realtime": 0.39 / 3600,
}
ELEVENLABS_STT_DEFAULT_PER_SECOND: float = 0.22 / 3600


# ── Pure cost calculators ───────────────────────────────────────


def calculate_chat_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return USD cost for a chat completion call."""
    rates = PRICING.get(model)
    if rates is None:
        logger.warning(f"Unknown model '{model}' — assuming gpt-4o pricing")
        rates = PRICING["gpt-4o"]
    cost = (input_tokens / 1000) * rates["input_per_1k"] + (
        output_tokens / 1000
    ) * rates["output_per_1k"]
    return round(cost, 8)


def calculate_stt_cost(audio_seconds: float, model: str = "whisper-1") -> float:
    """Return USD cost for a Whisper STT call."""
    rates = PRICING.get(model, PRICING["whisper-1"])
    cost = (audio_seconds / 60) * rates["per_minute"]
    return round(cost, 8)


def calculate_tts_cost(characters: int, model: str = "tts-1") -> float:
    """Return USD cost for a TTS call."""
    rates = PRICING.get(model, PRICING["tts-1"])
    cost = (characters / 1000) * rates["per_1k_chars"]
    return round(cost, 8)


# ── Session-level cost accumulator ──────────────────────────────


@dataclass
class SessionCostTracker:
    """Accumulates API costs for one conversation session.

    Thread-safe: multiple agent calls can log concurrently.
    """

    user_id: int
    session_id: str
    _total_cost: float = 0.0
    _entries: list = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ── Recording calls ─────────────────────────────────────────

    def record_chat(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Record a chat completion call. Returns its cost."""
        cost = calculate_chat_cost(model, input_tokens, output_tokens)
        with self._lock:
            self._total_cost += cost
            self._entries.append(
                {
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "audio_seconds": 0,
                    "characters": 0,
                    "cost_usd": cost,
                }
            )
        logger.info(
            f"   {Colors.YELLOW}💰 Cost: ${cost:.6f} "
            f"({model} {input_tokens}+{output_tokens} tok){Colors.END}"
        )
        return cost

    def record_stt(
        self,
        audio_seconds: float,
        model: str = "whisper-1",
    ) -> float:
        """Record a Whisper STT call. Returns its cost."""
        cost = calculate_stt_cost(audio_seconds, model)
        with self._lock:
            self._total_cost += cost
            self._entries.append(
                {
                    "model": model,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "audio_seconds": audio_seconds,
                    "characters": 0,
                    "cost_usd": cost,
                }
            )
        logger.info(
            f"   {Colors.YELLOW}💰 Cost: ${cost:.6f} "
            f"({model} {audio_seconds:.1f}s){Colors.END}"
        )
        return cost

    def record_tts(
        self,
        characters: int,
        model: str = "tts-1",
    ) -> float:
        """Record a TTS call. Returns its cost."""
        cost = calculate_tts_cost(characters, model)
        with self._lock:
            self._total_cost += cost
            self._entries.append(
                {
                    "model": model,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "audio_seconds": 0,
                    "characters": characters,
                    "cost_usd": cost,
                }
            )
        logger.info(
            f"   {Colors.YELLOW}💰 Cost: ${cost:.6f} "
            f"({model} {characters} chars){Colors.END}"
        )
        return cost

    # ── Accessors ───────────────────────────────────────────────

    @property
    def total_cost(self) -> float:
        with self._lock:
            return round(self._total_cost, 6)

    # ── Persist to DB & deduct credits ──────────────────────────

    def flush_to_db(self, db: Session) -> float:
        """Write all accumulated entries to usage_logs and deduct from user
        credits. Returns total session cost."""
        with self._lock:
            entries = list(self._entries)
            total = round(self._total_cost, 6)

        for entry in entries:
            log = UsageLog(
                user_id=self.user_id,
                session_id=self.session_id,
                model=entry["model"],
                input_tokens=entry["input_tokens"],
                output_tokens=entry["output_tokens"],
                audio_seconds=entry["audio_seconds"],
                characters=entry["characters"],
                cost_usd=entry["cost_usd"],
            )
            db.add(log)

        # Deduct credits (2× raw cost markup, then convert to credit units)
        charge = round(total * 2 * CREDITS_PER_API_USD, 6)
        user = db.query(User).filter(User.id == self.user_id).first()
        if user:
            user.credits_balance = max(0.0, user.credits_balance - charge)

        db.commit()

        logger.info(
            f"   {Colors.GREEN}💳 Session total: ${total:.4f} "
            f"(charged {charge:.2f} credits){Colors.END}"
        )
        return total


def check_sufficient_credits(user: User, min_credits: float = 1.0) -> bool:
    """Return True if the user has enough credits to start a session."""
    return user.credits_balance >= min_credits


# ── Centralized OpenAI wrapper with automatic cost tracking ─────


class _TrackedChatCompletions:
    """Proxy for client.chat.completions — records cost on every create()."""

    def __init__(self, real_client: "OpenAI", tracker: "TrackedOpenAI"):
        self._real = real_client.chat.completions
        self._tracker = tracker

    def create(self, **kwargs):
        model = kwargs.get("model", "gpt-4o")

        # Inject Langfuse trace attributes so all calls are grouped by session/user.
        # langfuse.openai strips these keys before forwarding to the real API.
        existing_meta = kwargs.get("metadata") or {}
        kwargs["metadata"] = {
            **existing_meta,
            "langfuse_session_id": self._tracker.session_id,
            "langfuse_user_id": str(self._tracker.user_id),
        }

        response = self._real.create(**kwargs)

        if response.usage:
            cost = calculate_chat_cost(
                model, response.usage.prompt_tokens, response.usage.completion_tokens
            )
            self._tracker._record_and_deduct(
                model=model,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                audio_seconds=0,
                characters=0,
                cost=cost,
            )
            logger.info(
                f"   {Colors.YELLOW}💰 Cost: ${cost:.6f} "
                f"({model} {response.usage.prompt_tokens}+{response.usage.completion_tokens} tok){Colors.END}"
            )
        return response


class _TrackedChat:
    """Proxy for client.chat — exposes .completions."""

    def __init__(self, real_client: "OpenAI", tracker: "TrackedOpenAI"):
        self.completions = _TrackedChatCompletions(real_client, tracker)


class _TrackedSpeech:
    """Proxy for client.audio.speech — records TTS cost on every create()."""

    def __init__(self, real_client: "OpenAI", tracker: "TrackedOpenAI"):
        self._real = real_client.audio.speech
        self._tracker = tracker

    def create(self, **kwargs):
        from langfuse import propagate_attributes

        model = kwargs.get("model", "tts-1")
        input_text = kwargs.get("input", "")
        characters = len(input_text)

        with propagate_attributes(
            session_id=self._tracker.session_id,
            user_id=str(self._tracker.user_id),
        ):
            response = self._real.create(**kwargs)

        cost = calculate_tts_cost(characters, model)
        self._tracker._record_and_deduct(
            model=model,
            input_tokens=0,
            output_tokens=0,
            audio_seconds=0,
            characters=characters,
            cost=cost,
        )
        logger.info(
            f"   {Colors.YELLOW}💰 Cost: ${cost:.6f} "
            f"({model} {characters} chars){Colors.END}"
        )
        return response


class _TrackedTranscriptions:
    """Proxy for client.audio.transcriptions — records STT cost on every create()."""

    def __init__(self, real_client: "OpenAI", tracker: "TrackedOpenAI"):
        self._real = real_client.audio.transcriptions
        self._tracker = tracker

    def create(self, **kwargs):
        from langfuse import propagate_attributes

        # Estimate audio duration from file size before the call
        file_obj = kwargs.get("file")
        estimated_seconds = 0.0
        if file_obj is not None:
            if hasattr(file_obj, "getbuffer"):
                estimated_seconds = len(file_obj.getbuffer()) / 2000
            elif hasattr(file_obj, "read"):
                pos = file_obj.tell()
                data = file_obj.read()
                estimated_seconds = len(data) / 2000
                file_obj.seek(pos)

        model = kwargs.get("model", "whisper-1")

        with propagate_attributes(
            session_id=self._tracker.session_id,
            user_id=str(self._tracker.user_id),
        ):
            response = self._real.create(**kwargs)

        cost = calculate_stt_cost(estimated_seconds, model)
        self._tracker._record_and_deduct(
            model=model,
            input_tokens=0,
            output_tokens=0,
            audio_seconds=estimated_seconds,
            characters=0,
            cost=cost,
        )
        logger.info(
            f"   {Colors.YELLOW}💰 Cost: ${cost:.6f} "
            f"({model} {estimated_seconds:.1f}s){Colors.END}"
        )
        return response


class _TrackedAudio:
    """Proxy for client.audio — exposes .speech and .transcriptions."""

    def __init__(self, real_client: "OpenAI", tracker: "TrackedOpenAI"):
        self.speech = _TrackedSpeech(real_client, tracker)
        self.transcriptions = _TrackedTranscriptions(real_client, tracker)


class TrackedOpenAI:
    """Drop-in replacement for ``OpenAI(api_key=...)`` that automatically
    records the cost of every API call, writes a ``UsageLog`` row, and
    immediately deducts credits (cost × 2) from the user's balance.

    Usage::

        client = TrackedOpenAI(api_key, user_id=user.id,
                               session_id=sid, db_factory=SessionLocal)
        # Then use exactly like the normal OpenAI client:
        client.chat.completions.create(model="gpt-4o", messages=[...])
        client.audio.speech.create(model="tts-1", input="hello", voice="nova")
        client.audio.transcriptions.create(model="whisper-1", file=f)
    """

    def __init__(
        self,
        api_key: str,
        *,
        user_id: int,
        session_id: str,
        db_factory,
    ):
        # Use the langfuse.openai drop-in replacement so every OpenAI call is
        # automatically traced. Falls back gracefully when keys are absent.
        try:
            from langfuse.openai import OpenAI as _OpenAI
        except Exception:
            from openai import OpenAI as _OpenAI

        self._real_client = _OpenAI(api_key=api_key)
        self.user_id = user_id
        self.session_id = session_id
        self._db_factory = db_factory

        self._total_cost: float = 0.0
        self._lock = threading.Lock()

        # Expose proxied API namespaces
        self.chat = _TrackedChat(self._real_client, self)
        self.audio = _TrackedAudio(self._real_client, self)

    # ── Internal: atomic log + deduct ──────────────────────────

    def record_elevenlabs_tts(
        self, characters: int, model: str = "eleven_multilingual_v2"
    ) -> float:
        """Record an ElevenLabs TTS call and deduct credits. Returns cost in USD."""
        rate = ELEVENLABS_TTS_PER_1K_CHARS.get(model, ELEVENLABS_TTS_DEFAULT_PER_1K)
        cost = round((characters / 1000) * rate, 8)
        self._record_and_deduct(
            model=f"elevenlabs/{model}",
            input_tokens=0,
            output_tokens=0,
            audio_seconds=0,
            characters=characters,
            cost=cost,
        )
        logger.info(
            f"   {Colors.YELLOW}💰 Cost: ${cost:.6f} (ElevenLabs TTS {characters} chars){Colors.END}"
        )
        return cost

    def record_elevenlabs_stt(
        self, audio_seconds: float, model: str = "scribe_v1"
    ) -> float:
        """Record an ElevenLabs STT call and deduct credits. Returns cost in USD."""
        rate = ELEVENLABS_STT_PER_SECOND.get(model, ELEVENLABS_STT_DEFAULT_PER_SECOND)
        cost = round(audio_seconds * rate, 8)
        self._record_and_deduct(
            model=f"elevenlabs/{model}",
            input_tokens=0,
            output_tokens=0,
            audio_seconds=audio_seconds,
            characters=0,
            cost=cost,
        )
        logger.info(
            f"   {Colors.YELLOW}💰 Cost: ${cost:.6f} (ElevenLabs STT {audio_seconds:.1f}s){Colors.END}"
        )
        return cost

    def _record_and_deduct(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        audio_seconds: float,
        characters: int,
        cost: float,
    ):
        """Write one UsageLog row and deduct credits in a single transaction."""
        charge = round(cost * 5 * CREDITS_PER_API_USD, 6)

        with self._lock:
            self._total_cost += cost

        db = self._db_factory()
        try:
            db.add(
                UsageLog(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    audio_seconds=audio_seconds,
                    characters=characters,
                    cost_usd=cost,
                    charged=charge,
                )
            )
            user = db.query(User).filter(User.id == self.user_id).first()
            if user:
                user.credits_balance = max(0.0, user.credits_balance - charge)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to record cost / deduct credits")
        finally:
            db.close()

    # ── Accessors ──────────────────────────────────────────────

    @property
    def total_cost(self) -> float:
        with self._lock:
            return round(self._total_cost, 6)
