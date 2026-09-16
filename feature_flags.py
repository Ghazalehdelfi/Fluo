"""Feature flags — toggle major feature sets via environment variables.

Flags are read once at import time (after aws_config.load_secrets() has run),
so they work with both local .env files and AWS SSM-injected env vars.
"""

import os


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# Teacher persona: classes, homework assignments, teacher role at signup,
# and the student-side homework views. When disabled, the classes router is
# not mounted, registration forces role="student", and the frontend hides
# all teacher/homework UI.
ENABLE_TEACHER_FEATURES = _flag("ENABLE_TEACHER_FEATURES", default=False)
