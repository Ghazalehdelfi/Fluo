"""
Shared state definitions for LangGraph agents.
All graph states used across the agent system are defined here.
"""

from typing import TypedDict, List, Dict, Optional


class NoteExtractionState(TypedDict, total=False):
    """State for the note extraction graph.

    Graph: START → [route] → extract_image | extract_text → END
    """

    input_type: str  # "image" or "text"
    image_base64: str
    mime_type: str
    text: str
    vocabulary: List[Dict]
    grammar: List[Dict]


class LessonPlanState(TypedDict, total=False):
    """State for the lesson planning graph with iterative level controller review.

    Graph: START → generate_plan → review_plan → [should_continue?] ─┐
                                        ↑                            │
                                        └──────── continue ──────────┘
                                              done → END
    """

    selected_items: Dict
    all_known_items: Dict
    level: str
    lesson_plan: Dict
    iteration: int


class DialogueResponseState(TypedDict, total=False):
    """State for per-turn dialogue response generation (agentic tool-calling flow)."""

    conversation_history: List[Dict]
    instruction: Optional[str]
    is_opening: bool
    current_response: str
    has_end_marker: bool


class AnalysisState(TypedDict, total=False):
    """State for the conversation analysis graph.

    Graph: START → extract_student_text → analyze → generate_feedback → END
    """

    transcript: str
    student_text: str
    practice_grammar: List[Dict]  # Grammar concepts to evaluate from lesson plan
    analysis: Dict  # Includes grammar_assessment when practice_grammar is provided
    overall_feedback: str


class PlacementTestState(TypedDict, total=False):
    """State for an in-progress adaptive placement test session.

    Stored in active_sessions on the server; not a LangGraph state.
    """

    level_index: int  # index into CEFR_LEVELS for the current question level
    questions_at_level: int  # how many questions asked at the current level
    correct_at_level: int  # how many correct at the current level
    questions: List[Dict]  # full question objects sent so far
    results: List[Dict]  # per-question {level, correct, ...}
    determined_level: Optional[str]  # set when the test is finished
    generated_content: Optional[Dict]  # vocab + grammar after generation
