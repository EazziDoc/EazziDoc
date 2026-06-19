"""
Admin API integration tests.
Admin users are created directly in the DB (no public registration for admin role).
"""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

from app.core.security import hash_password
from app.models.user import User

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost/eazzidoc_test"

ADMIN_EMAIL = "admin@admin-tests.dev"
ADMIN_PASSWORD = "AdminPass1"

PATIENT_DATA = {
    "email": "patient@admin-tests.dev",
    "password": "PatientPass1",
    "role": "patient",
    "first_name": "Ama",
    "last_name": "Adjei",
}

DOCTOR_DATA = {
    "email": "doctor@admin-tests.dev",
    "password": "DoctorPass1",
    "role": "doctor",
    "first_name": "Kwame",
    "last_name": "Mensah",
}


async def _create_admin(client: AsyncClient) -> str:
    """Insert admin user directly into DB and return access token."""
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
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── access control ─────────────────────────────────────────────────────────────


async def test_non_admin_cannot_access(client: AsyncClient):
    await client.post("/api/v1/auth/register", json=PATIENT_DATA)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": PATIENT_DATA["email"], "password": PATIENT_DATA["password"]},
    )
    token = resp.json()["access_token"]
    r = await client.get("/api/v1/admin/stats/overview", headers=_auth(token))
    assert r.status_code == 403


async def test_unauthenticated_cannot_access(client: AsyncClient):
    r = await client.get("/api/v1/admin/stats/overview")
    assert r.status_code == 403  # HTTPBearer returns 403 on missing creds


# ── overview stats ─────────────────────────────────────────────────────────────


async def test_overview_stats(client: AsyncClient):
    token = await _create_admin(client)
    # seed a patient
    await client.post("/api/v1/auth/register", json=PATIENT_DATA)

    r = await client.get("/api/v1/admin/stats/overview", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert "total_users" in data
    assert "total_patients" in data
    assert "total_diagnoses" in data
    assert data["total_users"] >= 2  # admin + patient


# ── diagnosis stats ────────────────────────────────────────────────────────────


async def test_diagnosis_stats(client: AsyncClient):
    token = await _create_admin(client)
    r = await client.get("/api/v1/admin/stats/diagnoses", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert "by_modality" in data
    assert "by_status" in data
    assert "override_rate" in data


# ── appointment stats ─────────────────────────────────────────────────────────


async def test_appointment_stats(client: AsyncClient):
    token = await _create_admin(client)
    r = await client.get("/api/v1/admin/stats/appointments", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "cancellation_rate" in data


# ── user list ─────────────────────────────────────────────────────────────────


async def test_list_users_default(client: AsyncClient):
    token = await _create_admin(client)
    await client.post("/api/v1/auth/register", json=PATIENT_DATA)
    r = await client.get("/api/v1/admin/users", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert "users" in data
    assert "total" in data
    assert data["total"] >= 2


async def test_list_users_filter_by_role(client: AsyncClient):
    token = await _create_admin(client)
    await client.post("/api/v1/auth/register", json=DOCTOR_DATA)
    r = await client.get("/api/v1/admin/users?role=doctor", headers=_auth(token))
    assert r.status_code == 200
    assert all(u["role"] == "doctor" for u in r.json()["users"])


async def test_list_users_search_by_email(client: AsyncClient):
    token = await _create_admin(client)
    await client.post("/api/v1/auth/register", json=PATIENT_DATA)
    r = await client.get("/api/v1/admin/users?search=patient%40admin-tests", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["total"] >= 1


# ── single user detail ────────────────────────────────────────────────────────


async def test_get_user_detail_patient(client: AsyncClient):
    token = await _create_admin(client)
    reg = await client.post("/api/v1/auth/register", json=PATIENT_DATA)
    user_id = reg.json()["user_id"]

    r = await client.get(f"/api/v1/admin/users/{user_id}", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "patient"
    assert data["display_name"] == "Ama Adjei"
    assert "total_diagnoses" in data


async def test_get_user_detail_not_found(client: AsyncClient):
    token = await _create_admin(client)
    r = await client.get(f"/api/v1/admin/users/{uuid.uuid4()}", headers=_auth(token))
    assert r.status_code == 404


# ── user update ───────────────────────────────────────────────────────────────


async def test_deactivate_user(client: AsyncClient):
    token = await _create_admin(client)
    reg = await client.post("/api/v1/auth/register", json=PATIENT_DATA)
    user_id = reg.json()["user_id"]

    r = await client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"is_active": False},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


async def test_verify_doctor(client: AsyncClient):
    token = await _create_admin(client)
    reg = await client.post("/api/v1/auth/register", json=DOCTOR_DATA)
    user_id = reg.json()["user_id"]

    r = await client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"is_verified": True},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["is_verified"] is True


async def test_admin_cannot_modify_self(client: AsyncClient):
    token = await _create_admin(client)
    # Get own user_id
    me = await client.get("/api/v1/auth/me", headers=_auth(token))
    user_id = me.json()["id"]

    r = await client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"is_active": False},
        headers=_auth(token),
    )
    assert r.status_code == 400


# ── diagnosis list ────────────────────────────────────────────────────────────


async def test_list_diagnoses(client: AsyncClient):
    token = await _create_admin(client)
    r = await client.get("/api/v1/admin/diagnoses", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert "diagnoses" in data
    assert "total" in data


async def test_list_diagnoses_filter_by_status(client: AsyncClient):
    token = await _create_admin(client)
    r = await client.get("/api/v1/admin/diagnoses?status=pending", headers=_auth(token))
    assert r.status_code == 200
    for dx in r.json()["diagnoses"]:
        assert dx["status"] == "pending"


# ── requeue ───────────────────────────────────────────────────────────────────


async def test_requeue_nonexistent_diagnosis(client: AsyncClient):
    token = await _create_admin(client)
    r = await client.post(
        f"/api/v1/admin/diagnoses/{uuid.uuid4()}/requeue",
        headers=_auth(token),
    )
    assert r.status_code == 404


# ── queue health ──────────────────────────────────────────────────────────────


async def test_queue_health_returns_structure(client: AsyncClient):
    token = await _create_admin(client)
    r = await client.get("/api/v1/admin/queue/health", headers=_auth(token))
    # Workers may be offline in test env — still expect the schema
    assert r.status_code == 200
    data = r.json()
    assert "workers" in data
    assert "active_tasks" in data
    assert "pending_in_broker" in data
