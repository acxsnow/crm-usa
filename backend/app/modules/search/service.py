"""Buscador global: una caja en la barra superior que busca en todo lo que la
persona puede ver (Housecall Pro busca en todos los registros; recorrido del
24 oct 2026).

Reglas:

- Un grupo por tipo de registro, y cada grupo solo para quien tiene el permiso
  de la pantalla a la que lleva. Si no lo tiene, el grupo ni se consulta.
- Dentro de cada grupo, el mismo recorte que su listado: el vendedor ve solo
  sus expedientes, el técnico solo sus obras (también las que tuvo o en las que
  fue ayudante) y solo sus salidas de bodega. Esconderlo en la pantalla no
  bastaría: la API es la que decide.
- Siempre con el `organization_id` del token.
- Pocos resultados por grupo (`limit`): es para saltar a algo, no para listar.
  El «Ver todos» de cada grupo abre su listado con el mismo texto.
- `%` y `_` del texto se buscan tal cual (no son comodines).
"""
from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import quote

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions
from app.modules.users.models import User

MIN_LENGTH = 2
MAX_LENGTH = 100

# Permisos con los que se entra al buscador: los de cualquiera de sus grupos.
SEARCH_PERMISSIONS = (
    "customers.read",
    "cases.read_own", "cases.read_all",
    "projects.read_all", "projects.read_assigned",
    "invoices.read",
    "quotes.manage",
    "warehouse.read", "warehouse.manage", "warehouse.count",
    "warehouse.request_release", "warehouse.approve_release", "warehouse.deliver",
    "suppliers.manage", "payables.manage", "payables.approve",
    "users.manage",
)

_PROJECT_STATUS = {
    "planning": "Por programar", "scheduled": "Programada", "in_progress": "En curso",
    "completed": "Terminada", "cancelled": "Cancelada",
}


def _patron(texto: str) -> str:
    return "%" + texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _like(columna, patron: str):
    return columna.ilike(patron, escape="\\")


def _une(*partes: Any) -> str:
    return " · ".join(str(p) for p in partes if p)


def _direccion(obj) -> str:
    return ", ".join(x for x in (obj.address_street, obj.address_unit, obj.address_city) if x)


def _tiene(perms: set[str], *codigos: str) -> bool:
    return bool(perms & set(codigos))


async def _nombres_clientes(db: AsyncSession, organization_id: uuid.UUID, ids) -> dict:
    from app.modules.crm.models import Customer

    ids = {i for i in ids if i}
    if not ids:
        return {}
    filas = await db.execute(select(Customer.id, Customer.legal_name).where(
        Customer.organization_id == organization_id, Customer.id.in_(ids)))
    return dict(filas.all())


def _clientes_que_coinciden(organization_id: uuid.UUID, patron: str):
    from app.modules.crm.models import Customer

    return select(Customer.id).where(Customer.organization_id == organization_id,
                                     _like(Customer.legal_name, patron))


# ---------------------------------------------------------------------------
# Un buscador por grupo. Cada uno devuelve la lista de resultados ya armada.
# ---------------------------------------------------------------------------

async def _customers(db, org, user, perms, patron, limit):
    from app.modules.crm.models import Customer

    filas = (await db.execute(
        select(Customer).where(Customer.organization_id == org,
                               or_(_like(Customer.legal_name, patron), _like(Customer.email, patron),
                                   _like(Customer.main_phone, patron)))
        .order_by(Customer.legal_name).limit(limit))).scalars().all()
    return [{"id": str(c.id), "title": c.legal_name, "subtitle": _une(c.main_phone, c.email),
             "url": f"/customers/{c.id}"} for c in filas]


async def _cases(db, org, user, perms, patron, limit):
    from app.modules.cases import stages
    from app.modules.cases.models import Case

    stmt = select(Case).where(Case.organization_id == org,
                              or_(_like(Case.case_number, patron), _like(Case.address_street, patron),
                                  _like(Case.address_city, patron),
                                  Case.customer_id.in_(_clientes_que_coinciden(org, patron))))
    # El mismo recorte que el tablero: sin `cases.read_all`, solo los propios.
    if "cases.read_all" not in perms:
        stmt = stmt.where(Case.assigned_salesperson_id == user.id)
    filas = (await db.execute(stmt.order_by(Case.updated_at.desc(), Case.id.desc()).limit(limit))).scalars().all()
    clientes = await _nombres_clientes(db, org, [c.customer_id for c in filas])
    # Como en el tablero: quien revisa abre la revisión; el vendedor, su formulario.
    revisa = _tiene(perms, "cases.review", "cases.approve")
    return [{"id": str(c.id), "title": _une(c.case_number, clientes.get(c.customer_id)) or "Expediente",
             "subtitle": _une(stages.STAGE_LABELS.get(c.stage_code, c.stage_code), _direccion(c)),
             "url": f"/cases/{c.id}/review" if revisa and c.stage_code != "new_prospect" else f"/cases/{c.id}/form"}
            for c in filas]


