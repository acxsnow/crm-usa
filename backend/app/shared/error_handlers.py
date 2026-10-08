"""Traducción de errores a respuestas HTTP.

Es el único lugar del backend que decide qué código de estado corresponde a
cada fallo y qué se le cuenta al usuario. Dos principios:

- **Lo interno no sale.** El traceback, el SQL y las rutas del servidor van al
  log; la respuesta lleva un mensaje que una persona pueda entender.
- **Todo se puede rastrear.** Cada respuesta de error incluye el `request_id`,
  así que cuando alguien reporta un problema basta buscar ese identificador en
  el log para encontrar el fallo exacto, con usuario, organización y traza.

Ver `docs/ERRORES.md`.
"""
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    ExternalServiceError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
)

logger = structlog.get_logger(__name__)

DOMAIN_ERROR_STATUS: dict[type[DomainError], int] = {
    ExternalServiceError: 502,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    InvalidInputError: status.HTTP_400_BAD_REQUEST,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
}

GENERIC_ERROR_MESSAGE = (
    "Ocurrió un error inesperado. Si vuelve a pasar, comparte el código de "
    "referencia con soporte."
)
GENERIC_CONFLICT_MESSAGE = (
    "La operación choca con datos que ya existen. Actualiza la página y vuelve "
    "a intentarlo."
)


def get_request_id(request: Request) -> str:
    """El identificador que el middleware puso en esta petición."""
    return getattr(request.state, "request_id", "")


def error_response(
    request: Request,
    *,
    status_code: int,
    detail: str,
    code: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = get_request_id(request)
    body: dict[str, Any] = {
        "detail": detail,
        "code": code,
        "request_id": request_id,
    }
    if extra:
        body.update(extra)
    # El header se repite aquí a propósito: la respuesta de un fallo no
    # controlado la genera Starlette por encima del middleware que lo añade,
    # así que sin esto el 500 —justo el caso donde más se necesita— saldría
    # sin identificador.
    headers = {"X-Request-ID": request_id} if request_id else None
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def _request_context(request: Request) -> dict[str, Any]:
    """Datos de la petición para el log. El cuerpo no se registra: puede traer
    contraseñas, firmas o datos del cliente."""
    user = getattr(request.state, "current_user", None)
    return {
        "method": request.method,
        "path": request.url.path,
        "user_id": str(user.id) if user is not None else None,
        "organization_id": str(user.organization_id) if user is not None else None,
    }


def build_unhandled_error_response(request: Request, exc: Exception) -> JSONResponse:
    """Respuesta para un fallo no previsto: traza completa al log, mensaje
    neutro al usuario.

    Vive aparte del manejador registrado porque el middleware de petición la
    necesita: ver el comentario en `app/main.py`."""
    logger.error(
        "unhandled_error",
        error_type=type(exc).__name__,
        error=str(exc),
        **_request_context(request),
        exc_info=True,
    )
    return error_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=GENERIC_ERROR_MESSAGE,
        code="internal_error",
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        status_code = next(
            (code for kind, code in DOMAIN_ERROR_STATUS.items() if isinstance(exc, kind)),
            status.HTTP_400_BAD_REQUEST,
        )
        # Son fallos esperados (el usuario pidió algo que no existe, chocó con
        # una regla): se registran en info, no como incidentes.
        logger.info("domain_error", code=exc.code, detail=exc.message, **_request_context(request))
        return error_response(request, status_code=status_code, detail=exc.message, code=exc.code)

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Mantiene funcionando el código que todavía usa `HTTPException`, pero
        con el mismo formato de respuesta que el resto."""
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return error_response(
            request,
            status_code=exc.status_code,
            detail=detail,
            code=f"http_{exc.status_code}",
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Normaliza el 422 de Pydantic al mismo formato.

        `detail` pasa a ser un texto legible —Pydantic devuelve una lista de
        objetos— y el desglose por campo queda en `errors`, para que el
        frontend pueda marcar los campos sin tener que interpretar dos
        estructuras distintas de error."""
        errors = [
            {
                "field": ".".join(str(part) for part in err.get("loc", ()) if part != "body"),
                "message": err.get("msg", ""),
            }
            for err in exc.errors()
        ]
        if errors:
            campos = ", ".join(e["field"] for e in errors if e["field"])
            detail = f"Hay datos inválidos en: {campos}." if campos else "Los datos enviados no son válidos."
        else:
            detail = "Los datos enviados no son válidos."

        logger.info("validation_error", errors=errors, **_request_context(request))
        return error_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            code="validation_error",
            extra={"errors": errors},
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        """Una restricción de la base saltó: casi siempre dos operaciones
        simultáneas creando el mismo registro. Es un conflicto (409), no un
        error del servidor, y el SQL no puede salir en la respuesta."""
        logger.warning(
            "integrity_error", error=str(exc.orig), **_request_context(request), exc_info=True
        )
        return error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            detail=GENERIC_CONFLICT_MESSAGE,
            code="conflict",
        )

    @app.exception_handler(SQLAlchemyError)
    async def _database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("database_error", error=str(exc), **_request_context(request), exc_info=True)
        return error_response(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=GENERIC_ERROR_MESSAGE,
            code="internal_error",
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        """Última red de seguridad, para lo que ocurra fuera del middleware de
        petición (por ejemplo, en otro middleware). El camino normal lo atrapa
        `add_request_id` en `main.py`, para que la respuesta pase por CORS."""
        return build_unhandled_error_response(request, exc)
