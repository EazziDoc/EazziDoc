"""Integration tests for the appointments endpoints."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

_PATIENT = {
    "email": "patient@appt-tests.dev",
    "password": "TestPass1",
    "role": "patient",
    "first_name": "Ada",
    "last_name": "Obi",
}

_DOCTOR = {
    "email": "doctor@appt-tests.dev",
    "password": "DoctorPass1",
    "role": "doctor",
    "first_name": "Emeka",
    "last_name": "Nwosu",
}


def _future() -> str:
    """ISO datetime 2 days from now."""
    return (datetime.now(UTC) + timedelta(days=2)).isoformat()


async def _login(client: AsyncClient, user: dict) -> str:
    await client.post("/api/v1/auth/register", json=user)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    return resp.json()["access_token"]


async def _get_doctor_id(client: AsyncClient, doctor_token: str) -> str:
    """Get doctors.id by fetching the doctor's own profile."""
    resp = await client.get(
        "/api/v1/doctors/me", headers={"Authorization": f"Bearer {doctor_token}"}
    )
    return resp.json()["id"]


async def _book(client: AsyncClient, patient_token: str, doctor_id: str) -> dict:
    resp = await client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"doctor_id": doctor_id, "scheduled_at": _future()},
    )
    return resp.json()


# ── browse doctors ────────────────────────────────────────────────────────────


async def test_list_available_doctors_public(client: AsyncClient):
    """No auth required to browse doctors."""
    await _login(client, _DOCTOR)
    resp = await client.get("/api/v1/doctors")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── book ──────────────────────────────────────────────────────────────────────


async def test_patient_books_appointment(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)

    resp = await client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={
            "doctor_id": doctor_id,
            "scheduled_at": _future(),
            "duration_mins": 45,
            "notes": "Follow-up on fundus scan",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "booked"
    assert data["doctor_id"] == doctor_id
    assert data["duration_mins"] == 45


async def test_book_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/appointments",
        json={"doctor_id": "00000000-0000-0000-0000-000000000000", "scheduled_at": _future()},
    )
    assert resp.status_code == 403


async def test_doctor_cannot_book(client: AsyncClient):
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    resp = await client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"doctor_id": doctor_id, "scheduled_at": _future()},
    )
    assert resp.status_code == 403


async def test_book_unknown_doctor_returns_404(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    resp = await client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={
            "doctor_id": "00000000-0000-0000-0000-000000000099",
            "scheduled_at": _future(),
        },
    )
    assert resp.status_code == 404


# ── patient: list / get ───────────────────────────────────────────────────────


async def test_patient_lists_own_appointments(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    await _book(client, patient_token, doctor_id)

    resp = await client.get(
        "/api/v1/appointments", headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_patient_gets_appointment_by_id(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    resp = await client.get(
        f"/api/v1/appointments/{appt['id']}",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == appt["id"]


# ── patient: cancel ───────────────────────────────────────────────────────────


async def test_patient_cancels_booked_appointment(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    resp = await client.patch(
        f"/api/v1/appointments/{appt['id']}/cancel",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_patient_cannot_cancel_completed(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    # Doctor confirms then completes
    await client.patch(
        f"/api/v1/doctor/appointments/{appt['id']}/confirm",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    await client.patch(
        f"/api/v1/doctor/appointments/{appt['id']}/complete",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )

    resp = await client.patch(
        f"/api/v1/appointments/{appt['id']}/cancel",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 409


# ── doctor: workflow ──────────────────────────────────────────────────────────


async def test_doctor_confirms_appointment(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    resp = await client.patch(
        f"/api/v1/doctor/appointments/{appt['id']}/confirm",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


async def test_doctor_completes_confirmed_appointment(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    await client.patch(
        f"/api/v1/doctor/appointments/{appt['id']}/confirm",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    resp = await client.patch(
        f"/api/v1/doctor/appointments/{appt['id']}/complete",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


async def test_doctor_cannot_complete_unconfirmed(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    resp = await client.patch(
        f"/api/v1/doctor/appointments/{appt['id']}/complete",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert resp.status_code == 409


async def test_doctor_lists_own_appointments(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    await _book(client, patient_token, doctor_id)

    resp = await client.get(
        "/api/v1/doctor/appointments",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_doctor_cancels_appointment(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    resp = await client.patch(
        f"/api/v1/doctor/appointments/{appt['id']}/cancel",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