async def _projects(db, org, user, perms, patron, limit):
    from app.modules.field_ops.access import scope_projects_stmt
    from app.modules.field_ops.models import Project

    stmt = select(Project).where(Project.organization_id == org,
                                 or_(_like(Project.title, patron), _like(Project.address_street, patron),
                                     _like(Project.address_city, patron),
                                     Project.customer_id.in_(_clientes_que_coinciden(org, patron))))
    stmt = scope_projects_stmt(stmt, user)
    filas = (await db.execute(stmt.order_by(Project.updated_at.desc(), Project.id.desc()).limit(limit))).scalars().all()
    estado = lambda p: _PROJECT_STATUS.get(getattr(p.status, "value", p.status), str(p.status))  # noqa: E731
    return [{"id": str(p.id), "title": p.title, "subtitle": _une(estado(p), _direccion(p)),
             "url": f"/projects/{p.id}"} for p in filas]


async def _invoices(db, org, user, perms, patron, limit):
    from app.modules.billing.models import Invoice

    filas = (await db.execute(
        select(Invoice).where(Invoice.organization_id == org,
                              or_(_like(Invoice.invoice_number, patron),
                                  Invoice.customer_id.in_(_clientes_que_coinciden(org, patron))))
        .order_by(Invoice.created_at.desc()).limit(limit))).scalars().all()
    clientes = await _nombres_clientes(db, org, [i.customer_id for i in filas])
    salida = []
    for i in filas:
        a_quien = (i.funder_program or "Programa") if i.kind == "rebate" else "Trabajo particular"
        # La de un programa se trabaja desde su cobro; la particular, en Facturas.
        url = (f"/invoices/claims/{i.claim_id}" if i.claim_id
               else f"/invoices?tab=invoices&q={quote(i.invoice_number)}")
        salida.append({"id": str(i.id), "title": _une(i.invoice_number, clientes.get(i.customer_id)),
                       "subtitle": _une(a_quien, "Borrador" if i.document_status == "draft" else None), "url": url})
    return salida


async def _quotes(db, org, user, perms, patron, limit):
    from app.modules.billing.models import Quote

    # Cada cotización tiene varias versiones con el mismo número: se muestra la última.
    filas = (await db.execute(
        select(Quote).where(Quote.organization_id == org,
                            or_(_like(Quote.quote_number, patron), _like(Quote.title, patron),
                                Quote.customer_id.in_(_clientes_que_coinciden(org, patron))))
        .order_by(Quote.created_at.desc(), Quote.version.desc()).limit(limit * 5))).scalars().all()
    ultimas: dict[str, Any] = {}
    for q in filas:
        if q.quote_number not in ultimas or q.version > ultimas[q.quote_number].version:
            ultimas[q.quote_number] = q
    elegidas = list(ultimas.values())[:limit]
    clientes = await _nombres_clientes(db, org, [q.customer_id for q in elegidas])
    return [{"id": str(q.id), "title": _une(q.quote_number, clientes.get(q.customer_id)),
             "subtitle": _une(q.title, f"versión {q.version}" if q.version > 1 else None),
             "url": f"/invoices/quotes/{q.id}"} for q in elegidas]


async def _items(db, org, user, perms, patron, limit):
    from app.modules.warehouse.models import WarehouseItem

    filas = (await db.execute(
        select(WarehouseItem).where(WarehouseItem.organization_id == org, WarehouseItem.active.is_(True),
                                    or_(_like(WarehouseItem.name, patron), _like(WarehouseItem.sku, patron),
                                        _like(WarehouseItem.manufacturer_part, patron),
                                        _like(WarehouseItem.brand, patron)))
        .order_by(WarehouseItem.name).limit(limit))).scalars().all()
    return [{"id": str(i.id), "title": i.name, "subtitle": _une(i.sku, i.manufacturer_part, i.brand),
             "url": f"/warehouse/items?q={quote(i.sku or i.name)}"} for i in filas]


_ALL_RELEASES = {"warehouse.read", "warehouse.manage", "warehouse.approve_release", "warehouse.deliver"}


