"""Rutas de la bodega: artículos, ubicaciones, existencias, movimientos,
carga del catálogo y conteos (spec `2026-10-19-control-bodega-design.md`)."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions, get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.users.models import User
from app.modules.warehouse import service as wh
from app.modules.warehouse import budgets as budget_svc
from app.modules.warehouse import categories as cat_svc
from app.modules.warehouse import costing as costing_svc
from app.modules.warehouse import day_logs as daylog_svc
from app.modules.warehouse import kits as kit_svc
from app.modules.warehouse import releases as rel
from app.modules.warehouse import xlsx
from app.modules.warehouse.catalogs import (
    BUDGET_CATEGORIES,
    BUDGET_STATUSES,
    ITEM_UNITS,
    LINE_ORIGINS,
    LOCATION_KINDS,
    MOVEMENT_TYPES,
    RELEASE_STATUSES,
)
from app.modules.warehouse.models import WarehouseItem, WarehouseLocation, WarehouseMovement
from app.shared.errors import InvalidInputError, NotFoundError
from app.shared.files.validation import read_limited
from app.shared.pagination import paginate, paginate_list, pagination_params

router = APIRouter(tags=["warehouse"])

MAX_CATALOG_BYTES = 10 * 1024 * 1024

_read = require_any_permission("warehouse.read", "warehouse.manage", "warehouse.count")
# El catálogo (artículos, ubicaciones, listas): también lo ve el técnico, que lo
# necesita para pedir material y llenar el diario, pero sin costos ni valores
# (`_sin_costos`). Las existencias, movimientos y presupuestos siguen en `_read`.
_catalog = require_any_permission("warehouse.read", "warehouse.manage", "warehouse.count",
                                  "warehouse.request_release", "daylogs.manage")
# Ver órdenes de salida: quien las pide (solo las suyas), autoriza o entrega.
_release_read = require_any_permission("warehouse.read", "warehouse.manage", "warehouse.request_release",
                                       "warehouse.approve_release", "warehouse.deliver")

# Quien ve costos de bodega: lectura o administración de bodega, o presupuesto.
_COST_PERMS = {"warehouse.read", "warehouse.manage", "budgets.manage", "budgets.approve"}
# Quien ve todas las órdenes de salida (no solo las propias).
_ALL_RELEASES_PERMS = {"warehouse.read", "warehouse.manage", "warehouse.approve_release", "warehouse.deliver"}
_COST_KEYS = {"unit_cost", "value"}


def _ve_costos(user) -> bool:
    return bool(_COST_PERMS & get_effective_permissions(user))


def _sin_costos(datos, user):
    """Quita costos y valores para quien no debe verlos (el técnico)."""
    if _ve_costos(user):
        return datos
    if isinstance(datos, list):
        return [_sin_costos(d, user) for d in datos]
    if isinstance(datos, dict):
        return {k: _sin_costos(v, user) for k, v in datos.items() if k not in _COST_KEYS}
    return datos


async def _articulos_para(db, organization_id, user, filas: list[dict]) -> list[dict]:
    """Bodega ve todo; el técnico ve el catálogo sin costos y, de existencias,
    solo lo que lleva en su camioneta (lo que puede usar en el diario)."""
    if _ve_costos(user):
        return filas
    from decimal import Decimal

    from sqlalchemy import select

    propias = {str(i) for i in (await db.execute(select(WarehouseLocation.id).where(
        WarehouseLocation.organization_id == organization_id,
        WarehouseLocation.technician_user_id == user.id))).scalars().all()}
    salida = []
    for fila in _sin_costos(filas, user):
        mias = [l for l in fila.get("by_location", []) if l["location_id"] in propias]
        total = sum((Decimal(str(l["quantity"])) for l in mias), Decimal("0"))
        salida.append({**fila, "by_location": mias, "total_quantity": f"{total:.2f}"})
    return salida


def _solo_propias(user) -> bool:
    return not (_ALL_RELEASES_PERMS & get_effective_permissions(user))


def _check_release_access(order, user) -> None:
    """El técnico solo ve sus órdenes (las que pidió o las que son para él);
    las ajenas responden 404 para no confirmar que existen."""
    if _solo_propias(user) and user.id not in (order.requested_by_user_id, order.technician_user_id):
        raise NotFoundError("La orden de salida no existe.", code="release_order_not_found")
_manage = require_permission("warehouse.manage")
_count = require_permission("warehouse.count")
# Pedir la salida: el técnico (respuesta 2 del cuestionario) o quien administra
# la bodega. Autorizar y entregar son permisos aparte: los tiene el supervisor.
_request = require_any_permission("warehouse.request_release", "warehouse.manage")
_approve = require_permission("warehouse.approve_release")
_deliver = require_any_permission("warehouse.deliver", "warehouse.manage")
# Las listas predefinidas: las edita quien administra la bodega, las usa quien
# arma la orden (el técnico).
_kits = require_permission("warehouse.kits_manage")
# El presupuesto del proyecto: lo arma el supervisor y lo aprueba quien tenga el
# permiso de aprobación (puede ser la misma persona, es el caso de la respuesta
# 17 del cuestionario: Administración hace las dos cosas).
_budget_manage = require_permission("budgets.manage")
_budget_approve = require_permission("budgets.approve")
# Ver el presupuesto: lo ve quien lo arma, quien lo aprueba y Gerencia, que solo
# tiene lectura de bodega.
_budget_read = require_any_permission("warehouse.read", "budgets.manage", "budgets.approve")
# El diario de obra: lo llena el técnico desde la obra (`daylogs.manage`) y lo
# lee cualquiera que vea la bodega, que es quien mira los gastos del día.
_daylog_read = require_any_permission("warehouse.read", "daylogs.manage")
_daylog_manage = require_permission("daylogs.manage")


async def _visible_project(db, organization_id, user, project_id):
    """El proyecto, si la persona lo ve: el técnico, solo los suyos (misma regla
    que el acta de instalación). Un proyecto ajeno responde 404."""
    from app.modules.field_ops.access import get_visible_project

    return await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)


@router.get("/warehouse/catalogs")
async def warehouse_catalogs(db: AsyncSession = Depends(get_db),
                             organization_id: uuid.UUID = Depends(get_organization_id),
                             current_user: User = Depends(_catalog)) -> dict:
    # Las categorías son las de la organización (fase 3): `categories` trae las
    # que se pueden elegir y `category_labels` todas, para nombrar las de los
    # artículos viejos aunque ya no se ofrezcan.
    todas = await cat_svc.list_categories(db, organization_id)
    return {"categories": {c.code: c.label for c in todas if c.active},
            "category_labels": {c.code: c.label for c in todas},
            "units": ITEM_UNITS, "movement_types": MOVEMENT_TYPES,
            "location_kinds": LOCATION_KINDS, "release_statuses": RELEASE_STATUSES,
            "line_origins": LINE_ORIGINS, "budget_categories": BUDGET_CATEGORIES,
            "budget_statuses": BUDGET_STATUSES}


# ---------------------------------------------------------------------------
# Artículos
# ---------------------------------------------------------------------------

class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sku: str | None = Field(default=None, max_length=80)
    brand: str | None = Field(default=None, max_length=120)
    manufacturer_part: str | None = Field(default=None, max_length=80)
    category: str = "other"
    unit: str = "unit"
    unit_cost: str = "0"
    supplier_name: str | None = Field(default=None, max_length=255)
    has_serial: bool = False
    min_quantity: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    active: bool = True


# ---------------------------------------------------------------------------
# Categorías (fase 3: las administra cada organización)
# ---------------------------------------------------------------------------

class CategoryIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)


class CategoryUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    active: bool | None = None


@router.get("/warehouse/categories")
async def list_categories(response: Response, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          pag: tuple[int, int] = Depends(pagination_params),
                          current_user: User = Depends(_catalog)) -> list[dict]:
    """Las categorías con cuántos artículos tiene cada una (para saber qué se
    afecta al renombrar o desactivar)."""
    from sqlalchemy import func, select

    conteo = dict((await db.execute(
        select(WarehouseItem.category, func.count()).where(WarehouseItem.organization_id == organization_id)
        .group_by(WarehouseItem.category))).all())
    filas = [cat_svc.category_out(c, item_count=conteo.get(c.code, 0))
             for c in await cat_svc.list_categories(db, organization_id)]
    return paginate_list(filas, limit=pag[0], offset=pag[1], response=response)


@router.post("/warehouse/categories", status_code=201)
async def create_category(payload: CategoryIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_manage)) -> dict:
    return cat_svc.category_out(await cat_svc.create_category(db, organization_id=organization_id,
                                                              user=current_user, label=payload.label))


@router.put("/warehouse/categories/{category_id}")
async def update_category(category_id: uuid.UUID, payload: CategoryUpdate, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_manage)) -> dict:
    return cat_svc.category_out(await cat_svc.update_category(
        db, organization_id=organization_id, user=current_user, category_id=category_id,
        label=payload.label, active=payload.active))


@router.get("/warehouse/items")
async def list_items(response: Response, q: str | None = None, category: str | None = None, active: bool | None = None,
                     db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                     pag: tuple[int, int] = Depends(pagination_params),
                     current_user: User = Depends(_catalog)) -> list[dict]:
    items = await paginate(db, wh.items_stmt(organization_id, q=q, category=category, active=active),
                           limit=pag[0], offset=pag[1], response=response)
    totales = await wh.totals_by_item(db, organization_id, [i.id for i in items])
    etiquetas = await cat_svc.category_labels(db, organization_id)
    return await _articulos_para(db, organization_id, current_user,
                                 [wh.item_out(i, totales.get(i.id), etiquetas) for i in items])


@router.get("/warehouse/items/{item_id}")
async def get_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                   organization_id: uuid.UUID = Depends(get_organization_id),
                   current_user: User = Depends(_catalog)) -> dict:
    item = await wh.get_item(db, organization_id, item_id)
    totales = await wh.totals_by_item(db, organization_id, [item.id])
    return (await _articulos_para(db, organization_id, current_user, [wh.item_out(item, totales.get(item.id), await cat_svc.category_labels(db, organization_id))]))[0]


@router.post("/warehouse/items", status_code=201)
async def create_item(payload: ItemIn, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_manage)) -> dict:
    item = await wh.save_item(db, organization_id=organization_id, user=current_user, data=payload.model_dump())
    return wh.item_out(item, labels=await cat_svc.category_labels(db, organization_id))


@router.put("/warehouse/items/{item_id}")
async def update_item(item_id: uuid.UUID, payload: ItemIn, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_manage)) -> dict:
    item = await wh.save_item(db, organization_id=organization_id, user=current_user, data=payload.model_dump(),
                              item_id=item_id)
    totales = await wh.totals_by_item(db, organization_id, [item.id])
    return wh.item_out(item, totales.get(item.id), await cat_svc.category_labels(db, organization_id))


# ---------------------------------------------------------------------------
# Ubicaciones (bodega y camionetas)
# ---------------------------------------------------------------------------

class LocationIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = "truck"
    technician_user_id: uuid.UUID | None = None
    active: bool = True


@router.get("/warehouse/locations")
async def list_locations(response: Response, active: bool | None = None, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         pag: tuple[int, int] = Depends(pagination_params),
                         current_user: User = Depends(_catalog)) -> list[dict]:
    items = await paginate(db, wh.locations_stmt(organization_id, active=active), limit=pag[0], offset=pag[1],
                           response=response)
    return [wh.location_out(l) for l in items]


@router.post("/warehouse/locations", status_code=201)
async def create_location(payload: LocationIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_manage)) -> dict:
    loc = await wh.save_location(db, organization_id=organization_id, user=current_user, data=payload.model_dump())
    return wh.location_out(loc)


@router.put("/warehouse/locations/{location_id}")
async def update_location(location_id: uuid.UUID, payload: LocationIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_manage)) -> dict:
    loc = await wh.save_location(db, organization_id=organization_id, user=current_user,
                                 data=payload.model_dump(), location_id=location_id)
    return wh.location_out(loc)


# ---------------------------------------------------------------------------
# Existencias
# ---------------------------------------------------------------------------

@router.get("/warehouse/stock")
async def list_stock(response: Response, q: str | None = None, category: str | None = None, low_only: bool = False,
                     db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                     pag: tuple[int, int] = Depends(pagination_params),
                     current_user: User = Depends(_read)) -> list[dict]:
    items = await paginate(db, wh.stock_stmt(organization_id, q=q, category=category, low_only=low_only),
                           limit=pag[0], offset=pag[1], response=response)
    totales = await wh.totals_by_item(db, organization_id, [i.id for i in items])
    etiquetas = await cat_svc.category_labels(db, organization_id)
    return [wh.item_out(i, totales.get(i.id), etiquetas) for i in items]


@router.get("/warehouse/stock/summary")
async def stock_summary(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_read)) -> dict:
    return {"low_count": await wh.low_stock_count(db, organization_id)}


# ---------------------------------------------------------------------------
# Movimientos
# ---------------------------------------------------------------------------

class MovementIn(BaseModel):
    item_id: uuid.UUID
    location_id: uuid.UUID | None = None
    to_location_id: uuid.UUID | None = None
    movement_type: str
    quantity: str
    unit_cost: str | None = None
    reference: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    project_id: uuid.UUID | None = None
    movement_date: date | None = None


async def _movement_out(db, organization_id, movimientos: list[WarehouseMovement]) -> list[dict]:
    if not movimientos:
        return []
    from sqlalchemy import select

    items = {i.id: i for i in (await db.execute(select(WarehouseItem).where(
        WarehouseItem.id.in_({m.item_id for m in movimientos})))).scalars().all()}
    lugares = {l.id: l.name for l in (await db.execute(select(WarehouseLocation).where(
        WarehouseLocation.id.in_({m.location_id for m in movimientos})))).scalars().all()}
    return [wh.movement_out(m, item_name=items[m.item_id].name if m.item_id in items else None,
                            unit_label=ITEM_UNITS.get(items[m.item_id].unit) if m.item_id in items else None,
                            location_name=lugares.get(m.location_id)) for m in movimientos]


@router.get("/warehouse/movements")
async def list_movements(response: Response, item_id: uuid.UUID | None = None, location_id: uuid.UUID | None = None,
                         movement_type: str | None = None, project_id: uuid.UUID | None = None,
                         date_from: date | None = None, date_to: date | None = None,
                         db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         pag: tuple[int, int] = Depends(pagination_params),
                         current_user: User = Depends(_read)) -> list[dict]:
    stmt = wh.movements_stmt(organization_id, item_id=item_id, location_id=location_id,
                             movement_type=movement_type, project_id=project_id, date_from=date_from,
                             date_to=date_to)
    items = await paginate(db, stmt, limit=pag[0], offset=pag[1], response=response)
    return await _movement_out(db, organization_id, items)


@router.post("/warehouse/movements", status_code=201)
async def create_movement(payload: MovementIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_manage)) -> dict:
    if payload.movement_type == "salida":
        # Una salida a mano saltaría la autorización del punto 1: esa sale por
        # una orden de salida, no por aquí.
        raise InvalidInputError("Las salidas se hacen con una orden autorizada, no a mano.",
                                code="movement_type_not_manual")
    item = await wh.get_item(db, organization_id, payload.item_id)
    location_id = payload.location_id or (await wh.default_location(db, organization_id)).id
    movimiento = await wh.record_movement(
        db, organization_id=organization_id, user=current_user, item_id=item.id, location_id=location_id,
        movement_type=payload.movement_type, quantity=payload.quantity,
        unit_cost=payload.unit_cost if payload.unit_cost is not None else item.unit_cost,
        reference=payload.reference, note=payload.note, project_id=payload.project_id,
        to_location_id=payload.to_location_id, movement_date=payload.movement_date)
    return (await _movement_out(db, organization_id, [movimiento]))[0]


# ---------------------------------------------------------------------------
# Carga del catálogo (fin de semana del conteo inicial)
# ---------------------------------------------------------------------------

class ImportRowsIn(BaseModel):
    rows: list[dict] = Field(min_length=1, max_length=2000)
    replace_stock: bool = False
    filename: str | None = None


@router.post("/warehouse/import")
async def import_catalog(file: UploadFile = File(...), replace_stock: bool = False,
                         db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)) -> dict:
    """Sube el Excel del cliente (hoja «Catálogo») y carga artículos y existencias."""
    contenido = await read_limited(file, MAX_CATALOG_BYTES)
    try:
        hojas = xlsx.read_sheets(contenido)
    except xlsx.NotAnXlsxError as exc:
        raise InvalidInputError(str(exc), code="invalid_workbook") from None
    if not hojas:
        raise InvalidInputError("El Excel no tiene hojas legibles.", code="empty_workbook")
    nombre = next((n for n in hojas if n.strip().casefold().startswith(("cat", "catalog"))), list(hojas)[0])
    filas = wh.rows_from_catalog_sheet(hojas[nombre])
    if not filas:
        raise InvalidInputError("No encontré filas por cargar en la hoja del catálogo.", code="empty_catalog")
    resultado = await wh.import_catalog(db, organization_id=organization_id, user=current_user, rows=filas,
                                       filename=file.filename, replace_stock=replace_stock)
    return {**resultado, "sheet": nombre, "rows_read": len(filas)}


@router.post("/warehouse/import/rows")
async def import_catalog_rows(payload: ImportRowsIn, db: AsyncSession = Depends(get_db),
                              organization_id: uuid.UUID = Depends(get_organization_id),
                              current_user: User = Depends(_manage)) -> dict:
    """Lo mismo, con las filas ya leídas: sirve cuando el catálogo viene en CSV
    o pegado, y es lo que usan las pruebas."""
    return await wh.import_catalog(db, organization_id=organization_id, user=current_user, rows=payload.rows,
                                  filename=payload.filename, replace_stock=payload.replace_stock)


# ---------------------------------------------------------------------------
# Conteo físico (mensual, respuesta 8)
# ---------------------------------------------------------------------------

class CountLineIn(BaseModel):
    item_id: uuid.UUID
    counted_quantity: str


class CountIn(BaseModel):
    location_id: uuid.UUID | None = None
    counted_on: date | None = None
    note: str | None = Field(default=None, max_length=1000)
    lines: list[CountLineIn] = Field(min_length=1, max_length=2000)


@router.post("/warehouse/counts")
async def create_count(payload: CountIn, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_count)) -> dict:
    location_id = payload.location_id or (await wh.default_location(db, organization_id)).id
    return await wh.register_count(db, organization_id=organization_id, user=current_user, location_id=location_id,
                                   lines=[l.model_dump() for l in payload.lines], note=payload.note,
                                   counted_on=payload.counted_on)


# ---------------------------------------------------------------------------
# Órdenes de salida (punto 1 del cuestionario)
# ---------------------------------------------------------------------------

class ReleaseLineIn(BaseModel):
    item_id: uuid.UUID
    quantity: str
    spec_label: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=1000)
    origin: str = "manual"
    section: str | None = Field(default=None, max_length=120)
    is_required: bool = False


class OmissionIn(BaseModel):
    """Un obligatorio de la lista que no se lleva, con el motivo."""
    item_id: uuid.UUID
    spec_label: str | None = Field(default=None, max_length=60)
    reason: str = Field(min_length=1, max_length=500)


class ReleaseIn(BaseModel):
    project_id: uuid.UUID | None = None
    technician_user_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    needed_on: date | None = None
    note: str | None = Field(default=None, max_length=2000)
    lines: list[ReleaseLineIn] = Field(min_length=1, max_length=200)
    omissions: list[OmissionIn] = Field(default_factory=list, max_length=200)


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class DeliverLineIn(BaseModel):
    line_id: uuid.UUID
    quantity: str


class DeliverIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
    # Lo que Bodega confirma que sale de cada renglón; sin esto, lo pedido.
    lines: list[DeliverLineIn] | None = Field(default=None, max_length=200)


class LoadIn(BaseModel):
    loaded: bool = True


@router.get("/warehouse/releases/pending")
async def list_pending_releases(response: Response, db: AsyncSession = Depends(get_db),
                                organization_id: uuid.UUID = Depends(get_organization_id),
                                pag: tuple[int, int] = Depends(pagination_params),
                                current_user: User = Depends(_approve)) -> list[dict]:
    """La bandeja «Salidas por autorizar»."""
    orders = await paginate(db, rel.releases_stmt(organization_id, pending_only=True),
                            limit=pag[0], offset=pag[1], response=response)
    return await rel.orders_out(db, organization_id, orders)


@router.get("/warehouse/releases")
async def list_releases(response: Response, status: str | None = None, project_id: uuid.UUID | None = None,
                        q: str | None = None, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        pag: tuple[int, int] = Depends(pagination_params),
                        current_user: User = Depends(_release_read)) -> list[dict]:
    stmt = rel.releases_stmt(organization_id, status=status, project_id=project_id, q=q,
                             own_user_id=current_user.id if _solo_propias(current_user) else None)
    orders = await paginate(db, stmt, limit=pag[0], offset=pag[1], response=response)
    return _sin_costos(await rel.orders_out(db, organization_id, orders), current_user)


@router.get("/warehouse/releases/{release_id}")
async def get_release(release_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_release_read)) -> dict:
    order = await rel.get_order(db, organization_id, release_id)
    _check_release_access(order, current_user)
    return _sin_costos((await rel.orders_out(db, organization_id, [order]))[0], current_user)


@router.post("/warehouse/releases", status_code=201)
async def create_release(payload: ReleaseIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_request)) -> dict:
    order = await rel.create_order(db, organization_id=organization_id, user=current_user,
                                   data=payload.model_dump())
    return _sin_costos((await rel.orders_out(db, organization_id, [order]))[0], current_user)


@router.put("/warehouse/releases/{release_id}")
async def update_release(release_id: uuid.UUID, payload: ReleaseIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_request)) -> dict:
    order = await rel.update_order(db, organization_id=organization_id, user=current_user, order_id=release_id,
                                   data=payload.model_dump())
    return _sin_costos((await rel.orders_out(db, organization_id, [order]))[0], current_user)


@router.post("/warehouse/releases/{release_id}/submit")
async def submit_release(release_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_request)) -> dict:
    order = await rel.submit_order(db, organization_id=organization_id, user=current_user, order_id=release_id)
    return _sin_costos((await rel.orders_out(db, organization_id, [order]))[0], current_user)


@router.post("/warehouse/releases/{release_id}/approve")
async def approve_release(release_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_approve)) -> dict:
    order = await rel.authorize_order(db, organization_id=organization_id, user=current_user, order_id=release_id)
    return (await rel.orders_out(db, organization_id, [order]))[0]


@router.post("/warehouse/releases/{release_id}/reject")
async def reject_release(release_id: uuid.UUID, payload: RejectIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_approve)) -> dict:
    order = await rel.reject_order(db, organization_id=organization_id, user=current_user, order_id=release_id,
                                   reason=payload.reason)
    return (await rel.orders_out(db, organization_id, [order]))[0]


@router.post("/warehouse/releases/{release_id}/deliver")
async def deliver_release(release_id: uuid.UUID, payload: DeliverIn | None = None,
                          db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_deliver)) -> dict:
    """Entrega el material y baja el saldo. Devuelve lo que no se pudo entregar."""
    cantidades = {l.line_id: l.quantity for l in payload.lines} if payload and payload.lines else None
    resultado = await rel.deliver_order(db, organization_id=organization_id, user=current_user,
                                        order_id=release_id, note=payload.note if payload else None,
                                        quantities=cantidades)
    order = resultado["order"]
    return {**(await rel.orders_out(db, organization_id, [order]))[0], "faltantes": resultado["faltantes"]}


@router.post("/warehouse/releases/{release_id}/lines/{line_id}/load")
async def load_release_line(release_id: uuid.UUID, line_id: uuid.UUID, payload: LoadIn,
                            db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            current_user: User = Depends(_request)) -> dict:
    """«Lo llevo»: el técnico marca el renglón al cargar la camioneta."""
    order = await rel.mark_loaded(db, organization_id=organization_id, user=current_user, order_id=release_id,
                                  line_id=line_id, loaded=payload.loaded)
    return (await rel.orders_out(db, organization_id, [order]))[0]


# ---------------------------------------------------------------------------
# Listas predefinidas por tipo de trabajo (punto 2 del cuestionario)
# ---------------------------------------------------------------------------

class KitItemIn(BaseModel):
    item_id: uuid.UUID
    quantity: str = "1"
    spec_label: str | None = Field(default=None, max_length=60)
    section: str | None = Field(default=None, max_length=120)
    is_required: bool = True
    notes: str | None = Field(default=None, max_length=1000)


class KitIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    project_type: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    active: bool = True
    items: list[KitItemIn] = Field(min_length=1, max_length=300)


class ApplyKitIn(BaseModel):
    release_id: uuid.UUID


@router.get("/warehouse/kits")
async def list_kits(response: Response, q: str | None = None, project_type: str | None = None,
                    active: bool | None = None, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    pag: tuple[int, int] = Depends(pagination_params),
                    current_user: User = Depends(_catalog)) -> list[dict]:
    kits = await paginate(db, kit_svc.kits_stmt(organization_id, q=q, project_type=project_type, active=active),
                          limit=pag[0], offset=pag[1], response=response)
    return _sin_costos(await kit_svc.kits_out(db, organization_id, kits), current_user)


@router.get("/warehouse/kits/{kit_id}")
async def get_kit(kit_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                  organization_id: uuid.UUID = Depends(get_organization_id),
                  current_user: User = Depends(_catalog)) -> dict:
    kit = await kit_svc.get_kit(db, organization_id, kit_id)
    return _sin_costos((await kit_svc.kits_out(db, organization_id, [kit]))[0], current_user)


@router.post("/warehouse/kits", status_code=201)
async def create_kit(payload: KitIn, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     current_user: User = Depends(_kits)) -> dict:
    kit = await kit_svc.save_kit(db, organization_id=organization_id, user=current_user,
                                 data=payload.model_dump())
    return (await kit_svc.kits_out(db, organization_id, [kit]))[0]


@router.put("/warehouse/kits/{kit_id}")
async def update_kit(kit_id: uuid.UUID, payload: KitIn, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     current_user: User = Depends(_kits)) -> dict:
    """Reemplaza la lista completa. No toca las órdenes que ya la usaron: cada una
    tiene su copia."""
    kit = await kit_svc.save_kit(db, organization_id=organization_id, user=current_user,
                                 data=payload.model_dump(), kit_id=kit_id)
    return (await kit_svc.kits_out(db, organization_id, [kit]))[0]


@router.delete("/warehouse/kits/{kit_id}", status_code=204)
async def delete_kit(kit_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     current_user: User = Depends(_kits)) -> None:
    await kit_svc.delete_kit(db, organization_id=organization_id, user=current_user, kit_id=kit_id)


@router.post("/warehouse/kits/{kit_id}/apply")
async def apply_kit(kit_id: uuid.UUID, payload: ApplyKitIn, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_request)) -> dict:
    """Copia la lista a un borrador de orden de salida."""
    resultado = await kit_svc.apply_to_release(db, organization_id=organization_id, user=current_user,
                                               kit_id=kit_id, release_id=payload.release_id)
    order = resultado["order"]
    return _sin_costos({**(await rel.orders_out(db, organization_id, [order]))[0],
                        "kit_name": resultado["kit"].name, "agregadas": resultado["agregadas"],
                        "omitidas": resultado["omitidas"]}, current_user)


# ---------------------------------------------------------------------------
# Presupuesto del proyecto (punto 3 del cuestionario)
# ---------------------------------------------------------------------------

class BudgetLineIn(BaseModel):
    category: str = "materials"
    item_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=255)
    quantity: str = "1"
    unit: str | None = Field(default=None, max_length=20)
    unit_cost: str | None = None
    notes: str | None = Field(default=None, max_length=1000)


def _budget_data(payload: "BudgetIn") -> dict:
    """El PUT reemplaza el borrador, pero el precio esperado solo cambia si viene:
    omitirlo lo deja igual; un `null` explícito lo borra."""
    data = payload.model_dump()
    if "expected_revenue" not in payload.model_fields_set:
        data.pop("expected_revenue")
    return data


class BudgetIn(BaseModel):
    project_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    expected_revenue: str | None = None
    lines: list[BudgetLineIn] = Field(default_factory=list, max_length=300)


class ApplyBudgetKitIn(BaseModel):
    kit_id: uuid.UUID


@router.get("/warehouse/budgets")
async def list_budgets(response: Response, project_id: uuid.UUID | None = None, status: str | None = None,
                       db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       pag: tuple[int, int] = Depends(pagination_params),
                       current_user: User = Depends(_budget_read)) -> list[dict]:
    budgets = await paginate(db, budget_svc.budgets_stmt(organization_id, project_id=project_id, status=status),
                             limit=pag[0], offset=pag[1], response=response)
    return await budget_svc.budgets_out(db, organization_id, budgets)


@router.get("/warehouse/budgets/{budget_id}")
async def get_budget(budget_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     current_user: User = Depends(_budget_read)) -> dict:
    budget = await budget_svc.get_budget(db, organization_id, budget_id)
    return (await budget_svc.budgets_out(db, organization_id, [budget]))[0]


@router.post("/warehouse/budgets", status_code=201)
async def create_budget(payload: BudgetIn, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_budget_manage)) -> dict:
    budget = await budget_svc.save_budget(db, organization_id=organization_id, user=current_user,
                                          data=_budget_data(payload))
    return (await budget_svc.budgets_out(db, organization_id, [budget]))[0]


@router.put("/warehouse/budgets/{budget_id}")
async def update_budget(budget_id: uuid.UUID, payload: BudgetIn, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_budget_manage)) -> dict:
    """Reemplaza el borrador completo. El proyecto no cambia."""
    budget = await budget_svc.save_budget(db, organization_id=organization_id, user=current_user,
                                          data=_budget_data(payload), budget_id=budget_id)
    return (await budget_svc.budgets_out(db, organization_id, [budget]))[0]


@router.delete("/warehouse/budgets/{budget_id}", status_code=204)
async def delete_budget(budget_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_budget_manage)) -> None:
    await budget_svc.delete_budget(db, organization_id=organization_id, user=current_user, budget_id=budget_id)


@router.post("/warehouse/budgets/{budget_id}/approve")
async def approve_budget(budget_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_budget_approve)) -> dict:
    """Aprueba el presupuesto; el anterior de la obra queda `reemplazado`."""
    budget = await budget_svc.approve_budget(db, organization_id=organization_id, user=current_user,
                                             budget_id=budget_id)
    return (await budget_svc.budgets_out(db, organization_id, [budget]))[0]


@router.post("/warehouse/budgets/{budget_id}/apply-kit")
async def apply_kit_to_budget(budget_id: uuid.UUID, payload: ApplyBudgetKitIn, db: AsyncSession = Depends(get_db),
                              organization_id: uuid.UUID = Depends(get_organization_id),
                              current_user: User = Depends(_budget_manage)) -> dict:
    """Copia una lista predefinida al borrador del presupuesto."""
    resultado = await budget_svc.apply_kit(db, organization_id=organization_id, user=current_user,
                                           budget_id=budget_id, kit_id=payload.kit_id)
    budget = resultado["budget"]
    return {**(await budget_svc.budgets_out(db, organization_id, [budget]))[0],
            "kit_name": resultado["kit"].name, "agregadas": resultado["agregadas"],
            "omitidas": resultado["omitidas"]}


@router.get("/warehouse/projects/{project_id}/budget")
async def get_project_budget(project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                             organization_id: uuid.UUID = Depends(get_organization_id),
                             current_user: User = Depends(_budget_read)) -> dict | None:
    """El presupuesto vigente de la obra (el aprobado, o el borrador más
    reciente). `null` cuando la obra todavía no tiene presupuesto."""
    project = await budget_svc.get_project(db, organization_id, project_id)
    budget = await budget_svc.current_budget(db, organization_id, project.id)
    if budget is None:
        return None
    return (await budget_svc.budgets_out(db, organization_id, [budget]))[0]


@router.get("/warehouse/projects/{project_id}/budget-vs-actual")
async def get_budget_vs_actual(project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                               organization_id: uuid.UUID = Depends(get_organization_id),
                               current_user: User = Depends(_budget_read)) -> dict:
    """El estimado del proyecto contra lo que de verdad costó, por categoría."""
    project = await budget_svc.get_project(db, organization_id, project_id)
    return await costing_svc.budget_vs_actual(db, organization_id=organization_id, project_id=project.id)


@router.get("/warehouse/purchasing")
async def list_purchasing(db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_budget_read)) -> dict:
    """Compras sugeridas: lo presupuestado por venir menos lo que hay en bodega."""
    return await costing_svc.purchasing_report(db, organization_id)


# ---------------------------------------------------------------------------
# Diario de obra (punto 4 del cuestionario)
# ---------------------------------------------------------------------------

class DayLogMaterialIn(BaseModel):
    id: uuid.UUID | None = None
    item_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=255)
    quantity: str = "1"
    unit: str | None = Field(default=None, max_length=20)
    # De dónde salió: la camioneta. Sin ubicación la línea no mueve existencia.
    location_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class DayLogIn(BaseModel):
    log_date: date
    technician_user_id: uuid.UUID | None = None
    crew: str | None = Field(default=None, max_length=255)
    hours: str | None = None
    work_done: str | None = Field(default=None, max_length=4000)
    progress_note: str | None = Field(default=None, max_length=255)
    missing_materials: str | None = Field(default=None, max_length=4000)
    next_day_plan: str | None = Field(default=None, max_length=4000)
    incidents: str | None = Field(default=None, max_length=4000)
    materials: list[DayLogMaterialIn] = Field(default_factory=list, max_length=100)


@router.get("/warehouse/projects/{project_id}/day-logs")
async def list_day_logs(project_id: uuid.UUID, response: Response,
                        date_from: date | None = None, date_to: date | None = None,
                        db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        pag: tuple[int, int] = Depends(pagination_params),
                        current_user: User = Depends(_daylog_read)) -> list[dict]:
    """El diario de la obra, del día más reciente al más viejo. Cada jornada
    trae su material y los gastos de ese día, que se leen de `expenses`."""
    project = await _visible_project(db, organization_id, current_user, project_id)
    logs = await paginate(db, daylog_svc.day_logs_stmt(organization_id, project_id=project.id,
                                                       date_from=date_from, date_to=date_to),
                          limit=pag[0], offset=pag[1], response=response)
    return await daylog_svc.day_logs_out(db, organization_id, logs)


@router.post("/warehouse/projects/{project_id}/day-logs", status_code=201)
async def create_day_log(project_id: uuid.UUID, payload: DayLogIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_daylog_manage)) -> dict:
    """Registra la jornada del día. El material que sale de una camioneta
    descuenta la existencia y queda como costo de la obra."""
    await _visible_project(db, organization_id, current_user, project_id)
    log = await daylog_svc.save_day_log(db, organization_id=organization_id, user=current_user,
                                        project_id=project_id, data=payload.model_dump())
    return (await daylog_svc.day_logs_out(db, organization_id, [log]))[0]


@router.put("/warehouse/projects/{project_id}/day-logs/{log_id}")
async def update_day_log(project_id: uuid.UUID, log_id: uuid.UUID, payload: DayLogIn,
                         db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_daylog_manage)) -> dict:
    """Corrige la jornada. Lo que ya descontó la camioneta no se edita: para eso
    se registra la devolución a bodega."""
    await _visible_project(db, organization_id, current_user, project_id)
    log = await daylog_svc.save_day_log(db, organization_id=organization_id, user=current_user,
                                        project_id=project_id, data=payload.model_dump(), log_id=log_id)
    return (await daylog_svc.day_logs_out(db, organization_id, [log]))[0]
