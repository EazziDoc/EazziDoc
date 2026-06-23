"""DB-polling worker — picks up pending diagnoses without Redis/Celery.

Runs as the 'worker' process on Fly.io:
  python -m app.workers.polling

Polls for pending diagnoses every POLL_INTERVAL seconds using
SELECT FOR UPDATE SKIP LOCKED so multiple workers (if ever scaled)
don't double-process the same row.
"""

import asyncio
import logging
import sys
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.diagnosis import Diagnosis

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5  # seconds between polls when the queue is empty

_engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=2, max_overflow=2)
_SessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _reset_stuck_processing() -> None:
    """On startup, reset any 'processing' diagnoses back to 'pending'.

    Diagnoses get stuck in 'processing' if the worker crashed mid-pipeline.
    Resetting them allows a fresh attempt on the next poll.
    """
    try:
        async with _SessionLocal() as db:
            result = await db.execute(
                update(Diagnosis)
                .where(Diagnosis.status == "processing")
                .values(status="pending")
                .returning(Diagnosis.id)
            )
            stuck_ids = [str(r[0]) for r in result.fetchall()]
            await db.commit()
        if stuck_ids:
            logger.warning(
                "Reset %d stuck 'processing' diagnoses to 'pending': %s",
                len(stuck_ids),
                stuck_ids,
            )
        else:
            logger.info("No stuck diagnoses found on startup")
    except Exception:
        logger.exception("Could not reset stuck diagnoses on startup — continuing anyway")


async def _claim_one() -> str | None:
    """Atomically claim one pending diagnosis.

    Uses SELECT FOR UPDATE SKIP LOCKED so concurrent workers (if scaled) each
    claim a different row. Returns the diagnosis ID, or None if queue is empty.
    """
    async with _SessionLocal() as db:
        result = await db.execute(
            select(Diagnosis)
            .where(Diagnosis.status == "pending")
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        dx = result.scalar_one_or_none()
        if not dx:
            return None
        dx.status = "processing"
        await db.commit()
        return str(dx.id)


async def _mark_failed(diagnosis_id: str) -> None:
    """Mark a diagnosis as 'flagged' after an unexpected pipeline crash."""
    try:
        async with _SessionLocal() as db:
            await db.execute(
                update(Diagnosis)
                .where(Diagnosis.id == uuid.UUID(diagnosis_id))
                .values(status="flagged", report={"error": "Processing failed unexpectedly"})
            )
            await db.commit()
    except Exception:
        logger.exception("Could not mark diagnosis %s as flagged", diagnosis_id)


async def _run(diagnosis_id: str) -> None:
    """Import and run the pipeline lazily so startup never fails due to an AI import error."""
    from app.workers.tasks import _run_pipeline

    await _run_pipeline(diagnosis_id)


async def main() -> None:
    logger.info(
        "Polling worker started — polling DB for pending diagnoses every %ds", POLL_INTERVAL
    )
    await _reset_stuck_processing()

    while True:
        try:
            diagnosis_id = await _claim_one()
            if diagnosis_id:
                logger.info("Claimed diagnosis %s — starting pipeline", diagnosis_id)
                try:
                    await _run(diagnosis_id)
                except Exception:
                    logger.exception("Pipeline crashed for diagnosis %s", diagnosis_id)
                    await _mark_failed(diagnosis_id)
            else:
                await asyncio.sleep(POLL_INTERVAL)
        except Exception:
            logger.exception("Polling loop error — restarting in 10s")
            await asyncio.sleep(10)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    asyncio.run(main())
