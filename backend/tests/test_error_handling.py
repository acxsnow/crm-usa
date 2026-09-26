"""Manejo de errores: qué ve el usuario y qué queda registrado.

Dos reglas que estos tests protegen:

1. **Nada de lo interno sale al cliente.** Un fallo inesperado devuelve un
   mensaje neutro; el traceback, la consulta SQL o la ruta del servidor van al
   log, nunca a la respuesta.
2. **Todo error se puede rastrear.** La respuesta trae el `request_id`, así que
   cuando alguien reporta un problema se puede buscar ese identificador en el
   log y encontrar el fallo exacto.
"""
import pytest
from fastapi import APIRouter
from sqlalchemy.exc import IntegrityError

from app.shared.errors import (
    ConflictError,
    DomainError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
)


# ---------------------------------------------------------------------------
# Las excepciones de dominio no saben de HTTP
# ---------------------------------------------------------------------------

def test_domain_errors_carry_a_message_and_a_code():
    error = NotFoundError("El expediente no existe.", code="case_not_found")
    assert error.message == "El expediente no existe."
    assert error.code == "case_not_found"
    assert isinstance(error, DomainError)


def test_domain_errors_have_a_default_code():
    assert NotFoundError("X").code == "not_found"
    assert ConflictError("X").code == "conflict"
    assert InvalidInputError("X").code == "invalid_input"
    assert ForbiddenError("X").code == "forbidden"


# ---------------------------------------------------------------------------
# Traducción a respuestas HTTP
# ---------------------------------------------------------------------------

@pytest.fixture
def failing_app():
    """Monta rutas que fallan de cada forma posible, sobre la app real, para
    probar los manejadores tal como están registrados en producción."""
    from app.main import app

    router = APIRouter(prefix="/_test_errors")

    @router.get("/not-found")
    async def _not_found():
        raise NotFoundError("El expediente no existe.", code="case_not_found")

    @router.get("/conflict")
    async def _conflict():
        raise ConflictError("Ese código ya está en uso.")

    @router.get("/invalid")
    async def _invalid():
        raise InvalidInputError("El amperaje debe ser un número.")

    @router.get("/forbidden")
    async def _forbidden():
        raise ForbiddenError("No puedes revisar tu propio expediente.")

    @router.get("/integrity")
    async def _integrity():
        raise IntegrityError(
            "INSERT INTO users (email) VALUES ('a@b.com')",
            {"email": "a@b.com"},
            Exception("duplicate key value violates unique constraint"),
        )

    @router.get("/boom")
    async def _boom():
        secret = "contraseña-interna-que-no-debe-salir"
        raise RuntimeError(f"fallo con {secret} en /srv/app/interno.py")

    # Al principio: la app tiene una ruta comodín al final que sirve el
    # frontend y se quedaría con estas peticiones.
    before = len(app.router.routes)
    app.include_router(router)
    added = app.router.routes[before:]
    app.router.routes = added + app.router.routes[:before]

    yield app

    app.router.routes = [r for r in app.router.routes if r not in added]


async def test_not_found_maps_to_404_with_code(app_client, failing_app):
    resp = await app_client.get("/_test_errors/not-found")
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"] == "El expediente no existe."
    assert body["code"] == "case_not_found"


async def test_conflict_maps_to_409(app_client, failing_app):
    resp = await app_client.get("/_test_errors/conflict")
    assert resp.status_code == 409
    assert resp.json()["code"] == "conflict"


async def test_invalid_input_maps_to_400(app_client, failing_app):
    resp = await app_client.get("/_test_errors/invalid")
    assert resp.status_code == 400


async def test_forbidden_maps_to_403(app_client, failing_app):
    resp = await app_client.get("/_test_errors/forbidden")
    assert resp.status_code == 403


async def test_database_integrity_error_becomes_409_not_500(app_client, failing_app):
    """Dos personas creando el mismo registro a la vez es un conflicto, no un
    error del servidor, y el SQL no puede salir en la respuesta."""
    resp = await app_client.get("/_test_errors/integrity")
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "conflict"
    for leak in ("INSERT INTO", "unique constraint", "a@b.com"):
        assert leak not in str(body), f"la respuesta filtra detalles de la base: {body}"


async def test_unexpected_error_is_a_neutral_500(app_client, failing_app):
    resp = await app_client.get("/_test_errors/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "internal_error"
    for leak in ("contraseña-interna", "/srv/app", "RuntimeError", "Traceback"):
        assert leak not in str(body), f"la respuesta filtra información interna: {body}"


# ---------------------------------------------------------------------------
# Trazabilidad
# ---------------------------------------------------------------------------

async def test_every_error_response_carries_the_request_id(app_client, failing_app):
    """Sin esto, un usuario que reporta un fallo no tiene nada que darnos para
    encontrarlo en el log."""
    resp = await app_client.get("/_test_errors/boom", headers={"X-Request-ID": "abc-123"})
    assert resp.json()["request_id"] == "abc-123"
    assert resp.headers["X-Request-ID"] == "abc-123"


async def test_request_id_is_generated_when_the_client_does_not_send_one(app_client, failing_app):
    resp = await app_client.get("/_test_errors/not-found")
    assert resp.json()["request_id"]


# ---------------------------------------------------------------------------
# Errores que ya existían: siguen funcionando igual
# ---------------------------------------------------------------------------

async def test_validation_errors_use_the_same_shape(app_client):
    """Un 422 de Pydantic se normaliza al mismo formato, para que el frontend
    lea siempre `detail` y no tenga que distinguir dos estructuras."""
    resp = await app_client.post("/api/v1/auth/login", json={"email": "no-es-un-email"})
    assert resp.status_code == 422
    body = resp.json()
    assert isinstance(body["detail"], str)
    assert body["code"] == "validation_error"
    assert body["request_id"]
    assert "errors" in body


async def test_http_exception_keeps_working(app_client):
    """El código que todavía usa HTTPException sigue respondiendo igual, para
    poder migrar módulo por módulo sin romper nada."""
    resp = await app_client.get("/api/v1/users")
    assert resp.status_code == 401
    assert resp.json()["detail"]
    assert resp.json()["request_id"]


# ---------------------------------------------------------------------------
# CORS en las respuestas de error
# ---------------------------------------------------------------------------

async def test_unexpected_error_still_carries_cors_headers(app_client, failing_app):
    """Un 500 tiene que llegar al navegador.

    El manejador de excepciones no controladas vive en el middleware de errores
    de Starlette, que está por encima del de CORS: su respuesta no pasaba por
    ahí, el navegador la bloqueaba por política de origen y el frontend recibía
    un error de red en vez del 500. El usuario nunca veía el código de
    referencia que necesita para reportar el problema."""
    resp = await app_client.get(
        "/_test_errors/boom", headers={"Origin": "http://localhost:5173"}
    )
    assert resp.status_code == 500
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert resp.json()["request_id"]


async def test_domain_errors_carry_cors_headers(app_client, failing_app):
    resp = await app_client.get(
        "/_test_errors/not-found", headers={"Origin": "http://localhost:5173"}
    )
    assert resp.status_code == 404
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
