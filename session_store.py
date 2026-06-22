"""
In-memory session stores (keyed by (user_id, session_id)).
In production, replace with Redis or a database-backed store.
"""

import time

# Sessions expire after this many seconds of inactivity (1 hour).
# Every session dict must contain an '_expires_at' key (float unix timestamp).
SESSION_TTL_SECONDS: int = 3600

# Active dialogue / scenario / placement-test sessions
active_sessions: dict = {}

# Active grammar practice sessions
grammar_practice_sessions: dict = {}


def purge_expired_sessions() -> int:
    """Remove sessions whose TTL has elapsed from all stores.

    Returns the total number of sessions purged.
    """
    now = time.time()
    purged = 0

    for store in (active_sessions, grammar_practice_sessions):
        expired_keys = [k for k, v in store.items() if v.get("_expires_at", 0) < now]
        for k in expired_keys:
            del store[k]
        purged += len(expired_keys)

    return purged
