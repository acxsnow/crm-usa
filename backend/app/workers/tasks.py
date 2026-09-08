"""Scheduled (Celery beat) tasks. Each task bridges into the async
SQLAlchemy session the rest of the app uses — Celery tasks are plain sync
functions, so every task here does asyncio.run() over a small async body
rather than trying to make Celery itself async."""
import asyncio

import structlog

from app.db.session import AsyncSessionLocal
from app.modules.billing.service import sweep_overdue_invoices
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _sweep_overdue_invoices() -> int:
    async with AsyncSessionLocal() as db:
        return await sweep_overdue_invoices(db)


@celery_app.task(name="workers.sweep_overdue_invoices")
def sweep_overdue_invoices_task() -> int:
    """Daily sweep (see beat_schedule in celery_app.py): marks any
    pending/sent invoice whose due date has passed as overdue, across every
    organization — the same transition the API already applies lazily on
    read, just proactive now instead of waiting for someone to open the
    Invoices page (spec 17 phase 4)."""
    changed = asyncio.run(_sweep_overdue_invoices())
    logger.info("billing.overdue_sweep_completed", invoices_marked_overdue=changed)
    return changed
