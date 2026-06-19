import uuid
from datetime import datetime

from pydantic import BaseModel


class CheckoutResponse(BaseModel):
    checkout_url: str
    payment_id: uuid.UUID


class PaymentResponse(BaseModel):
    id: uuid.UUID
    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    stripe_session_id: str
    stripe_payment_intent_id: str | None
    amount_cents: int
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
