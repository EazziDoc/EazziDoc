"""GDPR compliance endpoints.

Right to data portability (Art. 20):  GET  /me/data-export
Right to erasure      (Art. 17):       DELETE /me/account

Both endpoints are available to authenticated patients and doctors.
Deletion requires the user's current password to prevent accidents.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import verify_password
from app.models.appointment import Appointment
from app.models.diagnosis import Diagnosis
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User

router = APIRouter(prefix="/me", tags=["gdpr"])
logger = logging.getLogger(__name__)


# ── schemas ───────────────────────────────────────────────────────────────────


class DeleteAccountRequest(BaseModel):
    password: str = Field(..., min_length=1)


# ── helpers ───────────────────────────────────────────────────────────────────


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _str(val) -> str | None:
    return str(val) if val is not None else None


# ── data export ───────────────────────────────────────────────────────────────


@router.get("/data-export")
async def data_export(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all personal data held about the requesting user as a JSON object."""
    exported_at = datetime.now(UTC).isoformat()

    account = {
        "id": _str(current_user.id),
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "created_at": _iso(current_user.created_at),
    }

    if current_user.role == "patient":
        return await _patient_export(db, current_user, account, exported_at)
    if current_user.role == "doctor":
        return await _doctor_export(db, current_user, account, exported_at)

    # Admin — only account-level data
    return {"exported_at": exported_at, "account": account}


async def _patient_export(db: AsyncSession, user: User, account: dict, exported_at: str) -> dict:
    patient = (
        await db.execute(select(Patient).where(Patient.user_id == user.id))
    ).scalar_one_or_none()

    profile = None
    diagnoses = []
    appointments = []

    if patient:
        profile = {
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": _iso(patient.date_of_birth),
            "gender": patient.gender,
            "phone": patient.phone,
            "country": patient.country,
            "medical_history": patient.medical_history or {},
            "created_at": _iso(patient.created_at),
        }

        dx_rows = (
            (
                await db.execute(
                    select(Diagnosis)
                    .where(Diagnosis.patient_id == patient.id)
                    .order_by(Diagnosis.created_at)
                )
            )
            .scalars()
            .all()
        )

        diagnoses = [
            {
                "id": _str(d.id),
                "modality": d.modality,
                "status": d.status,
                "model_used": d.model_used,
                "confidence_score": d.confidence_score,
                "report": d.report,
                "doctor_notes": d.doctor_notes,
                "image_count": len(d.image_keys) if d.image_keys else 0,
                "created_at": _iso(d.created_at),
                "doctor_reviewed_at": _iso(d.doctor_reviewed_at),
            }
            for d in dx_rows
        ]

        appt_rows = (
            (
                await db.execute(
                    select(Appointment)
                    .where(Appointment.patient_id == patient.id)
                    .order_by(Appointment.scheduled_at)
                )
            )
            .scalars()
            .all()
        )

        appointments = [
            {
                "id": _str(a.id),
                "status": a.status,
                "scheduled_at": _iso(a.scheduled_at),
                "duration_mins": a.duration_mins,
                "notes": a.notes,
                "created_at": _iso(a.created_at),
            }
            for a in appt_rows
        ]

    return {
        "exported_at": exported_at,
        "account": account,
        "profile": profile,
        "diagnoses": diagnoses,
        "appointments": appointments,
    }


async def _doctor_export(db: AsyncSession, user: User, account: dict, exported_at: str) -> dict:
    doctor = (
        await db.execute(select(Doctor).where(Doctor.user_id == user.id))
    ).scalar_one_or_none()

    profile = None
    appointments = []

    if doctor:
        profile = {
            "first_name": doctor.first_name,
            "last_name": doctor.last_name,
            "specialty": doctor.specialty,
            "license_number": doctor.license_number,
            "is_verified": doctor.is_verified,
            "is_available": doctor.is_available,
            "created_at": _iso(doctor.created_at),
        }

        appt_rows = (
            (
                await db.execute(
                    select(Appointment)
                    .where(Appointment.doctor_id == doctor.id)
                    .order_by(Appointment.scheduled_at)
                )
            )
            .scalars()
            .all()
        )

        appointments = [
            {
                "id": _str(a.id),
                "status": a.status,
                "scheduled_at": _iso(a.scheduled_at),
                "duration_mins": a.duration_mins,
                "notes": a.notes,
                "created_at": _iso(a.created_at),
            }
            for a in appt_rows
        ]

    return {
        "exported_at": exported_at,
        "account": account,
        "profile": profile,
        "appointments": appointments,
    }


# ── account deletion ───────────────────────────────────────────────────────────


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    body: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete the authenticated user's account and all associated data.

    Requires current password confirmation. For doctors, deletion is blocked
    while they have pending or confirmed appointments.
    """
    if not verify_password(body.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )

    if current_user.role == "doctor":
        doctor = (
            await db.execute(select(Doctor).where(Doctor.user_id == current_user.id))
        ).scalar_one_or_none()

        if doctor:
            blocking = (
                await db.execute(
                    select(Appointment.id)
                    .where(
                        Appointment.doctor_id == doctor.id,
                        Appointment.status.in_(["booked", "confirmed"]),
                    )
                    .limit(1)
                )
            ).first()

            if blocking:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Cannot delete account while you have pending or confirmed appointments. "
                        "Cancel or complete them first."
                    ),
                )

    logger.info(
        "Account deletion: user_id=%s email=%s role=%s",
        current_user.id,
        current_user.email,
        current_user.role,
    )

    # Cascade deletes handle Patient/Doctor/Diagnosis/Appointment/RefreshToken
    await db.delete(current_user)
    await db.commit()
