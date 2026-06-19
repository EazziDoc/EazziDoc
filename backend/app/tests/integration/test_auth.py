from httpx import AsyncClient

PATIENT = {
    "email": "patient@auth-tests.dev",
    "password": "TestPass1",
    "role": "patient",
    "first_name": "Ada",
    "last_name": "Obi",
}

DOCTOR = {
    "email": "doctor@auth-tests.dev",
    "password": "DoctorPass1",
    "role": "doctor",
    "first_name": "Emeka",
    "last_name": "Nwosu",
}

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
        json={**PATIENT, "email": "new@auth-tests.dev", "password": "weakpass"},
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
        json={"email": "nobody@auth-tests.dev", "password": "TestPass1"},
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
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403


async def test_me_with_invalid_token(client: AsyncClient):
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
