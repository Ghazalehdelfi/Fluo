"""Shared SlowAPI rate-limiter instances.

Two limiters are provided:
- ``limiter``      — keyed by **remote IP**; use on public/unauthenticated endpoints
                     (register, login).
- ``user_limiter`` — keyed by **JWT user ID**; use on authenticated endpoints so
                     every user has their own independent bucket and shared NAT
                     addresses don't collide.  Falls back to IP for requests
                     without a valid token.
"""

import os

import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_user_id(request: Request) -> str:
    """Extract the user ID from the Bearer JWT; fall back to remote IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            secret = os.getenv("JWT_SECRET", "change-me-to-a-real-secret-in-production")
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            return f"user:{payload['sub']}"
        except Exception:
            pass
    return get_remote_address(request)


# IP-based — for unauthenticated endpoints
limiter = Limiter(key_func=get_remote_address)

# User-ID-based — for authenticated endpoints
user_limiter = Limiter(key_func=_get_user_id)
