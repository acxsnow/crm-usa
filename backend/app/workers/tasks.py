"""Scheduled (Celery beat) tasks. Each task bridges into the async
SQLAlchemy session the rest of the app uses — Celery tasks are plain sync
functions, so every task here does asyncio.run() over a small async body
rather than trying to make Celery itself async."""
import asyncio

import structlog

from app.db.session import worker_session
from app.modules.billing.service import count_overdue_invoices
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _count_overdue_invoices() -> int:
    async with worker_session() as db:
        return await count_overdue_invoices(db)


@celery_app.task(name="workers.sweep_overdue_invoices")
def sweep_overdue_invoices_task() -> int:
    """Revisión diaria (ver beat_schedule en celery_app.py). Desde el módulo 6
    el estado "vencida" se calcula al leer con la fecha de cada organización,
    así que ya no hay nada que cambiar: la tarea registra cuántas facturas
    están vencidas. El nombre se conserva para no tocar la programación de
    Celery Beat."""
    vencidas = asyncio.run(_count_overdue_invoices())
    logger.info("billing.overdue_sweep_completed", overdue_invoices=vencidas)
    return vencidas
