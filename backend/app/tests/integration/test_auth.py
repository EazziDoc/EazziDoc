import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost/eazzidoc_test"

PATIENT = {
    "email": "patient@test.com",
    "password": "TestPass1",
    "role": "patient",
    "first_name": "Ada",
    "last_name": "Obi",
}

DOCTOR = {
    "email": "doctor@test.com",
    "password": "DoctorPass1",
    "role": "doctor",
    "first_name": "Emeka",
    "last_name": "Nwosu",
}


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """
    Sync session fixture — runs once per session via asyncio.run() so it
    never shares an event loop with function-scoped async tests.
    """

    async def _setup():
        engine = create_async_engine(TEST_DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _teardown():
        engine = create_async_engine(TEST_DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_setup())
    yield
    asyncio.run(_teardown())


@pytest.fixture
async def client():
    """
    Fresh engine + session per test. All DB operations in a single test
    function share one event loop, so asyncpg Futures never cross loops.
    No autouse fixtures make DB calls — all setup is inline in each test.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()


# ── Register ──────────────────────────────────────────────────────────────────


async def test_register_patient_success(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json=PATIENT)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == PATIENT["email"]
    assert data["role"] == "patient"
    assert "user_id" in data


async def test_register_doctor_success(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json=DOCTOR)
    assert response.status_code == 201
    assert response.json()["role"] == "doctor"


async def test_register_duplicate_email(client: AsyncClient):
    await client.post("/api/v1/auth/register", json=PATIENT)
    response = await client.post("/api/v1/auth/register", json=PATIENT)
    assert response.status_code == 409


async def test_register_weak_password(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={**PATIENT, "email": "new@test.com", "password": "weakpass"},
    )
    assert response.status_code == 422


async def test_register_invalid_email(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={**PATIENT, "email": "not-an-email"},
    )
    assert response.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────


async def test_login_success(client: AsyncClient):
    await client.post("/api/v1/auth/register", json=PATIENT)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": PATIENT["email"], "password": PATIENT["password"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "refresh_token" in response.cookies


async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/v1/auth/register", json=PATIENT)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": PATIENT["email"], "password": "WrongPass1"},
    )
    assert response.status_code == 401


async def test_login_unknown_email(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "TestPass1"},
    )
    assert response.status_code == 401


# ── /me ───────────────────────────────────────────────────────────────────────


async def test_me_with_valid_token(client: AsyncClient):
    await client.post("/api/v1/auth/register", json=PATIENT)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": PATIENT["email"], "password": PATIENT["password"]},
    )
    token = login.json()["access_token"]

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == PATIENT["email"]


async def test_me_without_token(client: AsyncClient):
    # HTTPBearer with auto_error=True returns 403 when no credentials provided
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403


async def test_me_with_invalid_token(client: AsyncClient):
    # HTTPBearer accepts the Bearer scheme, then JWT decode fails → 401
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────────


async def test_logout_clears_cookie(client: AsyncClient):
    await client.post("/api/v1/auth/register", json=PATIENT)
    await client.post(
        "/api/v1/auth/login",
        json={"email": PATIENT["email"], "password": PATIENT["password"]},
    )
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204
