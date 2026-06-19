"""
Security regression tests.

Covers:
  - Unauthenticated access to protected endpoints (auth bypass)
  - Role-based access control: cross-role requests
  - IDOR: accessing another user's appointments, diagnoses, and payments
  - JWT tampering: forged signature, expired token, alg:none, role escalation
  - Mass assignment: self-registration as admin
  - Deactivated-user token rejection
  - Stripe webhook signature verification
"""

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost/eazzidoc_test"

# ── user fixtures ─────────────────────────────────────────────────────────────

_PATIENT_A = {
    "email": "patient-a@security-tests.dev",
    "password": "SecurePass1",
    "role": "patient",
    "first_name": "Aisha",
    "last_name": "Kofi",
}
_PATIENT_B = {
    "email": "patient-b@security-tests.dev",
    "password": "SecurePass1",
    "role": "patient",
    "first_name": "Bola",
    "last_name": "Eze",
}
_DOCTOR = {
    "email": "doctor@security-tests.dev",
    "password": "SecurePass1",
    "role": "doctor",
    "first_name": "Chidi",
    "last_name": "Obi",
}
_ADMIN_EMAIL = "admin@security-tests.dev"
_ADMIN_PASSWORD = "AdminPass1"

_IMAGE_KEYS = ["images/test/00000000-0000-0000-0000-000000000099.jpg"]


# ── helpers ───────────────────────────────────────────────────────────────────


async def _login(client: AsyncClient, user: dict) -> str:
    await client.post("/api/v1/auth/register", json=user)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    return resp.json()["access_token"]


async def _create_admin_token(client: AsyncClient) -> str:
    """Insert an admin user directly into the test DB, then log in."""
    engine = create_async_engine(TEST_DATABASE_URL)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        existing = (
            await session.execute(select(User).where(User.email == _ADMIN_EMAIL))
        ).scalar_one_or_none()
        if not existing:
            session.add(
                User(
                    id=uuid.uuid4(),
                    email=_ADMIN_EMAIL,
                    password_hash=hash_password(_ADMIN_PASSWORD),
                    role="admin",
                    is_verified=True,
                    is_active=True,
                )
            )
            await session.commit()
    await engine.dispose()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
    )
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _future() -> str:
    return (datetime.now(UTC) + timedelta(days=2)).isoformat()


async def _book(client: AsyncClient, patient_token: str, doctor_id: str) -> dict:
    resp = await client.post(
        "/api/v1/appointments",
        headers=_auth(patient_token),
        json={"doctor_id": doctor_id, "scheduled_at": _future()},
    )
    assert resp.status_code == 201
    return resp.json()


async def _get_doctor_id(client: AsyncClient, token: str) -> str:
    resp = await client.get("/api/v1/doctors/me", headers=_auth(token))
    return resp.json()["id"]


# ── JWT crafting helpers ──────────────────────────────────────────────────────


def _forge_token(subject: str, role: str = "patient") -> str:
    """JWT signed with the wrong secret — should be rejected."""
    expire = datetime.now(UTC) + timedelta(minutes=15)
    return jwt.encode(
        {"sub": subject, "role": role, "exp": expire},
        "totally_wrong_secret_key",
        algorithm="HS256",
    )


def _expired_token(subject: str) -> str:
    """JWT signed with the real secret but already expired."""
    expire = datetime.now(UTC) - timedelta(minutes=1)
    return jwt.encode(
        {"sub": subject, "role": "patient", "exp": expire},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def _none_alg_token(subject: str) -> str:
    """JWT using alg=none (unsigned) — classic algorithm confusion attack."""
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    payload_data = {"sub": subject, "role": "admin"}
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}."


def _role_escalated_token(subject: str) -> str:
    """Valid JWT (real secret, not expired) but with role='admin' for a non-admin user."""
    expire = datetime.now(UTC) + timedelta(minutes=15)
    return jwt.encode(
        {"sub": subject, "role": "admin", "exp": expire},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def _mock_celery():
    return patch("app.api.v1.diagnoses.process_diagnosis.delay")


# ── 1. authentication bypass ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/appointments"),
        ("GET", "/api/v1/patients/me"),
        ("GET", "/api/v1/diagnoses"),
        ("GET", "/api/v1/admin/stats/overview"),
        ("GET", "/api/v1/payments/appointments/00000000-0000-0000-0000-000000000001"),
    ],
)
async def test_protected_endpoints_reject_unauthenticated(
    client: AsyncClient, method: str, path: str
):
    """Every protected endpoint must return 4xx without an Authorization header."""
    resp = await client.request(method, path)
    assert resp.status_code in (401, 403), f"{method} {path} → {resp.status_code}"


