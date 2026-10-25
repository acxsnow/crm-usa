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


async def _purge_old_locations() -> int:
    from app.modules.attendance.mapdata import purge_old_locations

    async with worker_session() as db:
        return await purge_old_locations(db)


@celery_app.task(name="attendance.purge_old_locations")
def purge_old_locations_task() -> int:
    """Borra las coordenadas de los eventos de turno más viejos que la
    retención de cada organización (90 días por defecto). Los eventos y las
    horas se quedan."""
    borradas = asyncio.run(_purge_old_locations())
    logger.info("attendance.locations_purged", events=borradas)
    return borradas


async def _sync_bank_feeds() -> int:
    from app.modules.payments.bankfeed import sync_all

    async with worker_session() as db:
        return await sync_all(db)


@celery_app.task(name="payments.sync_bank_feeds")
def sync_bank_feeds_task() -> int:
    """Trae cada mañana los movimientos nuevos de los bancos conectados (además
    del webhook de Plaid, por si alguno no llegó)."""
    hechas = asyncio.run(_sync_bank_feeds())
    logger.info("payments.bank_feeds_synced", connections=hechas)
    return hechas
