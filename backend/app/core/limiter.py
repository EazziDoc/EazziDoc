"""Shared SlowAPI limiter instance.

Key function: authenticated requests are keyed by user ID (from the JWT
sub claim), unauthenticated requests fall back to the client IP address.
This prevents shared NAT from unfairly consuming a single IP bucket.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def _request_key(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from jose import jwt

            payload = jwt.decode(
                auth[7:],
                settings.SECRET_KEY,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
            if sub := payload.get("sub"):
                return f"user:{sub}"
        except Exception:
            pass
    return get_remote_address(request)


limiter = Limiter(
    key_func=_request_key,
    default_limits=["300/minute"],
    enabled=settings.RATELIMIT_ENABLED,
)
