import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import CheckoutResponse, PaymentResponse

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(tags=["payments"])


async def _get_patient_or_404(db: AsyncSession, user: User) -> Patient:
    result = await db.execute(select(Patient).where(Patient.user_id == user.id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient profile not found")
    return p


@router.post(
    "/payments/appointments/{appointment_id}/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_checkout_session(
    appointment_id,
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout Session for an appointment consultation fee."""
    patient = await _get_patient_or_404(db, current_user)

    appt_result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    appt = appt_result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    if appt.patient_id != patient.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your appointment")
    if appt.status == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot pay for a cancelled appointment")

    paid_result = await db.execute(
        select(Payment).where(
            Payment.appointment_id == appt.id,
            Payment.status == "paid",
        )
    )
    if paid_result.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "This appointment is already paid")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "EazziDoc Consultation"},
                    "unit_amount": settings.CONSULTATION_FEE_CENTS,
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=(f"{settings.FRONTEND_URL}/appointments/{appointment_id}?payment=success"),
        cancel_url=(f"{settings.FRONTEND_URL}/appointments/{appointment_id}?payment=cancelled"),
        metadata={
            "appointment_id": str(appt.id),
            "patient_id": str(patient.id),
        },
    )

    # Upsert: reuse an existing pending record (retry-safe) or create a new one
    pending_result = await db.execute(
        select(Payment).where(
            Payment.appointment_id == appt.id,
            Payment.status == "pending",
        )
    )
    payment = pending_result.scalar_one_or_none()
    if payment:
        payment.stripe_session_id = session.id
        payment.amount_cents = settings.CONSULTATION_FEE_CENTS
    else:
        payment = Payment(
            appointment_id=appt.id,
            patient_id=patient.id,
            stripe_session_id=session.id,
            amount_cents=settings.CONSULTATION_FEE_CENTS,
            currency="usd",
            status="pending",
        )
        db.add(payment)

    await db.commit()
    await db.refresh(payment)

    return CheckoutResponse(checkout_url=session.url, payment_id=payment.id)


@router.get(
    "/payments/appointments/{appointment_id}",
    response_model=PaymentResponse | None,
)
async def get_payment_status(
    appointment_id,
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent payment record for an appointment."""
    patient = await _get_patient_or_404(db, current_user)

    appt_result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    appt = appt_result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    if appt.patient_id != patient.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your appointment")

    result = await db.execute(
        select(Payment).where(Payment.appointment_id == appt.id).order_by(Payment.created_at.desc())
    )
    return result.scalars().first()


@router.post("/payments/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive and process Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except Exception as exc:
        logger.warning("Stripe webhook rejected: %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook payload or signature")

    event_type = event["type"]
    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(db, event["data"]["object"])
    elif event_type == "payment_intent.payment_failed":
        await _handle_payment_failed(db, event["data"]["object"])
    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return {"received": True}


async def _handle_checkout_completed(db: AsyncSession, session: dict) -> None:
    stripe_session_id = session["id"]
    result = await db.execute(select(Payment).where(Payment.stripe_session_id == stripe_session_id))
    payment = result.scalar_one_or_none()
    if not payment:
        logger.warning("checkout.session.completed for unknown session %s", stripe_session_id)
        return
    payment.status = "paid"
    payment.stripe_payment_intent_id = session.get("payment_intent")
    await db.commit()
    logger.info("Payment %s marked paid (session %s)", payment.id, stripe_session_id)


async def _handle_payment_failed(db: AsyncSession, intent: dict) -> None:
    payment_intent_id = intent["id"]
    result = await db.execute(
        select(Payment).where(Payment.stripe_payment_intent_id == payment_intent_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        logger.warning("payment_intent.payment_failed for unknown intent %s", payment_intent_id)
        return
    payment.status = "failed"
    await db.commit()
    logger.info("Payment %s marked failed (intent %s)", payment.id, payment_intent_id)
