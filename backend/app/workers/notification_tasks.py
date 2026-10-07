"""Tareas de Celery del módulo 7. Cada una abre su propia sesión async."""
import asyncio

import structlog

from app.db.session import AsyncSessionLocal
from app.modules.notifications import service
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _process(event: str, payload: dict) -> int:
    async with AsyncSessionLocal() as db:
        creados = await service.process_event(db, event, payload)
        if creados:
            await service.deliver_pending(db)
        return creados


async def _deliver() -> int:
    async with AsyncSessionLocal() as db:
        return await service.deliver_pending(db)


async def _daily() -> int:
    async with AsyncSessionLocal() as db:
        total = await service.daily_alerts_all(db)
        await service.deliver_pending(db, limit=500)
        return total


@celery_app.task(name="notifications.process_event", autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_event_task(event: str, payload: dict) -> int:
    return asyncio.run(_process(event, payload))


@celery_app.task(name="notifications.deliver_pending")
def deliver_pending_task() -> int:
    return asyncio.run(_deliver())


@celery_app.task(name="notifications.daily_alerts")
def daily_alerts_task() -> int:
    total = asyncio.run(_daily())
    logger.info("notifications.daily_alerts_done", created=total)
    return total
