"""Eventos de dominio, en proceso.

Existe para que los **puntos de emisión** estén en su sitio desde el principio.
Agregar `emit()` después, cuando ya hay veinte lugares que cambian de estado, es
como poner la auditoría al final: siempre falta uno.

Deliberadamente mínimo. **No** es una cola: los suscriptores corren en el mismo
proceso y dentro de la misma transacción que quien emite. Si un suscriptor
tarda, quien emitió tarda. El módulo 7 (Mateo, notificaciones) lo reemplaza por
Celery/Redis; cuando eso pase, esta firma no cambia y los emisores no se tocan.

Un suscriptor que falla **no tumba la operación**: el cambio de etapa es el
hecho de negocio, y que un aviso no salga no puede deshacerlo. El fallo se
registra para que no pase inadvertido.
"""
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)

Subscriber = Callable[[str, dict[str, Any]], None]

_SUBSCRIBERS: dict[str, list[Subscriber]] = {}


def subscribe(event_name: str, fn: Subscriber) -> None:
    _SUBSCRIBERS.setdefault(event_name, []).append(fn)


def emit(event_name: str, payload: dict[str, Any]) -> None:
    """Registra el evento y avisa a los suscriptores.

    Siempre deja rastro en el log, haya o no suscriptores: hoy no hay ninguno y
    el registro es lo único que prueba que la emisión ocurrió."""
    # `event` es la clave reservada de structlog para el mensaje, así que el
    # nombre del evento de dominio va como `domain_event`.
    logger.info("domain_event", domain_event=event_name, **payload)
    for fn in _SUBSCRIBERS.get(event_name, []):
        try:
            fn(event_name, payload)
        except Exception:
            logger.exception(
                "domain_event.subscriber_failed", domain_event=event_name, subscriber=getattr(fn, "__name__", repr(fn))
            )


def clear_subscribers() -> None:
    """Solo para pruebas."""
    _SUBSCRIBERS.clear()