async def _releases(db, org, user, perms, patron, limit):
    from app.modules.field_ops.models import Project
    from app.modules.warehouse.catalogs import RELEASE_STATUSES
    from app.modules.warehouse.models import WarehouseReleaseOrder as Orden

    obras = select(Project.id).where(Project.organization_id == org, _like(Project.title, patron))
    stmt = select(Orden).where(Orden.organization_id == org,
                               or_(_like(Orden.number, patron), _like(Orden.note, patron),
                                   Orden.project_id.in_(obras)))
    # Como en Salidas: quien no ve todas, solo las que pidió o son para él.
    if not (perms & _ALL_RELEASES):
        stmt = stmt.where(or_(Orden.requested_by_user_id == user.id, Orden.technician_user_id == user.id))
    filas = (await db.execute(stmt.order_by(Orden.created_at.desc()).limit(limit))).scalars().all()
    titulos = {}
    ids = {o.project_id for o in filas if o.project_id}
    if ids:
        titulos = dict((await db.execute(select(Project.id, Project.title).where(Project.id.in_(ids)))).all())
    return [{"id": str(o.id), "title": o.number or "Salida sin número",
             "subtitle": _une(RELEASE_STATUSES.get(o.status, o.status), titulos.get(o.project_id)),
             "url": f"/warehouse/releases?q={quote(o.number)}" if o.number else "/warehouse/releases"}
            for o in filas]


async def _suppliers(db, org, user, perms, patron, limit):
    from app.modules.finance.models import Supplier

    filas = (await db.execute(
        select(Supplier).where(Supplier.organization_id == org,
                               or_(_like(Supplier.name, patron), _like(Supplier.legal_name, patron),
                                   _like(Supplier.contact_name, patron)))
        .order_by(Supplier.name).limit(limit))).scalars().all()
    return [{"id": str(s.id), "title": s.name, "subtitle": _une(s.contact_name, s.phone),
             "url": f"/payables?tab=suppliers&q={quote(s.name)}"} for s in filas]


async def _users(db, org, user, perms, patron, limit):
    filas = (await db.execute(
        select(User).where(User.organization_id == org,
                           or_(_like(User.full_name, patron), _like(User.email_display, patron)))
        .order_by(User.full_name).limit(limit))).scalars().all()
    return [{"id": str(u.id), "title": u.full_name, "subtitle": u.email_display,
             "url": f"/users?q={quote(u.email_display)}"} for u in filas]


# (clave, título, permisos que abren el grupo, buscador, «Ver todos» con {q})
GROUPS = (
    ("customers", "Clientes", ("customers.read",), _customers, "/customers?q={q}"),
    ("cases", "Expedientes", ("cases.read_own", "cases.read_all"), _cases, "/cases?q={q}"),
    ("projects", "Obras", ("projects.read_all", "projects.read_assigned"), _projects, "/projects?q={q}"),
    ("invoices", "Facturas", ("invoices.read",), _invoices, "/invoices?tab=invoices&q={q}"),
    ("quotes", "Cotizaciones", ("quotes.manage",), _quotes, "/invoices?tab=quotes"),
    ("items", "Artículos de bodega", ("warehouse.read", "warehouse.manage", "warehouse.count"), _items,
     "/warehouse/items?q={q}"),
    ("releases", "Salidas de bodega", ("warehouse.read", "warehouse.manage", "warehouse.request_release",
                                       "warehouse.approve_release", "warehouse.deliver"), _releases,
     "/warehouse/releases?q={q}"),
    ("suppliers", "Proveedores", ("suppliers.manage", "payables.manage", "payables.approve"), _suppliers,
     "/payables?tab=suppliers&q={q}"),
    ("users", "Usuarios", ("users.manage",), _users, "/users?q={q}"),
)


async def search(db: AsyncSession, *, organization_id: uuid.UUID, user: User, q: str, limit: int = 5) -> dict:
    texto = " ".join((q or "").split())[:MAX_LENGTH]
    if len(texto) < MIN_LENGTH:
        return {"q": texto, "groups": []}
    perms = get_effective_permissions(user)
    patron = _patron(texto)

    grupos = []
    for clave, titulo, permisos, buscar, ver_todos in GROUPS:
        if not _tiene(perms, *permisos):
            continue
        resultados = await buscar(db, organization_id, user, perms, patron, limit)
        if resultados:
            grupos.append({"key": clave, "label": titulo, "results": resultados,
                           "more_url": ver_todos.format(q=quote(texto))})
    return {"q": texto, "groups": grupos}
