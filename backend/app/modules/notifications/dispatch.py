"""Puente de los eventos de dominio a la cola (módulo 7).

`shared/events.emit()` llama a los suscriptores en el mismo proceso y de forma
síncrona; aquí solo se encola el evento en Celery (Redis) y se vuelve. El
trabajo de verdad (buscar destinatarios, crear avisos, enviar) lo hace el
worker. Si Redis no responde, el evento queda en el log y la operación sigue.

`NOTIFICATIONS_DISPATCH=off` lo apaga (pruebas, scripts)."""
import structlog

from app.core.config import get_settings
from app.shared import events as domain_events

logger = structlog.get_logger(__name__)

EVENTS = (
    "case.submitted", "case.substatus_changed", "case.stage_changed", "installation.scheduled",
    "installation.closed",
    "project.returned_to_technician", "claim.rejected", "claim.paid",
    "expense.submitted", "expense.reviewed", "payable.pending_approval",
    # Bodega (cuestionario del 19 de octubre, punto 1).
    "warehouse.release_pending", "warehouse.release_delivered", "warehouse.stock_low",
)


def enqueue(event_name: str, payload: dict) -> None:
    if get_settings().NOTIFICATIONS_DISPATCH != "celery":
        return
    try:
        from app.workers.celery_app import celery_app

        celery_app.send_task("notifications.process_event", args=[event_name, payload], retry=False)
    except Exception as exc:
        logger.warning("notifications.enqueue_failed", domain_event=event_name, error=str(exc))


_registrado = False


def register() -> None:
    global _registrado
    if _registrado:
        return
    for e in EVENTS:
        domain_events.subscribe(e, enqueue)
    _registrado = True


def _reset_for_tests() -> None:
    global _registrado
    _registrado = False