# ── 2. role-based access control ──────────────────────────────────────────────


async def test_patient_cannot_access_doctor_only_endpoints(client: AsyncClient):
    """Patient token must be rejected on doctor-scoped endpoints."""
    token = await _login(client, _PATIENT_A)
    resp = await client.get("/api/v1/doctor/appointments", headers=_auth(token))
    assert resp.status_code == 403


async def test_doctor_cannot_access_patient_only_endpoints(client: AsyncClient):
    """Doctor token must be rejected on patient-scoped endpoints."""
    token = await _login(client, _DOCTOR)
    resp = await client.get("/api/v1/patients/me", headers=_auth(token))
    assert resp.status_code == 403


async def test_patient_cannot_access_admin_endpoints(client: AsyncClient):
    token = await _login(client, _PATIENT_A)
    resp = await client.get("/api/v1/admin/stats/overview", headers=_auth(token))
    assert resp.status_code == 403


async def test_doctor_cannot_access_admin_endpoints(client: AsyncClient):
    token = await _login(client, _DOCTOR)
    resp = await client.get("/api/v1/admin/stats/overview", headers=_auth(token))
    assert resp.status_code == 403


async def test_patient_cannot_book_on_behalf_of_doctor(client: AsyncClient):
    """Booking endpoint is patient-only; doctor token must be rejected."""
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    resp = await client.post(
        "/api/v1/appointments",
        headers=_auth(doctor_token),
        json={"doctor_id": doctor_id, "scheduled_at": _future()},
    )
    assert resp.status_code == 403


# ── 3. IDOR ───────────────────────────────────────────────────────────────────


async def test_patient_cannot_view_another_patients_appointment(client: AsyncClient):
    """Patient B must not be able to retrieve Patient A's appointment by ID."""
    token_a = await _login(client, _PATIENT_A)
    token_b = await _login(client, _PATIENT_B)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)

    appt = await _book(client, token_a, doctor_id)
    resp = await client.get(f"/api/v1/appointments/{appt['id']}", headers=_auth(token_b))
    assert resp.status_code == 403


async def test_patient_cannot_cancel_another_patients_appointment(client: AsyncClient):
    """Patient B must not be able to cancel Patient A's appointment."""
    token_a = await _login(client, _PATIENT_A)
    token_b = await _login(client, _PATIENT_B)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)

    appt = await _book(client, token_a, doctor_id)
    resp = await client.patch(f"/api/v1/appointments/{appt['id']}/cancel", headers=_auth(token_b))
    assert resp.status_code == 403


async def test_patient_cannot_view_another_patients_diagnosis(client: AsyncClient):
    """Patient B must get 404 when requesting Patient A's diagnosis (resource existence hidden)."""
    token_a = await _login(client, _PATIENT_A)
    token_b = await _login(client, _PATIENT_B)

    with _mock_celery():
        resp_create = await client.post(
            "/api/v1/diagnoses",
            headers=_auth(token_a),
            json={"image_keys": _IMAGE_KEYS},
        )
    assert resp_create.status_code == 202
    diagnosis_id = resp_create.json()["id"]

    resp = await client.get(f"/api/v1/diagnoses/{diagnosis_id}", headers=_auth(token_b))
    # Returns 404, not 403 — does not reveal resource existence
    assert resp.status_code == 404


async def test_patient_cannot_view_another_patients_payment(client: AsyncClient):
    """Patient B must get 403 when requesting the payment status of Patient A's appointment."""
    token_a = await _login(client, _PATIENT_A)
    token_b = await _login(client, _PATIENT_B)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)

    appt = await _book(client, token_a, doctor_id)
    resp = await client.get(f"/api/v1/payments/appointments/{appt['id']}", headers=_auth(token_b))
    assert resp.status_code == 403


async def test_patient_cannot_initiate_checkout_for_another_patients_appointment(
    client: AsyncClient,
):
    """Patient B must not be able to create a checkout session for Patient A's appointment."""
    token_a = await _login(client, _PATIENT_A)
    token_b = await _login(client, _PATIENT_B)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)

    appt = await _book(client, token_a, doctor_id)
    with patch("stripe.checkout.Session.create"):
        resp = await client.post(
            f"/api/v1/payments/appointments/{appt['id']}/checkout",
            headers=_auth(token_b),
        )
    assert resp.status_code == 403


# ── 4. JWT tampering ──────────────────────────────────────────────────────────


