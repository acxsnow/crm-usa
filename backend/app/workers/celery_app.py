"""Celery application entrypoint. Task modules for PDF generation and
thumbnailing are still to come in a later phase; the overdue-invoice sweep
(Phase 5) lives in app/workers/tasks.py and is scheduled below via
celery beat — see docker-compose.yml's `beat` service, which runs
`celery -A app.workers.celery_app beat`, separate from the `worker` service
that actually executes tasks (standard Celery split: beat only enqueues,
worker(s) consume)."""
from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "crm_field_ops",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "sweep-overdue-invoices-daily": {
        "task": "workers.sweep_overdue_invoices",
        "schedule": crontab(hour=6, minute=0),  # once a day, 06:00 UTC
    },
}

# Registers the tasks defined there (sweep_overdue_invoices_task) with this
# app — imported for the side effect of the @celery_app.task decorator
# running, not for anything used directly here.
from app.workers import tasks as _tasks  # noqa: E402,F401


@celery_app.task(name="workers.health_check")
def health_check() -> str:
    return "ok"
