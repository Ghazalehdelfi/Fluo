"""Helpers for persisting generated vocabulary/grammar into a language's
knowledge base with de-duplication (exact for vocab, semantic for grammar)."""

import json
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from database import Vocabulary, Grammar
from grammar_utils import (
    GRAMMAR_SIMILARITY_HIGH,
    cosine_similarity,
    embed_text,
    grammar_embed_text,
    find_most_similar_grammar,
)


def save_generated_content(
    db: Session,
    api_key: str,
    lang_id: int,
    vocabulary: List[Dict],
    grammar: List[Dict],
) -> Tuple[int, int]:
    """Insert new vocabulary + grammar rows for ``lang_id``, skipping anything
    already present. Does NOT commit. Returns (vocab_added, grammar_added)."""

    # Deduplicate within the submitted batch
    seen_vocab = set()
    vocab_batch = []
    for v in vocabulary:
        key = (v.get("target_word") or "").strip().lower()
        if key and key not in seen_vocab:
            seen_vocab.add(key)
            vocab_batch.append(v)

    seen_grammar = set()
    grammar_batch = []
    for g in grammar:
        key = (g.get("concept_name") or "").strip().lower()
        if key and key not in seen_grammar:
            seen_grammar.add(key)
            grammar_batch.append(g)

    added_vocab = 0
    for vocab in vocab_batch:
        existing = (
            db.query(Vocabulary)
            .filter(
                Vocabulary.language_id == lang_id,
                Vocabulary.target_word.ilike(vocab["target_word"].strip()),
            )
            .first()
        )
        if existing:
            continue
        db.add(
            Vocabulary(
                language_id=lang_id,
                target_word=vocab["target_word"].strip(),
                native_translation=vocab.get("native_translation", ""),
                example_sentence=vocab.get("example_sentence", ""),
                fluency_level="low",
            )
        )
        added_vocab += 1

    added_grammar = 0
    all_existing_grammar = (
        db.query(Grammar).filter(Grammar.language_id == lang_id).all()
    )
    accepted_in_batch: list = []  # (concept_name_lower, embedding_vec)

    for gram in grammar_batch:
        existing_exact = (
            db.query(Grammar)
            .filter(
                Grammar.language_id == lang_id,
                Grammar.concept_name.ilike(gram["concept_name"]),
            )
            .first()
        )
        if existing_exact:
            continue

        concept_lower = gram["concept_name"].lower()
        if any(concept_lower == name for name, _ in accepted_in_batch):
            continue

        candidate_vec = embed_text(
            api_key, grammar_embed_text(gram["concept_name"], gram.get("description", ""))
        )
        _, similarity = find_most_similar_grammar(
            candidate_vec, all_existing_grammar, api_key, db
        )
        if similarity >= GRAMMAR_SIMILARITY_HIGH:
            continue
        batch_best = max(
            (cosine_similarity(candidate_vec, vec) for _, vec in accepted_in_batch),
            default=0.0,
        )
        if batch_best >= GRAMMAR_SIMILARITY_HIGH:
            continue

        accepted_in_batch.append((concept_lower, candidate_vec))
        db.add(
            Grammar(
                language_id=lang_id,
                concept_name=gram["concept_name"],
                description=gram.get("description", ""),
                examples=gram.get("examples", ""),
                fluency_level="low",
                embedding=json.dumps(candidate_vec),
            )
        )
        added_grammar += 1

    return added_vocab, added_grammar
