"""Grammar embedding and semantic-similarity utilities."""

import json
import logging

logger = logging.getLogger(__name__)

# Cosine-similarity thresholds for grammar deduplication
# score >= HIGH  → treat as duplicate, skip silently
# LOW <= score < HIGH → surface to user for merge-or-new decision
# score < LOW    → treat as a new concept, insert immediately
GRAMMAR_SIMILARITY_HIGH: float = 0.92
GRAMMAR_SIMILARITY_LOW: float = 0.60

_EMBEDDING_MODEL = "text-embedding-3-small"


def cosine_similarity(a: list, b: list) -> float:
    """Return cosine similarity in [0, 1] between two equal-length float vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def embed_text(api_key: str, text: str) -> list:
    """Embed *text* with text-embedding-3-small and return the float vector."""
    from openai import OpenAI as _OpenAI
    client = _OpenAI(api_key=api_key)
    response = client.embeddings.create(model=_EMBEDDING_MODEL, input=text[:8192])
    return response.data[0].embedding


def grammar_embed_text(concept_name: str, description: str) -> str:
    """Build the text to embed for a grammar item (concept + description)."""
    return f"{concept_name} {description}".strip()


def ensure_grammar_embedding(item, api_key: str, db) -> list:
    """Return the embedding for an existing Grammar row, generating it if absent."""
    if item.embedding:
        try:
            return json.loads(item.embedding)
        except (json.JSONDecodeError, ValueError):
            pass
    vec = embed_text(api_key, grammar_embed_text(item.concept_name, item.description or ""))
    item.embedding = json.dumps(vec)
    db.add(item)
    db.flush()
    return vec


def find_most_similar_grammar(
    candidate_vec: list,
    existing_items: list,
    api_key: str,
    db,
):
    """Return (most_similar_Grammar, score) or (None, 0.0) if no items exist."""
    best_item = None
    best_score = 0.0
    for item in existing_items:
        vec = ensure_grammar_embedding(item, api_key, db)
        score = cosine_similarity(candidate_vec, vec)
        if score > best_score:
            best_score = score
            best_item = item
    return best_item, best_score
