"""
Dialogue + Lesson Planning Agent
Handles both lesson planning (theme/goals) and conversation with TTS/STT.
Given randomly-selected vocabulary words, this agent:
  1. Generates a conversation theme and goals in one LLM call.
  2. Produces every response using an agentic tool-calling flow that checks the
     student's vocabulary knowledge base before committing to word choices.
  3. After generation, validates that ≥80% of content words come from the student's
     DB; if not, regenerates once.
  4. Submits the final response to the Level Controller for a single review pass;
     if rejected, regenerates once with the feedback, then accepts.
Language-agnostic: works with any target/native language pair.
"""

import json
import re
import random
from datetime import datetime
from typing import List, Dict, Optional
import io
from sqlalchemy.orm import Session
from agents.config import (
    LLM_MODEL,
    TTS_MODEL,
    TTS_VOICE_ID,
    TTS_VOICE_ID_BY_LANGUAGE,
    STT_MODEL,
    DEFAULT_TARGET_LANGUAGE,
    DEFAULT_NATIVE_LANGUAGE,
)
from agents.logging_utils import (
    Colors,
    get_logger,
    log_section as _log_section,
    call_llm_with_json,
)
from database import SUPPORTED_LANGUAGES, Vocabulary, Grammar
from agents.romanization_utils import romanize_to_finglish as _romanize_to_finglish

logger = get_logger(__name__)


def log_section(title: str):
    """Log a visually distinct section header."""
    _log_section(logger, title)


