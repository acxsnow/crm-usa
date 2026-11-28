"""Scheduled (Celery beat) tasks. Each task bridges into the async
SQLAlchemy session the rest of the app uses — Celery tasks are plain sync
functions, so every task here does asyncio.run() over a small async body
rather than trying to make Celery itself async."""
import asyncio
from uuid import uuid4

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


async def _sync_accounting() -> int:
    from app.modules.accounting.posting import sync_all

    async with worker_session() as db:
        return await sync_all(db)


@celery_app.task(name="accounting.sync")
def sync_accounting_task() -> int:
    """Pasa a asientos lo nuevo de facturas, pagos, gastos y bodega."""
    hechas = asyncio.run(_sync_accounting())
    logger.info("accounting.synced", organizations=hechas)
    return hechas


async def _companycam_download_batch(organization_id: str) -> dict:
    import uuid

    import redis.asyncio as aioredis

    from app.core.config import get_settings
    from app.modules.imports.companycam import downloads
    from app.modules.imports.companycam.client import CompanyCamClient, resolve_token

    # Cliente propio de esta tarea (cada tarea corre su propio `asyncio.run()`:
    # uno compartido quedaría atado al ciclo de la tarea anterior).
    redis = aioredis.from_url(get_settings().REDIS_URL, decode_responses=True,
                              socket_connect_timeout=0.5, socket_timeout=0.5)
    clave, token = f"lock:imports.companycam_download:{organization_id}", uuid4().hex
    client = None
    try:
        try:
            tomado = await redis.set(clave, token, nx=True, ex=200)
        except Exception:  # sin Redis no hay candado; FOR UPDATE SKIP LOCKED ya evita duplicados
            tomado = True
        if not tomado:
            return {"locked": True, "remaining": 1}  # otro lote en marcha: reintenta luego
        token_cc = get_settings().COMPANYCAM_TOKEN or resolve_token()
        client = CompanyCamClient(token_cc) if token_cc else None
        async with worker_session() as db:
            return await downloads.process_batch(db, uuid.UUID(organization_id), client=client)
    finally:
        if client is not None:
            await client.aclose()
        try:
            if await redis.get(clave) == token:
                await redis.delete(clave)
        except Exception:
            pass
        await redis.aclose()


@celery_app.task(name="imports.companycam_download_batch", time_limit=180, soft_time_limit=170)
def companycam_download_batch_task(organization_id: str) -> dict:
    """Baja un lote de 10 fotos/documentos importados de CompanyCam de una
    organización y se vuelve a encolar mientras queden (`companycam_download.py
    enqueue --org` la dispara una vez). El lote se corta solo a los ~100 s."""
    resultado = asyncio.run(_companycam_download_batch(organization_id))
    logger.info("imports.companycam_batch", **resultado)
    if resultado.get("remaining"):
        companycam_download_batch_task.apply_async(args=[organization_id], countdown=2)
    return resultado
