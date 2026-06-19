"""Integration tests for the audit log.

Verifies that admin actions produce entries in the audit_logs table and
that the GET /admin/audit-logs endpoint surfaces them correctly.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

from app.core.security import hash_password
from app.models.user import User

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost/eazzidoc_test"

ADMIN_EMAIL = "admin@audit-tests.dev"
ADMIN_PASSWORD = "AdminAudit1!"

PATIENT_DATA = {
    "email": "patient@audit-tests.dev",
    "password": "PatientAudit1!",
    "role": "patient",
    "first_name": "Audit",
    "last_name": "Patient",
}


async def _create_admin(client: AsyncClient) -> str:
    engine = create_async_engine(TEST_DATABASE_URL)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        existing = (
            await session.execute(select(User).where(User.email == ADMIN_EMAIL))
        ).scalar_one_or_none()
        if not existing:
            admin = User(
                id=uuid.uuid4(),
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                role="admin",
                is_verified=True,
                is_active=True,
            )
            session.add(admin)
            await session.commit()
    await engine.dispose()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_audit_log_empty_initially(client: AsyncClient):
    token = await _create_admin(client)
    resp = await client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert "total" in data
    assert isinstance(data["entries"], list)


@pytest.mark.asyncio
async def test_deactivate_user_creates_audit_entry(client: AsyncClient):
    token = await _create_admin(client)

    # Register a patient to deactivate
    reg = await client.post(
        "/api/v1/auth/register",
        json={**PATIENT_DATA, "email": "deactivate-audit@audit-tests.dev"},
    )
    assert reg.status_code == 201, reg.text
    user_id = reg.json()["user_id"]

    # Deactivate via admin
    patch = await client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch.status_code == 200, patch.text

    # Check audit log
    logs = await client.get(
        "/api/v1/admin/audit-logs",
        params={"target_id": user_id, "action": "user.deactivated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logs.status_code == 200
    data = logs.json()
    assert data["total"] >= 1
    entry = data["entries"][0]
    assert entry["action"] == "user.deactivated"
    assert entry["target_type"] == "user"
    assert entry["target_id"] == user_id
    assert entry["meta"]["changes"]["is_active"]["to"] is False
    assert entry["actor_email"] == ADMIN_EMAIL


@pytest.mark.asyncio
async def test_verify_doctor_creates_audit_entry(client: AsyncClient):
    token = await _create_admin(client)

    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "verify-audit@audit-tests.dev",
            "password": "DoctorAudit1!",
            "role": "doctor",
            "first_name": "Verify",
            "last_name": "Audit",
        },
    )
    assert reg.status_code == 201, reg.text
    user_id = reg.json()["user_id"]

    patch = await client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"is_verified": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch.status_code == 200, patch.text

    logs = await client.get(
        "/api/v1/admin/audit-logs",
        params={"target_id": user_id, "action": "doctor.verified"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logs.status_code == 200
    data = logs.json()
    assert data["total"] >= 1
    entry = data["entries"][0]
    assert entry["action"] == "doctor.verified"
    assert entry["meta"]["changes"]["is_verified"]["to"] is True


@pytest.mark.asyncio
async def test_audit_log_filters_by_action(client: AsyncClient):
    token = await _create_admin(client)

    resp = await client.get(
        "/api/v1/admin/audit-logs",
        params={"action": "nonexistent.action"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["entries"] == []


@pytest.mark.asyncio
async def test_audit_log_requires_admin(client: AsyncClient):
    reg = await client.post("/api/v1/auth/register", json=PATIENT_DATA)
    token = (
        reg.json().get("access_token")
        or (
            await client.post(
                "/api/v1/auth/login",
                json={"email": PATIENT_DATA["email"], "password": PATIENT_DATA["password"]},
            )
        ).json()["access_token"]
    )

    resp = await client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_no_audit_entry_when_nothing_changes(client: AsyncClient):
    """PATCH with values identical to current state must not write an audit entry."""
    token = await _create_admin(client)

    reg = await client.post(
        "/api/v1/auth/register",
        json={**PATIENT_DATA, "email": "no-change-audit@audit-tests.dev"},
    )
    user_id = reg.json()["user_id"]

    # is_active is True by default — patching with True is a no-op
    await client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"is_active": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    logs = await client.get(
        "/api/v1/admin/audit-logs",
        params={"target_id": user_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logs.json()["total"] == 0
