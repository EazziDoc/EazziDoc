"""
Admin API — gated to role='admin'.
All endpoints are under /admin prefix.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.core.metrics import admin_actions_total
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.diagnosis import Diagnosis
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.schemas.admin import (
    AdminDiagnosisDetail,
    AdminDiagnosisItem,
    AdminDiagnosisList,
    AdminDoctorDetail,
    AdminDoctorItem,
    AdminDoctorList,
    AdminDoctorReviewRequest,
    AdminUserDetail,
    AdminUserItem,
    AdminUserList,
    AdminUserUpdate,
    AppointmentStats,
    AuditLogItem,
    AuditLogList,
    DiagnosisStats,
    ModalityCount,
    ModelCount,
    OverviewStats,
    QueueHealth,
    StatusCount,
    UrgencyCount,
    WorkerInfo,
)
from app.services.audit import log_action
from app.services.storage import storage_service
from app.workers.tasks import process_diagnosis

router = APIRouter(prefix="/admin", tags=["admin"])

_require_admin = require_role("admin")


# ── helpers ───────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


def _30d_ago() -> datetime:
    return _now() - timedelta(days=30)


def _infer_action(changes: dict) -> str:
    """Return the most descriptive action string for the set of field changes."""
    if "role" in changes:
        return "user.role_changed"
    if "is_active" in changes:
        return "user.activated" if changes["is_active"]["to"] else "user.deactivated"
    if "is_verified" in changes:
        return "doctor.verified" if changes["is_verified"]["to"] else "doctor.unverified"
    return "user.updated"


# ── overview ──────────────────────────────────────────────────────────────────


@router.get("/stats/overview", response_model=OverviewStats)
async def stats_overview(
    _: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    cutoff = _30d_ago()

    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    total_patients = (await db.execute(select(func.count()).select_from(Patient))).scalar_one()
    total_doctors = (await db.execute(select(func.count()).select_from(Doctor))).scalar_one()
    verified_doctors = (
        await db.execute(
            select(func.count()).select_from(Doctor).where(Doctor.is_verified.is_(True))
        )
    ).scalar_one()
    total_diagnoses = (await db.execute(select(func.count()).select_from(Diagnosis))).scalar_one()
    pending_diagnoses = (
        await db.execute(
            select(func.count()).select_from(Diagnosis).where(Diagnosis.status == "pending")
        )
    ).scalar_one()
    ai_complete_diagnoses = (
        await db.execute(
            select(func.count()).select_from(Diagnosis).where(Diagnosis.status == "ai_complete")
        )
    ).scalar_one()
    failed_diagnoses = (
        await db.execute(
            select(func.count()).select_from(Diagnosis).where(Diagnosis.status == "failed")
        )
    ).scalar_one()
    total_appointments = (
        await db.execute(select(func.count()).select_from(Appointment))
    ).scalar_one()
    new_users_30d = (
        await db.execute(select(func.count()).select_from(User).where(User.created_at >= cutoff))
    ).scalar_one()
    new_diagnoses_30d = (
        await db.execute(
            select(func.count()).select_from(Diagnosis).where(Diagnosis.created_at >= cutoff)
        )
    ).scalar_one()

    return OverviewStats(
        total_users=total_users,
        total_patients=total_patients,
        total_doctors=total_doctors,
        verified_doctors=verified_doctors,
        total_diagnoses=total_diagnoses,
        pending_diagnoses=pending_diagnoses,
        ai_complete_diagnoses=ai_complete_diagnoses,
        failed_diagnoses=failed_diagnoses,
        total_appointments=total_appointments,
        new_users_30d=new_users_30d,
        new_diagnoses_30d=new_diagnoses_30d,
    )


# ── diagnosis stats ───────────────────────────────────────────────────────────


@router.get("/stats/diagnoses", response_model=DiagnosisStats)
async def stats_diagnoses(
    _: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    # By modality
    modality_rows = (
        await db.execute(
            select(Diagnosis.modality, func.count().label("cnt"))
            .where(Diagnosis.modality.isnot(None))
            .group_by(Diagnosis.modality)
            .order_by(func.count().desc())
        )
    ).all()
    by_modality = [ModalityCount(modality=r.modality, count=r.cnt) for r in modality_rows]

    # By status
    status_rows = (
        await db.execute(
            select(Diagnosis.status, func.count().label("cnt"))
            .group_by(Diagnosis.status)
            .order_by(func.count().desc())
        )
    ).all()
    by_status = [StatusCount(status=r.status, count=r.cnt) for r in status_rows]

    # By model
    model_rows = (
        await db.execute(
            select(Diagnosis.model_used, func.count().label("cnt"))
            .where(Diagnosis.model_used.isnot(None))
            .group_by(Diagnosis.model_used)
            .order_by(func.count().desc())
        )
    ).all()
    by_model = [ModelCount(model_used=r.model_used, count=r.cnt) for r in model_rows]

    # By urgency (from report JSONB field)
    # Use func.jsonb_extract_path_text so SELECT and GROUP BY share one expression,
    # avoiding the "$1 vs $3" parameter-identity issue that confuses the PG planner.
    urgency_expr = func.jsonb_extract_path_text(Diagnosis.report, "urgency")
    urgency_rows = (
        await db.execute(
            select(
                urgency_expr.label("urgency"),
                func.count().label("cnt"),
            )
            .where(urgency_expr.isnot(None))
            .group_by(urgency_expr)
            .order_by(func.count().desc())
        )
    ).all()
    by_urgency = [UrgencyCount(urgency=r.urgency, count=r.cnt) for r in urgency_rows]

    # Avg confidence
    avg_conf = (
        await db.execute(
            select(func.avg(Diagnosis.confidence_score)).where(
                Diagnosis.confidence_score.isnot(None)
            )
        )
    ).scalar_one()

    # Avg time submission → ai_complete (proxy: updated_at - created_at for ai_complete+)
    # We don't store a separate ai_completed_at column so we use doctor_reviewed_at - created_at
    # as a proxy for time-to-review; for time-to-AI we use updated_at on ai_complete records.
    avg_review_secs = (
        await db.execute(
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        Diagnosis.doctor_reviewed_at - Diagnosis.created_at,
                    )
                )
            ).where(Diagnosis.doctor_reviewed_at.isnot(None))
        )
    ).scalar_one()

    # Override rate: overridden / (confirmed + overridden)
    overridden = (
        await db.execute(
            select(func.count()).select_from(Diagnosis).where(Diagnosis.status == "overridden")
        )
    ).scalar_one()
    confirmed = (
        await db.execute(
            select(func.count()).select_from(Diagnosis).where(Diagnosis.status == "confirmed")
        )
    ).scalar_one()
    override_rate = overridden / (overridden + confirmed) if (overridden + confirmed) > 0 else None

    return DiagnosisStats(
        by_modality=by_modality,
        by_status=by_status,
        by_model=by_model,
        by_urgency=by_urgency,
        avg_confidence=float(avg_conf) if avg_conf else None,
        avg_time_to_ai_secs=None,  # needs dedicated column; placeholder
        avg_time_to_review_secs=float(avg_review_secs) if avg_review_secs else None,
        override_rate=override_rate,
    )


# ── appointment stats ─────────────────────────────────────────────────────────


@router.get("/stats/appointments", response_model=AppointmentStats)
async def stats_appointments(
    _: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Appointment.status, func.count().label("cnt")).group_by(Appointment.status)
        )
    ).all()
    counts = {r.status: r.cnt for r in rows}
    total = sum(counts.values())
    completed = counts.get("completed", 0)
    cancelled = counts.get("cancelled", 0)

    avg_dur = (await db.execute(select(func.avg(Appointment.duration_mins)))).scalar_one()

    return AppointmentStats(
        total=total,
        booked=counts.get("booked", 0),
        confirmed=counts.get("confirmed", 0),
        completed=completed,
        cancelled=cancelled,
        completion_rate=completed / total if total else None,
        cancellation_rate=cancelled / total if total else None,
        avg_duration_mins=float(avg_dur) if avg_dur else None,
    )


# ── user management ───────────────────────────────────────────────────────────


@router.get("/users", response_model=AdminUserList)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    role: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    _: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(User)
    if role:
        q = q.where(User.role == role)
    if is_active is not None:
        q = q.where(User.is_active == is_active)
    if search:
        q = q.where(User.email.ilike(f"%{search}%"))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    users = (
        (
            await db.execute(
                q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    # Fetch display names: join patients and doctors in Python to avoid complex outer join
    patient_map: dict[uuid.UUID, str] = {}
    doctor_map: dict[uuid.UUID, str] = {}

    patient_user_ids = [u.id for u in users if u.role == "patient"]
    doctor_user_ids = [u.id for u in users if u.role == "doctor"]

    if patient_user_ids:
        pts = (
            (await db.execute(select(Patient).where(Patient.user_id.in_(patient_user_ids))))
            .scalars()
            .all()
        )
        patient_map = {p.user_id: f"{p.first_name} {p.last_name}" for p in pts}

    if doctor_user_ids:
        docs = (
            (await db.execute(select(Doctor).where(Doctor.user_id.in_(doctor_user_ids))))
            .scalars()
            .all()
        )
        doctor_map = {d.user_id: f"{d.first_name} {d.last_name}" for d in docs}

    items = [
        AdminUserItem(
            id=u.id,
            email=u.email,
            role=u.role,
            is_verified=u.is_verified,
            is_active=u.is_active,
            created_at=u.created_at,
            display_name=patient_map.get(u.id) or doctor_map.get(u.id),
        )
        for u in users
    ]

    return AdminUserList(users=items, total=total, page=page, page_size=page_size)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user(
    user_id: uuid.UUID,
    _: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    display_name = None
    specialty = None
    total_diagnoses = 0
    total_appointments = 0

    if user.role == "patient":
        pt = (
            await db.execute(select(Patient).where(Patient.user_id == user_id))
        ).scalar_one_or_none()
        if pt:
            display_name = f"{pt.first_name} {pt.last_name}"
            total_diagnoses = (
                await db.execute(
                    select(func.count()).select_from(Diagnosis).where(Diagnosis.patient_id == pt.id)
                )
            ).scalar_one()
            total_appointments = (
                await db.execute(
                    select(func.count())
                    .select_from(Appointment)
                    .where(Appointment.patient_id == pt.id)
                )
            ).scalar_one()

    elif user.role == "doctor":
        doc = (
            await db.execute(select(Doctor).where(Doctor.user_id == user_id))
        ).scalar_one_or_none()
        if doc:
            display_name = f"{doc.first_name} {doc.last_name}"
            specialty = doc.specialty
            total_appointments = (
                await db.execute(
                    select(func.count())
                    .select_from(Appointment)
                    .where(Appointment.doctor_id == doc.id)
                )
            ).scalar_one()

    return AdminUserDetail(
        id=user.id,
        email=user.email,
        role=user.role,
        is_verified=user.is_verified,
        is_active=user.is_active,
        created_at=user.created_at,
        display_name=display_name,
        specialty=specialty,
        total_diagnoses=total_diagnoses,
        total_appointments=total_appointments,
    )


@router.patch("/users/{user_id}", response_model=AdminUserDetail)
async def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdate,
    current_admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == current_admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot modify your own account")

    changes: dict = {}

    if body.is_active is not None and body.is_active != user.is_active:
        changes["is_active"] = {"from": user.is_active, "to": body.is_active}
        user.is_active = body.is_active
    if body.is_verified is not None and body.is_verified != user.is_verified:
        changes["is_verified"] = {"from": user.is_verified, "to": body.is_verified}
        user.is_verified = body.is_verified
        if user.role == "doctor":
            doc = (
                await db.execute(select(Doctor).where(Doctor.user_id == user_id))
            ).scalar_one_or_none()
            if doc:
                doc.is_verified = body.is_verified
    if body.role is not None and body.role != user.role:
        changes["role"] = {"from": user.role, "to": body.role}
        user.role = body.role

    if changes:
        action = _infer_action(changes)
        await log_action(
            db,
            actor=current_admin,
            action=action,
            target_type="user",
            target_id=user_id,
            meta={"changes": changes, "target_email": user.email},
        )
        admin_actions_total.labels(action=action).inc()

    await db.commit()
    await db.refresh(user)

    return await get_user(user_id, current_admin, db)


@router.post("/users/{user_id}/ban", status_code=status.HTTP_200_OK)
async def ban_user(
    user_id: uuid.UUID,
    current_admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Deny platform access for a patient or doctor (sets is_active=False)."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == current_admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot ban your own account")
    if user.role == "admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot ban another admin")
    if not user.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already banned")

    user.is_active = False
    await log_action(
        db,
        actor=current_admin,
        action="user.banned",
        target_type="user",
        target_id=user_id,
        meta={"target_email": user.email, "target_role": user.role},
    )
    admin_actions_total.labels(action="user.banned").inc()
    await db.commit()
    return {"id": str(user_id), "is_active": False}


@router.post("/users/{user_id}/unban", status_code=status.HTTP_200_OK)
async def unban_user(
    user_id: uuid.UUID,
    current_admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Restore platform access for a banned user."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already active")

    user.is_active = True
    await log_action(
        db,
        actor=current_admin,
        action="user.unbanned",
        target_type="user",
        target_id=user_id,
        meta={"target_email": user.email, "target_role": user.role},
    )
    admin_actions_total.labels(action="user.unbanned").inc()
    await db.commit()
    return {"id": str(user_id), "is_active": True}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    current_admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a user and all their data. Diagnosis records are retained."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == current_admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete your own account")
    if user.role == "admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete another admin")

    await log_action(
        db,
        actor=current_admin,
        action="user.deleted",
        target_type="user",
        target_id=user_id,
        meta={"target_email": user.email, "target_role": user.role},
    )
    admin_actions_total.labels(action="user.deleted").inc()
    await db.delete(user)
    await db.commit()


# ── diagnosis management ───────────────────────────────────────────────────────


@router.get("/diagnoses", response_model=AdminDiagnosisList)
async def list_diagnoses(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    modality: str | None = Query(default=None),
    urgency: str | None = Query(default=None),
    _: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Diagnosis)
    if status_filter:
        q = q.where(Diagnosis.status == status_filter)
    if modality:
        q = q.where(Diagnosis.modality == modality)
    if urgency:
        q = q.where(Diagnosis.report["urgency"].astext == urgency)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    diagnoses = (
        (
            await db.execute(
                q.order_by(Diagnosis.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    # Fetch patient names
    patient_ids = list({d.patient_id for d in diagnoses})
    patient_name_map: dict[uuid.UUID, str] = {}
    if patient_ids:
        pts = (await db.execute(select(Patient).where(Patient.id.in_(patient_ids)))).scalars().all()
        patient_name_map = {p.id: f"{p.first_name} {p.last_name}" for p in pts}

    items = [
        AdminDiagnosisItem(
            id=d.id,
            patient_id=d.patient_id,
            patient_name=patient_name_map.get(d.patient_id),
            modality=d.modality,
            status=d.status,
            model_used=d.model_used,
            confidence_score=d.confidence_score,
            urgency=d.report.get("urgency") if isinstance(d.report, dict) else None,
            image_count=len(d.image_keys) if d.image_keys else 0,
            created_at=d.created_at,
            doctor_reviewed_at=d.doctor_reviewed_at,
        )
        for d in diagnoses
    ]

    return AdminDiagnosisList(diagnoses=items, total=total, page=page, page_size=page_size)


@router.get("/diagnoses/{diagnosis_id}", response_model=AdminDiagnosisDetail)
async def get_diagnosis(
    diagnosis_id: uuid.UUID,
    _: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    dx = (
        await db.execute(select(Diagnosis).where(Diagnosis.id == diagnosis_id))
    ).scalar_one_or_none()
    if not dx:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diagnosis not found")

    patient_name = patient_email = None
    pt = (await db.execute(select(Patient).where(Patient.id == dx.patient_id))).scalar_one_or_none()
    if pt:
        patient_name = f"{pt.first_name} {pt.last_name}"
        u = (await db.execute(select(User).where(User.id == pt.user_id))).scalar_one_or_none()
        if u:
            patient_email = u.email

    return AdminDiagnosisDetail(
        id=dx.id,
        patient_id=dx.patient_id,
        patient_name=patient_name,
        patient_email=patient_email,
        modality=dx.modality,
        status=dx.status,
        model_used=dx.model_used,
        confidence_score=dx.confidence_score,
        urgency=dx.report.get("urgency") if isinstance(dx.report, dict) else None,
        image_keys=dx.image_keys or [],
        report=dx.report if isinstance(dx.report, dict) else None,
        doctor_notes=dx.doctor_notes,
        created_at=dx.created_at,
        updated_at=dx.updated_at,
        doctor_reviewed_at=dx.doctor_reviewed_at,
    )


@router.post("/diagnoses/{diagnosis_id}/requeue", status_code=status.HTTP_202_ACCEPTED)
async def requeue_diagnosis(
    diagnosis_id: uuid.UUID,
    current_admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    dx = (
        await db.execute(select(Diagnosis).where(Diagnosis.id == diagnosis_id))
    ).scalar_one_or_none()
    if not dx:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diagnosis not found")
    if dx.status not in {"failed", "pending"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot requeue a diagnosis with status '{dx.status}'",
        )

    previous_status = dx.status
    dx.status = "pending"
    await log_action(
        db,
        actor=current_admin,
        action="diagnosis.requeued",
        target_type="diagnosis",
        target_id=diagnosis_id,
        meta={"previous_status": previous_status},
    )
    await db.commit()
    process_diagnosis.delay(str(dx.id))
    return {"queued": True, "diagnosis_id": str(diagnosis_id)}


# ── queue / worker health ─────────────────────────────────────────────────────


@router.get("/queue/health", response_model=QueueHealth)
async def queue_health(_: User = Depends(_require_admin)):
    from app.core.celery_app import celery_app

    workers: list[WorkerInfo] = []
    total_active = 0
    total_scheduled = 0
    total_reserved = 0

    try:
        inspect = celery_app.control.inspect(timeout=3.0)
        active = inspect.active() or {}
        scheduled = inspect.scheduled() or {}
        reserved = inspect.reserved() or {}
        stats = inspect.stats() or {}

        for name in set(active) | set(scheduled) | set(reserved) | set(stats):
            active_tasks = len(active.get(name) or [])
            total_active += active_tasks
            total_scheduled += len(scheduled.get(name) or [])
            total_reserved += len(reserved.get(name) or [])
            worker_stats = stats.get(name, {})
            processed = worker_stats.get("total", {})
            processed_count = sum(processed.values()) if isinstance(processed, dict) else None

            workers.append(
                WorkerInfo(
                    name=name,
                    status="online",
                    active_tasks=active_tasks,
                    processed=processed_count,
                )
            )
    except Exception:
        # Celery/Redis unavailable — return empty but valid structure
        pass

    # Pending task count from broker (best-effort)
    try:
        with celery_app.connection_or_acquire() as conn:
            pending_in_broker = conn.default_channel.queue_declare(
                queue="celery", passive=True
            ).message_count
    except Exception:
        pending_in_broker = 0

    return QueueHealth(
        workers=workers,
        active_tasks=total_active,
        scheduled_tasks=total_scheduled,
        reserved_tasks=total_reserved,
        total_tasks_in_queue=total_active + total_reserved + total_scheduled,
        pending_in_broker=pending_in_broker,
    )


# ── audit log ─────────────────────────────────────────────────────────────────


@router.get("/audit-logs", response_model=AuditLogList)
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None),
    actor_id: uuid.UUID | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    _: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action == action)
    if actor_id:
        q = q.where(AuditLog.actor_id == actor_id)
    if target_type:
        q = q.where(AuditLog.target_type == target_type)
    if target_id:
        q = q.where(AuditLog.target_id == target_id)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    entries = (
        (
            await db.execute(
                q.order_by(AuditLog.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return AuditLogList(
        entries=[AuditLogItem.model_validate(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── doctor registration review ────────────────────────────────────────────────


@router.get("/doctors", response_model=AdminDoctorList)
async def list_doctors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    _: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Doctor)
    if status_filter:
        q = q.where(Doctor.registration_status == status_filter)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    doctors = (
        (
            await db.execute(
                q.order_by(Doctor.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    user_ids = [d.user_id for d in doctors]
    user_email_map: dict[uuid.UUID, str] = {}
    if user_ids:
        users = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        user_email_map = {u.id: u.email for u in users}

    items = [
        AdminDoctorItem(
            id=d.id,
            user_id=d.user_id,
            email=user_email_map.get(d.user_id, ""),
            first_name=d.first_name,
            last_name=d.last_name,
            specialty=d.specialty,
            license_number=d.license_number,
            qualifications=d.qualifications or [],
            other_qualifications=d.other_qualifications,
            registration_status=d.registration_status,
            is_verified=d.is_verified,
            created_at=d.created_at,
            reviewed_at=d.reviewed_at,
        )
        for d in doctors
    ]
    return AdminDoctorList(doctors=items, total=total, page=page, page_size=page_size)


@router.get("/doctors/{doctor_id}", response_model=AdminDoctorDetail)
async def get_doctor(
    doctor_id: uuid.UUID,
    _: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    doctor = (await db.execute(select(Doctor).where(Doctor.id == doctor_id))).scalar_one_or_none()
    if not doctor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")

    user = (await db.execute(select(User).where(User.id == doctor.user_id))).scalar_one_or_none()
    email = user.email if user else ""

    cert_urls: list[str] = []
    for key in doctor.certification_keys or []:
        try:
            url = await storage_service.presigned_url(key, expires_in=3600)
            cert_urls.append(url)
        except Exception:
            cert_urls.append("")

    return AdminDoctorDetail(
        id=doctor.id,
        user_id=doctor.user_id,
        email=email,
        first_name=doctor.first_name,
        last_name=doctor.last_name,
        specialty=doctor.specialty,
        license_number=doctor.license_number,
        qualifications=doctor.qualifications or [],
        other_qualifications=doctor.other_qualifications,
        certification_urls=cert_urls,
        registration_status=doctor.registration_status,
        rejection_reason=doctor.rejection_reason,
        is_verified=doctor.is_verified,
        is_available=doctor.is_available,
        created_at=doctor.created_at,
        updated_at=doctor.updated_at,
        reviewed_at=doctor.reviewed_at,
    )


@router.post("/doctors/{doctor_id}/approve", status_code=status.HTTP_200_OK)
async def approve_doctor(
    doctor_id: uuid.UUID,
    current_admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    doctor = (await db.execute(select(Doctor).where(Doctor.id == doctor_id))).scalar_one_or_none()
    if not doctor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")
    if doctor.registration_status == "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Doctor registration is already approved")

    doctor.registration_status = "approved"
    doctor.is_verified = True
    doctor.reviewed_at = _now()
    doctor.rejection_reason = None

    user = (await db.execute(select(User).where(User.id == doctor.user_id))).scalar_one_or_none()
    if user:
        user.is_verified = True

    await log_action(
        db,
        actor=current_admin,
        action="doctor.registration_approved",
        target_type="doctor",
        target_id=doctor_id,
        meta={"doctor_email": user.email if user else None},
    )
    admin_actions_total.labels(action="doctor.registration_approved").inc()
    await db.commit()
    return {"approved": True, "doctor_id": str(doctor_id)}


@router.post("/doctors/{doctor_id}/reject", status_code=status.HTTP_200_OK)
async def reject_doctor(
    doctor_id: uuid.UUID,
    body: AdminDoctorReviewRequest,
    current_admin: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    doctor = (await db.execute(select(Doctor).where(Doctor.id == doctor_id))).scalar_one_or_none()
    if not doctor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")
    if doctor.registration_status == "rejected":
        raise HTTPException(status.HTTP_409_CONFLICT, "Doctor registration is already rejected")
    if not body.reason:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A rejection reason is required")

    doctor.registration_status = "rejected"
    doctor.is_verified = False
    doctor.reviewed_at = _now()
    doctor.rejection_reason = body.reason

    user = (await db.execute(select(User).where(User.id == doctor.user_id))).scalar_one_or_none()

    await log_action(
        db,
        actor=current_admin,
        action="doctor.registration_rejected",
        target_type="doctor",
        target_id=doctor_id,
        meta={"reason": body.reason, "doctor_email": user.email if user else None},
    )
    admin_actions_total.labels(action="doctor.registration_rejected").inc()
    await db.commit()
    return {"rejected": True, "doctor_id": str(doctor_id)}
