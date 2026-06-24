"""Celery tasks for async AI diagnosis processing."""

import asyncio
import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.metrics import diagnoses_total, diagnosis_pipeline_seconds
from app.models.diagnosis import Diagnosis
from app.models.patient import Patient
from app.models.user import User
from app.services.ai import gemini, groq_client, medsam, router
from app.services.email import send_diagnosis_ready
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

# Module-level engine — one pool shared across all tasks on this worker process.
# Creating a new engine per task was creating a new connection pool every call,
# which exhausted Fly Postgres connection limits (root cause of OperationalError
# "invalid username-password pair" under load).
_engine = create_async_engine(
    settings.DATABASE_URL, echo=False, pool_size=2, max_overflow=2, connect_args={"ssl": False}
)
_SessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _run_pipeline(diagnosis_id: str) -> None:
    SessionLocal = _SessionLocal
    _start = time.perf_counter()

    async with SessionLocal() as db:
        result = await db.execute(select(Diagnosis).where(Diagnosis.id == uuid.UUID(diagnosis_id)))
        diagnosis = result.scalar_one_or_none()
        if not diagnosis:
            logger.error("Diagnosis %s not found", diagnosis_id)
            return

        if diagnosis.status == "cancelled":
            logger.info(
                "Diagnosis %s was cancelled before processing started, skipping", diagnosis_id
            )
            return

        # ── download all images from R2 ───────────────────────────────────────
        images: list[tuple[bytes, str]] = []
        for key in diagnosis.image_keys:
            try:
                url = await storage_service.presigned_url(key, expires_in=300)
                import httpx

                async with httpx.AsyncClient(timeout=30) as http:
                    resp = await http.get(url)
                    resp.raise_for_status()
                    ct = resp.headers.get("content-type", "image/jpeg")
                    images.append((resp.content, ct))
            except Exception:
                logger.exception("Failed to download image %s", key)

        if not images:
            diagnosis.status = "flagged"
            diagnosis.report = {"error": "Could not retrieve images for analysis"}
            await db.commit()
            return

        # Modality is set at upload time by the user — no detection needed.
        modality = diagnosis.modality or "unknown"

        # ── specialist model (TorchXRayVision / RETFound / HAM10000) ─────────
        primary_image_bytes = images[0][0]
        specialist = await router.run_specialist(primary_image_bytes, modality)

        # ── MedSAM segmentation overlay ───────────────────────────────────────
        seg_key = await medsam.segment_and_upload(
            primary_image_bytes, diagnosis_id, storage_service, modality=modality
        )

        # ── report generation (Gemini → Groq fallback) ───────────────────────
        patient_notes = diagnosis.report.get("patient_notes") if diagnosis.report else None

        report = gemini.generate_report(images, modality, patient_notes, specialist)
        if not report:
            logger.warning("Gemini failed, falling back to Groq for diagnosis %s", diagnosis_id)
            report = groq_client.generate_report(modality, patient_notes, specialist)

        if report:
            diagnosis.model_used = "gemini-2.0-flash"
            diagnosis.confidence_score = float(report.pop("confidence", 0.0))
            if specialist:
                report["specialist_model"] = specialist
            if seg_key:
                report["segmentation_key"] = seg_key
            diagnosis.report = report
            diagnosis.status = "ai_complete"
        else:
            diagnosis.status = "flagged"
            diagnosis.report = {"error": "AI report generation failed"}

        await db.commit()
        elapsed = time.perf_counter() - _start
        diagnoses_total.labels(status=diagnosis.status).inc()
        diagnosis_pipeline_seconds.observe(elapsed)
        logger.info("Diagnosis %s processed — status: %s", diagnosis_id, diagnosis.status)

        # ── email notification ────────────────────────────────────────────────
        if diagnosis.status == "ai_complete":
            try:
                row = (
                    await db.execute(
                        select(Patient, User)
                        .join(User, User.id == Patient.user_id)
                        .where(Patient.id == diagnosis.patient_id)
                    )
                ).first()
                if row:
                    patient, user = row
                    urgency = (diagnosis.report or {}).get("urgency")
                    send_diagnosis_ready(
                        patient_email=user.email,
                        patient_name=f"{patient.first_name} {patient.last_name}",
                        diagnosis_id=diagnosis_id,
                        modality=diagnosis.modality or "Unknown",
                        urgency=urgency,
                    )
            except Exception:
                logger.exception("Diagnosis-ready email failed for %s", diagnosis_id)


@celery_app.task(bind=True, name="tasks.process_diagnosis", max_retries=3, default_retry_delay=60)
def process_diagnosis(self, diagnosis_id: str) -> None:
    try:
        asyncio.run(_run_pipeline(diagnosis_id))
    except Exception as exc:
        logger.exception("Task failed for diagnosis %s", diagnosis_id)
        raise self.retry(exc=exc)
