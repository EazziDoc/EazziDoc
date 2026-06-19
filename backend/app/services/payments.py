import logging

import stripe
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.payment import Payment

stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)


async def refund_appointment_payment(db: AsyncSession, appointment_id) -> bool:
    """Issue a Stripe refund for the paid payment on an appointment.

    Returns True if a refund was issued, False if no paid payment exists
    or the refund attempt failed.
    """
    result = await db.execute(
        select(Payment).where(
            Payment.appointment_id == appointment_id,
            Payment.status == "paid",
        )
    )
    payment = result.scalar_one_or_none()
    if not payment or not payment.stripe_payment_intent_id:
        return False

    try:
        stripe.Refund.create(payment_intent=payment.stripe_payment_intent_id)
        payment.status = "refunded"
        await db.flush()
        logger.info("Refunded payment %s for appointment %s", payment.id, appointment_id)
        return True
    except Exception:
        logger.exception("Stripe refund failed for payment %s", payment.id)
        return False
