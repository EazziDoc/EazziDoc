import uuid
from datetime import datetime

from pydantic import BaseModel

# ── overview stats ────────────────────────────────────────────────────────────


class OverviewStats(BaseModel):
    total_users: int
    total_patients: int
    total_doctors: int
    verified_doctors: int
    total_diagnoses: int
    pending_diagnoses: int
    ai_complete_diagnoses: int
    failed_diagnoses: int
    total_appointments: int
    # 30-day window
    new_users_30d: int
    new_diagnoses_30d: int


# ── diagnosis stats ────────────────────────────────────────────────────────────


class ModalityCount(BaseModel):
    modality: str
    count: int


class StatusCount(BaseModel):
    status: str
    count: int


class ModelCount(BaseModel):
    model_used: str
    count: int


class UrgencyCount(BaseModel):
    urgency: str
    count: int


class DiagnosisStats(BaseModel):
    by_modality: list[ModalityCount]
    by_status: list[StatusCount]
    by_model: list[ModelCount]
    by_urgency: list[UrgencyCount]
    avg_confidence: float | None
    # Seconds (None = no completed data yet)
    avg_time_to_ai_secs: float | None
    avg_time_to_review_secs: float | None
    override_rate: float | None  # fraction of AI reports overridden


# ── appointment stats ─────────────────────────────────────────────────────────


class AppointmentStats(BaseModel):
    total: int
    booked: int
    confirmed: int
    completed: int
    cancelled: int
    completion_rate: float | None
    cancellation_rate: float | None
    avg_duration_mins: float | None


# ── user management ───────────────────────────────────────────────────────────


class AdminUserItem(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_verified: bool
    is_active: bool
    created_at: datetime
    display_name: str | None  # first + last from profile
    identity_verification_status: str | None = None

    class Config:
        from_attributes = True


class AdminUserList(BaseModel):
    users: list[AdminUserItem]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    is_verified: bool | None = None
    role: str | None = None


class AdminUserDetail(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_verified: bool
    is_active: bool
    created_at: datetime
    display_name: str | None
    specialty: str | None  # doctors only
    total_diagnoses: int  # patients only
    total_appointments: int

    class Config:
        from_attributes = True


# ── diagnosis management ───────────────────────────────────────────────────────


class AdminDiagnosisItem(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None
    modality: str | None
    status: str
    model_used: str | None
    confidence_score: float | None
    urgency: str | None
    image_count: int
    created_at: datetime
    doctor_reviewed_at: datetime | None

    class Config:
        from_attributes = True


class AdminDiagnosisList(BaseModel):
    diagnoses: list[AdminDiagnosisItem]
    total: int
    page: int
    page_size: int


class AdminDiagnosisDetail(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None
    patient_email: str | None
    modality: str | None
    status: str
    model_used: str | None
    confidence_score: float | None
    urgency: str | None
    image_keys: list[str]
    report: dict | None
    doctor_notes: str | None
    created_at: datetime
    updated_at: datetime
    doctor_reviewed_at: datetime | None

    model_config = {"from_attributes": True}


# ── queue / worker health ─────────────────────────────────────────────────────


class WorkerInfo(BaseModel):
    name: str
    status: str
    active_tasks: int
    processed: int | None


class QueueHealth(BaseModel):
    workers: list[WorkerInfo]
    active_tasks: int
    scheduled_tasks: int
    reserved_tasks: int
    total_tasks_in_queue: int
    # Counts from broker (may be approximate)
    pending_in_broker: int


# ── audit log ─────────────────────────────────────────────────────────────────


class AuditLogItem(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID
    actor_email: str
    action: str
    target_type: str
    target_id: str
    meta: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogList(BaseModel):
    entries: list[AuditLogItem]
    total: int
    page: int
    page_size: int


# ── doctor registration review ────────────────────────────────────────────────


class AdminDoctorItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    specialty: str | None
    license_number: str | None
    qualifications: list[str]
    other_qualifications: str | None
    registration_status: str
    is_verified: bool
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class AdminDoctorList(BaseModel):
    doctors: list[AdminDoctorItem]
    total: int
    page: int
    page_size: int


class AdminDoctorDetail(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    specialty: str | None
    license_number: str | None
    qualifications: list[str]
    other_qualifications: str | None
    certification_urls: list[str]  # presigned download URLs
    registration_status: str
    rejection_reason: str | None
    is_verified: bool
    is_available: bool
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class AdminDoctorReviewRequest(BaseModel):
    reason: str | None = None  # required only for rejection
