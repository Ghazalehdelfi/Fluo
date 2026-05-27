"""
Placement Test Agent
Adaptive placement test that determines a user's CEFR level, then generates
starter vocabulary and grammar content at the appropriate level.
Language-agnostic: works with any target/native language pair.
"""

import json
from typing import Dict, List, Optional
from agents.config import LLM_MODEL, DEFAULT_TARGET_LANGUAGE, DEFAULT_NATIVE_LANGUAGE
from agents.logging_utils import Colors, get_logger

logger = get_logger(__name__)

# CEFR levels in order of difficulty
CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

LEVEL_DESCRIPTIONS = {
    "A1": "Beginner",
    "A2": "Elementary",
    "B1": "Intermediate",
    "B2": "Upper Intermediate",
    "C1": "Advanced",
    "C2": "Proficient",
}

# How many questions per level during the adaptive test
QUESTIONS_PER_LEVEL = 3
# Minimum accuracy to advance to next level
ADVANCE_THRESHOLD = 0.6


class PlacementTestAgent:
    def __init__(
        self,
        client,
        target_language: str = DEFAULT_TARGET_LANGUAGE,
        native_language: str = DEFAULT_NATIVE_LANGUAGE,
    ):
        self.client = client
        self.model = LLM_MODEL
        self.target_language = target_language
        self.native_language = native_language

    # ── Question Generation ─────────────────────────────────────

    def generate_question(self, level: str, previous_questions: List[Dict]) -> Dict:
        """Generate a single placement test question at the given CEFR level.

        Returns dict with: question, type, options (for mc), level, correct_answer
        """
        logger.info(
            f"   {Colors.CYAN}Generating {level} question for {self.target_language}...{Colors.END}"
        )

        prev_summary = ""
        if previous_questions:
            prev_items = [q.get("question", "") for q in previous_questions[-6:]]
            prev_summary = (
                "\n\nPrevious questions already asked (do NOT repeat similar content):\n"
                + "\n".join(f"- {q}" for q in prev_items)
            )

        prompt = f"""You are an expert {self.target_language} language examiner creating a placement test.

Generate ONE question at CEFR level {level} ({LEVEL_DESCRIPTIONS[level]}) for a student whose native language is {self.native_language}.

CEFR Level Guidelines:
- A1: Very basic phrases, greetings, simple present, concrete nouns
- A2: Simple past, everyday vocabulary, routine tasks
- B1: Multiple tenses, abstract concepts, opinions, experiences
- B2: Complex grammar, nuanced vocabulary, passive voice, conditionals
- C1: Sophisticated structures, idioms, subtle distinctions
- C2: Near-native mastery, rare forms, literary expressions

Question types to choose from:
1. "multiple_choice" — A {self.target_language} sentence/word with 4 options (for translation or meaning)
2. "translation" — Translate a {self.native_language} sentence into {self.target_language}
3. "fill_in_blank" — Complete a {self.target_language} sentence with the missing word

Mix question types. Make questions clearly match the {level} level — not easier, not harder.
{prev_summary}

Return valid JSON:
{{
    "question": "The question text to display to the user",
    "type": "multiple_choice" | "translation" | "fill_in_blank",
    "options": ["A", "B", "C", "D"],  // only for multiple_choice, otherwise omit
    "correct_answer": "The correct answer",
    "hint": "A brief hint in {self.native_language} about what's being tested"
}}

Return ONLY the JSON, no extra text."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=500,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        result["level"] = level
        logger.info(
            f"   {Colors.GREEN}✓ Generated {result.get('type', '?')} question at {level}{Colors.END}"
        )
        return result

    # ── Answer Evaluation ───────────────────────────────────────

    def evaluate_answer(self, question: Dict, user_answer: str) -> Dict:
        """Evaluate the user's answer to a placement test question.

        Returns dict with: correct (bool), explanation (str)
        """
        logger.info(f"   {Colors.CYAN}Evaluating answer...{Colors.END}")

        prompt = f"""You are an expert {self.target_language} language examiner evaluating a student's answer.

Question: {question['question']}
Question type: {question['type']}
Correct answer: {question['correct_answer']}
Student's answer: {user_answer}

Evaluate whether the student's answer is correct or acceptably correct.
For translation questions, accept reasonable alternative translations that convey the same meaning.
For fill-in-the-blank, accept answers that are grammatically and semantically correct even if slightly different from the expected answer.

Return valid JSON:
{{
    "correct": true or false,
    "explanation": "Brief explanation in {self.native_language} of why the answer is correct or what the correct answer should be"
}}

