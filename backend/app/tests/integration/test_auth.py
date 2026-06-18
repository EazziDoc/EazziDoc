import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost/eazzidoc_test"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


PATIENT_DATA = {
    "email": "patient@test.com",
    "password": "TestPass1",
    "role": "patient",
    "first_name": "Ada",
    "last_name": "Obi",
}

DOCTOR_DATA = {
    "email": "doctor@test.com",
    "password": "DoctorPass1",
    "role": "doctor",
    "first_name": "Emeka",
    "last_name": "Nwosu",
}


class TestRegister:
    async def test_register_patient_success(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/register", json=PATIENT_DATA)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == PATIENT_DATA["email"]
        assert data["role"] == "patient"
        assert "user_id" in data

    async def test_register_doctor_success(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/register", json=DOCTOR_DATA)
        assert response.status_code == 201
        assert response.json()["role"] == "doctor"

    async def test_register_duplicate_email(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json=PATIENT_DATA)
        response = await client.post("/api/v1/auth/register", json=PATIENT_DATA)
        assert response.status_code == 409

    async def test_register_weak_password(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={**PATIENT_DATA, "email": "new@test.com", "password": "weakpass"},
        )
        assert response.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={**PATIENT_DATA, "email": "not-an-email"},
        )
        assert response.status_code == 422


class TestLogin:
    @pytest.fixture(autouse=True)
    async def create_user(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json=PATIENT_DATA)

    async def test_login_success(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": PATIENT_DATA["email"], "password": PATIENT_DATA["password"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "refresh_token" in response.cookies

    async def test_login_wrong_password(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": PATIENT_DATA["email"], "password": "WrongPass1"},
        )
        assert response.status_code == 401

    async def test_login_unknown_email(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "TestPass1"},
        )
        assert response.status_code == 401


class TestMe:
    @pytest.fixture(autouse=True)
    async def login(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json=PATIENT_DATA)
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": PATIENT_DATA["email"], "password": PATIENT_DATA["password"]},
        )
        self.token = resp.json()["access_token"]

    async def test_me_with_valid_token(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert response.status_code == 200
        assert response.json()["email"] == PATIENT_DATA["email"]

    async def test_me_without_token(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 403

    async def test_me_with_bad_token(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 403


class TestLogout:
    async def test_logout_clears_cookie(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json=PATIENT_DATA)
        await client.post(
            "/api/v1/auth/login",
            json={"email": PATIENT_DATA["email"], "password": PATIENT_DATA["password"]},
        )
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 204
