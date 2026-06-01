"""Background tasks that run outside of the request/response cycle."""

import os
import logging

logger = logging.getLogger(__name__)


def rebuild_topics(language_id: int, language_name: str) -> None:
    """
    Re-cluster vocabulary embeddings and regenerate conversation topics.
    Opens its own DB session so it is safe to run after the request has returned.
    """
    from database import SessionLocal
    from agents.cluster_topic_agent import ClusterTopicAgent

    db = SessionLocal()
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("ClusterTopicAgent: OPENAI_API_KEY not set — skipping")
            return
        from openai import OpenAI as _OpenAI
        client = _OpenAI(api_key=api_key)
        agent = ClusterTopicAgent(client)
        agent.run(language_id, db, language_name)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"ClusterTopicAgent failed (language_id={language_id}): {exc}")
    finally:
        db.close()
