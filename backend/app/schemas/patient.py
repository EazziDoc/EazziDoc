import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class PatientProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)
    medical_history: dict | None = None


class PatientProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: date | None
    gender: str | None
    phone: str | None
    country: str | None
    medical_history: dict
    identity_verification_status: str = "unverified"
    id_type: str | None = None
    id_rejection_reason: str | None = None
    id_verified_at: datetime | None = None

    model_config = {"from_attributes": True}


class PatientIdentitySubmit(BaseModel):
    id_type: str = Field(..., pattern="^(national_id|passport|drivers_license)$")
    id_number: str = Field(..., min_length=3, max_length=100)


class PatientIdentityRejectRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class DoctorProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    specialty: str | None = Field(default=None, max_length=100)
    license_number: str | None = Field(default=None, max_length=100)


class DoctorProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    first_name: str
    last_name: str
    specialty: str | None
    license_number: str | None
    is_verified: bool
    is_available: bool
    qualifications: list[str] = []
    other_qualifications: str | None = None
    registration_status: str = "pending_review"
    rejection_reason: str | None = None

    model_config = {"from_attributes": True}