# Tool schemas passed to the LLM
_DIALOGUE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_practice_words",
            "description": (
                "Return the vocabulary words selected for practice in this session. "
                "Always call this first so you know which words to weave into the conversation."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_words",
            "description": (
                "Check which words from a list exist in the student's vocabulary knowledge base. "
                "Pass all content words you plan to use in your response at once. "
                "Returns 'known' and 'unknown' lists so you can swap out unfamiliar words before responding."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "words": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of target-language content words to look up.",
                    }
                },
                "required": ["words"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_words",
            "description": (
                "Search the student's vocabulary for words containing a substring or matching a concept. "
                "Returns up to 10 matching entries. Useful for finding the right word to use."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Substring or partial word to search for.",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


class DialogueAgent:
    def __init__(
        self,
        client,
        target_language: str = DEFAULT_TARGET_LANGUAGE,
        native_language: str = DEFAULT_NATIVE_LANGUAGE,
        elevenlabs_client=None,
    ):
        self.client = client
        self.elevenlabs_client = elevenlabs_client
        self.model = LLM_MODEL
        self.tts_model = TTS_MODEL
        self.tts_voice_id = TTS_VOICE_ID_BY_LANGUAGE.get(target_language, TTS_VOICE_ID)
        self.stt_model = STT_MODEL

        self.target_language = target_language
        self.native_language = native_language
        self.language_code = SUPPORTED_LANGUAGES.get(target_language, "en")

        self.conversation_history: List[Dict] = []
        self.lesson_plan: Optional[Dict] = None
        self.system_prompt: str = ""
        # In-memory knowledge base index (built at conversation init)
        self._vocab_lookup: Dict[str, Dict] = {}  # target_word.lower() -> entry
        self._vocab_list: List[Dict] = []  # full list for substring search
        self._grammar_list: List[Dict] = []  # grammar concepts

    # ─────────────────────────────────────────────────────────────────────────
    # DB helpers (item selection — merged from LessonPlannerAgent)
    # ─────────────────────────────────────────────────────────────────────────

    def get_all_known_items(
        self, db: Session, language_id: Optional[int] = None
    ) -> Dict:
        """Return ALL vocabulary and grammar the student has learned."""
        query_vocab = db.query(Vocabulary)
        query_grammar = db.query(Grammar)
        if language_id is not None:
            query_vocab = query_vocab.filter(Vocabulary.language_id == language_id)
            query_grammar = query_grammar.filter(Grammar.language_id == language_id)
        all_vocab = query_vocab.all()
        all_grammar = query_grammar.all()
        return {
            "all_vocabulary": [
                {
                    "id": v.id,
                    "target_word": v.target_word,
                    "native_translation": v.native_translation,
                    "example_sentence": v.example_sentence,
                    "fluency_level": v.fluency_level,
                }
                for v in all_vocab
            ],
            "all_grammar": [
                {
                    "id": g.id,
                    "concept_name": g.concept_name,
                    "description": g.description,
                    "examples": g.examples,
                    "fluency_level": g.fluency_level,
                }
                for g in all_grammar
            ],
        }

    def select_items_for_practice(
        self,
        db: Session,
        num_vocab: int = 10,
        num_grammar: int = 2,
        language_id: Optional[int] = None,
    ) -> Dict:
        """Select vocabulary and grammar items for practice using weighted random sampling."""

        def calculate_weight(item) -> float:
            fluency_weights = {"low": 10.0, "medium": 3.0, "high": 1.0}
            weight = fluency_weights.get(item.fluency_level, 5.0)
            if item.last_practiced_at is None:
                weight *= 2.0
            else:
                days_since = (datetime.now() - item.last_practiced_at).days
                if days_since >= 7:
                    weight *= 1.5
                elif days_since >= 3:
                    weight *= 1.2
            if item.times_practiced == 0:
                weight *= 1.3
            elif item.times_practiced < 3:
                weight *= 1.1
            return weight

        def weighted_sample(items, n: int) -> list:
            if len(items) <= n:
                return list(items)
            available = list(zip(items, [calculate_weight(i) for i in items]))
            selected = []
            for _ in range(n):
                if not available:
                    break
                total = sum(w for _, w in available)
                if total == 0:
                    idx = random.randint(0, len(available) - 1)
                else:
                    r = random.uniform(0, total)
                    cumulative = 0
                    idx = 0
                    for i, (_, w) in enumerate(available):
                        cumulative += w
                        if cumulative >= r:
                            idx = i
                            break
                selected.append(available[idx][0])
                available.pop(idx)
            return selected

        query_vocab = db.query(Vocabulary)
        if language_id is not None:
            query_vocab = query_vocab.filter(Vocabulary.language_id == language_id)
        vocab_items = weighted_sample(query_vocab.all(), num_vocab)

        query_grammar = db.query(Grammar)
        if language_id is not None:
            query_grammar = query_grammar.filter(Grammar.language_id == language_id)
        grammar_items = weighted_sample(query_grammar.all(), num_grammar)

        logger.info(f"\n   {Colors.GREEN}✓ Selected Items for Practice:{Colors.END}")
        logger.info(f"   Vocabulary ({len(vocab_items)} items):")
        for v in vocab_items:
            last = (
                v.last_practiced_at.strftime("%m/%d")
                if v.last_practiced_at
                else "Never"
            )
            logger.info(
                f"      • {v.target_word}: {Colors.CYAN}fluency={v.fluency_level}{Colors.END}, last={last}"
            )
        logger.info(f"   Grammar ({len(grammar_items)} items):")
        for g in grammar_items:
            logger.info(
                f"      • {g.concept_name}: {Colors.CYAN}fluency={g.fluency_level}{Colors.END}"
            )

        return {
            "vocabulary": [
                {
                    "id": v.id,
                    "target_word": v.target_word,
                    "native_translation": v.native_translation,
                    "example_sentence": v.example_sentence,
                    "fluency_level": v.fluency_level,
                }
                for v in vocab_items
            ],
            "grammar": [
                {
                    "id": g.id,
                    "concept_name": g.concept_name,
                    "description": g.description,
                    "examples": g.examples,
                    "fluency_level": g.fluency_level,
                }
                for g in grammar_items
            ],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Lesson planning helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_theme(
        self, selected_items: Dict, level: str, theme_hint: str = None
    ) -> Dict:
        """
        Generate a conversation theme and goals from the selected vocabulary/grammar.
        Returns a dict with 'theme', 'conversation_goals', and 'suggested_topics'.
        One LLM call — no iteration.
        """
        vocab_list = "\n".join(
            [
                f"- {v['target_word']} ({v.get('native_translation', '')})"
                for v in selected_items.get("vocabulary", [])
            ]
        )
        grammar_list = (
            "\n".join(
                [f"- {g['concept_name']}" for g in selected_items.get("grammar", [])]
            )
            or "- none specific"
        )

        if theme_hint:
            prompt = (
                f"You are a {self.target_language} tutor. The conversation theme is pre-set: '{theme_hint}'.\n"
                f"Create 2-3 conversation goals for a {level} CEFR student that focus on these items:\n"
                f"VOCABULARY:\n{vocab_list}\nGRAMMAR:\n{grammar_list}\n"
                f'Return JSON: {{"theme": "{theme_hint}", "conversation_goals": [...], "suggested_topics": [...]}}'
            )
        else:
            prompt = (
                f"You are a {self.target_language} tutor. Choose a natural conversation theme suitable "
                f"for a {level} CEFR student that incorporates these vocabulary words.\n"
                f"VOCABULARY TO PRACTICE:\n{vocab_list}\nGRAMMAR TO FOCUS:\n{grammar_list}\n"
                f'Return JSON: {{"theme": "...", "conversation_goals": [...], "suggested_topics": [...]}}'
            )

        return call_llm_with_json(
            self.client.chat.completions.create,
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=512,
            response_format={"type": "json_object"},
        )

    def initialize_conversation(
        self,
        selected_items: Dict,
        all_known_items: Dict = None,
        level: str = "A1",
        theme_hint: str = None,
    ) -> str:
        """
        Initialize a new conversation from randomly-selected vocabulary/grammar items.
        Generates the lesson theme internally (one LLM call) then produces the opening
        message.  The Level Controller reviews the opening exactly once.

        Args:
            selected_items: Vocabulary and grammar chosen for this session.
            all_known_items: ALL vocabulary/grammar the student has learned.
            level: CEFR level (A1–C2).
            theme_hint: Optional pre-determined theme (e.g., from pre-computed topics).
        """
        log_section("🎭 DIALOGUE AGENT: Initializing Conversation")
        logger.info(
            f"{Colors.YELLOW}Target Language:{Colors.END} {self.target_language}"
        )
        logger.info(
            f"{Colors.YELLOW}Native Language:{Colors.END} {self.native_language}"
        )
        logger.info(f"{Colors.YELLOW}CEFR Level:{Colors.END} {level}")

        self.conversation_history = []
        self.level = level
        self.practice_vocabulary = selected_items.get("vocabulary", [])
        self.practice_grammar = selected_items.get("grammar", [])

        # ── Step 1: Generate theme + goals in one call ──────────────────────
        logger.info(f"\n{Colors.YELLOW}📋 Generating lesson theme...{Colors.END}")
        theme_data = self._generate_theme(selected_items, level, theme_hint)
        self.theme = theme_data.get("theme", theme_hint or "General conversation")
        logger.info(f"   Theme: {Colors.BOLD}{self.theme}{Colors.END}")

        # Store the full lesson plan (used by main.py and the end-of-session analysis)
        self.lesson_plan = {
            "theme": self.theme,
            "conversation_goals": theme_data.get("conversation_goals", []),
            "suggested_topics": theme_data.get("suggested_topics", []),
            "difficulty_level": level,
            "selected_items": selected_items,
        }

        # Log selected items
        vocab_items = self.practice_vocabulary
        grammar_items = self.practice_grammar
        logger.info(f"   Vocabulary ({len(vocab_items)} items):")
        for v in vocab_items[:5]:
            logger.info(
                f"      • {v['target_word']} → {v.get('native_translation', '')}"
            )
        if len(vocab_items) > 5:
            logger.info(f"      ... and {len(vocab_items) - 5} more")
        logger.info(f"   Grammar ({len(grammar_items)} items):")
        for g in grammar_items[:3]:
            logger.info(f"      • {g['concept_name']}")

        # ── Step 2: Build vocab index ────────────────────────────────────────
        vocab_source = (
            all_known_items.get("all_vocabulary", [])
            if all_known_items
            else vocab_items
        )
        grammar_source = (
            all_known_items.get("all_grammar", []) if all_known_items else grammar_items
        )
        self._build_vocab_index(vocab_source, grammar_source)
        logger.info(
            f"\n{Colors.BLUE}📚 Knowledge base: {Colors.CYAN}{len(self._vocab_lookup)}{Colors.END}"
            f"{Colors.BLUE} vocab, {Colors.CYAN}{len(self._grammar_list)}{Colors.END}"
            f"{Colors.BLUE} grammar{Colors.END}"
        )

        # ── Step 3: Generate opening message (with 80% coverage check) ──────
        opening_instruction = (
            f"Start a friendly conversation in {self.target_language}. "
            f"Use an appropriate greeting and ask one engaging question related to the theme: {self.theme}."
        )
        logger.info(f"\n{Colors.GREEN}💬 Generating opening message...{Colors.END}")
        opening = self._generate_dialogue_response(
            instruction=opening_instruction, is_opening=True
        )
        opening = opening.replace("[END]", "").strip()

        self.conversation_history.append({"role": "assistant", "content": opening})

        logger.info(
            f"\n{Colors.GREEN}✅ Conversation initialized successfully!{Colors.END}"
        )
        logger.info(
            f"{Colors.BOLD}Opening:{Colors.END} {opening[:150]}{'...' if len(opening) > 150 else ''}"
        )
        return opening

    def initialize_scenario(
        self, scenario: str, all_known_items: Dict = None, level: str = "A1"
    ) -> str:
        """
        Initialize a free-form scenario conversation (no lesson plan).
        Returns the opening message in target language.
        """
        log_section("🎭 DIALOGUE AGENT: Initializing Scenario")
        logger.info(f"{Colors.YELLOW}Scenario:{Colors.END} {scenario[:120]}")
        logger.info(f"{Colors.YELLOW}CEFR Level:{Colors.END} {level}")

        empty_items: Dict = {"vocabulary": [], "grammar": []}
        self.lesson_plan = {"theme": scenario, "selected_items": empty_items}
        self.conversation_history = []
        self.level = level
        self.practice_vocabulary = []
        self.practice_grammar = []
        self.theme = scenario

        vocab_source = (
            all_known_items.get("all_vocabulary", []) if all_known_items else []
        )
        grammar_source = (
            all_known_items.get("all_grammar", []) if all_known_items else []
        )
        self._build_vocab_index(vocab_source, grammar_source)

        opening_instruction = (
            f"Start a conversation in {self.target_language} based on this scenario: {scenario}. "
            f"Play the role described in the scenario and open naturally with an appropriate greeting or line."
        )
        opening = self._generate_dialogue_response(
            instruction=opening_instruction, is_opening=True
        )
        opening = opening.replace("[END]", "").strip()

        self.conversation_history.append({"role": "assistant", "content": opening})
        logger.info(
            f"\n{Colors.GREEN}✅ Scenario initialized successfully!{Colors.END}"
        )
        return opening

    # ─────────────────────────────────────────────────────────────────────────
    # Knowledge base index helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _build_vocab_index(
        self, vocab_list: List[Dict], grammar_list: List[Dict]
    ) -> None:
        """Build in-memory lookup structures from the student's known vocabulary."""
        self._vocab_list = vocab_list
        self._grammar_list = grammar_list
        self._vocab_lookup = {
            v["target_word"].lower(): v for v in vocab_list if v.get("target_word")
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Tool handlers (operate on in-memory index — no DB calls)
    # ─────────────────────────────────────────────────────────────────────────

    def _tool_get_practice_words(self) -> List[Dict]:
        """Return the session's practice vocabulary list."""
        return [
            {
                "target_word": v["target_word"],
                "native_translation": v.get("native_translation", ""),
                "fluency_level": v.get("fluency_level", "low"),
            }
            for v in self.practice_vocabulary
        ]

    def _tool_check_word(self, word: str) -> Dict:
        """Exact then partial match lookup against the in-memory vocab index."""
        key = word.lower().strip()
        if key in self._vocab_lookup:
            entry = self._vocab_lookup[key]
            return {
                "found": True,
                "match_type": "exact",
                "target_word": entry["target_word"],
                "native_translation": entry.get("native_translation", ""),
                "fluency_level": entry.get("fluency_level", "unknown"),
            }
        for known_key, entry in self._vocab_lookup.items():
            if key in known_key or known_key in key:
                return {
                    "found": True,
                    "match_type": "partial",
                    "target_word": entry["target_word"],
                    "native_translation": entry.get("native_translation", ""),
                    "fluency_level": entry.get("fluency_level", "unknown"),
                }
        return {"found": False, "word": word}

    def _tool_check_words(self, words: List[str]) -> Dict:
        """Batch lookup — returns known and unknown words in one pass."""
        known = []
        unknown = []
        for word in words:
            if self._tool_check_word(word)["found"]:
                known.append(word)
            else:
                unknown.append(word)
        return {"known": known, "unknown": unknown}

    def _tool_search_words(self, query: str) -> List[Dict]:
        """Return up to 10 known vocab entries whose target_word contains the query substring."""
        q = query.lower().strip()
        results = [
            {
                "target_word": v["target_word"],
                "native_translation": v.get("native_translation", ""),
                "fluency_level": v.get("fluency_level", "unknown"),
            }
            for v in self._vocab_list
            if q in v.get("target_word", "").lower()
        ]
        return results[:10]

    # ─────────────────────────────────────────────────────────────────────────
    # 70% vocabulary coverage check
    # ─────────────────────────────────────────────────────────────────────────

    def _check_vocab_coverage(self, text: str) -> tuple[float, list[str]]:
        """
        Estimate the fraction of content words in *text* that exist in the
        student's vocabulary knowledge base.

        Content words: tokens with length > 2 (crude proxy to skip articles,
        prepositions, conjunctions).

        Returns (coverage, unknown_words). Coverage is 1.0 when the DB is
        empty or has < 10 entries (no meaningful check possible) or when no
        content words are found; unknown_words is empty in those cases.
        """
        if len(self._vocab_lookup) < 10:
            return 1.0, []
        # Extract tokens preserving original capitalisation to detect proper nouns.
        # A token is treated as a proper noun (and skipped) if it appears capitalised
        # at a non-sentence-start position, i.e. it is preceded by a non-punctuation
        # character in the original text.
        raw_tokens = re.findall(r"\b\w+\b", text)
        proper_nouns: set[str] = set()
        for m in re.finditer(r"(?<=[\w,;:])\s+([A-Z][a-z]+)", text):
            proper_nouns.add(m.group(1).lower())
        content = [
            t.lower()
            for t in raw_tokens
            if len(t) > 2 and t.lower() not in proper_nouns
        ]
        if not content:
            return 1.0, []
        unknown = sorted({t for t in content if not self._tool_check_word(t)["found"]})
        coverage = (len(content) - len(unknown)) / len(content)
        return coverage, unknown

    def _finalize_response(self, content: str, messages: list) -> str:
        """
        Post-generation quality gate: if fewer than 80% of content words come
        from the student's vocabulary DB, ask the agent to regenerate once.
        The second attempt is accepted regardless of its coverage score.
        """
        coverage, unknown_words = self._check_vocab_coverage(content)
        if coverage >= 0.7:
            return content

        logger.info(
            f"   {Colors.YELLOW}⚠ Vocab coverage {coverage:.0%} < 70% — unknown words: {unknown_words}{Colors.END}"
        )
        sample_known = ", ".join(list(self._vocab_lookup.keys())[:20])
        regen_messages = list(messages) + [
            {"role": "assistant", "content": content},
            {
                "role": "user",
                "content": (
                    f"Your response contained words the student does not know yet. "
                    f"Unknown words found: {', '.join(unknown_words)}. "
                    f"Please replace these with simpler words the student already knows. "
                    f"Some known words: {sample_known}"
                ),
            },
        ]
        regen = self.client.chat.completions.create(
            model=self.model,
            messages=regen_messages,
            max_completion_tokens=500,
        )
        revised = regen.choices[0].message.content or content
        logger.info(
            f"   {Colors.CYAN}Coverage-regen response:{Colors.END} {revised[:100]}"
        )
        return revised

    def _dispatch_tool(self, name: str, arguments: Dict) -> str:
        """Route a tool call from the LLM to the correct handler and return JSON string."""
        if name == "get_practice_words":
            result = self._tool_get_practice_words()
        elif name == "check_words":
            result = self._tool_check_words(arguments.get("words", []))
        elif name == "search_words":
            result = self._tool_search_words(arguments.get("query", ""))
        else:
            result = {"error": f"unknown tool: {name}"}
        return json.dumps(result, ensure_ascii=False)

    # ─────────────────────────────────────────────────────────────────────────
    # Agentic response generation
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_dialogue_response(
        self,
        instruction: str = None,
        is_opening: bool = False,
        max_tool_rounds: int = 3,
    ) -> str:
        """
        Generate a dialogue response using an agentic tool-calling flow:
        1. The agent calls get_practice_words to know what to weave into conversation.
        2. The agent calls check_words([...]) with all planned content words at once.
        3. Once satisfied, it produces its final response in the target language.
        """
        logger.info(
            f"\n{Colors.BLUE}🤖 Agentic Dialogue Generation (max {max_tool_rounds} tool rounds):{Colors.END}"
        )

        practice_grammar_str = (
            ", ".join([g["concept_name"] for g in self.practice_grammar])
            if self.practice_grammar
            else "basic grammar appropriate for the student's level"
        )

        has_knowledge_base = bool(self._vocab_lookup)
        kb_instruction = (
            (
                "You have three tools available:\n"
                "  • get_practice_words() — call this FIRST to see which words to practice.\n"
                "  • check_words(words) — pass the FULL list of content words (nouns, verbs, adjectives, "
                "adverbs) you plan to use in your response in a single call. "
                "It returns 'known' and 'unknown' lists. Replace any unknown words with known alternatives "
                "before writing your final response.\n"
                "  • search_words(query) — search the knowledge base for words matching a substring.\n"
                "IMPORTANT: Skip proper nouns (people, places, brands such as 'Merve', 'Istanbul', 'Google') "
                "and basic function words (articles, conjunctions, common prepositions) — "
                "these do not need to be checked.\n"
            )
            if has_knowledge_base
            else (
                "The student's vocabulary knowledge base is empty (new student). "
                "Use only very basic, common words appropriate for an absolute beginner."
            )
        )

        system_prompt = f"""You are a friendly {self.target_language} language tutor having a natural conversation with a student.

CONVERSATION THEME: {self.theme}
STUDENT CEFR LEVEL: {self.level}
GRAMMAR FOCUS: {practice_grammar_str}

{kb_instruction}
Generate your final response ENTIRELY in {self.target_language}.
Do NOT include translations, parenthetical explanations, or romanisations.
Keep sentence complexity and length appropriate for {self.level} level.
Be warm, encouraging, and ask a natural follow-up question when appropriate."""

        messages = [{"role": "system", "content": system_prompt}]

        if is_opening and instruction:
            messages.append({"role": "user", "content": instruction})
        else:
            messages.extend(self.conversation_history)
            if instruction:
                messages.append({"role": "user", "content": instruction})

        tools = _DIALOGUE_TOOLS if has_knowledge_base else None

        for round_num in range(1, max_tool_rounds + 1):
            logger.info(
                f"   {Colors.YELLOW}Round {round_num}/{max_tool_rounds}{Colors.END}"
            )

            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_completion_tokens": 500,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            msg = choice.message

            if choice.finish_reason == "stop" or not getattr(msg, "tool_calls", None):
                content = msg.content or ""
                logger.info(
                    f"   {Colors.GREEN}✓ Final response generated (round {round_num}){Colors.END}"
                )
                logger.info(f"   {Colors.CYAN}Response:{Colors.END} {content}")
                return self._finalize_response(content, messages)

            # Handle tool calls
            messages.append(msg)
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                logger.info(f"      🔧 Tool call: {tc.function.name}({args})")
                tool_result = self._dispatch_tool(tc.function.name, args)
                logger.info(f"         → {tool_result[:120]}")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    }
                )

        # Safety fallback: request final response without tools
        logger.info(
            f"   {Colors.YELLOW}⚠ Max tool rounds reached — requesting final response{Colors.END}"
        )
        messages.append(
            {"role": "user", "content": "Please now produce your final response."}
        )
        response = self.client.chat.completions.create(
            model=self.model, messages=messages, max_completion_tokens=500
        )
        content = response.choices[0].message.content or ""
        return self._finalize_response(content, messages)

    def generate_response(self, user_message: str) -> tuple[str, bool]:
        """
        Generate a response to the user's message in target language.
        Uses two-step flow: dialogue agent generates, level controller reviews/adjusts.
        Returns (response_text, is_conversation_ended)
        """
        log_section("💬 DIALOGUE AGENT: Processing Student Message")
        logger.info(f"{Colors.YELLOW}Student said:{Colors.END} {user_message}")

        self.conversation_history.append({"role": "user", "content": user_message})

        # Check if conversation should end (based on number of exchanges)
        num_exchanges = len(
            [m for m in self.conversation_history if m["role"] == "user"]
        )
        logger.info(f"Conversation exchange #{num_exchanges}")

        # Add end instruction only if we're past 10 exchanges
        end_instruction = None
        if num_exchanges >= 10:
            logger.info(
                f"{Colors.YELLOW}⏰ Exchange limit approaching - may wrap up conversation{Colors.END}"
            )
            end_instruction = "If the conversation feels complete, you may wrap up naturally and add [END] at the end. But if the student is still engaged, continue the conversation."

        # Generate response (80% coverage check built into _generate_dialogue_response)
        response_text = self._generate_dialogue_response(instruction=end_instruction)

        # Check if conversation should end - only force end at 15 exchanges
        is_ended = "[END]" in response_text or num_exchanges >= 15
        response_text = response_text.replace("[END]", "").strip()

        self.conversation_history.append(
            {"role": "assistant", "content": response_text}
        )

        if is_ended:
            logger.info(f"\n{Colors.RED}🏁 Conversation ending{Colors.END}")

        logger.info(
            f"\n{Colors.GREEN}📤 Final tutor response:{Colors.END} {response_text}"
        )

        return response_text, is_ended

    def text_to_speech(self, text: str) -> bytes:
        """
        Convert text in target language to speech using ElevenLabs.
        Falls back to OpenAI TTS if ElevenLabs client is not configured.
        Returns audio bytes (MP3 format).
        """
        import re

        logger.info(f"\n{Colors.BLUE}🔊 TEXT-TO-SPEECH:{Colors.END}")
        logger.info(f"   Input text: {text[:80]}{'...' if len(text) > 80 else ''}")

        clean_text = re.sub(r"\([^)]*\)", "", text).strip() or text.strip() or "..."

        if self.elevenlabs_client is not None:
            logger.info(
                f"   Provider: ElevenLabs | model={self.tts_model} voice={self.tts_voice_id}"
            )
            try:
                audio_generator = self.elevenlabs_client.text_to_speech.convert(
                    voice_id=self.tts_voice_id,
                    text=clean_text,
                    model_id=self.tts_model,
                )
                audio_bytes = b"".join(audio_generator)
                logger.info(
                    f"   {Colors.GREEN}✓ Audio generated:{Colors.END} {len(audio_bytes) / 1024:.1f} KB"
                )
                if hasattr(self.client, "record_elevenlabs_tts"):
                    self.client.record_elevenlabs_tts(len(clean_text), self.tts_model)
                return audio_bytes
            except Exception as e:
                logger.error(f"   {Colors.RED}✗ ElevenLabs TTS error: {e}{Colors.END}")
                return b""
        else:
            # Fallback: OpenAI TTS
            logger.info(f"   Provider: OpenAI TTS (ElevenLabs not configured)")
            try:
                response = self.client.audio.speech.create(
                    model="tts-1", voice="nova", input=clean_text
                )
                logger.info(
                    f"   {Colors.GREEN}✓ Audio generated:{Colors.END} {len(response.content) / 1024:.1f} KB"
                )
                return response.content
            except Exception as e:
                logger.error(f"   {Colors.RED}✗ OpenAI TTS error: {e}{Colors.END}")
                return b""

    def speech_to_text(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        """
        Convert speech to text using ElevenLabs Scribe.
        Falls back to OpenAI Whisper if ElevenLabs client is not configured.
        """
        logger.info(f"\n{Colors.BLUE}🎤 SPEECH-TO-TEXT:{Colors.END}")
        logger.info(f"   Language: {self.language_code} ({self.target_language})")
        logger.info(f"   Audio size: {len(audio_bytes) / 1024:.1f} KB")

        if self.elevenlabs_client is not None:
            logger.info(f"   Provider: ElevenLabs Scribe | model={self.stt_model}")
            try:
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = filename
                response = self.elevenlabs_client.speech_to_text.convert(
                    audio=audio_file,
                    model_id=self.stt_model,
                    language_code=self.language_code,
                )
                text = response.text
                logger.info(f"   {Colors.GREEN}✓ Transcribed:{Colors.END} {text}")
                audio_seconds = len(audio_bytes) / 16000  # ~16kbps estimate
                if hasattr(self.client, "record_elevenlabs_stt"):
                    self.client.record_elevenlabs_stt(audio_seconds, self.stt_model)
                return text
            except Exception as e:
                logger.error(f"   {Colors.RED}✗ ElevenLabs STT error: {e}{Colors.END}")
                return ""
        else:
            # Fallback: OpenAI Whisper
            logger.info(f"   Provider: OpenAI Whisper (ElevenLabs not configured)")
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = filename
            response = self.client.audio.transcriptions.create(
                model="whisper-1", file=audio_file, language=self.language_code
            )
            logger.info(f"   {Colors.GREEN}✓ Transcribed:{Colors.END} {response.text}")
            return response.text

    def get_transcript(self) -> List[Dict]:
        """
        Get the full conversation transcript.
        """
        return self.conversation_history

    def get_transcript_text(self) -> str:
        """
        Get the transcript as formatted text.
        """
        transcript = []
        for msg in self.conversation_history:
            role = "Tutor" if msg["role"] == "assistant" else "Student"
            transcript.append(f"{role}: {msg['content']}")
        return "\n\n".join(transcript)

    def translate_to_native(self, text: str) -> str:
        """
        Translate text from target language to native language.
        Used for showing translations to help learners understand.
        """
        logger.info(f"\n{Colors.BLUE}🌐 TRANSLATION:{Colors.END}")
        logger.info(f"   From: {self.target_language} → To: {self.native_language}")
        logger.info(f"   Input: {text[:60]}{'...' if len(text) > 60 else ''}")

        translation_prompt = f"""Translate the following {self.target_language} text to {self.native_language}.
Provide ONLY the translation, no explanations or notes.

Text to translate:
{text}

Translation:"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": translation_prompt}],
            max_completion_tokens=300,
        )

        translation = response.choices[0].message.content.strip()
        logger.info(f"   {Colors.GREEN}✓ Translation:{Colors.END} {translation}")

        return translation

    def romanize_to_finglish(self, text: str) -> str:
        """
        Romanize Persian text to Finglish (phonetic Latin alphabet representation).
        Only meaningful when target_language is Persian/Farsi.
        """
        return _romanize_to_finglish(self.client, self.model, text)