Return ONLY the JSON, no extra text."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=300,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        status = "✓ Correct" if result.get("correct") else "✗ Incorrect"
        logger.info(f"   {Colors.GREEN}{status}{Colors.END}")
        return result

    # ── Level Determination ─────────────────────────────────────

    def determine_level(self, question_results: List[Dict]) -> str:
        """Determine CEFR level from question results.

        Uses highest level where the student got >= 60% correct.
        """
        # Group results by level
        level_scores = {}
        for r in question_results:
            lvl = r.get("level", "A1")
            if lvl not in level_scores:
                level_scores[lvl] = {"correct": 0, "total": 0}
            level_scores[lvl]["total"] += 1
            if r.get("correct"):
                level_scores[lvl]["correct"] += 1

        # Find highest level with >= 60% accuracy
        determined = "A1"
        for lvl in CEFR_LEVELS:
            scores = level_scores.get(lvl)
            if scores and scores["total"] > 0:
                accuracy = scores["correct"] / scores["total"]
                if accuracy >= ADVANCE_THRESHOLD:
                    determined = lvl
                else:
                    break  # Stop at the first level they fail
            else:
                break  # No questions asked at this level

        logger.info(
            f"   {Colors.GREEN}✓ Determined level: {determined} ({LEVEL_DESCRIPTIONS[determined]}){Colors.END}"
        )
        return determined

    # ── Starter Content Generation ──────────────────────────────

    def generate_starter_content(self, level: str) -> Dict:
        """Generate 100 vocabulary words and 10 grammar rules at the given CEFR level.

        Returns dict with 'vocabulary' list and 'grammar' list matching the
        existing note_extractor schema.
        """
        logger.info(
            f"   {Colors.CYAN}Generating starter content at {level} for {self.target_language}...{Colors.END}"
        )

        # Split into two calls to stay within token limits and get better quality

        # --- Vocabulary (two batches of 50) ---
        all_vocab = []
        for batch in range(2):
            batch_num = batch + 1
            exclude_words = ""
            if all_vocab:
                existing = ", ".join(v["target_word"] for v in all_vocab)
                exclude_words = f"\n\nDo NOT include any of these words (already generated): {existing}"

            vocab_prompt = f"""You are an expert {self.target_language} language teacher creating a starter vocabulary set.

Generate exactly 50 vocabulary words appropriate for a {level} ({LEVEL_DESCRIPTIONS[level]}) level student.
This is batch {batch_num} of 2 — provide different words from batch 1.

The student's native language is {self.native_language}.

Requirements:
- Words should be useful, common, and appropriate for the {level} CEFR level
- Include a mix of nouns, verbs, adjectives, and useful phrases
- Cover everyday topics: greetings, food, family, work, travel, etc.
- Example sentences should use grammar appropriate for {level} level
{exclude_words}

Return valid JSON:
{{
    "vocabulary": [
        {{
            "target_word": "the {self.target_language} word",
            "native_translation": "{self.native_language} meaning",
            "example_sentence": "A simple example sentence using this word at {level} level"
        }}
    ]
}}

Return exactly 50 items. Return ONLY valid JSON."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": vocab_prompt}],
                max_completion_tokens=8000,
                response_format={"type": "json_object"},
            )

            batch_result = json.loads(response.choices[0].message.content)
            batch_vocab = batch_result.get("vocabulary", [])
            all_vocab.extend(batch_vocab)
            logger.info(
                f"   {Colors.GREEN}✓ Vocabulary batch {batch_num}: {len(batch_vocab)} words{Colors.END}"
            )

        # --- Grammar ---
        grammar_prompt = f"""You are an expert {self.target_language} language teacher creating a starter grammar set.

Generate exactly 10 grammar rules/concepts appropriate for a {level} ({LEVEL_DESCRIPTIONS[level]}) level student.
The student's native language is {self.native_language}.

Requirements:
- Grammar concepts should be essential for the {level} level
- Progress from simpler to more complex within the level
- Include clear descriptions and multiple examples
- Examples should be in {self.target_language} with {self.native_language} translations in parentheses
- CRITICAL: Every concept must be DISTINCT. Do NOT generate overlapping or near-duplicate rules.
  For example, do NOT include both "Present Tense" and "Simple Present Tense" — pick one.
  Each concept should cover a clearly different grammatical topic from all others in the list.
- Review your list before returning and merge or remove any concepts that are too similar to each other.

Return valid JSON:
{{
    "grammar": [
        {{
            "concept_name": "Name of the grammar concept",
            "description": "Clear explanation of the rule in {self.native_language}",
            "examples": "2-3 example sentences in {self.target_language} (with {self.native_language} translation)"
        }}
    ]
}}

Return exactly 10 items. Return ONLY valid JSON."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": grammar_prompt}],
            max_completion_tokens=4000,
            response_format={"type": "json_object"},
        )

        grammar_result = json.loads(response.choices[0].message.content)
        grammar = grammar_result.get("grammar", [])

        logger.info(
            f"   {Colors.GREEN}✓ Generated {len(all_vocab)} vocab + {len(grammar)} grammar at {level}{Colors.END}"
        )

        return {"vocabulary": all_vocab, "grammar": grammar}
