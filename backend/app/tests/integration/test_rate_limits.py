"""Unit tests for the rate-limiting configuration.

These tests verify that the limiter is correctly configured and that the
smart key function behaves as expected. They do NOT exhaust real limits —
doing so in integration tests causes cross-test interference because the
in-memory store is shared for the entire test session.
"""

from unittest.mock import MagicMock


def test_limiter_has_default_limits():
    from app.core.limiter import limiter

    assert limiter._default_limits, "Limiter must have at least one default limit"


def test_key_func_returns_ip_for_unauthenticated():
    from app.core.limiter import _request_key

    request = MagicMock()
    request.headers = {}
    request.client.host = "203.0.113.42"
    request.scope = {"type": "http"}

    key = _request_key(request)
    assert key == "203.0.113.42"


def test_key_func_returns_user_id_for_authenticated():
    """JWT sub is used as the rate-limit key so users on shared NAT get separate buckets."""
    from jose import jwt

    from app.core.config import settings
    from app.core.limiter import _request_key

    token = jwt.encode({"sub": "user-abc-123"}, settings.SECRET_KEY, algorithm="HS256")

    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}
    request.client.host = "10.0.0.1"
    request.scope = {"type": "http"}

    key = _request_key(request)
    assert key == "user:user-abc-123"


def test_key_func_falls_back_to_ip_for_invalid_token():
    from app.core.limiter import _request_key

    request = MagicMock()
    request.headers = {"Authorization": "Bearer not-a-valid-jwt"}
    request.client.host = "192.168.1.1"
    request.scope = {"type": "http"}

    key = _request_key(request)
    assert key == "192.168.1.1"
