import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AppointmentCreate(BaseModel):
    doctor_id: uuid.UUID
    scheduled_at: datetime
    duration_mins: int = Field(default=30, ge=15, le=120)
    notes: str | None = Field(default=None, max_length=500)
    diagnosis_id: uuid.UUID | None = None


class AppointmentResponse(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    diagnosis_id: uuid.UUID | None
    scheduled_at: datetime
    duration_mins: int
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
