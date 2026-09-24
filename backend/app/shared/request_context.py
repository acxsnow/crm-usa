"""Contexto de la petición en curso.

Guarda el identificador de la petición, la IP y el navegador para que la
auditoría los registre sin que cada llamada tenga que ir pasándolos por
parámetro desde el endpoint hasta el service.

Usa `contextvars`, que en async se aísla por tarea: dos peticiones atendidas a
la vez en el mismo worker no se pisan. El middleware lo llena al entrar y lo
limpia al salir.
"""
from contextvars import ContextVar
from typing import NamedTuple


class RequestContext(NamedTuple):
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


_context: ContextVar[RequestContext] = ContextVar("request_context", default=RequestContext())


def set_request_context(
    *, request_id: str | None, ip_address: str | None, user_agent: str | None
) -> None:
    _context.set(
        RequestContext(request_id=request_id, ip_address=ip_address, user_agent=user_agent)
    )


def get_request_context() -> RequestContext:
    return _context.get()


def clear_request_context() -> None:
    _context.set(RequestContext())
