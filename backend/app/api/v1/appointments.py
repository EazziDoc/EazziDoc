import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.appointment import Appointment
from app.models.diagnosis import Diagnosis
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentResponse
from app.schemas.patient import DoctorProfileResponse, PatientProfileResponse
from app.services import email as email_svc

logger = logging.getLogger(__name__)

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


async def _appt_parties(db: AsyncSession, appt: Appointment):
    """Return (patient, patient_user, doctor, doctor_user) for notification use."""
    p_row = (
        await db.execute(
            select(Patient, User)
            .join(User, User.id == Patient.user_id)
            .where(Patient.id == appt.patient_id)
        )
    ).first()
    d_row = (
        await db.execute(
            select(Doctor, User)
            .join(User, User.id == Doctor.user_id)
            .where(Doctor.id == appt.doctor_id)
        )
    ).first()
    return p_row, d_row


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

    try:
        p_row, d_row = await _appt_parties(db, appt)
        if p_row and d_row:
            patient, _ = p_row
            doctor, doctor_user = d_row
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: email_svc.send_appointment_booked_to_doctor(
                    doctor_email=doctor_user.email,
                    doctor_name=f"{doctor.first_name} {doctor.last_name}",
                    patient_name=f"{patient.first_name} {patient.last_name}",
                    scheduled_at=appt.scheduled_at,
                    duration_mins=appt.duration_mins,
                    appointment_id=str(appt.id),
                ),
            )
    except Exception:
        logger.exception("book notification failed for appt %s", appt.id)

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

    try:
        _, d_row = await _appt_parties(db, appt)
        if d_row:
            doctor, doctor_user = d_row
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: email_svc.send_appointment_cancelled(
                    to_email=doctor_user.email,
                    to_name=f"Dr. {doctor.first_name} {doctor.last_name}",
                    other_party_name=f"{patient.first_name} {patient.last_name}",
                    scheduled_at=appt.scheduled_at,
                    cancelled_by="patient",
                ),
            )
    except Exception:
        logger.exception("cancel notification failed for appt %s", appt.id)

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

    try:
        p_row, _ = await _appt_parties(db, appt)
        if p_row:
            patient, patient_user = p_row
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: email_svc.send_appointment_confirmed_to_patient(
                    patient_email=patient_user.email,
                    patient_name=f"{patient.first_name} {patient.last_name}",
                    doctor_name=f"{doctor.first_name} {doctor.last_name}",
                    scheduled_at=appt.scheduled_at,
                    duration_mins=appt.duration_mins,
                ),
            )
    except Exception:
        logger.exception("confirm notification failed for appt %s", appt.id)

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

    try:
        p_row, _ = await _appt_parties(db, appt)
        if p_row:
            patient, patient_user = p_row
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: email_svc.send_appointment_cancelled(
                    to_email=patient_user.email,
                    to_name=f"{patient.first_name} {patient.last_name}",
                    other_party_name=f"{doctor.first_name} {doctor.last_name}",
                    scheduled_at=appt.scheduled_at,
                    cancelled_by="doctor",
                ),
            )
    except Exception:
        logger.exception("doctor-cancel notification failed for appt %s", appt.id)
    return appt


# ── doctor: list linked patients ───────────────────────────────────────────────


@router.get("/doctor/patients", response_model=list[PatientProfileResponse])
async def list_doctor_patients(
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    """Unique patients linked via appointments or reviewed diagnoses."""
    doctor = await _get_doctor(db, current_user)

    appt_ids = {
        row[0]
        for row in (
            await db.execute(
                select(Appointment.patient_id).where(Appointment.doctor_id == doctor.id).distinct()
            )
        ).all()
    }
    diag_ids = {
        row[0]
        for row in (
            await db.execute(
                select(Diagnosis.patient_id)
                .where(Diagnosis.reviewing_doctor_id == doctor.id)
                .distinct()
            )
        ).all()
    }

    all_ids = appt_ids | diag_ids
    if not all_ids:
        return []

    result = await db.execute(
        select(Patient).where(Patient.id.in_(all_ids)).order_by(Patient.last_name)
    )
    return result.scalars().all()
