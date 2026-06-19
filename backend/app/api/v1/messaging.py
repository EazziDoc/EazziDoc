"""Email-relay messaging between patients and doctors.

No message history is stored in the database. Each message triggers an
SMTP email with Reply-To set to the sender's registered address so the
recipient can reply directly.
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.appointment import Appointment
from app.models.diagnosis import Diagnosis
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.services import email as email_svc

router = APIRouter(tags=["messaging"])
logger = logging.getLogger(__name__)


class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


# ── patient → doctor ──────────────────────────────────────────────────────────


@router.post("/patient/message/doctor/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def patient_message_doctor(
    doctor_id: uuid.UUID,
    body: MessageRequest,
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    """Patient sends an email to a doctor via EazziDoc relay."""
    # Resolve patient profile
    p_result = await db.execute(select(Patient).where(Patient.user_id == current_user.id))
    patient = p_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient profile not found")

    # Resolve target doctor + their user (for email)
    row = (
        await db.execute(
            select(Doctor, User).join(User, User.id == Doctor.user_id).where(Doctor.id == doctor_id)
        )
    ).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")

    doctor, doctor_user = row

    asyncio.get_event_loop().run_in_executor(
        None,
        lambda: email_svc.send_contact_message(
            to_email=doctor_user.email,
            to_name=f"Dr. {doctor.first_name} {doctor.last_name}",
            from_name=f"{patient.first_name} {patient.last_name}",
            from_email=current_user.email,
            from_role="patient",
            message=body.message,
        ),
    )


# ── doctor → patient ──────────────────────────────────────────────────────────


@router.post("/doctor/message/patient/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def doctor_message_patient(
    patient_id: uuid.UUID,
    body: MessageRequest,
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    """Doctor sends an email to one of their linked patients via EazziDoc relay."""
    # Resolve doctor profile
    d_result = await db.execute(select(Doctor).where(Doctor.user_id == current_user.id))
    doctor = d_result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor profile not found")

    # Verify the patient is linked (appointment or reviewed diagnosis)
    appt_check = await db.execute(
        select(Appointment.id)
        .where(Appointment.doctor_id == doctor.id, Appointment.patient_id == patient_id)
        .limit(1)
    )
    diag_check = await db.execute(
        select(Diagnosis.id)
        .where(Diagnosis.reviewing_doctor_id == doctor.id, Diagnosis.patient_id == patient_id)
        .limit(1)
    )
    if not appt_check.first() and not diag_check.first():
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You can only message patients linked to you via appointments or diagnoses",
        )

    # Resolve patient profile + user email
    row = (
        await db.execute(
            select(Patient, User)
            .join(User, User.id == Patient.user_id)
            .where(Patient.id == patient_id)
        )
    ).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")

    patient, patient_user = row

    asyncio.get_event_loop().run_in_executor(
        None,
        lambda: email_svc.send_contact_message(
            to_email=patient_user.email,
            to_name=f"{patient.first_name} {patient.last_name}",
            from_name=f"{doctor.first_name} {doctor.last_name}",
            from_email=current_user.email,
            from_role="doctor",
            message=body.message,
        ),
    )
