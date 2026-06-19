"""Integration tests for Stripe payment endpoints."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from httpx import AsyncClient

_PATIENT = {
    "email": "patient@payment-tests.dev",
    "password": "TestPass1",
    "role": "patient",
    "first_name": "Chinwe",
    "last_name": "Okafor",
}

_DOCTOR = {
    "email": "doctor@payment-tests.dev",
    "password": "DoctorPass1",
    "role": "doctor",
    "first_name": "Femi",
    "last_name": "Adeleke",
}

_OTHER_PATIENT = {
    "email": "other@payment-tests.dev",
    "password": "TestPass1",
    "role": "patient",
    "first_name": "Other",
    "last_name": "Patient",
}


def _future() -> str:
    return (datetime.now(UTC) + timedelta(days=2)).isoformat()


async def _login(client: AsyncClient, user: dict) -> str:
    await client.post("/api/v1/auth/register", json=user)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    return resp.json()["access_token"]


async def _get_doctor_id(client: AsyncClient, token: str) -> str:
    resp = await client.get("/api/v1/doctors/me", headers={"Authorization": f"Bearer {token}"})
    return resp.json()["id"]


async def _book(client: AsyncClient, patient_token: str, doctor_id: str) -> dict:
    resp = await client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"doctor_id": doctor_id, "scheduled_at": _future()},
    )
    assert resp.status_code == 201
    return resp.json()


def _fake_session(session_id: str = "cs_test_abc123") -> MagicMock:
    session = MagicMock()
    session.id = session_id
    session.url = f"https://checkout.stripe.com/pay/{session_id}"
    return session


def _checkout_event(session_id: str, payment_intent: str = "pi_test_xyz") -> dict:
    return {
        "type": "checkout.session.completed",
        "data": {"object": {"id": session_id, "payment_intent": payment_intent}},
    }


def _failed_event(payment_intent: str) -> dict:
    return {
        "type": "payment_intent.payment_failed",
        "data": {"object": {"id": payment_intent}},
    }


# ── checkout ──────────────────────────────────────────────────────────────────


async def test_checkout_returns_url(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    with patch("stripe.checkout.Session.create", return_value=_fake_session()) as mock_create:
        resp = await client.post(
            f"/api/v1/payments/appointments/{appt['id']}/checkout",
            headers={"Authorization": f"Bearer {patient_token}"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert "checkout.stripe.com" in data["checkout_url"]
    assert uuid.UUID(data["payment_id"])
    mock_create.assert_called_once()


async def test_checkout_requires_patient_auth(client: AsyncClient):
    resp = await client.post(f"/api/v1/payments/appointments/{uuid.uuid4()}/checkout")
    assert resp.status_code == 403


async def test_checkout_forbidden_for_wrong_patient(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    other_token = await _login(client, _OTHER_PATIENT)
    with patch("stripe.checkout.Session.create", return_value=_fake_session()):
        resp = await client.post(
            f"/api/v1/payments/appointments/{appt['id']}/checkout",
            headers={"Authorization": f"Bearer {other_token}"},
        )
    assert resp.status_code == 403


async def test_checkout_404_for_missing_appointment(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    with patch("stripe.checkout.Session.create", return_value=_fake_session()):
        resp = await client.post(
            f"/api/v1/payments/appointments/{uuid.uuid4()}/checkout",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
    assert resp.status_code == 404


async def test_checkout_409_for_already_paid(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    session_id = "cs_test_paid_idempotent"
    with patch("stripe.checkout.Session.create", return_value=_fake_session(session_id)):
        await client.post(
            f"/api/v1/payments/appointments/{appt['id']}/checkout",
            headers={"Authorization": f"Bearer {patient_token}"},
        )

    event = _checkout_event(session_id)
    with patch("stripe.Webhook.construct_event", return_value=event):
        await client.post(
            "/api/v1/payments/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "t=1,v1=abc"},
        )

    with patch("stripe.checkout.Session.create", return_value=_fake_session("cs_test_new")):
        resp = await client.post(
            f"/api/v1/payments/appointments/{appt['id']}/checkout",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
    assert resp.status_code == 409


# ── get payment status ────────────────────────────────────────────────────────


async def test_get_payment_status_returns_none_before_checkout(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    resp = await client.get(
        f"/api/v1/payments/appointments/{appt['id']}",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() is None


# ── webhook ───────────────────────────────────────────────────────────────────


async def test_webhook_checkout_completed_marks_paid(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    session_id = "cs_test_webhook_paid"
    with patch("stripe.checkout.Session.create", return_value=_fake_session(session_id)):
        await client.post(
            f"/api/v1/payments/appointments/{appt['id']}/checkout",
            headers={"Authorization": f"Bearer {patient_token}"},
        )

    event = _checkout_event(session_id, "pi_test_success")
    with patch("stripe.Webhook.construct_event", return_value=event):
        resp = await client.post(
            "/api/v1/payments/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "t=1,v1=abc"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"received": True}

    status_resp = await client.get(
        f"/api/v1/payments/appointments/{appt['id']}",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert status_resp.json()["status"] == "paid"
    assert status_resp.json()["stripe_payment_intent_id"] == "pi_test_success"


async def test_webhook_invalid_signature_returns_400(client: AsyncClient):
    with patch("stripe.Webhook.construct_event", side_effect=ValueError("bad sig")):
        resp = await client.post(
            "/api/v1/payments/webhook",
            content=b"{}",
            headers={"stripe-signature": "invalid"},
        )
    assert resp.status_code == 400


async def test_webhook_unknown_session_returns_200(client: AsyncClient):
    """Webhook always returns 200 to Stripe; unknown sessions are logged and ignored."""
    event = _checkout_event("cs_test_nonexistent")
    with patch("stripe.Webhook.construct_event", return_value=event):
        resp = await client.post(
            "/api/v1/payments/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "t=1,v1=abc"},
        )
    assert resp.status_code == 200


async def test_webhook_payment_failed_marks_failed(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    session_id = "cs_test_fail_flow"
    intent_id = "pi_test_failed_xyz"
    with patch("stripe.checkout.Session.create", return_value=_fake_session(session_id)):
        await client.post(
            f"/api/v1/payments/appointments/{appt['id']}/checkout",
            headers={"Authorization": f"Bearer {patient_token}"},
        )

    # First simulate completed so payment_intent_id is recorded
    completed_event = _checkout_event(session_id, intent_id)
    with patch("stripe.Webhook.construct_event", return_value=completed_event):
        await client.post(
            "/api/v1/payments/webhook",
            content=json.dumps(completed_event).encode(),
            headers={"stripe-signature": "t=1,v1=abc"},
        )

    # Now simulate failure (edge case: intent marked failed after initial success dispute, etc.)
    failed_event = _failed_event(intent_id)
    with patch("stripe.Webhook.construct_event", return_value=failed_event):
        resp = await client.post(
            "/api/v1/payments/webhook",
            content=json.dumps(failed_event).encode(),
            headers={"stripe-signature": "t=1,v1=abc"},
        )
    assert resp.status_code == 200


# ── cancel with refund ────────────────────────────────────────────────────────


async def test_cancel_paid_appointment_triggers_refund(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    session_id = "cs_test_refund"
    intent_id = "pi_refund_xyz"
    with patch("stripe.checkout.Session.create", return_value=_fake_session(session_id)):
        await client.post(
            f"/api/v1/payments/appointments/{appt['id']}/checkout",
            headers={"Authorization": f"Bearer {patient_token}"},
        )

    event = _checkout_event(session_id, intent_id)
    with patch("stripe.Webhook.construct_event", return_value=event):
        await client.post(
            "/api/v1/payments/webhook",
            content=json.dumps(event).encode(),
            headers={"stripe-signature": "t=1,v1=abc"},
        )

    with patch("stripe.Refund.create", return_value=MagicMock()) as mock_refund:
        cancel_resp = await client.patch(
            f"/api/v1/appointments/{appt['id']}/cancel",
            headers={"Authorization": f"Bearer {patient_token}"},
        )

    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"
    mock_refund.assert_called_once_with(payment_intent=intent_id)

    status_resp = await client.get(
        f"/api/v1/payments/appointments/{appt['id']}",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert status_resp.json()["status"] == "refunded"


async def test_cancel_unpaid_appointment_skips_refund(client: AsyncClient):
    patient_token = await _login(client, _PATIENT)
    doctor_token = await _login(client, _DOCTOR)
    doctor_id = await _get_doctor_id(client, doctor_token)
    appt = await _book(client, patient_token, doctor_id)

    with patch("stripe.Refund.create") as mock_refund:
        cancel_resp = await client.patch(
            f"/api/v1/appointments/{appt['id']}/cancel",
            headers={"Authorization": f"Bearer {patient_token}"},
        )

    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"
    mock_refund.assert_not_called()
