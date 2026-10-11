"""Paginación común de todos los listados (limit/offset, total en X-Total-Count).

Es el equivalente de `DEFAULT_PAGINATION_CLASS` de Django REST Framework, con
una diferencia: aquí cada endpoint la declara con `Depends(pagination_params)`,
y `tests/test_pagination_everywhere.py` recorre todas las rutas y falla si un
listado `GET` no la tiene. Así ningún listado nuevo puede salir sin paginar.
Las únicas excepciones están en `EXCEPTIONS`, cada una con su motivo.

Reglas:

- `DEFAULT_LIMIT` filas por defecto y nunca más de `MAX_LIMIT`, aunque el
  cliente pida más. Una consulta sin tope es un riesgo de agotar recursos
  (OWASP API4:2023, Unrestricted Resource Consumption).
- La respuesta sigue siendo una lista; el total viaja en el encabezado
  `X-Total-Count`. Por eso el frontend que lee `res.data` como lista sigue
  funcionando, y `fetchPage` (frontend `lib/pagination.ts`) lee el total.
- Tres formas, según de dónde salen los datos:
  - `paginate(db, stmt)`: una consulta que devuelve un modelo por fila.
  - `paginate(db, stmt, scalars=False)`: una consulta de varias columnas o
    entidades por fila (por ejemplo, envío + aviso).
  - `paginate_list(items)`: una lista que se arma en Python (catálogos fijos,
    datos calculados). La consulta de origen debe estar acotada por sí misma.
"""
from fastapi import Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

DEFAULT_LIMIT = 100
MAX_LIMIT = 500

# Listados que paginan a su manera, a propósito. Clave: ruta tal como la
# declara FastAPI; valor: el motivo. Agregar algo aquí debe ser una decisión.
EXCEPTIONS: dict[str, str] = {
    "/api/v1/case-board": "Tablero por etapa: pagina cada columna por separado (limit/offset por etapa, "
                          "ROW_NUMBER en la base).",
    "/api/v1/cases/activity": "Actividad del Inicio: tope fijo de 50 eventos (parámetro limit), sin páginas.",
}


def pagination_params(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> tuple[int, int]:
    return limit, offset


async def paginate(
    db: AsyncSession, stmt: Select, *, limit: int, offset: int, response: Response, scalars: bool = True,
) -> list:
    """Cuenta el total, pone X-Total-Count y devuelve una página de `stmt`.
    `stmt` ya debe traer el filtro de organización y un ORDER BY estable.
    Con `scalars=False` devuelve filas completas (varias columnas o entidades)."""
    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    result = await db.execute(stmt.limit(limit).offset(offset))
    return list(result.scalars().all() if scalars else result.all())


def paginate_list(items: list, *, limit: int, offset: int, response: Response) -> list:
    """La misma paginación para una lista que ya está en memoria (catálogos
    fijos o datos que se calculan en Python): pone X-Total-Count y recorta."""
    response.headers["X-Total-Count"] = str(len(items))
    return list(items[offset:offset + limit])
