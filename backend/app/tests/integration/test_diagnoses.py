"""Integration tests for the diagnoses endpoints.

All AI (Gemini, Groq) and Celery calls are mocked — no external services needed.
"""

from httpx import AsyncClient

_PATIENT = {
    "email": "patient@diag-tests.dev",
    "password": "TestPass1",
    "role": "patient",
    "first_name": "Ada",
    "last_name": "Obi",
}

_DOCTOR = {
    "email": "doctor@diag-tests.dev",
    "password": "DoctorPass1",
    "role": "doctor",
    "first_name": "Emeka",
    "last_name": "Nwosu",
}

_IMAGE_KEYS = ["images/user-id/00000000-0000-0000-0000-000000000001.jpg"]
_MODALITY = "chest_xray"


async def _login(client: AsyncClient, user: dict) -> str:
    await client.post("/api/v1/auth/register", json=user)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    return resp.json()["access_token"]


# ── create diagnosis ──────────────────────────────────────────────────────────


async def test_create_diagnosis_returns_pending(client: AsyncClient):
    token = await _login(client, _PATIENT)

    resp = await client.post(
        "/api/v1/diagnoses",
        headers={"Authorization": f"Bearer {token}"},
        json={"image_keys": _IMAGE_KEYS, "modality": _MODALITY},
    )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pending"
    assert data["image_keys"] == _IMAGE_KEYS
    assert "id" in data


async def test_create_diagnosis_with_patient_notes(client: AsyncClient):
    token = await _login(client, _PATIENT)

    resp = await client.post(
        "/api/v1/diagnoses",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "image_keys": _IMAGE_KEYS,
            "modality": _MODALITY,
            "patient_notes": "Blurry vision for 2 weeks",
        },
    )

    assert resp.status_code == 202
    data = resp.json()
    assert data["report"]["patient_notes"] == "Blurry vision for 2 weeks"


async def test_create_diagnosis_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/diagnoses",
        json={"image_keys": _IMAGE_KEYS, "modality": _MODALITY},
    )
    assert resp.status_code == 403


async def test_create_diagnosis_doctor_cannot_submit(client: AsyncClient):
    token = await _login(client, _DOCTOR)
    resp = await client.post(
        "/api/v1/diagnoses",
        headers={"Authorization": f"Bearer {token}"},
        json={"image_keys": _IMAGE_KEYS, "modality": _MODALITY},
    )
    assert resp.status_code == 403


async def test_create_diagnosis_rejects_empty_image_keys(client: AsyncClient):
    token = await _login(client, _PATIENT)
    resp = await client.post(
        "/api/v1/diagnoses",
        headers={"Authorization": f"Bearer {token}"},
        json={"image_keys": []},
    )
    assert resp.status_code == 422


async def test_create_diagnosis_rejects_too_many_images(client: AsyncClient):
    token = await _login(client, _PATIENT)
    resp = await client.post(
        "/api/v1/diagnoses",
        headers={"Authorization": f"Bearer {token}"},
        json={"image_keys": [f"images/uid/{i}.jpg" for i in range(6)]},
    )
    assert resp.status_code == 422


# ── list / get ────────────────────────────────────────────────────────────────


async def test_list_diagnoses_returns_own_only(client: AsyncClient):
    token = await _login(client, _PATIENT)

    await client.post(
        "/api/v1/diagnoses",
        headers={"Authorization": f"Bearer {token}"},
        json={"image_keys": _IMAGE_KEYS, "modality": _MODALITY},
    )

    resp = await client.get(
        "/api/v1/diagnoses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    assert all(item["status"] == "pending" for item in items)


async def test_get_diagnosis_by_id(client: AsyncClient):
    token = await _login(client, _PATIENT)

    create_resp = await client.post(
        "/api/v1/diagnoses",
        headers={"Authorization": f"Bearer {token}"},
        json={"image_keys": _IMAGE_KEYS, "modality": _MODALITY},
    )
    diagnosis_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/diagnoses/{diagnosis_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == diagnosis_id


async def test_get_diagnosis_not_found(client: AsyncClient):
    token = await _login(client, _PATIENT)
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(
        f"/api/v1/diagnoses/{fake_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ── doctor review ─────────────────────────────────────────────────────────────


async def test_doctor_can_review_diagnosis(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)

    create_resp = await client.post(
        "/api/v1/diagnoses",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"image_keys": _IMAGE_KEYS, "modality": _MODALITY},
    )
    diagnosis_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/diagnoses/{diagnosis_id}/review",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"notes": "Confirmed glaucoma signs.", "status": "confirmed"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "confirmed"
    assert data["doctor_notes"] == "Confirmed glaucoma signs."


async def test_doctor_review_rejects_invalid_status(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)

    create_resp = await client.post(
        "/api/v1/diagnoses",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"image_keys": _IMAGE_KEYS, "modality": _MODALITY},
    )
    diagnosis_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/diagnoses/{diagnosis_id}/review",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"notes": "Some notes", "status": "hacked"},
    )
    assert resp.status_code == 422


async def test_doctor_pending_queue(client: AsyncClient):
    doctor_token = await _login(client, _DOCTOR)
    resp = await client.get(
        "/api/v1/diagnoses/queue/pending",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
