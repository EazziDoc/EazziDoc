import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DiagnosisCreate(BaseModel):
    image_keys: list[str] = Field(min_length=1, max_length=5)
    patient_notes: str | None = Field(default=None, max_length=1000)


class DiagnosisResponse(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    reviewing_doctor_id: uuid.UUID | None = None
    uploaded_by_role: str = "patient"
    uploading_doctor_id: uuid.UUID | None = None
    image_keys: list
    modality: str | None
    model_used: str | None
    confidence_score: float | None
    report: dict
    status: str
    doctor_notes: str | None = None
    treatment_plan: str | None = None
    referral: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DoctorReviewRequest(BaseModel):
    notes: str = Field(min_length=1, max_length=2000)
    status: str = Field(pattern="^(confirmed|overridden|flagged|under_review)$")
    treatment_plan: str | None = Field(default=None, max_length=3000)
    referral: str | None = Field(default=None, max_length=1000)


class DoctorPatientView(BaseModel):
    """Patient profile + diagnosis history returned to a doctor."""

    id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: datetime | None = None
    gender: str | None = None
    phone: str | None = None
    country: str | None = None
    identity_verification_status: str | None = None
    diagnoses: list[DiagnosisResponse] = []

    model_config = {"from_attributes": True}
