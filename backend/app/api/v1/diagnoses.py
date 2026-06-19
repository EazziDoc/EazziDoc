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
from app.schemas.diagnosis import DiagnosisCreate, DiagnosisResponse, DoctorReviewRequest
from app.workers.tasks import process_diagnosis

router = APIRouter(prefix="/diagnoses", tags=["diagnoses"])


# ── helpers ───────────────────────────────────────────────────────────────────


async def _get_patient(db: AsyncSession, user_id) -> Patient:
    result = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found"
        )
    return patient


async def _owned_diagnosis(db: AsyncSession, diagnosis_id, patient_id) -> Diagnosis:
    result = await db.execute(
        select(Diagnosis).where(Diagnosis.id == diagnosis_id, Diagnosis.patient_id == patient_id)
    )
    dx = result.scalar_one_or_none()
    if not dx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis not found")
    return dx


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
    patient = await _get_patient(db, current_user.id)

    # Store patient notes inside the report dict until AI overwrites it
    initial_report = {"patient_notes": body.patient_notes} if body.patient_notes else {}

    diagnosis = Diagnosis(
        patient_id=patient.id,
        image_keys=body.image_keys,
        status="pending",
        report=initial_report,
    )
    db.add(diagnosis)
    await db.commit()
    await db.refresh(diagnosis)

    # Queue async AI processing — fire and forget
    process_diagnosis.delay(str(diagnosis.id))

    return diagnosis


# ── patient: list ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[DiagnosisResponse])
async def list_diagnoses(
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    patient = await _get_patient(db, current_user.id)
    result = await db.execute(
        select(Diagnosis)
        .where(Diagnosis.patient_id == patient.id)
        .order_by(Diagnosis.created_at.desc())
    )
    return result.scalars().all()


# ── patient: single ───────────────────────────────────────────────────────────


# ── doctor: list pending reviews — must come BEFORE /{diagnosis_id} ──────────


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


# ── patient: single ───────────────────────────────────────────────────────────


@router.get("/{diagnosis_id}", response_model=DiagnosisResponse)
async def get_diagnosis(
    diagnosis_id,
    current_user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    patient = await _get_patient(db, current_user.id)
    return await _owned_diagnosis(db, diagnosis_id, patient.id)


# ── doctor: review ────────────────────────────────────────────────────────────


@router.patch("/{diagnosis_id}/review", response_model=DiagnosisResponse)
async def review_diagnosis(
    diagnosis_id,
    body: DoctorReviewRequest,
    current_user: User = Depends(require_role("doctor")),
    db: AsyncSession = Depends(get_db),
):
    doctor_result = await db.execute(select(Doctor).where(Doctor.user_id == current_user.id))
    doctor = doctor_result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found"
        )

    result = await db.execute(select(Diagnosis).where(Diagnosis.id == diagnosis_id))
    dx = result.scalar_one_or_none()
    if not dx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis not found")

    dx.reviewing_doctor_id = doctor.id
    dx.doctor_notes = body.notes
    dx.status = body.status
    dx.doctor_reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(dx)
    return dx
