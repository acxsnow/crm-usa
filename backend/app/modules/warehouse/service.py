"""Existencias de bodega: artículos, ubicaciones, movimientos y conteos.

Todo lo que mueve un saldo pasa por `record_movement`. Nadie escribe
`warehouse_stock` a mano: así el libro de movimientos y el saldo no se pueden
desincronizar, y la regla «el mismo movimiento no se aplica dos veces» vive en
un solo lugar (la clave `source_key`).
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import ZERO, to_money
from app.modules.warehouse.catalogs import (
    DEFAULT_WAREHOUSE_NAME,
    ITEM_CATEGORIES,
    ITEM_UNITS,
    LOCATION_KINDS,
    MOVEMENT_SIGN,
    MOVEMENT_TYPES,
    MovementType,
)
from app.modules.warehouse.models import (
    WarehouseItem,
    WarehouseLocation,
    WarehouseMovement,
    WarehouseStock,
)
from app.shared import events as domain_events
from app.shared.decimals import to_quantity
from app.shared.audit import record_audit_event
from app.shared.errors import InvalidInputError, NotFoundError

Q2 = Decimal("0.01")


def _q(value) -> Decimal:
    """Cantidad con dos decimales, como la columna."""
    return to_quantity(value)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Ubicaciones
# ---------------------------------------------------------------------------

async def default_location(db: AsyncSession, organization_id: uuid.UUID) -> WarehouseLocation:
    """La bodega. Se crea la primera vez que hace falta (respuesta 1: hay una)."""
    fila = (await db.execute(select(WarehouseLocation).where(
        WarehouseLocation.organization_id == organization_id,
        WarehouseLocation.kind == "warehouse",
    ).order_by(WarehouseLocation.created_at))).scalars().first()
    if fila is None:
        fila = WarehouseLocation(organization_id=organization_id, name=DEFAULT_WAREHOUSE_NAME, kind="warehouse")
        db.add(fila)
        await db.flush()
    return fila


async def get_location(db: AsyncSession, organization_id, location_id) -> WarehouseLocation:
    fila = await db.get(WarehouseLocation, location_id)
    if fila is None or fila.organization_id != organization_id:
        raise NotFoundError("La ubicación no existe.", code="warehouse_location_not_found")
    return fila


def locations_stmt(organization_id, *, active: bool | None = None):
    stmt = select(WarehouseLocation).where(WarehouseLocation.organization_id == organization_id)
    if active is not None:
        stmt = stmt.where(WarehouseLocation.active.is_(active))
    return stmt.order_by(WarehouseLocation.kind, WarehouseLocation.name)


async def save_location(db: AsyncSession, *, organization_id, user, data: dict, location_id=None) -> WarehouseLocation:
    if data["kind"] not in ("warehouse", "truck"):
        raise InvalidInputError("El tipo de ubicación no existe.", code="invalid_location_kind")
    fila = await get_location(db, organization_id, location_id) if location_id else WarehouseLocation(
        organization_id=organization_id)
    if location_id is None:
        db.add(fila)
    fila.name, fila.kind = data["name"].strip(), data["kind"]
    fila.technician_user_id = data.get("technician_user_id")
    if "active" in data:
        fila.active = bool(data["active"])
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.location_saved", entity_type="warehouse_location",
                             entity_id=str(fila.id), after_data={"name": fila.name, "kind": fila.kind})
    await db.commit()
    await db.refresh(fila)
    return fila


# ---------------------------------------------------------------------------
# Artículos
# ---------------------------------------------------------------------------

async def get_item(db: AsyncSession, organization_id, item_id) -> WarehouseItem:
    item = await db.get(WarehouseItem, item_id)
    if item is None or item.organization_id != organization_id:
        raise NotFoundError("El artículo no existe.", code="warehouse_item_not_found")
    return item


def _matches(q: str):
    """Lo que busca el buscador: nombre, código de AC Pro, número del fabricante,
    marca o proveedor (el técnico busca con lo que tenga a mano)."""
    patron = f"%{q.strip()}%"
    return or_(WarehouseItem.name.ilike(patron), WarehouseItem.sku.ilike(patron),
               WarehouseItem.manufacturer_part.ilike(patron), WarehouseItem.brand.ilike(patron),
               WarehouseItem.supplier_name.ilike(patron))


def items_stmt(organization_id, *, q: str | None = None, category: str | None = None, active: bool | None = None):
    stmt = select(WarehouseItem).where(WarehouseItem.organization_id == organization_id)
    if q:
        stmt = stmt.where(_matches(q))
    if category:
        stmt = stmt.where(WarehouseItem.category == category)
    if active is not None:
        stmt = stmt.where(WarehouseItem.active.is_(active))
    return stmt.order_by(WarehouseItem.name)


def stock_stmt(organization_id, *, q: str | None = None, category: str | None = None, low_only: bool = False):
    """Existencias: los artículos activos con lo que hay, los que están en el
    mínimo primero. El filtro `low_only` va en la consulta y no en Python para
    que la paginación siga contando lo que de verdad se está mostrando.

    La subconsulta del total se arma una sola vez: si se llama dos veces,
    SQLAlchemy le da dos alias distintos y el `ON` del join apunta a uno que no
    está en el `FROM`."""
    sub = _stock_total_subquery(organization_id)
    total = func.coalesce(sub.c.total, 0)
    stmt = (select(WarehouseItem)
            .outerjoin(sub, sub.c.item_id == WarehouseItem.id)
            .where(WarehouseItem.organization_id == organization_id, WarehouseItem.active.is_(True)))
    if q:
        stmt = stmt.where(_matches(q))
    if category:
        stmt = stmt.where(WarehouseItem.category == category)
    below = and_(WarehouseItem.min_quantity.is_not(None), total <= WarehouseItem.min_quantity)
    if low_only:
        stmt = stmt.where(below)
    return stmt.order_by(desc(below), WarehouseItem.name)


def _stock_total_subquery(organization_id):
    return (select(WarehouseStock.item_id.label("item_id"),
                   func.sum(WarehouseStock.quantity).label("total"))
            .where(WarehouseStock.organization_id == organization_id)
            .group_by(WarehouseStock.item_id).subquery())


async def save_item(db: AsyncSession, *, organization_id, user, data: dict, item_id=None) -> WarehouseItem:
    from app.modules.warehouse.categories import check_category

    if data["unit"] not in ITEM_UNITS:
        raise InvalidInputError("La unidad no existe.", code="invalid_item_unit")
    item = await get_item(db, organization_id, item_id) if item_id else None
    await check_category(db, organization_id, data["category"], current=item.category if item else None)
    if item is None:
        item = WarehouseItem(organization_id=organization_id)
        db.add(item)
    item.name = data["name"].strip()
    item.sku = (data.get("sku") or "").strip() or None
    item.brand = (data.get("brand") or "").strip() or None
    item.manufacturer_part = (data.get("manufacturer_part") or "").strip() or None
    item.category, item.unit = data["category"], data["unit"]
    item.unit_cost = to_money(data.get("unit_cost") or 0)
    item.supplier_name = (data.get("supplier_name") or "").strip() or None
    item.has_serial = bool(data.get("has_serial"))
    item.min_quantity = None if data.get("min_quantity") in (None, "") else _q(data["min_quantity"])
    item.notes = (data.get("notes") or "").strip() or None
    if "active" in data:
        item.active = bool(data["active"])
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.item_saved", entity_type="warehouse_item", entity_id=str(item.id),
                             after_data={"name": item.name, "sku": item.sku, "category": item.category})
    await db.commit()
    await db.refresh(item)
    return item


async def _find_item(db, organization_id, *, sku: str | None, name: str) -> WarehouseItem | None:
    """El mismo artículo de una carga anterior. Por referencia (SKU) cuando la
    hay, que es lo único que no cambia entre un Excel y el siguiente.

    Por nombre solo se busca un artículo **sin código**: AC Pro tiene productos
    con el mismo nombre y distinto código (la cinta de espuma de Armacell 36140 y
    la de Diversitech 3088), y si el nombre bastara el segundo pisaría el código
    del primero y se perdería (ataque del 24 oct, hallazgo A2). Así un catálogo
    cargado antes sin códigos los recibe en la carga siguiente.
    """
    if sku:
        fila = (await db.execute(select(WarehouseItem).where(
            WarehouseItem.organization_id == organization_id, WarehouseItem.sku == sku))).scalar_one_or_none()
        if fila is not None:
            return fila
    mismo_nombre = select(WarehouseItem).where(WarehouseItem.organization_id == organization_id,
                                               func.lower(WarehouseItem.name) == name.lower())
    if sku:
        mismo_nombre = mismo_nombre.where(or_(WarehouseItem.sku.is_(None), WarehouseItem.sku == ""))
    return (await db.execute(mismo_nombre.order_by(WarehouseItem.created_at).limit(1))).scalars().first()


# ---------------------------------------------------------------------------
# Movimientos y saldo
# ---------------------------------------------------------------------------

async def stock_quantity(db: AsyncSession, organization_id, *, item_id, location_id) -> Decimal:
    fila = (await db.execute(select(WarehouseStock).where(
        WarehouseStock.organization_id == organization_id, WarehouseStock.item_id == item_id,
        WarehouseStock.location_id == location_id))).scalar_one_or_none()
    return _q(fila.quantity) if fila is not None else ZERO


async def _apply_to_stock(db: AsyncSession, organization_id, *, item_id, location_id, delta: Decimal) -> WarehouseStock:
    fila = (await db.execute(select(WarehouseStock).where(
        WarehouseStock.organization_id == organization_id, WarehouseStock.item_id == item_id,
        WarehouseStock.location_id == location_id))).scalar_one_or_none()
    if fila is None:
        fila = WarehouseStock(organization_id=organization_id, item_id=item_id, location_id=location_id,
                              quantity=ZERO)
        db.add(fila)
    fila.quantity = _q(fila.quantity) + delta
    await db.flush()
    return fila


async def record_movement(
    db: AsyncSession,
    *,
    organization_id,
    user,
    item_id,
    location_id,
    movement_type: str,
    quantity,
    unit_cost=None,
    reference: str | None = None,
    note: str | None = None,
    project_id=None,
    to_location_id=None,
    movement_date: date | None = None,
    source_key: str | None = None,
    commit: bool = True,
) -> WarehouseMovement:
    """Registra un movimiento y mueve el saldo en la misma transacción.

    `quantity` es la magnitud para entrada, salida, devolución y traslado (el
    signo lo pone el tipo), y el delta con signo para un ajuste.

    Con `source_key` el movimiento es idempotente: repetir la misma factura o el
    mismo conteo devuelve el movimiento ya hecho y no vuelve a tocar el saldo.
    """
    if movement_type not in MOVEMENT_TYPES:
        raise InvalidInputError("El tipo de movimiento no existe.", code="invalid_movement_type")
    if movement_type == MovementType.TRASLADO and to_location_id is None:
        raise InvalidInputError("Un traslado necesita la ubicación de destino.", code="transfer_destination_required")

    if source_key is not None:
        previo = (await db.execute(select(WarehouseMovement).where(
            WarehouseMovement.organization_id == organization_id,
            WarehouseMovement.source_key == source_key))).scalar_one_or_none()
        if previo is not None:
            return previo

    cantidad = _q(quantity)
    if movement_type == MovementType.AJUSTE:
        delta = cantidad
    else:
        if cantidad <= ZERO:
            raise InvalidInputError("La cantidad debe ser mayor que cero.", code="invalid_quantity")
        delta = cantidad * MOVEMENT_SIGN[movement_type]

    if movement_type == MovementType.SALIDA or movement_type == MovementType.TRASLADO:
        if delta == ZERO:
            raise InvalidInputError("La cantidad debe ser mayor que cero.", code="invalid_quantity")

    # Lo que había antes de mover: contra esto se detecta si el movimiento dejó
    # el artículo en su mínimo.
    total_antes = await _total_quantity(db, organization_id, item_id)

    movimiento = WarehouseMovement(
        organization_id=organization_id, item_id=item_id, location_id=location_id,
        to_location_id=to_location_id if movement_type == MovementType.TRASLADO else None,
        movement_type=movement_type, quantity=delta,
        unit_cost=None if unit_cost is None else to_money(unit_cost),
        movement_date=movement_date or await _today(db, organization_id),
        reference=(reference or "").strip() or None, note=(note or "").strip() or None,
        project_id=project_id, source_key=source_key, created_by_user_id=user.id if user else None,
        recorded_at=_now(),
    )
    db.add(movimiento)
    await db.flush()

    # Al trasladar, la cantidad sale de `location_id` y entra a la otra.
    await _apply_to_stock(db, organization_id, item_id=item_id, location_id=location_id, delta=delta)
    if movement_type == MovementType.TRASLADO:
        await _apply_to_stock(db, organization_id, item_id=item_id, location_id=to_location_id, delta=-delta)
    else:
        await _avisar_si_bajo_del_minimo(db, organization_id, item_id=item_id, total_antes=total_antes, delta=delta)

    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id if user else None,
                             action=f"warehouse.movement_{movement_type}", entity_type="warehouse_movement",
                             entity_id=str(movimiento.id),
                             after_data={"item_id": str(item_id), "quantity": str(delta)})
    if commit:
        await db.commit()
        await db.refresh(movimiento)
    return movimiento


async def _total_quantity(db: AsyncSession, organization_id, item_id) -> Decimal:
    """Lo que hay del artículo sumando todas las ubicaciones."""
    total = (await db.execute(select(func.sum(WarehouseStock.quantity)).where(
        WarehouseStock.organization_id == organization_id, WarehouseStock.item_id == item_id))).scalar()
    return _q(total or ZERO)


async def _avisar_si_bajo_del_minimo(db, organization_id, *, item_id, total_antes: Decimal, delta: Decimal) -> None:
    """Avisa cuando el movimiento dejó el artículo en su mínimo.

    Solo al cruzar el mínimo, no en cada salida que lo deja por debajo: si no,
    el aviso se repetiría con cada entrega de la temporada."""
    if delta >= ZERO:
        return
    item = await db.get(WarehouseItem, item_id)
    if item is None or item.min_quantity is None:
        return
    minimo, despues = _q(item.min_quantity), total_antes + delta
    if total_antes > minimo >= despues:
        domain_events.emit("warehouse.stock_low", {
            "organization_id": str(organization_id), "item_id": str(item_id), "item_name": item.name,
            "existencia": str(despues), "minimo": str(minimo)})


async def _today(db, organization_id) -> date:
    from app.modules.field_ops.clock import org_today

    return await org_today(db, organization_id)


def movements_stmt(organization_id, *, item_id=None, location_id=None, movement_type=None,
                   project_id=None, date_from=None, date_to=None):
    stmt = select(WarehouseMovement).where(WarehouseMovement.organization_id == organization_id)
    if item_id:
        stmt = stmt.where(WarehouseMovement.item_id == item_id)
    if location_id:
        stmt = stmt.where(WarehouseMovement.location_id == location_id)
    if movement_type:
        stmt = stmt.where(WarehouseMovement.movement_type == movement_type)
    if project_id:
        stmt = stmt.where(WarehouseMovement.project_id == project_id)
    if date_from:
        stmt = stmt.where(WarehouseMovement.movement_date >= date_from)
    if date_to:
        stmt = stmt.where(WarehouseMovement.movement_date <= date_to)
    return stmt.order_by(WarehouseMovement.movement_date.desc(), WarehouseMovement.created_at.desc())


# ---------------------------------------------------------------------------
# Carga inicial desde el Excel del cliente
# ---------------------------------------------------------------------------

# Columna de la hoja «Catálogo» (cuestionario del 19 de octubre) → campo del
# artículo. Se busca por el nombre de la columna y no por su posición, para que
# mover una columna en el Excel no cargue el proveedor como categoría.
CATALOG_COLUMNS: dict[str, tuple[str, ...]] = {
    "name": ("nombre del material", "nombre", "material"),
    "sku": ("referencia / sku", "referencia", "sku", "código ac pro", "codigo ac pro", "ac pro"),
    "manufacturer_part": ("número del fabricante", "numero del fabricante", "número de fabricante",
                          "numero de fabricante", "mfg #", "mfg"),
    "brand": ("marca",),
    "category": ("categoría", "categoria"),
    "unit": ("unidad",),
    "unit_cost": ("costo unitario", "costo"),
    "supplier_name": ("proveedor habitual", "proveedor"),
    "quantity": ("cantidad en bodega hoy", "cantidad en bodega", "cantidad hoy", "existencia"),
    "min_quantity": ("cantidad mínima", "cantidad minima", "mínimo", "minimo"),
    "notes": ("notas",),
    "has_serial": ("¿lleva serial?", "lleva serial", "serial"),
}

# La fila gris de ejemplo no se borra ni se cuenta (hoja «Cómo llenar»).
_SKIP_PREFIXES = ("ejemplo",)


def _texto(valor) -> str | None:
    """Una celda como texto. Los códigos de AC Pro son números («3496») y el
    Excel los guarda como número: sin esto llegaban como `Decimal('3496')` y la
    fila fallaba al limpiarle los espacios (o quedaba «3496.0»)."""
    if valor is None:
        return None
    if isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
        numero = Decimal(str(valor))
        return str(int(numero)) if numero == numero.to_integral_value() else str(numero)
    return str(valor).strip() or None


def _truthy(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    if valor is None:
        return False
    return str(valor).strip().casefold() in ("sí", "si", "s", "yes", "y", "true", "1", "x")


def _header_row(filas: list[list]) -> int | None:
    for i, fila in enumerate(filas[:15]):
        textos = {str(c).strip().casefold() for c in fila if c is not None}
        if any(t.startswith("nombre del material") or t == "nombre" for t in textos):
            return i
    return None


def _column_map(fila: list) -> dict[str, int]:
    """Campo del artículo → índice de columna, tolerando espacios y mayúsculas."""
    cabeceras = {i: str(c).strip().casefold() for i, c in enumerate(fila) if c is not None}
    mapa: dict[str, int] = {}
    for campo, alias in CATALOG_COLUMNS.items():
        for indice, texto in cabeceras.items():
            if campo in mapa:
                break
            if any(texto == a or texto.startswith(a) for a in alias):
                mapa[campo] = indice
    return mapa


def rows_from_catalog_sheet(filas: list[list]) -> list[dict]:
    """Filas de la hoja «Catálogo» como diccionarios listos para `import_catalog`."""
    cabecera = _header_row(filas)
    if cabecera is None:
        raise InvalidInputError("No encontré la hoja «Catálogo» con la columna «Nombre del material».",
                                code="catalog_sheet_not_found")
    mapa = _column_map(filas[cabecera])
    if "name" not in mapa:
        raise InvalidInputError("La hoja «Catálogo» no tiene la columna «Nombre del material».",
                                code="catalog_name_column_missing")

    def celda(fila: list, campo: str):
        indice = mapa.get(campo)
        return fila[indice] if indice is not None and indice < len(fila) else None

    filas_out: list[dict] = []
    for fila in filas[cabecera + 1:]:
        if not any(c is not None and str(c).strip() for c in fila):
            continue
        nombre = str(celda(fila, "name") or "").strip()
        if nombre.casefold().startswith(_SKIP_PREFIXES):
            continue
        filas_out.append({
            "name": nombre,
            "sku": _texto(celda(fila, "sku")),
            "manufacturer_part": _texto(celda(fila, "manufacturer_part")),
            "brand": _texto(celda(fila, "brand")),
            "category": _texto(celda(fila, "category")),
            "unit": _texto(celda(fila, "unit")),
            "unit_cost": celda(fila, "unit_cost"),
            "supplier_name": _texto(celda(fila, "supplier_name")),
            "quantity": celda(fila, "quantity"),
            "min_quantity": celda(fila, "min_quantity"),
            "notes": _texto(celda(fila, "notes")),
            "has_serial": _truthy(celda(fila, "has_serial")),
        })
    return filas_out

async def import_catalog(db: AsyncSession, *, organization_id, user, rows: list[dict], filename: str | None = None,
                         replace_stock: bool = False) -> dict:
    """Crea o actualiza los artículos del catálogo y registra el conteo inicial.

    Es la carga del fin de semana (D-BOD-1): la primera vez que aparece un
    artículo, su cantidad entra como movimiento `entrada` de «conteo inicial»,
    con clave por artículo, para que volver a subir el mismo archivo no sume la
    cantidad dos veces. Los artículos que ya existían solo se actualizan en sus
    datos descriptivos; su existencia se corrige con un conteo.

    Una fila mala no aborta la carga: se cuenta y se explica en `errores`.
    """
    from app.modules.warehouse.catalogs import ITEM_UNITS as UNITS
    from app.modules.warehouse.catalogs import code_of
    from app.modules.warehouse.categories import create_category, list_categories

    bodega = await default_location(db, organization_id)
    # Las categorías de la organización (siembra las iniciales si no tiene).
    # Una categoría que el Excel trae y no existe se crea: la hoja «Listas»
    # dejaba al cliente agregar las suyas.
    categorias = {c.code: c.label for c in await list_categories(db, organization_id)}
    nuevas: list[str] = []
    creados = actualizados = omitidos = 0
    iniciales = 0
    errores: list[dict] = []

    for numero, fila in enumerate(rows, start=1):
        nombre = (_texto(fila.get("name")) or "")
        if not nombre:
            omitidos += 1
            continue
        # Cada fila en su propio punto de guardado: una fila mala se deshace
        # sola y la carga sigue con la siguiente.
        try:
            async with db.begin_nested():
                categoria, ok_cat = code_of(_texto(fila.get("category")), categorias, "other")
                if not ok_cat:
                    nueva = await create_category(db, organization_id=organization_id, user=user,
                                                  label=_texto(fila.get("category")) or "", commit=False)
                    categorias[nueva.code] = nueva.label
                    nuevas.append(nueva.label)
                    categoria = nueva.code
                unidad, ok_uni = code_of(_texto(fila.get("unit")), UNITS, "unit")
                if not ok_uni:
                    errores.append({"fila": numero, "error": f"Unidad «{fila.get('unit')}» no reconocida; "
                                                            "se guardó como «unidades»."})

                sku = _texto(fila.get("sku"))
                marca = _texto(fila.get("brand"))
                fabricante = _texto(fila.get("manufacturer_part"))
                item = await _find_item(db, organization_id, sku=sku, name=nombre)
                cantidad = _q(fila.get("quantity") or 0)
                if item is None:
                    item = WarehouseItem(
                        organization_id=organization_id, name=nombre, sku=sku, category=categoria, unit=unidad,
                        brand=marca, manufacturer_part=fabricante,
                        unit_cost=to_money(fila.get("unit_cost") or 0),
                        supplier_name=(fila.get("supplier_name") or "").strip() or None,
                        has_serial=bool(fila.get("has_serial")),
                        min_quantity=None if fila.get("min_quantity") in (None, "") else _q(fila["min_quantity"]),
                        notes=(fila.get("notes") or "").strip() or None,
                    )
                    db.add(item)
                    await db.flush()
                    creados += 1
                    if cantidad != ZERO:
                        await record_movement(db, organization_id=organization_id, user=user, item_id=item.id,
                                              location_id=bodega.id, movement_type=MovementType.ENTRADA,
                                              quantity=cantidad, unit_cost=item.unit_cost, reference="Conteo inicial",
                                              note=f"Carga del catálogo ({filename or 'Excel'})",
                                              source_key=f"initial-count:{item.id}", commit=False)
                        iniciales += 1
                else:
                    item.name, item.category, item.unit = nombre, categoria, unidad
                    if sku:
                        item.sku = sku
                    item.brand = marca or item.brand
                    item.manufacturer_part = fabricante or item.manufacturer_part
                    item.unit_cost = to_money(fila.get("unit_cost") or item.unit_cost or 0)
                    item.supplier_name = (fila.get("supplier_name") or "").strip() or item.supplier_name
                    item.has_serial = bool(fila.get("has_serial")) or item.has_serial
                    if fila.get("min_quantity") not in (None, ""):
                        item.min_quantity = _q(fila["min_quantity"])
                    item.notes = (fila.get("notes") or "").strip() or item.notes
                    actualizados += 1
                    if replace_stock:
                        actual = await stock_quantity(db, organization_id, item_id=item.id, location_id=bodega.id)
                        if cantidad != actual:
                            await record_movement(db, organization_id=organization_id, user=user, item_id=item.id,
                                                  location_id=bodega.id, movement_type=MovementType.AJUSTE,
                                                  quantity=cantidad - actual, reference="Conteo inicial",
                                                  note=f"Recarga del catálogo ({filename or 'Excel'})", commit=False)
                            iniciales += 1
        except Exception as exc:  # noqa: BLE001 — una fila mala no puede tumbar la carga entera
            errores.append({"fila": numero, "error": str(exc)})

    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.catalog_imported", entity_type="warehouse_item",
                             after_data={"creados": creados, "actualizados": actualizados, "errores": len(errores),
                                         "categorias_nuevas": nuevas})
    await db.commit()
    return {"creados": creados, "actualizados": actualizados, "omitidos": omitidos,
            "conteo_inicial": iniciales, "errores": errores, "categorias_nuevas": nuevas}


# ---------------------------------------------------------------------------
# Conteo físico
# ---------------------------------------------------------------------------

async def register_count(db: AsyncSession, *, organization_id, user, location_id, lines: list[dict],
                         note: str | None = None, counted_on: date | None = None) -> dict:
    """Cuadra el saldo con lo contado. La diferencia queda como movimiento
    `ajuste` con su motivo, nunca como un saldo escrito a mano."""
    ubicacion = await get_location(db, organization_id, location_id)
    ajustes, sin_cambio = [], 0
    for linea in lines:
        item = await get_item(db, organization_id, linea["item_id"])
        contado = _q(linea["counted_quantity"])
        actual = await stock_quantity(db, organization_id, item_id=item.id, location_id=ubicacion.id)
        diferencia = contado - actual
        if diferencia == ZERO:
            sin_cambio += 1
            continue
        movimiento = await record_movement(
            db, organization_id=organization_id, user=user, item_id=item.id, location_id=ubicacion.id,
            movement_type=MovementType.AJUSTE, quantity=diferencia, unit_cost=item.unit_cost,
            reference="Conteo físico", note=(note or "").strip() or None, movement_date=counted_on, commit=False)
        ajustes.append({"item_id": str(item.id), "item_name": item.name, "antes": str(actual), "contado": str(contado),
                        "diferencia": str(diferencia), "movement_id": str(movimiento.id)})
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.counted", entity_type="warehouse_location",
                             entity_id=str(ubicacion.id),
                             after_data={"ajustes": len(ajustes), "sin_cambio": sin_cambio})
    await db.commit()
    return {"location_id": str(ubicacion.id), "location_name": ubicacion.name, "revisados": len(lines),
            "sin_cambio": sin_cambio, "ajustes": ajustes}


# ---------------------------------------------------------------------------
# Salidas para las pantallas
# ---------------------------------------------------------------------------

def location_out(loc: WarehouseLocation | None) -> dict | None:
    if loc is None:
        return None
    return {"id": str(loc.id), "name": loc.name, "kind": loc.kind,
            "kind_label": LOCATION_KINDS.get(loc.kind, loc.kind),
            "technician_user_id": str(loc.technician_user_id) if loc.technician_user_id else None,
            "active": loc.active}


def item_out(item: WarehouseItem, totals: dict | None = None, labels: dict[str, str] | None = None) -> dict:
    """`labels`: las categorías de la organización (`category_labels`); sin
    ellas se usa la etiqueta inicial."""
    datos = totals or {"total": ZERO, "by_location": []}
    total = datos["total"]
    bajo_minimo = item.min_quantity is not None and total <= _q(item.min_quantity)
    etiquetas = labels or ITEM_CATEGORIES
    return {
        "id": str(item.id), "name": item.name, "sku": item.sku,
        "brand": item.brand, "manufacturer_part": item.manufacturer_part,
        "category": item.category, "category_label": etiquetas.get(item.category, item.category),
        "unit": item.unit, "unit_label": ITEM_UNITS.get(item.unit, item.unit),
        "unit_cost": str(to_money(item.unit_cost)), "supplier_name": item.supplier_name,
        "has_serial": item.has_serial,
        "min_quantity": None if item.min_quantity is None else str(_q(item.min_quantity)),
        "notes": item.notes, "active": item.active,
        "total_quantity": str(_q(total)), "by_location": datos["by_location"],
        "below_minimum": bajo_minimo,
        "value": str(to_money(to_money(item.unit_cost) * _q(total))),
    }


def movement_out(m: WarehouseMovement, *, item_name=None, unit_label=None, location_name=None) -> dict:
    return {
        "id": str(m.id), "item_id": str(m.item_id), "item_name": item_name,
        "unit_label": unit_label, "location_id": str(m.location_id), "location_name": location_name,
        "vendor_location_id": str(m.to_location_id) if m.to_location_id else None,
        "movement_type": m.movement_type, "movement_type_label": MOVEMENT_TYPES.get(m.movement_type, m.movement_type),
        "quantity": str(_q(m.quantity)),
        "unit_cost": None if m.unit_cost is None else str(to_money(m.unit_cost)),
        "amount": None if m.unit_cost is None else str(to_money(to_money(m.unit_cost) * abs(_q(m.quantity)))),
        "movement_date": m.movement_date.isoformat() if m.movement_date else None,
        "reference": m.reference, "note": m.note,
        "project_id": str(m.project_id) if m.project_id else None,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


async def totals_by_item(db: AsyncSession, organization_id, item_ids) -> dict:
    """Existencia total de cada artículo y su desglose por ubicación."""
    ids = list(item_ids)
    if not ids:
        return {}
    filas = (await db.execute(
        select(WarehouseStock.item_id, WarehouseLocation.id, WarehouseLocation.name, WarehouseLocation.kind,
               WarehouseStock.quantity)
        .join(WarehouseLocation, WarehouseLocation.id == WarehouseStock.location_id)
        .where(WarehouseStock.organization_id == organization_id, WarehouseStock.item_id.in_(ids))
    )).all()
    totales: dict = {}
    for item_id, location_id, nombre, kind, cantidad in filas:
        datos = totales.setdefault(item_id, {"total": ZERO, "by_location": []})
        datos["total"] += _q(cantidad)
        if _q(cantidad) != ZERO:
            datos["by_location"].append({"location_id": str(location_id), "name": nombre, "kind": kind,
                                         "quantity": str(_q(cantidad))})
    return totales


async def low_stock_count(db: AsyncSession, organization_id) -> int:
    """Cuántos artículos están en o por debajo de su mínimo (el aviso de la lista)."""
    sub = (select(WarehouseStock.item_id.label("item_id"),
                  func.sum(WarehouseStock.quantity).label("total"))
           .where(WarehouseStock.organization_id == organization_id)
           .group_by(WarehouseStock.item_id).subquery())
    consulta = (select(func.count()).select_from(WarehouseItem)
                .outerjoin(sub, sub.c.item_id == WarehouseItem.id)
                .where(WarehouseItem.organization_id == organization_id, WarehouseItem.active.is_(True),
                       WarehouseItem.min_quantity.is_not(None),
                       func.coalesce(sub.c.total, 0) <= WarehouseItem.min_quantity))
    return int((await db.execute(consulta)).scalar_one())
