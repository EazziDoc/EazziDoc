from httpx import AsyncClient

PATIENT = {
    "email": "patient@profiles.test",
    "password": "TestPass1",
    "role": "patient",
    "first_name": "Ada",
    "last_name": "Obi",
}

DOCTOR = {
    "email": "doctor@profiles.test",
    "password": "DoctorPass1",
    "role": "doctor",
    "first_name": "Emeka",
    "last_name": "Nwosu",
}


async def _login(client: AsyncClient, user: dict) -> str:
    await client.post("/api/v1/auth/register", json=user)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    return resp.json()["access_token"]


# ── Patient profile ───────────────────────────────────────────────────────────


async def test_get_patient_profile(client: AsyncClient):
    token = await _login(client, PATIENT)
    response = await client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == PATIENT["first_name"]
    assert data["last_name"] == PATIENT["last_name"]
    assert "id" in data


async def test_update_patient_profile(client: AsyncClient):
    token = await _login(client, PATIENT)
    response = await client.patch(
        "/api/v1/patients/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"phone": "+2348012345678", "country": "Nigeria", "gender": "Female"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "+2348012345678"
    assert data["country"] == "Nigeria"


async def test_patient_cannot_access_doctor_endpoint(client: AsyncClient):
    token = await _login(client, PATIENT)
    response = await client.get("/api/v1/doctors/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_patient_profile_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/patients/me")
    assert response.status_code == 403


# ── Doctor profile ────────────────────────────────────────────────────────────


async def test_get_doctor_profile(client: AsyncClient):
    token = await _login(client, DOCTOR)
    response = await client.get("/api/v1/doctors/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == DOCTOR["first_name"]
    assert data["is_verified"] is False


async def test_update_doctor_profile(client: AsyncClient):
    token = await _login(client, DOCTOR)
    response = await client.patch(
        "/api/v1/doctors/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"specialty": "Ophthalmology", "license_number": "MD-NG-12345"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["specialty"] == "Ophthalmology"
    assert data["license_number"] == "MD-NG-12345"


async def test_doctor_set_availability(client: AsyncClient):
    token = await _login(client, DOCTOR)
    response = await client.patch(
        "/api/v1/doctors/me/availability",
        headers={"Authorization": f"Bearer {token}"},
        params={"is_available": False},
    )
    assert response.status_code == 200
    assert response.json()["is_available"] is False


async def test_doctor_cannot_access_patient_endpoint(client: AsyncClient):
    token = await _login(client, DOCTOR)
    response = await client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
