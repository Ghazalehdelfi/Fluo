"""
Lesson Plan Agent
Selects vocabulary and grammar with low fluency and creates a conversation plan.
Also fetches ALL known vocabulary/grammar for level control.
Iterates with Level Controller 3 times to refine the plan.
Language-agnostic: works with any target/native language pair.
"""

import json
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from database import Vocabulary, Grammar
from agents.level_controller import LevelControllerAgent
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

    def generate_lesson_plan(
        self, selected_items: Dict, all_known_items: Dict = None, level: str = "A1"
    ) -> Dict:
        """
        Generate a conversation plan based on selected vocabulary and grammar.
        Respects the student's CEFR level and only uses appropriate grammar.

        Args:
            selected_items: Vocabulary and grammar to practice
            all_known_items: All vocabulary and grammar the student knows
            level: CEFR level (A1, A2, B1, B2, C1, C2)
        """
        vocab_list = "\n".join(
            [
                f"- {v['target_word']} ({v['native_translation']})"
                for v in selected_items["vocabulary"]
            ]
        )

        grammar_list = (
            "\n".join(
                [
                    f"- {g['concept_name']}: {g['description']}"
                    for g in selected_items["grammar"]
                ]
            )
            if selected_items["grammar"]
            else "- No specific grammar focus"
        )

        # Get fluent grammar (can be used freely)
        fluent_grammar = []
        if all_known_items:
            fluent_grammar = [
                g
                for g in all_known_items.get("all_grammar", [])
                if g.get("fluency_level") == "high"
            ]

        fluent_grammar_str = (
            "\n".join([f"- {g['concept_name']}" for g in fluent_grammar])
            if fluent_grammar
            else "- None yet"
        )

        # Define level-specific constraints (language-agnostic)
        level_guidelines = {
            "A1": f"""
A1 (BEGINNER) CONSTRAINTS:
- Use ONLY simple present tense by default
- Sentences should be 3-5 words maximum
- Use basic word order typical for {self.target_language}
- NO past tense, future tense, or continuous aspects unless being practiced
- Simple questions only: yes/no or single-word answers
- Topics: greetings, basic introductions, simple preferences
- Vocabulary: common everyday words only""",
            "A2": f"""
A2 (ELEMENTARY) CONSTRAINTS:
- Simple present tense is default, can use present continuous if known
- Sentences can be 4-7 words
- Can use simple past tense if mastered
- Simple compound sentences with conjunctions like 'and', 'but'
- Topics: daily routines, shopping, directions, simple descriptions
- Can ask 'what', 'where', 'when' questions""",
            "B1": f"""
B1 (INTERMEDIATE) CONSTRAINTS:
- Can use present, past, and future tenses
- Sentences can be 5-10 words
- Can use present continuous and simple compound sentences
- Topics: travel, work, hobbies, opinions, experiences
- Can express simple opinions and reasons
- Can use basic conditionals""",
            "B2": f"""
B2 (UPPER INTERMEDIATE) CONSTRAINTS:
- All basic tenses available
- Complex sentences allowed (10-15 words)
- Can use conditionals, reported speech basics
- Topics: current events, abstract concepts, detailed descriptions
- Can express and justify opinions
- Can use relative clauses and more complex structures""",
            "C1": f"""
C1 (ADVANCED) CONSTRAINTS:
- Full range of tenses and moods
- Complex and compound-complex sentences
- Can use passive voice, causatives, formal language
- Topics: nuanced discussions, hypotheticals, professional topics
- Idiomatic expressions encouraged
- Can handle ambiguity and implicit meanings""",
            "C2": f"""
C2 (PROFICIENT) CONSTRAINTS:
- Native-like complexity allowed
- All grammatical structures available
- Sophisticated vocabulary and expressions
- Topics: any topic including abstract, academic, specialized
- Natural flow with cultural nuances
- Can use humor, sarcasm, and subtle meanings""",
        }

        level_constraint = level_guidelines.get(level, level_guidelines["A1"])

        prompt = f"""You are a {self.target_language} language lesson planner. Create a conversation plan for a student at CEFR level {level}.

TARGET LANGUAGE: {self.target_language}
STUDENT'S NATIVE LANGUAGE: {self.native_language}
STUDENT'S CEFR LEVEL: {level}

{level_constraint}

VOCABULARY TO PRACTICE:
{vocab_list}

GRAMMAR TO PRACTICE THIS SESSION:
{grammar_list}

GRAMMAR STUDENT HAS MASTERED (can use naturally):
{fluent_grammar_str}

Create a conversation plan that:
1. STRICTLY follows the {level} level constraints above
2. Naturally incorporates the vocabulary words
3. Feels natural but stays within the student's ability
4. Has achievable goals for a {level} learner

Return your response as valid JSON with this structure:
{{
    "theme": "A theme appropriate for {level} level",
    "opening": "A {level}-appropriate {self.target_language} greeting/question to start",
    "conversation_goals": [
        "Goal appropriate for {level} level",
        ...
    ],
    "suggested_topics": [
        "Topic appropriate for {level} that uses the vocabulary",
        ...
    ],
    "target_vocab_usage": {{
        "word1": "How to prompt this word at {level} level",
        ...
    }},
    "target_grammar_usage": {{
        "concept1": "How to encourage using this grammar",
        ...
    }},
    "difficulty_level": "{level}",
    "grammar_allowed": ["List of grammar structures allowed at this level"],
    "grammar_forbidden": ["List of grammar structures to AVOID at this level"]
}}

Remember: This is for a {level} level student learning {self.target_language}. Keep complexity appropriate!"""

        logger.info(
            f"\n{Colors.YELLOW}📝 Generating initial lesson plan...{Colors.END}"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=2048,
            response_format={"type": "json_object"},
        )

        initial_plan = json.loads(response.choices[0].message.content)
        initial_plan["selected_items"] = selected_items
        initial_plan["difficulty_level"] = level

        logger.info(f"   {Colors.GREEN}✓ Initial plan generated{Colors.END}")
        logger.info(f"   Theme: {initial_plan.get('theme', 'N/A')}")

        # Initialize Level Controller for review iterations
        level_controller = LevelControllerAgent(
            self.client,
            target_language=self.target_language,
            native_language=self.native_language,
        )
        level_controller.set_level(level)

        # Set student knowledge for level controller
        if all_known_items:
            level_controller.set_student_knowledge(
                all_vocabulary=all_known_items.get("all_vocabulary", []),
                all_grammar=all_known_items.get("all_grammar", []),
                practice_vocabulary=selected_items["vocabulary"],
                practice_grammar=selected_items["grammar"],
            )
        else:
            level_controller.set_student_knowledge(
                all_vocabulary=selected_items["vocabulary"],
                all_grammar=selected_items["grammar"],
                practice_vocabulary=selected_items["vocabulary"],
                practice_grammar=selected_items["grammar"],
            )

        # Iterate 3 times with Level Controller to refine the plan
        logger.info(
            f"\n{Colors.MAGENTA}🔄 Refining lesson plan with Level Controller (3 iterations)...{Colors.END}"
        )
        current_plan = initial_plan
        for iteration in range(1, 3):
            logger.info(f"   Iteration {iteration}/3...")

            review_result = level_controller.review_lesson_plan(current_plan, iteration)
            refined_plan = review_result.get("refined_plan", current_plan)

            # Preserve selected_items and ensure level is set
            refined_plan["selected_items"] = selected_items
            refined_plan["difficulty_level"] = level

            current_plan = refined_plan

        logger.info(f"\n{Colors.GREEN}✅ Final Lesson Plan Ready{Colors.END}")
        logger.info(f"   Theme: {current_plan.get('theme', 'N/A')}")
        goals = current_plan.get("conversation_goals", [])
        if goals:
            logger.info(f"   Goals:")
            for goal in goals[:3]:
                logger.info(f"      • {goal}")

        return current_plan
