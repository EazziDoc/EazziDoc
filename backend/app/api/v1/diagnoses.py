import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import require_role
from app.core.limiter import limiter
from app.models.diagnosis import Diagnosis
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.diagnosis import (
    DiagnosisCreate,
    DiagnosisResponse,
    DoctorPatientView,
    DoctorReviewRequest,
)
from app.services import email as email_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnoses", tags=["diagnoses"])


# ── helpers ───────────────────────────────────────────────────────────────────


async def _get_patient_by_user(db: AsyncSession, user_id) -> Patient:
    result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found"
        )
    return patient


async def _get_patient_by_id(db: AsyncSession, patient_id: str) -> Patient:
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


async def _owned_diagnosis(db: AsyncSession, diagnosis_id, patient_id) -> Diagnosis:
    result = await db.execute(
        select(Diagnosis).where(Diagnosis.id == diagnosis_id, Diagnosis.patient_id == patient_id)
    )
    dx = result.scalar_one_or_none()
    if not dx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis not found")
    return dx


async def _get_doctor(db: AsyncSession, current_user: User) -> Doctor:
    result = await db.execute(select(Doctor).where(Doctor.user_id == current_user.id))
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )
    return doctor


async def _get_verified_doctor(db: AsyncSession, current_user: User) -> Doctor:
    doctor = await _get_doctor(db, current_user)
    if not doctor.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor account is not yet verified by admin",
        )
    return doctor


# ── patient: create ───────────────────────────────────────────────────────────


