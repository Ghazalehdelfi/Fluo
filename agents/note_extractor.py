"""
Note Extractor Agent — LangGraph Implementation
Uses GPT-4o Vision to extract vocabulary and grammar from uploaded notes.
Language-agnostic: works with any target/native language pair.

Graph: START → [route] → extract_image | extract_text → END
"""

import base64
import json
from typing import Tuple, List, Dict

from langgraph.graph import StateGraph, START, END
from agents.state import NoteExtractionState
from agents.config import LLM_MODEL, DEFAULT_TARGET_LANGUAGE, DEFAULT_NATIVE_LANGUAGE
from agents.logging_utils import Colors, get_logger, call_llm_with_json

logger = get_logger(__name__)


class NoteExtractorAgent:
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
        self._graph = self._build_graph()

    # ── Graph construction ──────────────────────────────────────────

    def _build_graph(self):
        graph = StateGraph(NoteExtractionState)
        graph.add_node("extract_image", self._extract_image_node)
        graph.add_node("extract_text", self._extract_text_node)
        graph.add_conditional_edges(
            START,
            self._route_input,
            {"extract_image": "extract_image", "extract_text": "extract_text"},
        )
        graph.add_edge("extract_image", END)
        graph.add_edge("extract_text", END)
        return graph.compile()

    @staticmethod
    def _route_input(state: NoteExtractionState) -> str:
        """Route to the correct extraction node based on input type."""
        return "extract_image" if state.get("input_type") == "image" else "extract_text"

    # ── Graph nodes ─────────────────────────────────────────────────

    def _extract_image_node(self, state: NoteExtractionState) -> dict:
        """Node: extract vocabulary and grammar from a base64-encoded image."""
        logger.info(f"   {Colors.CYAN}Extracting from image...{Colors.END}")
        image_base64 = state["image_base64"]
        mime_type = state.get("mime_type", "image/jpeg")

        prompt = self._build_image_prompt()

        result = call_llm_with_json(
            self.client.chat.completions.create,
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            },
                        },
                    ],
                }
            ],
            max_completion_tokens=16384,
            response_format={"type": "json_object"},
        )
        vocab = result.get("vocabulary", [])
        grammar = result.get("grammar", [])
        logger.info(
            f"   {Colors.GREEN}✓ Extracted {len(vocab)} vocab, {len(grammar)} grammar{Colors.END}"
        )
        return {"vocabulary": vocab, "grammar": grammar}

    def _extract_text_node(self, state: NoteExtractionState) -> dict:
        """Node: extract vocabulary and grammar from text notes."""
        logger.info(f"   {Colors.CYAN}Extracting from text...{Colors.END}")
        text = state["text"]

        prompt = self._build_text_prompt(text)

        result = call_llm_with_json(
            self.client.chat.completions.create,
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=16384,
            response_format={"type": "json_object"},
        )
        vocab = result.get("vocabulary", [])
        grammar = result.get("grammar", [])
        logger.info(
            f"   {Colors.GREEN}✓ Extracted {len(vocab)} vocab, {len(grammar)} grammar{Colors.END}"
        )
        return {"vocabulary": vocab, "grammar": grammar}

    # ── Prompt builders ─────────────────────────────────────────────

    def _json_schema_hint(self) -> str:
        return f"""Return your response as valid JSON with this exact structure:
{{
    "vocabulary": [
        {{
            "target_word": "the {self.target_language} word",
            "native_translation": "{self.native_language} meaning",
            "example_sentence": "An example sentence using this word (if visible in notes, otherwise create one)"
        }}
    ],
    "grammar": [
        {{
            "concept_name": "Name of the grammar concept (e.g., \"Present Continuous Tense\", \"Accusative Case\")",
            "description": "Clear explanation of the grammar rule",
            "examples": "Example sentences demonstrating this grammar"
        }}
    ]
}}"""

    def _build_image_prompt(self) -> str:
        return f"""You are an expert {self.target_language} language teacher analyzing a student's notes.

Extract ALL vocabulary words and grammar concepts from this image of {self.target_language} language notes.

{self._json_schema_hint()}

Be thorough - extract every vocabulary word and grammar concept you can see.
If the notes are handwritten, do your best to read them.
If something is unclear, make your best interpretation.
Return ONLY valid JSON, no other text."""

    def _build_text_prompt(self, text: str) -> str:
        return f"""You are an expert {self.target_language} language teacher analyzing a student's notes.

Extract ALL vocabulary words and grammar concepts from these {self.target_language} language notes:

---
{text}
---

{self._json_schema_hint()}

Be thorough - extract every vocabulary word and grammar concept you can find.
Return ONLY valid JSON, no other text."""

    # ── Public API (backward-compatible) ────────────────────────────

    def extract_from_image(
        self, image_bytes: bytes, mime_type: str = "image/jpeg"
    ) -> Tuple[List[Dict], List[Dict]]:
        """Extract vocabulary and grammar from an image of notes.

        Returns:
            Tuple of (vocabulary_list, grammar_list)
        """
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        result = self._graph.invoke(
            {
                "input_type": "image",
                "image_base64": image_base64,
                "mime_type": mime_type,
            }
        )
        return result["vocabulary"], result["grammar"]

    def extract_from_text(self, text: str) -> Tuple[List[Dict], List[Dict]]:
        """Extract vocabulary and grammar from text notes.

        Returns:
            Tuple of (vocabulary_list, grammar_list)
        """
        result = self._graph.invoke({"input_type": "text", "text": text})
        return result["vocabulary"], result["grammar"]