async def test_forged_jwt_signature_rejected(client: AsyncClient):
    """A JWT signed with the wrong secret must be rejected with 401."""
    fake_id = str(uuid.uuid4())
    token = _forge_token(fake_id)
    resp = await client.get("/api/v1/auth/me", headers=_auth(token))
    assert resp.status_code == 401


async def test_expired_jwt_rejected(client: AsyncClient):
    """An expired JWT (valid secret) must be rejected with 401."""
    # Register a real user so the sub resolves to a real user_id
    await client.post("/api/v1/auth/register", json=_PATIENT_A)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": _PATIENT_A["email"], "password": _PATIENT_A["password"]},
    )
    user_id = jwt.decode(resp.json()["access_token"], settings.SECRET_KEY, algorithms=["HS256"])[
        "sub"
    ]

    expired = _expired_token(user_id)
    resp2 = await client.get("/api/v1/auth/me", headers=_auth(expired))
    assert resp2.status_code == 401


async def test_alg_none_jwt_rejected(client: AsyncClient):
    """A JWT with alg=none (unsigned) must be rejected — algorithm confusion attack."""
    fake_id = str(uuid.uuid4())
    token = _none_alg_token(fake_id)
    resp = await client.get("/api/v1/auth/me", headers=_auth(token))
    assert resp.status_code in (401, 403)


async def test_jwt_role_field_cannot_escalate_privileges(client: AsyncClient):
    """
    A token carrying role='admin' in the JWT payload for a patient user
    must still be denied on admin endpoints — the server uses the DB role,
    not the JWT payload role.
    """
    await client.post("/api/v1/auth/register", json=_PATIENT_A)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": _PATIENT_A["email"], "password": _PATIENT_A["password"]},
    )
    user_id = jwt.decode(
        login_resp.json()["access_token"], settings.SECRET_KEY, algorithms=["HS256"]
    )["sub"]

    escalated = _role_escalated_token(user_id)
    resp = await client.get("/api/v1/admin/stats/overview", headers=_auth(escalated))
    assert resp.status_code == 403


# ── 5. mass assignment ────────────────────────────────────────────────────────


async def test_cannot_register_with_admin_role(client: AsyncClient):
    """Registration must reject 'admin' as a role value."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "evil@security-tests.dev",
            "password": "EvilPass1",
            "role": "admin",
            "first_name": "Evil",
            "last_name": "Admin",
        },
    )
    assert resp.status_code == 422


async def test_cannot_register_with_arbitrary_role(client: AsyncClient):
    """Registration must reject unknown role values."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "evil2@security-tests.dev",
            "password": "EvilPass1",
            "role": "superuser",
            "first_name": "Evil",
            "last_name": "Super",
        },
    )
    assert resp.status_code == 422


# ── 6. deactivated user ───────────────────────────────────────────────────────


async def test_deactivated_user_token_rejected(client: AsyncClient):
    """
    A valid, non-expired JWT for a deactivated account must be rejected.
    `get_current_user` checks `user.is_active` on every request.
    """
    # Register and log in to get a token
    await client.post("/api/v1/auth/register", json=_PATIENT_A)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": _PATIENT_A["email"], "password": _PATIENT_A["password"]},
    )
    token = login_resp.json()["access_token"]
    user_id = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])["sub"]

    # Deactivate directly in the test DB
    engine = create_async_engine(TEST_DATABASE_URL)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        user.is_active = False
        await session.commit()
    await engine.dispose()

    # The token is still structurally valid, but the user is now inactive
    resp = await client.get("/api/v1/auth/me", headers=_auth(token))
    assert resp.status_code == 401

    # Restore to avoid polluting other tests that use the same user
    engine = create_async_engine(TEST_DATABASE_URL)
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        u.is_active = True
        await s.commit()
    await engine.dispose()


# ── 7. webhook security ───────────────────────────────────────────────────────


async def test_webhook_without_signature_rejected(client: AsyncClient):
    """Stripe webhook endpoint must reject requests without a valid signature."""
    with patch("stripe.Webhook.construct_event", side_effect=ValueError("no sig")):
        resp = await client.post(
            "/api/v1/payments/webhook",
            content=b'{"type": "checkout.session.completed"}',
            headers={"stripe-signature": ""},
        )
    assert resp.status_code == 400


async def test_webhook_with_no_stripe_header_rejected(client: AsyncClient):
    """Webhook must reject requests that omit the stripe-signature header entirely."""
    with patch("stripe.Webhook.construct_event", side_effect=ValueError("missing header")):
        resp = await client.post(
            "/api/v1/payments/webhook",
            content=b"{}",
        )
    assert resp.status_code == 400
