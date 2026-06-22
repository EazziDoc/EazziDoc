import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
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
from app.services.storage import ALLOWED_CERT_TYPES, MAX_FILE_SIZE, storage_service

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


@router.post("/doctors/me/certifications", status_code=status.HTTP_200_OK)
async def upload_certifications(
    files: list[UploadFile],
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    """Upload certification documents (PDF or image). Max 5 files, 10 MB each."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")
    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 5 certification files allowed"
        )

    result = await db.execute(select(Doctor).where(Doctor.user_id == current_user.id))
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    uploaded_keys: list[str] = []
    for file in files:
        if file.content_type not in ALLOWED_CERT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, JPEG, PNG",
            )
        data = await file.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File {file.filename!r} exceeds 10 MB limit",
            )
        key = storage_service.make_cert_key(str(current_user.id), file.content_type)
        await storage_service.upload(data, key, file.content_type)
        uploaded_keys.append(key)

    doctor.certification_keys = list(doctor.certification_keys or []) + uploaded_keys
    await db.commit()
    return {"uploaded": len(uploaded_keys), "total": len(doctor.certification_keys)}


@router.delete("/patients/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_patient_account(
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete the patient's own account. Diagnosis history is preserved."""
    current_user.is_active = False
    await db.commit()


@router.delete("/doctors/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_doctor_account(
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete the doctor's own account. Diagnosis history is preserved."""
    current_user.is_active = False
    await db.commit()


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
