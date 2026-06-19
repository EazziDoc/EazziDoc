"""Append-only audit log helper.

Call `log_action()` inside any admin route after a mutation commits.
The entry is written in the same DB session — if the outer transaction
rolls back, the log entry rolls back with it (intentional: we only log
actions that actually happened).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


async def log_action(
    db: AsyncSession,
    actor: User,
    action: str,
    target_type: str,
    target_id: uuid.UUID | str,
    meta: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id,
        actor_email=actor.email,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        meta=meta,
    )
    db.add(entry)
    await db.flush()
    return entry
