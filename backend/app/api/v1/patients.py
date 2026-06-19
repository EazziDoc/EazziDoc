import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import (
    DoctorProfileResponse,
    DoctorProfileUpdate,
    PatientProfileResponse,
    PatientProfileUpdate,
)
from app.services import email as email_svc

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profiles"])


# ── Patient ───────────────────────────────────────────────────────────────────


@router.get("/patients/me", response_model=PatientProfileResponse)
async def get_my_patient_profile(
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Patient).where(Patient.user_id == current_user.id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found"
        )
    return patient


@router.patch("/patients/me", response_model=PatientProfileResponse)
async def update_my_patient_profile(
    body: PatientProfileUpdate,
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Patient).where(Patient.user_id == current_user.id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found"
        )

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(patient, field, value)

    await db.commit()
    await db.refresh(patient)

    if updates:
        try:
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: email_svc.send_settings_updated(
                    email=current_user.email,
                    name=patient.first_name,
                    changed_fields=list(updates.keys()),
                ),
            )
        except Exception:
            logger.exception("Settings email failed for user %s", current_user.id)

    return patient


# ── Doctor ────────────────────────────────────────────────────────────────────


@router.get("/doctors/me", response_model=DoctorProfileResponse)
async def get_my_doctor_profile(
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Doctor).where(Doctor.user_id == current_user.id))
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )
    return doctor


@router.patch("/doctors/me", response_model=DoctorProfileResponse)
async def update_my_doctor_profile(
    body: DoctorProfileUpdate,
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Doctor).where(Doctor.user_id == current_user.id))
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(doctor, field, value)

    await db.commit()
    await db.refresh(doctor)

    if updates:
        try:
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: email_svc.send_settings_updated(
                    email=current_user.email,
                    name=doctor.first_name,
                    changed_fields=list(updates.keys()),
                ),
            )
        except Exception:
            logger.exception("Settings email failed for user %s", current_user.id)

    return doctor


@router.patch("/doctors/me/availability", response_model=DoctorProfileResponse)
async def set_doctor_availability(
    is_available: bool,
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Doctor).where(Doctor.user_id == current_user.id))
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    doctor.is_available = is_available
    await db.commit()
    await db.refresh(doctor)
    return doctor
