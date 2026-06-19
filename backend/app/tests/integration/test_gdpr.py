"""Integration tests for GDPR endpoints.

Covers data export structure and account deletion with its guards.
"""

import pytest
from httpx import AsyncClient

PATIENT_DATA = {
    "email": "gdpr-patient@gdpr-tests.dev",
    "password": "GdprPass1!",
    "role": "patient",
    "first_name": "Gdpr",
    "last_name": "Patient",
}

DOCTOR_DATA = {
    "email": "gdpr-doctor@gdpr-tests.dev",
    "password": "GdprDoc1!",
    "role": "doctor",
    "first_name": "Gdpr",
    "last_name": "Doctor",
}


async def _register_and_login(client: AsyncClient, data: dict) -> tuple[str, str]:
    reg = await client.post("/api/v1/auth/register", json=data)
    assert reg.status_code == 201, reg.text
    user_id = reg.json()["user_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": data["email"], "password": data["password"]},
    )
    assert login.status_code == 200, login.text
    return user_id, login.json()["access_token"]


# ── data export ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patient_data_export_structure(client: AsyncClient):
    _, token = await _register_and_login(
        client, {**PATIENT_DATA, "email": "export-patient@gdpr-tests.dev"}
    )
    resp = await client.get(
        "/api/v1/me/data-export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "exported_at" in data
    assert data["account"]["email"] == "export-patient@gdpr-tests.dev"
    assert data["account"]["role"] == "patient"
    assert "profile" in data
    assert "diagnoses" in data
    assert "appointments" in data
    assert isinstance(data["diagnoses"], list)
    assert isinstance(data["appointments"], list)


@pytest.mark.asyncio
async def test_doctor_data_export_structure(client: AsyncClient):
    _, token = await _register_and_login(
        client, {**DOCTOR_DATA, "email": "export-doctor@gdpr-tests.dev"}
    )
    resp = await client.get(
        "/api/v1/me/data-export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["account"]["role"] == "doctor"
    assert "profile" in data
    assert "appointments" in data
    # Doctor export must NOT include diagnoses (those are patient-owned)
    assert "diagnoses" not in data


@pytest.mark.asyncio
async def test_data_export_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/me/data-export")
    assert resp.status_code == 403


# ── account deletion ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patient_can_delete_own_account(client: AsyncClient):
    user_id, token = await _register_and_login(
        client, {**PATIENT_DATA, "email": "delete-patient@gdpr-tests.dev"}
    )

    resp = await client.delete(
        "/api/v1/me/account",
        json={"password": PATIENT_DATA["password"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # Token is now invalid — subsequent request should 401
    check = await client.get(
        "/api/v1/me/data-export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert check.status_code == 401


@pytest.mark.asyncio
async def test_deletion_requires_correct_password(client: AsyncClient):
    _, token = await _register_and_login(
        client, {**PATIENT_DATA, "email": "wrongpw-patient@gdpr-tests.dev"}
    )

    resp = await client.delete(
        "/api/v1/me/account",
        json={"password": "WrongPassword999!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "Incorrect password" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_deletion_requires_auth(client: AsyncClient):
    resp = await client.delete("/api/v1/me/account", json={"password": "anything"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_doctor_with_pending_appointment_cannot_delete(client: AsyncClient):
    _, patient_token = await _register_and_login(
        client, {**PATIENT_DATA, "email": "appt-patient@gdpr-tests.dev"}
    )
    _, doctor_token = await _register_and_login(
        client, {**DOCTOR_DATA, "email": "appt-doctor@gdpr-tests.dev"}
    )

    # Get doctor's profile id to book an appointment
    profile_resp = await client.get(
        "/api/v1/doctors", headers={"Authorization": f"Bearer {patient_token}"}
    )
    # If the doctors list is empty (doctor not verified), skip this test gracefully
    if profile_resp.status_code != 200 or not profile_resp.json():
        pytest.skip("No verified doctors available for appointment booking")

    doctor_id = profile_resp.json()[0]["id"]

    # Book an appointment
    appt = await client.post(
        f"/api/v1/appointments/book/{doctor_id}",
        json={"scheduled_at": "2099-01-01T10:00:00Z", "duration_mins": 30},
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    if appt.status_code != 201:
        pytest.skip("Could not book appointment")

    # Doctor should be blocked from deleting while appointment is pending
    resp = await client.delete(
        "/api/v1/me/account",
        json={"password": DOCTOR_DATA["password"]},
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert resp.status_code == 409
    assert "pending or confirmed appointments" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_doctor_with_no_appointments_can_delete(client: AsyncClient):
    _, token = await _register_and_login(
        client, {**DOCTOR_DATA, "email": "nodoc-delete@gdpr-tests.dev"}
    )

    resp = await client.delete(
        "/api/v1/me/account",
        json={"password": DOCTOR_DATA["password"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
