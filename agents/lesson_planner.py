"""
Lesson Plan Agent
Selects vocabulary and grammar items for practice using weighted random sampling.
Lesson planning (theme/goals generation) is now handled by the DialogueAgent directly.
Language-agnostic: works with any target/native language pair.
"""

import json
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from database import Vocabulary, Grammar
from agents.config import LLM_MODEL, DEFAULT_TARGET_LANGUAGE, DEFAULT_NATIVE_LANGUAGE
from agents.logging_utils import Colors, get_logger

logger = get_logger(__name__)


class LessonPlannerAgent:
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

    def get_all_known_items(
        self, db: Session, language_id: Optional[int] = None
    ) -> Dict:
        """
        Get ALL vocabulary and grammar the student has learned.
        This represents their complete knowledge base.
        Optionally filter by language_id.
        """
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
        """
        Select vocabulary and grammar items for practice with weighted randomness.
        Uses weighted random sampling that:
        1. Heavily favors low fluency items (need more practice)
        2. Considers recency (items not practiced recently get higher weight)
        3. Adds randomness to keep sessions varied
        Optionally filter by language_id.
        """
        import random
        from datetime import datetime, timedelta

        def calculate_weight(item) -> float:
            """
            Calculate selection weight for an item.
            Higher weight = more likely to be selected.
            """
            # Base weight by fluency level (low=10, medium=3, high=1)
            fluency_weights = {"low": 10.0, "medium": 3.0, "high": 1.0}
            weight = fluency_weights.get(item.fluency_level, 5.0)

            # Boost weight for items never practiced (2x) or not practiced recently
            if item.last_practiced_at is None:
                weight *= 2.0
            else:
                days_since_practice = (datetime.now() - item.last_practiced_at).days
                # Boost items not practiced in last 3+ days
                if days_since_practice >= 7:
                    weight *= 1.5
                elif days_since_practice >= 3:
                    weight *= 1.2

            # Slight boost for items practiced fewer times overall
            if item.times_practiced == 0:
                weight *= 1.3
            elif item.times_practiced < 3:
                weight *= 1.1

            return weight

        def weighted_sample(items, n: int) -> list:
            """
            Randomly sample n items using weights.
            Items with higher weights are more likely to be selected.
            """
            if len(items) <= n:
                return list(items)

            weights = [calculate_weight(item) for item in items]
            selected = []
            available = list(zip(items, weights))

            for _ in range(n):
                if not available:
                    break
                total_weight = sum(w for _, w in available)
                if total_weight == 0:
                    # Fallback to uniform random if all weights are 0
                    idx = random.randint(0, len(available) - 1)
                else:
                    # Weighted random selection
                    r = random.uniform(0, total_weight)
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

        # Get vocabulary items, optionally filtered by language
        query_vocab = db.query(Vocabulary)
        if language_id is not None:
            query_vocab = query_vocab.filter(Vocabulary.language_id == language_id)
        all_vocab = query_vocab.all()

        # Select vocabulary using weighted random sampling
        vocab_items = weighted_sample(all_vocab, num_vocab)

        # Get grammar items similarly
        query_grammar = db.query(Grammar)
        if language_id is not None:
            query_grammar = query_grammar.filter(Grammar.language_id == language_id)
        all_grammar = query_grammar.all()

        # Select grammar using weighted random sampling
        grammar_items = weighted_sample(all_grammar, num_grammar)

        logger.info(f"\n   {Colors.GREEN}✓ Selected Items for Practice:{Colors.END}")
        logger.info(f"   Vocabulary ({len(vocab_items)} items):")
        for v in vocab_items:
            last_practiced = (
                v.last_practiced_at.strftime("%m/%d")
                if v.last_practiced_at
                else "Never"
            )
            logger.info(
                f"      • {v.target_word}: {Colors.CYAN}fluency={v.fluency_level}{Colors.END}, last={last_practiced}, times={v.times_practiced}"
            )
        logger.info(f"   Grammar ({len(grammar_items)} items):")
        for g in grammar_items:
            last_practiced = (
                g.last_practiced_at.strftime("%m/%d")
                if g.last_practiced_at
                else "Never"
            )
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
