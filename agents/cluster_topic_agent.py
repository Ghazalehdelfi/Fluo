"""
Cluster Topic Agent
───────────────────
Clusters a language's vocabulary by embedding similarity, identifies each
cluster's common theme, and generates 5 conversation topics per cluster.

Designed to run as a background task (or Lambda) after new vocabulary is added.
Results are stored in the `conversation_topics` table so the practice tab can
serve pre-computed topics with zero on-the-fly generation latency.

Embedding model : text-embedding-3-small  (~$0.02 / 1M tokens — very cheap)
Embeddings stored : JSON text in vocabulary.embedding (no pgvector required)
Clustering       : sklearn KMeans, k = max(2, min(10, n_vocab // 6))
"""

import json
import numpy as np
from typing import List, Dict, Tuple

from sqlalchemy.orm import Session

from database import Vocabulary, ConversationTopic
from agents.config import LLM_MODEL
from agents.logging_utils import Colors, get_logger, call_llm_with_json

logger = get_logger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
_BATCH_SIZE = 100  # OpenAI embeddings API max per request


class ClusterTopicAgent:
    def __init__(self, client):
        """
        Args:
            client: An OpenAI client instance (plain openai.OpenAI or TrackedOpenAI).
                    Must support both .embeddings.create() and .chat.completions.create().
        """
        self.client = client
        self.model = LLM_MODEL

    # ── Embedding helpers ────────────────────────────────────────

    def _get_or_create_embeddings(
        self, vocab_items: List[Vocabulary], db: Session
    ) -> Tuple[List[Vocabulary], np.ndarray]:
        """
        Ensure every item in vocab_items has a stored embedding.
        Items missing an embedding are batched to the API and saved.
        Returns (vocab_items, matrix) where matrix[i] is the embedding for vocab_items[i].
        """
        to_embed = [v for v in vocab_items if not v.embedding]

        if to_embed:
            logger.info(
                f"   Generating embeddings for {len(to_embed)} new vocab items..."
            )
            texts = [f"{v.target_word}: {v.native_translation}" for v in to_embed]

            for i in range(0, len(texts), _BATCH_SIZE):
                batch_texts = texts[i : i + _BATCH_SIZE]
                batch_items = to_embed[i : i + _BATCH_SIZE]

                response = self.client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch_texts,
                )

                for j, embedding_data in enumerate(response.data):
                    batch_items[j].embedding = json.dumps(embedding_data.embedding)

            db.commit()
            logger.info(f"   {Colors.GREEN}✓ Embeddings saved{Colors.END}")

        matrix = np.array(
            [json.loads(v.embedding) for v in vocab_items], dtype=np.float32
        )
        return vocab_items, matrix

    # ── Clustering ───────────────────────────────────────────────

    def _cluster(self, matrix: np.ndarray) -> np.ndarray:
        """
        K-means cluster the embedding matrix.
        k = max(2, min(10, n_vocab // 6)), capped at n_vocab to avoid degenerate runs.
        Returns an integer label array of length n_vocab.
        """
        from sklearn.cluster import KMeans  # lazy import — only needed here

        n = len(matrix)
        k = max(2, min(10, n // 6))
        k = min(k, n)

        logger.info(f"   Running k-means: k={k} clusters over {n} vocab items...")

        kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
        labels = kmeans.fit_predict(matrix)
        return labels

    # ── LLM topic generation ─────────────────────────────────────

    def _generate_topics_for_cluster(
        self, words: List[Dict], language_name: str
    ) -> Dict:
        """
        Ask the LLM to identify the semantic theme of a word cluster and
        propose 5 specific conversation topics that naturally use those words.

        Args:
            words: list of {"target_word": ..., "native_translation": ...}
            language_name: e.g. "Turkish"

        Returns:
            {"theme": str, "topics": [str, str, str, str, str]}
        """
        word_list = "\n".join(
            [f"- {w['target_word']} ({w['native_translation']})" for w in words]
        )

        prompt = f"""You are a language learning curriculum designer.

The following {language_name} vocabulary words were grouped together by semantic similarity:

{word_list}

Based on these words:
1. Identify the common theme connecting them (1-4 words, e.g. "Food & Dining", "Travel", "Daily Routines")
2. Generate exactly 5 specific, engaging conversation topics that naturally use these words

Return ONLY valid JSON with no extra text:
{{
    "theme": "Short theme label",
    "topics": [
        "Topic 1: a specific, concrete conversation scenario",
        "Topic 2: a specific, concrete conversation scenario",
        "Topic 3: a specific, concrete conversation scenario",
        "Topic 4: a specific, concrete conversation scenario",
        "Topic 5: a specific, concrete conversation scenario"
    ]
}}

Topics must be concrete scenarios (e.g. "Ordering food at a restaurant and discussing the menu"),
not generic labels (e.g. NOT just "Food")."""

        return call_llm_with_json(
            self.client.chat.completions.create,
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=600,
            response_format={"type": "json_object"},
        )

    # ── Main entry point ─────────────────────────────────────────

    def run(
        self, language_id: int, db: Session, language_name: str = "this language"
    ) -> int:
        """
        Cluster all vocabulary for a language and (re)generate conversation topics.

        Steps:
            1. Load all vocab for language_id
            2. Generate/cache embeddings for any new words
            3. K-means cluster the embedding matrix
            4. For each cluster: call LLM → theme + 5 topics
            5. Delete old conversation_topics for this language, insert fresh rows

        Args:
            language_id: FK from languages table
            db: SQLAlchemy session (owned by the caller — will be committed here)
            language_name: human-readable language name for prompts (e.g. "Turkish")

        Returns:
            Number of ConversationTopic rows created (clusters × 5).
        """
        logger.info(
            f"\n{Colors.CYAN}🔮 ClusterTopicAgent: language_id={language_id} ({language_name}){Colors.END}"
        )

        vocab_items = (
            db.query(Vocabulary).filter(Vocabulary.language_id == language_id).all()
        )

        if len(vocab_items) < 2:
            logger.info(
                f"   {Colors.YELLOW}Only {len(vocab_items)} vocab item(s) — need ≥2 to cluster. Skipping.{Colors.END}"
            )
            return 0

        # Embeddings (cached per word)
        vocab_items, matrix = self._get_or_create_embeddings(vocab_items, db)

        # Cluster
        labels = self._cluster(matrix)

        # Group vocab IDs + display info by cluster label
        clusters: Dict[int, List[Dict]] = {}
        for vocab, label in zip(vocab_items, labels):
            cid = int(label)
            if cid not in clusters:
                clusters[cid] = []
            clusters[cid].append(
                {
                    "id": vocab.id,
                    "target_word": vocab.target_word,
                    "native_translation": vocab.native_translation,
                }
            )

        logger.info(f"   {Colors.GREEN}✓ Formed {len(clusters)} clusters{Colors.END}")

        # Replace all existing topics for this language atomically
        db.query(ConversationTopic).filter(
            ConversationTopic.language_id == language_id
        ).delete()
        db.flush()

        total_topics = 0
        for cluster_id, words in clusters.items():
            logger.info(
                f"   Generating topics for cluster {cluster_id} "
                f"({len(words)} words: {', '.join(w['target_word'] for w in words[:4])}"
                f"{'...' if len(words) > 4 else ''})..."
            )
            try:
                result = self._generate_topics_for_cluster(words, language_name)
                theme = result.get("theme", f"Cluster {cluster_id}")
                topics = result.get("topics", [])[:5]
                vocab_ids_json = json.dumps([w["id"] for w in words])

                for topic_text in topics:
                    db.add(
                        ConversationTopic(
                            language_id=language_id,
                            cluster_id=cluster_id,
                            theme=theme,
                            topic=topic_text,
                            vocab_ids=vocab_ids_json,
                        )
                    )
                    total_topics += 1

                logger.info(
                    f"   {Colors.GREEN}✓ Theme: '{theme}' → {len(topics)} topics{Colors.END}"
                )

            except Exception as exc:  # noqa: BLE001
                logger.error(
                    f"   {Colors.RED}✗ Failed cluster {cluster_id}: {exc}{Colors.END}"
                )

        db.commit()
        logger.info(
            f"\n{Colors.GREEN}✅ ClusterTopicAgent complete: "
            f"{total_topics} topics across {len(clusters)} clusters{Colors.END}"
        )
        return total_topics
