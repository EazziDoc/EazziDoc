from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentResponse
from app.schemas.patient import DoctorProfileResponse

router = APIRouter(tags=["appointments"])

# Valid transitions per actor
_PATIENT_CANCEL_FROM = {"booked", "confirmed"}
_DOCTOR_CONFIRM_FROM = {"booked"}
_DOCTOR_COMPLETE_FROM = {"confirmed"}
_DOCTOR_CANCEL_FROM = {"booked", "confirmed"}


# ── helpers ───────────────────────────────────────────────────────────────────


async def _get_patient(db: AsyncSession, user: User) -> Patient:
    result = await db.execute(select(Patient).where(Patient.user_id == user.id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient profile not found")
    return p


async def _get_doctor(db: AsyncSession, user: User) -> Doctor:
    result = await db.execute(select(Doctor).where(Doctor.user_id == user.id))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor profile not found")
    return d


async def _get_appointment(db: AsyncSession, appointment_id) -> Appointment:
    result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    return appt


def _enforce_transition(appt: Appointment, allowed_from: set, action: str) -> None:
    if appt.status not in allowed_from:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot {action} an appointment with status '{appt.status}'",
        )


# ── public: browse doctors ────────────────────────────────────────────────────


@router.get("/doctors", response_model=list[DoctorProfileResponse])
async def list_available_doctors(db: AsyncSession = Depends(get_db)):
    """List doctors available for booking (no auth required)."""
    result = await db.execute(
        select(Doctor).where(Doctor.is_available == True).order_by(Doctor.last_name)  # noqa: E712
    )
    return result.scalars().all()


# ── patient: book ─────────────────────────────────────────────────────────────


@router.post(
    "/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def book_appointment(
    body: AppointmentCreate,
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    patient = await _get_patient(db, current_user)

    # Verify the target doctor exists
    doc_result = await db.execute(select(Doctor).where(Doctor.id == body.doctor_id))
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")

    appt = Appointment(
        patient_id=patient.id,
        doctor_id=body.doctor_id,
        diagnosis_id=body.diagnosis_id,
        scheduled_at=body.scheduled_at,
        duration_mins=body.duration_mins,
        notes=body.notes,
        status="booked",
    )
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return appt


# ── patient: list own ─────────────────────────────────────────────────────────


@router.get("/appointments", response_model=list[AppointmentResponse])
async def list_my_appointments(
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    patient = await _get_patient(db, current_user)
    result = await db.execute(
        select(Appointment)
        .where(Appointment.patient_id == patient.id)
        .order_by(Appointment.scheduled_at.desc())
    )
    return result.scalars().all()


# ── patient: single ───────────────────────────────────────────────────────────


@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id,
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    patient = await _get_patient(db, current_user)
    appt = await _get_appointment(db, appointment_id)
    if appt.patient_id != patient.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your appointment")
    return appt


# ── patient: cancel ───────────────────────────────────────────────────────────


@router.patch("/appointments/{appointment_id}/cancel", response_model=AppointmentResponse)
async def patient_cancel_appointment(
    appointment_id,
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    patient = await _get_patient(db, current_user)
    appt = await _get_appointment(db, appointment_id)
    if appt.patient_id != patient.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your appointment")
    _enforce_transition(appt, _PATIENT_CANCEL_FROM, "cancel")
    appt.status = "cancelled"
    await db.commit()
    await db.refresh(appt)
    return appt


# ── doctor: list own ─────────────────────────────────────────────────────────


@router.get("/doctor/appointments", response_model=list[AppointmentResponse])
async def list_doctor_appointments(
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    doctor = await _get_doctor(db, current_user)
    result = await db.execute(
        select(Appointment)
        .where(Appointment.doctor_id == doctor.id)
        .order_by(Appointment.scheduled_at.asc())
    )
    return result.scalars().all()


# ── doctor: confirm ───────────────────────────────────────────────────────────


@router.patch("/doctor/appointments/{appointment_id}/confirm", response_model=AppointmentResponse)
async def confirm_appointment(
    appointment_id,
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    doctor = await _get_doctor(db, current_user)
    appt = await _get_appointment(db, appointment_id)
    if appt.doctor_id != doctor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your appointment")
    _enforce_transition(appt, _DOCTOR_CONFIRM_FROM, "confirm")
    appt.status = "confirmed"
    await db.commit()
    await db.refresh(appt)
    return appt


# ── doctor: complete ──────────────────────────────────────────────────────────


@router.patch("/doctor/appointments/{appointment_id}/complete", response_model=AppointmentResponse)
async def complete_appointment(
    appointment_id,
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    doctor = await _get_doctor(db, current_user)
    appt = await _get_appointment(db, appointment_id)
    if appt.doctor_id != doctor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your appointment")
    _enforce_transition(appt, _DOCTOR_COMPLETE_FROM, "complete")
    appt.status = "completed"
    await db.commit()
    await db.refresh(appt)
    return appt


# ── doctor: cancel ────────────────────────────────────────────────────────────


@router.patch("/doctor/appointments/{appointment_id}/cancel", response_model=AppointmentResponse)
async def doctor_cancel_appointment(
    appointment_id,
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    doctor = await _get_doctor(db, current_user)
    appt = await _get_appointment(db, appointment_id)
    if appt.doctor_id != doctor.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your appointment")
    _enforce_transition(appt, _DOCTOR_CANCEL_FROM, "cancel")
    appt.status = "cancelled"
    await db.commit()
    await db.refresh(appt)
    return appt
