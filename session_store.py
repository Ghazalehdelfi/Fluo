"""
In-memory session stores (keyed by (user_id, session_id)).
In production, replace with Redis or a database-backed store.
"""

# Active dialogue / scenario / placement-test sessions
active_sessions: dict = {}

# Active grammar practice sessions
grammar_practice_sessions: dict = {}
