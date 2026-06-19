import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DiagnosisCreate(BaseModel):
    image_keys: list[str] = Field(min_length=1, max_length=5)
    patient_notes: str | None = Field(default=None, max_length=1000)


class DiagnosisResponse(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    image_keys: list
    modality: str | None
    model_used: str | None
    confidence_score: float | None
    report: dict
    status: str
    doctor_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DoctorReviewRequest(BaseModel):
    notes: str = Field(min_length=1, max_length=2000)
    status: str = Field(pattern="^(confirmed|overridden|flagged|under_review)$")
