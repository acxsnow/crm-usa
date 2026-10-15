"""Ningún listado sale sin paginar.

Recorre todas las rutas de la API y falla si un `GET` que devuelve una lista no
declara `Depends(pagination_params)` (`app/shared/pagination.py`). Es lo que en
Django REST Framework hace `DEFAULT_PAGINATION_CLASS` de forma global: aquí se
garantiza con esta prueba, que corre en integración continua.

Si un listado nuevo falla aquí, la solución casi siempre es paginarlo. Solo si
pagina a su manera por una razón de peso va a `EXCEPTIONS`, con el motivo."""
import inspect
import typing

from fastapi.routing import APIRoute

from app.main import app
from app.shared.pagination import EXCEPTIONS, MAX_LIMIT, pagination_params


def _returns_items(r: APIRoute, devuelve) -> bool:
    """¿Devuelve un objeto con la lista en `items` (`{"items": [...], ...}`)?
    Se escapó «Mis avisos» (15 oct 2026): la guardia solo miraba listas."""
    campos = getattr(r.response_model, "model_fields", None)
    if campos and "items" in campos and typing.get_origin(campos["items"].annotation) is list:
        return True
    return devuelve is dict and '"items":' in inspect.getsource(r.endpoint)


def _list_routes() -> list[APIRoute]:
    rutas = []
    for r in app.routes:
        if not isinstance(r, APIRoute) or "GET" not in r.methods:
            continue
        devuelve = inspect.signature(r.endpoint).return_annotation
        if (typing.get_origin(r.response_model) is list or typing.get_origin(devuelve) is list
                or _returns_items(r, devuelve)):
            rutas.append(r)
    return rutas


def _paginated(r: APIRoute) -> bool:
    return any(d.call is pagination_params for d in r.dependant.dependencies)


def test_every_list_endpoint_is_paginated():
    sin_paginar = sorted(r.path for r in _list_routes() if not _paginated(r) and r.path not in EXCEPTIONS)
    assert not sin_paginar, (
        "Estos listados no tienen Depends(pagination_params). Paginarlos con "
        "app/shared/pagination.py (o, si de verdad paginan a su manera, agregarlos a EXCEPTIONS "
        f"con el motivo): {sin_paginar}"
    )


def test_exceptions_are_real_list_routes_with_a_reason():
    """Una excepción que ya no existe o sin motivo no debe quedarse escrita."""
    rutas = {r.path for r in _list_routes()}
    for ruta, motivo in EXCEPTIONS.items():
        assert ruta in rutas, f"{ruta} está en EXCEPTIONS pero no es un listado GET"
        assert len(motivo) > 20, f"{ruta}: el motivo de la excepción es muy corto"


async def test_the_limit_can_never_exceed_the_maximum(app_client, active_admin_user):
    """El tope se respeta aunque el cliente pida más."""
    from tests.field_helpers import headers_for

    headers = await headers_for(app_client, "admin@acme-demo.com")
    r = await app_client.get(f"/api/v1/customers?limit={MAX_LIMIT + 1}", headers=headers)
    assert r.status_code == 422