@router.post("", response_model=DiagnosisResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/hour")
async def create_diagnosis(
    request: Request,
    body: DiagnosisCreate,
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a diagnosis request.

    Pass the `image_keys` returned by POST /uploads/images.
    The AI pipeline runs asynchronously — poll GET /diagnoses/{id} for results.
    """
    patient = await _get_patient_by_user(db, current_user.id)
    initial_report = {"patient_notes": body.patient_notes} if body.patient_notes else {}

    diagnosis = Diagnosis(
        patient_id=patient.id,
        image_keys=body.image_keys,
        modality=body.modality,
        status="pending",
        report=initial_report,
        uploaded_by_role="patient",
    )
    db.add(diagnosis)
    await db.commit()
    await db.refresh(diagnosis)
    # Polling worker picks this up automatically — no Redis/Celery call needed.
    return diagnosis


# ── patient: cancel pending diagnosis ─────────────────────────────────────────


@router.post("/{diagnosis_id}/cancel", response_model=DiagnosisResponse)
async def cancel_diagnosis(
    diagnosis_id: str,
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending or processing diagnosis. Has no effect once AI is complete."""
    patient = await _get_patient_by_user(db, current_user.id)
    dx = await _owned_diagnosis(db, diagnosis_id, patient.id)

    if dx.status not in ("pending", "processing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel a diagnosis with status '{dx.status}'",
        )

    dx.status = "cancelled"
    await db.commit()
    await db.refresh(dx)
    return dx


# ── patient: list ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[DiagnosisResponse])
async def list_diagnoses(
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    patient = await _get_patient_by_user(db, current_user.id)
    result = await db.execute(
        select(Diagnosis)
        .where(Diagnosis.patient_id == patient.id)
        .order_by(Diagnosis.created_at.desc())
    )
    return result.scalars().all()


# ── doctor: pending review queue — must come BEFORE /{diagnosis_id} ──────────


@router.get("/queue/pending", response_model=list[DiagnosisResponse])
async def doctor_pending_queue(
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    """Returns ai_complete diagnoses awaiting doctor review, newest first."""
    result = await db.execute(
        select(Diagnosis)
        .where(Diagnosis.status == "ai_complete")
        .order_by(Diagnosis.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


# ── doctor: upload scan for a patient ─────────────────────────────────────────


@router.post(
    "/doctor/patients/{patient_id}",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def doctor_create_diagnosis(
    patient_id: str,
    body: DiagnosisCreate,
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    """
    Doctor uploads a scan on behalf of a patient.
    Images must be pre-uploaded via POST /uploads/images.
    Passes through the same AI pipeline; the doctor reviews the AI report and
    can add clinical notes, a treatment plan, or a referral.
    The patient receives an email notification.
    """
    doctor = await _get_verified_doctor(db, current_user)
    patient = await _get_patient_by_id(db, patient_id)

    patient_user = (
        await db.execute(select(User).where(User.id == patient.user_id))
    ).scalar_one_or_none()

    initial_report = {"patient_notes": body.patient_notes} if body.patient_notes else {}

    diagnosis = Diagnosis(
        patient_id=patient.id,
        image_keys=body.image_keys,
        modality=body.modality,
        status="pending",
        report=initial_report,
        uploaded_by_role="doctor",
        uploading_doctor_id=doctor.id,
    )
    db.add(diagnosis)
    await db.commit()
    await db.refresh(diagnosis)
    # Polling worker picks this up automatically — no Redis/Celery call needed.

    if patient_user:
        try:
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: email_svc.send_doctor_scan_uploaded(
                    patient_email=patient_user.email,
                    patient_name=patient.first_name,
                    doctor_name=f"{doctor.first_name} {doctor.last_name}",
                ),
            )
        except Exception:
            logger.exception("Doctor scan upload notification failed for patient %s", patient.id)

    return diagnosis


# ── doctor: patient detail + diagnosis history ────────────────────────────────


@router.get("/doctor/patients/{patient_id}", response_model=DoctorPatientView)
async def doctor_get_patient(
    patient_id: str,
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    """Return a patient's profile and their full diagnosis history for doctor review."""
    await _get_verified_doctor(db, current_user)
    patient = await _get_patient_by_id(db, patient_id)

    diagnoses = (
        (
            await db.execute(
                select(Diagnosis)
                .where(Diagnosis.patient_id == patient.id)
                .order_by(Diagnosis.created_at.desc())
            )
        )
        .scalars()
        .all()
    )

    return DoctorPatientView(
        id=patient.id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        phone=patient.phone,
        country=patient.country,
        identity_verification_status=patient.identity_verification_status,
        diagnoses=list(diagnoses),
    )


# ── patient: segmentation overlay URL (on-demand presigned) ──────────────────


@router.get("/{diagnosis_id}/segmentation-overlay", status_code=status.HTTP_200_OK)
async def get_segmentation_overlay_url(
    diagnosis_id: str,
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    """Return a fresh 1-hour presigned URL for the MedSAM segmentation overlay."""
    from app.services.storage import storage_service

    patient = await _get_patient_by_user(db, current_user.id)
    dx = await _owned_diagnosis(db, diagnosis_id, patient.id)

    seg_key = (dx.report or {}).get("segmentation_key")
    if not seg_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No segmentation overlay for this diagnosis",
        )

    url = await storage_service.presigned_url(seg_key, expires_in=3600)
    return {"url": url}


# ── patient: single ───────────────────────────────────────────────────────────


@router.get("/{diagnosis_id}", response_model=DiagnosisResponse)
async def get_diagnosis(
    diagnosis_id,
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    patient = await _get_patient_by_user(db, current_user.id)
    return await _owned_diagnosis(db, diagnosis_id, patient.id)


# ── doctor: review ────────────────────────────────────────────────────────────


@router.patch("/{diagnosis_id}/review", response_model=DiagnosisResponse)
async def review_diagnosis(
    diagnosis_id,
    body: DoctorReviewRequest,
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    doctor = await _get_doctor(db, current_user)

    result = await db.execute(select(Diagnosis).where(Diagnosis.id == diagnosis_id))
    dx = result.scalar_one_or_none()
    if not dx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis not found")

    dx.reviewing_doctor_id = doctor.id
    dx.doctor_notes = body.notes
    dx.status = body.status
    dx.doctor_reviewed_at = datetime.now(UTC)
    if body.treatment_plan is not None:
        dx.treatment_plan = body.treatment_plan
    if body.referral is not None:
        dx.referral = body.referral

    await db.commit()
    await db.refresh(dx)
    return dx
