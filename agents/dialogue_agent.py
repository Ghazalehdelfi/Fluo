"""
Dialogue Agent
Handles language conversation with TTS output and STT input.
Uses Level Controller to ensure responses match student's knowledge level.
Language-agnostic: works with any target/native language pair.
"""

import json
from typing import List, Dict, Optional, Generator
import io
from agents.level_controller import LevelControllerAgent
from agents.config import (
    LLM_MODEL,
    TTS_MODEL,
    TTS_VOICE,
    STT_MODEL,
    DEFAULT_TARGET_LANGUAGE,
    DEFAULT_NATIVE_LANGUAGE,
)
from agents.logging_utils import Colors, get_logger, log_section as _log_section
from database import SUPPORTED_LANGUAGES

logger = get_logger(__name__)


def log_section(title: str):
    """Log a visually distinct section header."""
    _log_section(logger, title)


class DialogueAgent:
    def __init__(
        self,
        client,
        target_language: str = DEFAULT_TARGET_LANGUAGE,
        native_language: str = DEFAULT_NATIVE_LANGUAGE,
    ):
        self.client = client
        self.model = LLM_MODEL
        self.tts_model = TTS_MODEL
        self.stt_model = STT_MODEL
        self.voice = TTS_VOICE

        self.target_language = target_language
        self.native_language = native_language
        self.language_code = SUPPORTED_LANGUAGES.get(target_language, "en")

        self.conversation_history: List[Dict] = []
        self.lesson_plan: Optional[Dict] = None
        self.system_prompt: str = ""
        self.level_controller: Optional[LevelControllerAgent] = None

    def initialize_conversation(
        self, lesson_plan: Dict, all_known_items: Dict = None, level: str = "A1"
    ) -> str:
        """
        Initialize a new conversation with the lesson plan.
        Returns the opening message in target language.

        Args:
            lesson_plan: The lesson plan with vocabulary/grammar to practice
            all_known_items: ALL vocabulary and grammar the student knows (for level control)
            level: CEFR level (A1, A2, B1, B2, C1, C2)
        """
        log_section("🎭 DIALOGUE AGENT: Initializing Conversation")
        logger.info(
            f"{Colors.YELLOW}Target Language:{Colors.END} {self.target_language}"
        )
        logger.info(
            f"{Colors.YELLOW}Native Language:{Colors.END} {self.native_language}"
        )
        logger.info(f"{Colors.YELLOW}CEFR Level:{Colors.END} {level}")

        self.lesson_plan = lesson_plan
        self.conversation_history = []
        self.level = level

        # Log lesson plan details
        theme = lesson_plan.get("theme", "General conversation")
        vocab_items = lesson_plan["selected_items"]["vocabulary"]
        grammar_items = lesson_plan["selected_items"]["grammar"]

        logger.info(f"\n{Colors.GREEN}📚 Lesson Plan Details:{Colors.END}")
        logger.info(f"   Theme: {Colors.BOLD}{theme}{Colors.END}")
        logger.info(f"   Vocabulary to practice ({len(vocab_items)} items):")
        for v in vocab_items[:5]:  # Show first 5
            logger.info(f"      • {v['target_word']} → {v['native_translation']}")
        if len(vocab_items) > 5:
            logger.info(f"      ... and {len(vocab_items) - 5} more")

        logger.info(f"   Grammar to practice ({len(grammar_items)} items):")
        for g in grammar_items[:3]:  # Show first 3
            logger.info(f"      • {g['concept_name']}")
        if len(grammar_items) > 3:
            logger.info(f"      ... and {len(grammar_items) - 3} more")

        # Initialize level controller with student's complete knowledge and level
        logger.info(f"\n{Colors.BLUE}🎚️  Initializing Level Controller...{Colors.END}")
        self.level_controller = LevelControllerAgent(
            self.client,
            target_language=self.target_language,
            native_language=self.native_language,
        )
        self.level_controller.set_level(level)
        logger.info(f"   Level set to: {Colors.BOLD}{level}{Colors.END}")

        if all_known_items:
            all_vocab_count = len(all_known_items.get("all_vocabulary", []))
            all_grammar_count = len(all_known_items.get("all_grammar", []))
            logger.info(
                f"   Student's total knowledge: {Colors.CYAN}{all_vocab_count}{Colors.END} vocab items, {Colors.CYAN}{all_grammar_count}{Colors.END} grammar concepts"
            )
            self.level_controller.set_student_knowledge(
                all_vocabulary=all_known_items.get("all_vocabulary", []),
                all_grammar=all_known_items.get("all_grammar", []),
                practice_vocabulary=lesson_plan["selected_items"]["vocabulary"],
                practice_grammar=lesson_plan["selected_items"]["grammar"],
            )
        else:
            # Fallback: use only the practice items
            logger.info(
                f"   {Colors.YELLOW}Using practice items only (no full knowledge provided){Colors.END}"
            )
            self.level_controller.set_student_knowledge(
                all_vocabulary=lesson_plan["selected_items"]["vocabulary"],
                all_grammar=lesson_plan["selected_items"]["grammar"],
                practice_vocabulary=lesson_plan["selected_items"]["vocabulary"],
                practice_grammar=lesson_plan["selected_items"]["grammar"],
            )

        # Store practice items for dialogue generation
        self.practice_vocabulary = lesson_plan["selected_items"]["vocabulary"]
        self.practice_grammar = lesson_plan["selected_items"]["grammar"]
        self.theme = lesson_plan.get("theme", "General conversation")

        # Generate opening message (dialogue agent generates, level controller reviews)
        logger.info(f"\n{Colors.GREEN}💬 Generating opening message...{Colors.END}")
        opening = self._generate_dialogue_response(
            instruction=f"Start a friendly conversation in {self.target_language}. Use an appropriate greeting and ask one engaging question related to the theme: {self.theme}.",
            is_opening=True,
        )

        # Remove any [END] from opening
        opening = opening.replace("[END]", "").strip()

        self.conversation_history.append({"role": "assistant", "content": opening})

        logger.info(
            f"\n{Colors.GREEN}✅ Conversation initialized successfully!{Colors.END}"
        )
        logger.info(
            f"{Colors.BOLD}Opening message:{Colors.END} {opening[:150]}{'...' if len(opening) > 150 else ''}"
        )

        return opening

    def initialize_scenario(
        self, scenario: str, all_known_items: Dict = None, level: str = "A1"
    ) -> str:
        """
        Initialize a free-form scenario conversation (no lesson plan).
        The user describes the scenario they want to practice.
        Returns the opening message in target language.
        """
        log_section("🎭 DIALOGUE AGENT: Initializing Scenario")
        logger.info(
            f"{Colors.YELLOW}Scenario:{Colors.END} {scenario[:120]}"
        )
        logger.info(f"{Colors.YELLOW}CEFR Level:{Colors.END} {level}")

        self.lesson_plan = {
            "theme": scenario,
            "selected_items": {"vocabulary": [], "grammar": []},
        }
        self.conversation_history = []
        self.level = level
        self.practice_vocabulary = []
        self.practice_grammar = []
        self.theme = scenario

        # Initialize level controller
        self.level_controller = LevelControllerAgent(
            self.client,
            target_language=self.target_language,
            native_language=self.native_language,
        )
        self.level_controller.set_level(level)

        if all_known_items:
            self.level_controller.set_student_knowledge(
                all_vocabulary=all_known_items.get("all_vocabulary", []),
                all_grammar=all_known_items.get("all_grammar", []),
                practice_vocabulary=[],
                practice_grammar=[],
            )

        # Generate opening message based on the scenario
        opening = self._generate_dialogue_response(
            instruction=f"Start a conversation in {self.target_language} based on this scenario: {scenario}. "
            f"Play the role described in the scenario and open naturally with an appropriate greeting or line.",
            is_opening=True,
        )

        opening = opening.replace("[END]", "").strip()
        self.conversation_history.append({"role": "assistant", "content": opening})

        logger.info(
            f"\n{Colors.GREEN}✅ Scenario initialized successfully!{Colors.END}"
        )

        return opening

    def _generate_dialogue_response(
        self, instruction: str = None, is_opening: bool = False, max_iterations: int = 2
    ) -> str:
        """
        Generate a dialogue response using a generate → review → regenerate feedback loop:
        1. Dialogue Agent generates a natural response based on conversation context
        2. Level Controller reviews it and returns feedback (not a rewritten sentence)
        3. If not approved, Dialogue Agent regenerates incorporating the feedback
        4. Repeat until approved or max iterations reached

        The Level Controller never writes conversation text — it only critiques.
        The Dialogue Agent owns all generation because it has the conversation context.

        Returns the final approved (or best-effort) response.
        """
        logger.info(
            f"\n{Colors.BLUE}🔄 Generate→Review Feedback Loop (max {max_iterations} iterations):{Colors.END}"
        )

        # Build practice vocabulary context for dialogue generation
        practice_vocab_str = (
            ", ".join(
                [
                    f"{v['target_word']} ({v['native_translation']})"
                    for v in self.practice_vocabulary
                ]
            )
            if self.practice_vocabulary
            else "general vocabulary"
        )

        practice_grammar_str = (
            ", ".join([g["concept_name"] for g in self.practice_grammar])
            if self.practice_grammar
            else "basic grammar"
        )

        feedback_so_far = ""  # Accumulates feedback across iterations

        for iteration in range(1, max_iterations + 1):
            # ── Step 1: Dialogue Agent generates ─────────────────────────
            logger.info(
                f"\n   {Colors.YELLOW}Iteration {iteration}/{max_iterations} — Generating...{Colors.END}"
            )
            logger.info(f"      Theme: {self.theme}")

            feedback_section = ""
            if feedback_so_far:
                feedback_section = f"""

IMPORTANT — LEVEL CONTROLLER FEEDBACK (you MUST address these issues):
{feedback_so_far}

Regenerate your response fixing the issues above while keeping the same conversational intent."""

            dialogue_system_prompt = f"""You are a friendly {self.target_language} language tutor having a conversation with a student.

CONVERSATION THEME: {self.theme}
TARGET LANGUAGE: {self.target_language}
STUDENT LEVEL: {self.level}

Your role is to:
1. Have a natural, engaging conversation in {self.target_language}
2. Create opportunities for the student to use these practice words: {practice_vocab_str}
3. Keep the conversation flowing and ask follow-up questions
4. Be encouraging and respond naturally to what the student says

GRAMMAR FOCUS: {practice_grammar_str}

Generate your response entirely in {self.target_language}. Be conversational and natural.
Do NOT include translations or parenthetical explanations.
Keep sentence complexity appropriate for {self.level} level.{feedback_section}"""

            messages = [{"role": "system", "content": dialogue_system_prompt}]

            if is_opening and instruction:
                messages.append({"role": "user", "content": instruction})
            else:
                messages.extend(self.conversation_history)
                if instruction:
                    messages.append({"role": "user", "content": instruction})

            logger.info(f"      Calling OpenAI API ({self.model})...")
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, max_completion_tokens=300
            )
            current_response = response.choices[0].message.content
            logger.info(f"      {Colors.GREEN}✓ Response generated{Colors.END}")
            logger.info(f"      {Colors.CYAN}Response:{Colors.END} {current_response}")

            # Strip [END] before sending to level controller
            has_end_marker = "[END]" in current_response
            response_for_review = current_response.replace("[END]", "").strip()

            # ── Step 2: Level Controller reviews ─────────────────────────
            logger.info(
                f"\n   {Colors.YELLOW}Iteration {iteration}/{max_iterations} — Level Controller reviewing...{Colors.END}"
            )
            review = self.level_controller.review_response(
                response=response_for_review,
                conversation_history=self.conversation_history,
            )

            if review["approved"]:
                logger.info(
                    f"      {Colors.GREEN}✓ Approved on iteration {iteration}{Colors.END}"
                )
                final = response_for_review
                if has_end_marker:
                    final += " [END]"
                return final

            # Not approved — accumulate feedback for next iteration
            feedback_so_far = review["feedback"]
            logger.info(
                f"      {Colors.YELLOW}✗ Not approved — feeding back to dialogue agent{Colors.END}"
            )

        # Max iterations reached — use the last generated response as best effort
        logger.info(
            f"\n   {Colors.YELLOW}⚠ Max iterations reached — using last response as best effort{Colors.END}"
        )
        final = response_for_review
        if has_end_marker:
            final += " [END]"
        return final

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

        # Generate response using generate-review flow
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
        Convert text in target language to speech.
        Returns audio bytes (MP3 format).
        """
        logger.info(f"\n{Colors.BLUE}🔊 TEXT-TO-SPEECH:{Colors.END}")
        logger.info(f"   Model: {self.tts_model}, Voice: {self.voice}")
        logger.info(f"   Input text: {text[:80]}{'...' if len(text) > 80 else ''}")

        # Remove any translations in parentheses for cleaner speech
        import re

        clean_text = re.sub(r"\([^)]*\)", "", text).strip()

        # If text is empty after cleaning, use original text
        if not clean_text:
            clean_text = text.strip() if text.strip() else "..."

        try:
            logger.info(f"   Calling OpenAI TTS API...")
            response = self.client.audio.speech.create(
                model=self.tts_model, voice=self.voice, input=clean_text
            )
            audio_size = len(response.content)
            logger.info(
                f"   {Colors.GREEN}✓ Audio generated:{Colors.END} {audio_size / 1024:.1f} KB"
            )
            return response.content
        except Exception as e:
            logger.error(f"   {Colors.RED}✗ TTS error: {e}{Colors.END}")
            # Return empty audio bytes on error
            return b""

    def speech_to_text(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        """
        Convert speech to text using Whisper.
        Uses the configured target language for better accuracy.
        """
        logger.info(f"\n{Colors.BLUE}🎤 SPEECH-TO-TEXT:{Colors.END}")
        logger.info(f"   Model: {self.stt_model}")
        logger.info(f"   Language: {self.language_code} ({self.target_language})")
        logger.info(f"   Audio size: {len(audio_bytes) / 1024:.1f} KB")

        # Create a file-like object from bytes
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        logger.info(f"   Calling OpenAI Whisper API...")
        response = self.client.audio.transcriptions.create(
            model=self.stt_model, file=audio_file, language=self.language_code
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
