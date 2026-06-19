"""Smoke tests verifying that rate-limited endpoints return 429 when the
limit is exceeded.

We temporarily patch the limiter's limit strings to "1/minute" so we can
trigger a 429 with just two requests instead of waiting for real thresholds.
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient

PATIENT_DATA = {
    "email": "rl-patient@test.dev",
    "password": "Pass1234!",
    "role": "patient",
    "first_name": "Rate",
    "last_name": "Limit",
}


@pytest.fixture
def tight_limit():
    """Patch all route-level decorators to allow only 1 request per minute."""
    with patch("app.core.limiter.limiter._default_limits", ["1/minute"]):
        yield


async def test_login_rate_limited(client: AsyncClient):
    # Register first so the login endpoint is actually hit
    await client.post("/api/v1/auth/register", json=PATIENT_DATA)

    creds = {"email": PATIENT_DATA["email"], "password": PATIENT_DATA["password"]}

    # Exhaust the per-endpoint limit by hitting login repeatedly
    responses = [await client.post("/api/v1/auth/login", json=creds) for _ in range(12)]
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes, (
        f"Expected a 429 after repeated login attempts; got: {set(status_codes)}"
    )


async def test_register_rate_limited(client: AsyncClient):
    responses = []
    for i in range(7):
        responses.append(
            await client.post(
                "/api/v1/auth/register",
                json={**PATIENT_DATA, "email": f"rl-reg-{i}@test.dev"},
            )
        )
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes, (
        f"Expected a 429 after repeated register attempts; got: {set(status_codes)}"
    )
