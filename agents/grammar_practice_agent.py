"""
Grammar Practice Agent
Generates 10 practice exercises from a grammar detail card, then evaluates
user answers with flexible semantic matching.
"""

import json
import uuid
from typing import List, Dict, Optional
from agents.config import LLM_MODEL, DEFAULT_TARGET_LANGUAGE, DEFAULT_NATIVE_LANGUAGE
from agents.logging_utils import Colors, get_logger

logger = get_logger(__name__)


class GrammarPracticeAgent:
    # Temperature ramps up with fluency so higher-level sessions get more varied questions
    _FLUENCY_TEMPERATURE = {"low": 0.9, "medium": 0.9, "high": 1.15}

    def __init__(
        self,
        client,
        target_language: str = DEFAULT_TARGET_LANGUAGE,
        native_language: str = DEFAULT_NATIVE_LANGUAGE,
        level: str = "B1",
        fluency_level: str = "low",
        cost_tracker=None,
    ):
        self.client = client
        self.model = LLM_MODEL
        self.target_language = target_language
        self.native_language = native_language
        self.level = level
        self.fluency_level = fluency_level
        self.cost_tracker = cost_tracker

    def generate_questions(self, grammar_card: Dict) -> List[Dict]:
        """
        Generate 10 practice exercises from a grammar detail card.
        Returns a list of 10 question dicts.
        - Questions 1-5: translation (native → target language)
        - Questions 6-10: error correction (wrong sentence in target language)
        """
        logger.info(
            f"\n{Colors.CYAN}📝 GRAMMAR PRACTICE: Generating questions for "
            f"'{grammar_card.get('concept', 'Unknown')}'...{Colors.END}"
        )

        card_json = json.dumps(grammar_card, ensure_ascii=False)

        prompt = f"""You are a language teacher creating grammar practice exercises.

Given this grammar card for {self.target_language} (learner level: {self.level}):
{card_json}

Generate exactly 10 exercises as a JSON array.
- Exercises 1-5: type "translation" — learner translates an {self.native_language} sentence into {self.target_language}
- Exercises 6-10: type "correction" — learner is shown a WRONG {self.target_language} sentence that contains a deliberate grammar mistake related to this concept, and must write the corrected version

Return ONLY a JSON array (no markdown fences, no preamble) with exactly 10 objects, each matching this schema:
{{
  "type": "translation" | "correction",
  "question_text": "Instruction shown to the user",
  "english_prompt": "The English sentence to translate (only for type=translation, else null)",
  "wrong_sentence": "The INCORRECT {self.target_language} sentence with a deliberate grammar mistake (only for type=correction, else null)",
  "correct_answer": "The correct {self.target_language} sentence",
  "explanation": "1-2 sentence explanation of the grammar rule being demonstrated",
  "highlighted_segments": [
    {{"text": "word or phrase", "highlight": true}},
    {{"text": " rest of sentence ", "highlight": false}},
    {{"text": "another highlighted part", "highlight": true}}
  ]
}}

Rules:
- highlighted_segments must cover the FULL correct_answer sentence (concatenated they equal correct_answer)
- highlight=true marks the parts that directly demonstrate this grammar concept
- Each exercise must test a different aspect or use-case of the concept
- Sentences should be natural and relevant to everyday topics
- CRITICAL for correction exercises: wrong_sentence MUST be grammatically WRONG — it must contain exactly one grammar error related to this concept. The wrong_sentence and the correct_answer must be DIFFERENT strings. Double-check that wrong_sentence is incorrect before including it.
- Do NOT repeat the same sentence across exercises
- question_text for translation: "Translate into {self.target_language}: \"[english sentence]\""
- question_text for correction: "Correct the grammar mistake: \"[wrong sentence]\""
"""

        temperature = self._FLUENCY_TEMPERATURE.get(self.fluency_level, 0.7)
        # Unique nonce prevents OpenAI from serving a cached response for the same prompt
        nonce = uuid.uuid4().hex
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": f"Session: {nonce}"},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=3000,
            temperature=temperature,
        )

        if self.cost_tracker and response.usage:
            self.cost_tracker.record_chat(
                self.model,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
            raw = raw.strip()

        questions = json.loads(raw)
        logger.info(
            f"   {Colors.GREEN}✓ Generated {len(questions)} questions{Colors.END}"
        )
        return questions

    def evaluate_answer(self, question: Dict, user_answer: str) -> Dict:
        """
        Evaluate a user's answer against the correct answer.
        Uses flexible semantic matching — minor spelling/word order accepted.
        Returns { is_correct: bool, feedback: str }
        """
        logger.info(
            f"\n{Colors.MAGENTA}🔍 GRAMMAR PRACTICE: Evaluating answer...{Colors.END}"
        )

        prompt = f"""You are evaluating a language learner's answer to a grammar exercise.

Grammar concept being practiced: {question.get('explanation', '')}
Exercise type: {question['type']}
{"English sentence to translate: " + (question.get('english_prompt') or '') if question['type'] == 'translation' else "Sentence to correct: " + (question.get('wrong_sentence') or '')}
Correct answer: {question['correct_answer']}
Grammar-critical parts (highlighted): {", ".join(s["text"] for s in question.get("highlighted_segments", []) if s.get("highlight"))}
Learner's answer: {user_answer}

Evaluate whether the learner correctly applied the grammar concept. Focus ONLY on the grammar being tested, not on matching the exact wording.

Rules:
- PASS if the grammar-relevant parts are correct, even if other words differ (synonyms, different but valid vocabulary, minor rewording)
- PASS if there are minor spelling mistakes in non-grammar parts
- PASS if word order varies but is grammatically valid in {self.target_language}
- FAIL only if the specific grammar form/structure being tested is wrong or missing
- Do NOT penalise the learner for using a different but valid translation of non-grammar words

Return ONLY this JSON (no markdown):
{{
  "is_correct": true/false,
  "feedback": "One encouraging sentence explaining what was right or what was wrong (max 20 words)"
}}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=200,
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        if self.cost_tracker and response.usage:
            self.cost_tracker.record_chat(
                self.model,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )

        result = json.loads(response.choices[0].message.content)
        logger.info(
            f"   {'✓ Correct' if result.get('is_correct') else '✗ Incorrect'}: {result.get('feedback', '')}"
        )
        return result
