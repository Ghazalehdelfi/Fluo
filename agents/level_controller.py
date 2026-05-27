"""
Level Control Agent
Reviews and simplifies dialogue to match the student's actual knowledge level.
Ensures conversations only use vocabulary and grammar the student has learned.
Controls grammar complexity - defaults to basic present tense unless grammar is learned.
Language-agnostic: works with any target/native language pair.
"""

import json
from typing import Dict, List
from agents.config import LLM_MODEL, DEFAULT_TARGET_LANGUAGE, DEFAULT_NATIVE_LANGUAGE
from agents.logging_utils import Colors, get_logger

logger = get_logger(__name__)


class LevelControllerAgent:
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
        self.known_vocabulary: List[Dict] = []
        self.known_grammar: List[Dict] = []
        self.practice_vocabulary: List[Dict] = []  # Low fluency - to practice
        self.practice_grammar: List[Dict] = []  # Low fluency grammar to practice
        self.fluent_grammar: List[Dict] = []  # High fluency grammar (can use freely)
        self.comfort_vocabulary: List[Dict] = (
            []
        )  # Medium/high fluency - for flexibility
        self.level: str = "A1"  # CEFR level

        # CEFR level guidelines (language-agnostic)
        self.level_guidelines = {
            "A1": {
                "name": "Beginner",
                "sentence_length": "2-5 words",
                "grammar": "Simple present only, basic existence forms, simple questions",
                "vocab_complexity": "Most common words, concrete nouns",
                "topics": "Greetings, introductions, basic questions",
                "style": "Very slow, repetitive, lots of cognates and hints",
            },
            "A2": {
                "name": "Elementary",
                "sentence_length": "4-7 words",
                "grammar": "Present tense, simple past, basic connectors",
                "vocab_complexity": "Common everyday vocabulary",
                "topics": "Daily activities, family, shopping, directions",
                "style": "Simple but more natural flow",
            },
            "B1": {
                "name": "Intermediate",
                "sentence_length": "5-10 words",
                "grammar": "All basic tenses, progressive aspects, basic conditionals",
                "vocab_complexity": "Abstract concepts, idiomatic expressions",
                "topics": "Work, travel, opinions, experiences",
                "style": "Natural conversation with some complexity",
            },
            "B2": {
                "name": "Upper Intermediate",
                "sentence_length": "8-15 words",
                "grammar": "Complex tenses, passive, causative, relative clauses",
                "vocab_complexity": "Nuanced vocabulary, formal/informal register",
                "topics": "Current events, culture, detailed descriptions",
                "style": "Fluent conversation, can handle nuance",
            },
            "C1": {
                "name": "Advanced",
                "sentence_length": "10-20 words",
                "grammar": "All structures including literary forms",
                "vocab_complexity": "Sophisticated vocabulary, idioms, slang",
                "topics": "Complex topics, humor, cultural nuance",
                "style": "Near-native interaction",
            },
            "C2": {
                "name": "Proficient",
                "sentence_length": "Unlimited",
                "grammar": "Full mastery including rare forms",
                "vocab_complexity": "Full range including archaic, poetic",
                "topics": "Any topic at native level",
                "style": "Indistinguishable from native speaker",
            },
        }

    def set_level(self, level: str):
        """Set the CEFR level for conversation complexity."""
        if level in self.level_guidelines:
            self.level = level
        else:
            self.level = "A1"  # Default to beginner

    def set_student_knowledge(
        self,
        all_vocabulary: List[Dict],
        all_grammar: List[Dict],
        practice_vocabulary: List[Dict],
        practice_grammar: List[Dict],
    ):
        """
        Set what the student knows. Assume they ONLY know these words/concepts.

        Args:
            all_vocabulary: ALL vocabulary the student has learned
            all_grammar: ALL grammar concepts the student has learned
            practice_vocabulary: Subset of vocab to actively practice (low fluency)
            practice_grammar: Subset of grammar to actively practice (low fluency)
        """
        self.known_vocabulary = all_vocabulary
        self.known_grammar = all_grammar
        self.practice_vocabulary = practice_vocabulary
        self.practice_grammar = practice_grammar

        # Comfort vocabulary = all known vocab minus the practice vocab
        practice_words = {v["target_word"].lower() for v in practice_vocabulary}
        self.comfort_vocabulary = [
            v for v in all_vocabulary if v["target_word"].lower() not in practice_words
        ]

        # Fluent grammar = grammar with high fluency (can use freely in conversations)
        self.fluent_grammar = [
            g for g in all_grammar if g.get("fluency_level") == "high"
        ]

    def get_vocabulary_context(self) -> str:
        """Generate a context string of all known vocabulary for the LLM."""
        practice_list = (
            "\n".join(
                [
                    f"  - {v['target_word']} = {v['native_translation']} [PRACTICE - MUST KEEP!]"
                    for v in self.practice_vocabulary
                ]
            )
            if self.practice_vocabulary
            else "  (none selected)"
        )

        comfort_list = (
            "\n".join(
                [
                    f"  - {v['target_word']} = {v['native_translation']}"
                    for v in self.comfort_vocabulary
                ]
            )
            if self.comfort_vocabulary
            else "  (none yet)"
        )

        return f"""VOCABULARY TO PRACTICE (student is learning these - NEVER replace or "correct" these words!):
{practice_list}

OTHER KNOWN VOCABULARY (student knows these - do NOT replace):
{comfort_list}"""

    def get_allowed_grammar_context(self) -> str:
        """
        Generate context for what grammar structures are allowed.
        Based on CEFR level + student's known/fluent grammar + practice grammar.
        """
        # Level-based allowed grammar (language-agnostic descriptions)
        level_grammar = {
            "A1": f"""GRAMMAR ALLOWED AT A1 LEVEL for {self.target_language}:
- Simple present tense forms
- Basic "to be" sentences
- Simple yes/no questions
- Basic word order typical for {self.target_language}
- Basic possessives (my, your, his/her)
- Simple negation
- Existence expressions (there is/there isn't)
- Basic imperatives""",
            "A2": f"""GRAMMAR ALLOWED AT A2 LEVEL for {self.target_language}:
- Everything from A1, plus:
- Simple past tense
- Basic connectors: and, but, because, then
- More possessive forms
- Location expressions
- Basic prepositions/postpositions
- Object marking (if applicable)""",
            "B1": f"""GRAMMAR ALLOWED AT B1 LEVEL for {self.target_language}:
- Everything from A2, plus:
- Present continuous/progressive
- Future tense
- Conditional forms
- Compound sentences
- Reported speech basics
- Modal expressions (should/must/can)""",
            "B2": f"""GRAMMAR ALLOWED AT B2 LEVEL for {self.target_language}:
- Everything from B1, plus:
- Passive voice
- Relative clauses
- Complex conditionals
- All major tense/aspect combinations
- Verbal nouns and nominalization""",
            "C1": f"""GRAMMAR ALLOWED AT C1 LEVEL for {self.target_language}:
- All grammar structures
- Complex tense combinations
- Literary forms
- Formal/archaic structures
- Nuanced mood expressions""",
            "C2": f"""GRAMMAR ALLOWED AT C2 LEVEL for {self.target_language}:
- Full native-level grammar
- All registers and styles
- Historical/literary forms
- Regional variations""",
        }

        basics = level_grammar.get(self.level, level_grammar["A1"])

        # Grammar being practiced this session
        practice_grammar_str = ""
        if self.practice_grammar:
            practice_grammar_str = (
                "\n\nGRAMMAR TO PRACTICE THIS SESSION (encourage student to use):\n"
                + "\n".join(
                    [
                        f"  - {g['concept_name']}: {g['description']}"
                        for g in self.practice_grammar
                    ]
                )
            )

        # Fluent grammar (can use naturally)
        fluent_grammar_str = ""
        if self.fluent_grammar:
            fluent_grammar_str = (
                "\n\nGRAMMAR STUDENT HAS MASTERED (can use naturally):\n"
                + "\n".join([f"  - {g['concept_name']}" for g in self.fluent_grammar])
            )

        # For lower levels, add forbidden grammar reminder
        forbidden = ""
        if self.level in ["A1", "A2"]:
            forbidden = f"""

IMPORTANT: Stay within {self.level} level. Do NOT use grammar structures above this level unless they are listed in the practice or mastered sections above."""

        return basics + practice_grammar_str + fluent_grammar_str + forbidden

    def review_response(self, response: str, conversation_history: List[Dict]) -> Dict:
        """
        Review a dialogue response and return feedback (not a rewritten sentence).
        The level controller acts as a REVIEWER only — it never generates conversation
        text because it lacks the full conversational context.

        Args:
            response: The response generated by the dialogue agent
            conversation_history: The conversation so far

        Returns:
            Dict with:
              - "approved": bool — True if the response is level-appropriate
              - "feedback": str  — Actionable critique for the dialogue agent
                                   (empty string when approved)
        """

        vocab_context = self.get_vocabulary_context()
        grammar_context = self.get_allowed_grammar_context()
        level_info = self.level_guidelines.get(self.level, self.level_guidelines["A1"])

        review_prompt = f"""You are a {self.target_language} level-appropriateness reviewer.
Your ONLY job is to evaluate whether a tutor's response matches the student's CEFR level and known vocabulary/grammar, then provide feedback. You do NOT rewrite the response yourself.

TARGET LANGUAGE: {self.target_language}
STUDENT'S NATIVE LANGUAGE: {self.native_language}

STUDENT'S TARGET LEVEL: {self.level} - {level_info['name']}
- Sentence length: {level_info['sentence_length']}
- Grammar allowed: {level_info['grammar']}
- Vocabulary complexity: {level_info['vocab_complexity']}
- Conversation style: {level_info['style']}

{vocab_context}

{grammar_context}

RESPONSE TO REVIEW:
"{response}"

Return your evaluation as JSON with exactly this structure:
{{
    "approved": true/false,
    "feedback": "If not approved, give specific, actionable feedback. List each issue clearly: which words are too advanced and what simpler alternatives exist in the known vocabulary, which grammar structures exceed the level and what simpler structures to use instead. If approved, leave this as an empty string."
}}

REVIEW CRITERIA:
1. Does the vocabulary match what the student knows? Flag specific unknown words.
2. Are the grammar structures within the allowed level? Flag specific violations.
3. Is the sentence complexity appropriate for {self.level}?
4. Are PRACTICE vocabulary words preserved exactly (never flagged for replacement)?
5. Is the {self.target_language} grammatically correct?

IMPORTANT:
- Be specific: say "replace 'X' with known word 'Y'" not just "simplify vocabulary"
- NEVER flag practice vocabulary words as problems — those are intentionally included
- NEVER flag other known vocabulary words as problems
- Only flag genuine level violations
- If the response is acceptable (even if not perfect), approve it
- Return ONLY valid JSON"""

        messages = [
            {"role": "system", "content": review_prompt},
            {
                "role": "user",
                "content": f"Please review this response for a {self.level} level student.",
            },
        ]

        response_obj = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_completion_tokens=400,
            response_format={"type": "json_object"},
        )

        result = json.loads(response_obj.choices[0].message.content)
        approved = result.get("approved", True)
        feedback = result.get("feedback", "")

        if approved:
            logger.info(
                f"      {Colors.GREEN}✓ Response approved — appropriate for {self.level} level{Colors.END}"
            )
        else:
            logger.info(
                f"      {Colors.YELLOW}⚠ Feedback for dialogue agent:{Colors.END} {feedback}"
            )

        return {"approved": approved, "feedback": feedback}

    def review_lesson_plan(self, lesson_plan: Dict, iteration: int = 1) -> Dict:
        """
        Review and refine a lesson plan to ensure it matches the CEFR level.
        Returns the refined plan.

        Args:
            lesson_plan: The lesson plan to review
            iteration: Which iteration this is (1, 2, or 3)
        """

        level_info = self.level_guidelines.get(self.level, self.level_guidelines["A1"])
        vocab_context = self.get_vocabulary_context()
        grammar_context = self.get_allowed_grammar_context()

        focus_area = {
            1: "Ensure level appropriateness and grammar restrictions are correct",
            2: "Improve vocabulary usage and conversation flow",
            3: "Polish for natural language and student engagement",
        }.get(iteration, "General improvement")

        review_prompt = f"""You are a {self.target_language} language curriculum expert refining a lesson plan for a {self.level} ({level_info['name']}) student.

TARGET LANGUAGE: {self.target_language}
STUDENT'S NATIVE LANGUAGE: {self.native_language}

FOCUS FOR THIS PASS: {focus_area}

TARGET LEVEL: {self.level} - {level_info['name']}
- Sentence length: {level_info['sentence_length']}
- Grammar allowed: {level_info['grammar']}
- Vocabulary complexity: {level_info['vocab_complexity']}
- Topics: {level_info['topics']}
- Conversation style: {level_info['style']}

{vocab_context}

{grammar_context}

CURRENT LESSON PLAN:
{json.dumps(lesson_plan, indent=2, ensure_ascii=False)}

Refine this lesson plan. Return ONLY the improved plan as valid JSON:
{{
    "theme": "...",
    "opening": "...",
    "conversation_goals": [...],
    "suggested_topics": [...],
    "target_vocab_usage": {{...}},
    "target_grammar_usage": {{...}},
    "difficulty_level": "{self.level}",
    "grammar_allowed": [...],
    "grammar_forbidden": [...]
}}

Keep it appropriate for {self.level} level learning {self.target_language}."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": review_prompt}],
            max_completion_tokens=2048,
            response_format={"type": "json_object"},
        )

        refined_plan = json.loads(response.choices[0].message.content)

        return {"refined_plan": refined_plan}
