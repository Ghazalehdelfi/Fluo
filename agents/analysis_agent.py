"""
Analysis Agent
Analyzes conversation transcripts, identifies correct/incorrect word and grammar usage,
updates fluency scores, and adds new vocabulary.
"""

import json
from datetime import datetime
from typing import List, Dict
from sqlalchemy.orm import Session
from database import Vocabulary, Grammar, Conversation
from agents.config import LLM_MODEL, DEFAULT_TARGET_LANGUAGE, DEFAULT_NATIVE_LANGUAGE
from agents.logging_utils import Colors, get_logger, call_llm_with_json

logger = get_logger(__name__)


class AnalysisAgent:
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

    def _extract_student_sentences(self, transcript: str) -> str:
        """Extract only student sentences from transcript."""
        lines = transcript.strip().split("\n")
        student_lines = []
        for line in lines:
            if line.strip().lower().startswith("student:"):
                # Remove the "Student:" prefix
                content = line.split(":", 1)[1].strip() if ":" in line else line
                student_lines.append(content)
        return "\n".join(student_lines)

    def analyze_conversation(
        self, transcript: str, practice_grammar: List[Dict] = None
    ) -> Dict:
        """
        Analyze student sentences for correct/incorrect words and grammar.
        When practice_grammar is provided, specifically evaluates whether the
        student demonstrated those grammar concepts.
        """
        logger.info(
            f"\n{Colors.MAGENTA}🔍 ANALYSIS AGENT: Analyzing conversation...{Colors.END}"
        )

        student_text = self._extract_student_sentences(transcript)
        logger.info(
            f"   Extracted {len(student_text.split(chr(10)))} student sentences"
        )

        # Build grammar assessment section if practice grammar was provided
        grammar_assessment_section = ""
        if practice_grammar:
            grammar_list = "\n".join(
                f"  - {g['concept_name']}: {g.get('description', '')}"
                for g in practice_grammar
            )
            logger.info(
                f"   Evaluating {len(practice_grammar)} practiced grammar concepts"
            )
            grammar_assessment_section = f"""

    "grammar_assessment": [
        {{
            "concept_name": "exact concept name from the list below",
            "demonstrated": true/false,
            "evidence": "quote from student text showing usage, or explanation of why not demonstrated"
        }}
    ]

GRAMMAR CONCEPTS PRACTICED THIS SESSION (evaluate each one):
{grammar_list}

For each grammar concept above, determine if the student demonstrated it correctly
in their sentences. "demonstrated" = true means the student used this grammar
pattern at least once correctly. Be fair — if the student made an attempt and
got it mostly right, count it as demonstrated."""

        prompt = f"""Analyze these {self.target_language} sentences from a language learner.
Input is from speech-to-text, so ignore punctuation/capitalization issues.

STUDENT SENTENCES:
{student_text}

Return JSON with:
{{
    "correct_words": [
        {{"word": "word in {self.target_language}", "translation": "{self.native_language} meaning"}}
    ],
    "incorrect_words": [
        {{"word": "word attempted", "correction": "correct form", "translation": "{self.native_language} meaning", "explanation": "brief explanation"}}
    ],
    "correct_grammar": [
        {{"pattern": "grammar pattern used correctly", "example": "from student text"}}
    ],
    "incorrect_grammar": [
        {{"pattern": "grammar pattern", "student_said": "what they said", "correction": "correct form", "explanation": "brief explanation"}}
    ]{grammar_assessment_section}
}}

Focus on meaningful vocabulary and grammar patterns. Be thorough but fair."""

        logger.info(f"   Calling OpenAI for word/grammar analysis...")
        analysis = call_llm_with_json(
            self.client.chat.completions.create,
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=2000,
            response_format={"type": "json_object"},
        )
        logger.info(
            f"   {Colors.GREEN}✓ Correct words: {len(analysis.get('correct_words', []))}{Colors.END}"
        )
        logger.info(
            f"   {Colors.YELLOW}✗ Incorrect words: {len(analysis.get('incorrect_words', []))}{Colors.END}"
        )
        logger.info(
            f"   {Colors.GREEN}✓ Correct grammar: {len(analysis.get('correct_grammar', []))}{Colors.END}"
        )
        logger.info(
            f"   {Colors.YELLOW}✗ Incorrect grammar: {len(analysis.get('incorrect_grammar', []))}{Colors.END}"
        )

        # Log grammar assessment if present
        grammar_assessment = analysis.get("grammar_assessment", [])
        if grammar_assessment:
            logger.info(f"\n   {Colors.MAGENTA}📐 Grammar Assessment:{Colors.END}")
            for item in grammar_assessment:
                status = "✓" if item.get("demonstrated") else "✗"
                color = Colors.GREEN if item.get("demonstrated") else Colors.YELLOW
                logger.info(
                    f"      {color}{status} {item.get('concept_name', '?')}{Colors.END}: {item.get('evidence', '')[:80]}"
                )

        return analysis

    def get_overall_feedback(self, transcript: str) -> str:
        """Generate overall feedback on the entire conversation."""
        logger.info(f"   Generating overall feedback...")

        prompt = f"""You are a friendly {self.target_language} tutor. Give 2-3 sentences of encouraging feedback on this conversation practice.
Mention what the student did well and one area to focus on.

CONVERSATION:
{transcript}

Return JSON: {{"overall_feedback": "your feedback here"}}"""

        result = call_llm_with_json(
            self.client.chat.completions.create,
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=300,
            response_format={"type": "json_object"},
        )
        feedback = result.get("overall_feedback", "Great practice session!")
        logger.info(f"   Feedback: {feedback[:80]}...")
        return feedback

    def update_fluency_scores(
        self, db: Session, analysis: Dict, language_id: int = None
    ) -> Dict:
        """
        Update fluency scores based on analysis.
        For correct words: find in DB, increase fluency. If not found, add it.
        For incorrect words: find in DB, track the attempt.
        Grammar: TODO - needs semantic search for matching.
        """
        updates = {
            "vocabulary_updated": [],
            "vocabulary_added": [],
            "grammar_updated": [],
        }

        # Process correct words
        for word_info in analysis.get("correct_words", []):
            word = word_info.get("word", "").strip()
            translation = word_info.get("translation", "")
            if not word:
                continue

            # Search for word in DB
            query = db.query(Vocabulary).filter(Vocabulary.target_word.ilike(word))
            if language_id:
                query = query.filter(Vocabulary.language_id == language_id)
            vocab_item = query.first()

            if vocab_item:
                # Exists - increase fluency
                vocab_item.times_practiced += 1
                vocab_item.times_correct += 1
                vocab_item.last_practiced_at = datetime.utcnow()
                self._update_fluency_level(vocab_item)
                updates["vocabulary_updated"].append(
                    {
                        "word": word,
                        "action": "increased",
                        "fluency": vocab_item.fluency_level,
                    }
                )
            else:
                # Doesn't exist - add it with medium fluency (they used it correctly)
                new_vocab = Vocabulary(
                    language_id=language_id,
                    target_word=word,
                    native_translation=translation,
                    fluency_level="medium",
                    times_practiced=1,
                    times_correct=1,
                )
                db.add(new_vocab)
                updates["vocabulary_added"].append(
                    {
                        "word": word,
                        "translation": translation,
                        "fluency": "medium",
                    }
                )

        # Process incorrect words
        for word_info in analysis.get("incorrect_words", []):
            word = word_info.get("word", "").strip()
            correction = word_info.get("correction", "")
            translation = word_info.get("translation", "")
            if not word:
                continue

            # Try to find the intended word (correction) in DB
            search_word = correction if correction else word
            query = db.query(Vocabulary).filter(
                Vocabulary.target_word.ilike(search_word)
            )
            if language_id:
                query = query.filter(Vocabulary.language_id == language_id)
            vocab_item = query.first()

            if vocab_item:
                # Track the attempt (practiced but not correct)
                vocab_item.times_practiced += 1
                vocab_item.last_practiced_at = datetime.utcnow()
                self._update_fluency_level(vocab_item)
                updates["vocabulary_updated"].append(
                    {
                        "word": search_word,
                        "action": "practiced (incorrect)",
                        "fluency": vocab_item.fluency_level,
                    }
                )
            else:
                # Add the correct form with low fluency
                new_vocab = Vocabulary(
                    language_id=language_id,
                    target_word=correction if correction else word,
                    native_translation=translation,
                    fluency_level="low",
                    times_practiced=1,
                    times_correct=0,
                )
                db.add(new_vocab)
                updates["vocabulary_added"].append(
                    {
                        "word": correction if correction else word,
                        "translation": translation,
                        "fluency": "low",
                    }
                )

        # Grammar: update fluency based on grammar_assessment from the analysis
        grammar_assessment = analysis.get("grammar_assessment", [])
        for item in grammar_assessment:
            concept_name = item.get("concept_name", "").strip()
            demonstrated = item.get("demonstrated", False)
            if not concept_name:
                continue

            # Find the grammar concept in DB (case-insensitive match)
            query = db.query(Grammar).filter(Grammar.concept_name.ilike(concept_name))
            if language_id:
                query = query.filter(Grammar.language_id == language_id)
            grammar_item = query.first()

            if grammar_item:
                grammar_item.times_practiced += 1
                grammar_item.last_practiced_at = datetime.utcnow()
                if demonstrated:
                    grammar_item.times_correct += 1
                self._update_grammar_fluency_level(grammar_item)
                updates["grammar_updated"].append(
                    {
                        "concept": concept_name,
                        "demonstrated": demonstrated,
                        "fluency": grammar_item.fluency_level,
                    }
                )
                logger.info(
                    f"   {'✓' if demonstrated else '✗'} Grammar: {concept_name} → {grammar_item.fluency_level}"
                )

        db.commit()

        logger.info(
            f"   {Colors.GREEN}Updated {len(updates['vocabulary_updated'])} words{Colors.END}"
        )
        logger.info(
            f"   {Colors.CYAN}Added {len(updates['vocabulary_added'])} new words{Colors.END}"
        )
        logger.info(
            f"   {Colors.MAGENTA}Updated {len(updates['grammar_updated'])} grammar concepts{Colors.END}"
        )

        return updates

    def _update_fluency_level(self, vocab_item: Vocabulary):
        """Update fluency level based on success rate."""
        if vocab_item.times_practiced == 0:
            return
        success_rate = vocab_item.times_correct / vocab_item.times_practiced
        if success_rate >= 0.8 and vocab_item.times_practiced >= 3:
            vocab_item.fluency_level = "high"
        elif success_rate >= 0.5 and vocab_item.times_practiced >= 2:
            vocab_item.fluency_level = "medium"
        else:
            vocab_item.fluency_level = "low"

    def _update_grammar_fluency_level(self, grammar_item: Grammar):
        """Update grammar fluency level based on demonstration success rate."""
        if grammar_item.times_practiced == 0:
            return
        success_rate = grammar_item.times_correct / grammar_item.times_practiced
        if success_rate >= 0.8 and grammar_item.times_practiced >= 3:
            grammar_item.fluency_level = "high"
        elif success_rate >= 0.5 and grammar_item.times_practiced >= 2:
            grammar_item.fluency_level = "medium"
        else:
            grammar_item.fluency_level = "low"

    def save_conversation(
        self,
        db: Session,
        transcript: str,
        analysis: Dict,
        overall_feedback: str,
        user_id: int = None,
        language_id: int = None,
        total_cost_usd: float = 0.0,
    ) -> int:
        """Save the conversation and analysis to the database."""
        # Combine analysis with feedback
        full_analysis = {**analysis, "overall_feedback": overall_feedback}

        conversation = Conversation(
            user_id=user_id,
            language_id=language_id,
            transcript=transcript,
            analysis=json.dumps(full_analysis),
            total_cost_usd=total_cost_usd,
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        return conversation.id
