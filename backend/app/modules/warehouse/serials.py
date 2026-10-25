"""Seriales de los artículos «con serial» (D-007; spec de bodega del 19 oct).

Cada unidad de un equipo tiene su serial y está en un solo lugar:

- `in_stock`: en bodega. Llega con una entrada que trae los seriales, o vuelve
  con una devolución de la obra.
- `delivered`: salió con una orden de salida para una obra. Bodega anota el
  serial de cada unidad al entregar; si el serial no estaba registrado (lo que
  ya había en bodega antes de este control), se registra en ese momento.
- `installed`: el técnico lo registró en «Equipos instalados» de esa obra.

Las reglas: no se entrega un serial que no está en bodega, no se devuelve uno
que no salió para esa obra y no se instala uno que salió para otra. Un equipo
que no pasó por bodega (D-BOD-3: los grandes van directo a la obra) se instala
con su serial escrito, sin cruce.

Solo este archivo cambia el estado de un serial.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.warehouse.catalogs import SERIAL_STATUSES, SerialStatus
from app.modules.warehouse.models import WarehouseItem, WarehouseSerial
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError
from app.shared.text_search import LIKE_ESCAPE, contains_pattern

MAX_SERIAL = 100


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize(serial: str) -> str:
    """Sin espacios de más y en mayúsculas: «ab 123» y «AB 123 » son el mismo."""
    return " ".join(str(serial or "").split()).upper()


def clean_list(item: WarehouseItem, serials: list[str] | None) -> list[str]:
    limpios = [normalize(s) for s in (serials or [])]
    if any(not s for s in limpios):
        raise InvalidInputError(f"«{item.name}»: hay un serial vacío.", code="serial_empty")
    if any(len(s) > MAX_SERIAL for s in limpios):
        raise InvalidInputError(f"«{item.name}»: un serial tiene más de {MAX_SERIAL} caracteres.",
                                code="serial_too_long")
    repetidos = sorted({s for s in limpios if limpios.count(s) > 1})
    if repetidos:
        raise InvalidInputError(f"«{item.name}»: el serial {', '.join(repetidos)} está repetido.",
                                code="serial_repeated")
    return limpios


def whole_units(item: WarehouseItem, cantidad) -> int:
    cantidad = Decimal(str(cantidad))
    if cantidad != cantidad.to_integral_value():
        raise InvalidInputError(f"«{item.name}» lleva serial: se mueve por unidades enteras.",
                                code="serial_whole_units")
    return int(cantidad)


def _check_count(item: WarehouseItem, serials: list[str], unidades: int, verbo: str) -> None:
    if len(serials) != unidades:
        raise InvalidInputError(
            f"«{item.name}» lleva serial: anota {unidades} serial{'es' if unidades != 1 else ''}, "
            f"uno por unidad {verbo} (llegaron {len(serials)}).", code="serials_count_mismatch")


async def _by_serial(db, organization_id, item_id, serials: list[str]) -> dict[str, WarehouseSerial]:
    if not serials:
        return {}
    filas = (await db.execute(select(WarehouseSerial).where(
        WarehouseSerial.organization_id == organization_id, WarehouseSerial.item_id == item_id,
        WarehouseSerial.serial.in_(serials)).with_for_update())).scalars().all()
    return {f.serial: f for f in filas}


def _donde(fila: WarehouseSerial) -> str:
    return SERIAL_STATUSES.get(fila.status, fila.status).lower()


async def receive(db: AsyncSession, *, organization_id, user, item: WarehouseItem, serials: list[str] | None,
                  cantidad, location_id) -> list[WarehouseSerial]:
    """Entrada con seriales (compra recibida). Los seriales son opcionales en
    la entrada; si llegan, uno por unidad y ninguno ya registrado."""
    limpios = clean_list(item, serials)
    if not limpios:
        return []
    _check_count(item, limpios, whole_units(item, cantidad), "recibida")
    existentes = await _by_serial(db, organization_id, item.id, limpios)
    if existentes:
        s = next(iter(existentes.values()))
        raise ConflictError(f"El serial {s.serial} de «{item.name}» ya está registrado ({_donde(s)}).",
                            code="serial_already_registered")
    filas = [WarehouseSerial(organization_id=organization_id, item_id=item.id, serial=s,
                             status=SerialStatus.IN_STOCK, location_id=location_id,
                             created_by_user_id=user.id if user else None) for s in limpios]
    db.add_all(filas)
    await db.flush()
    await _audit(db, organization_id, user, "warehouse.serials_received", item, limpios)
    return filas


async def deliver(db: AsyncSession, *, organization_id, user, item: WarehouseItem, serials: list[str] | None,
                  cantidad, location_id, order, line) -> list[WarehouseSerial]:
    """Entrega de una orden: un serial por unidad entregada."""
    limpios = clean_list(item, serials)
    _check_count(item, limpios, whole_units(item, cantidad), "entregada")
    existentes = await _by_serial(db, organization_id, item.id, limpios)
    for s in limpios:
        fila = existentes.get(s)
        if fila is not None and fila.status != SerialStatus.IN_STOCK:
            raise ConflictError(f"El serial {s} de «{item.name}» no está en bodega: está {_donde(fila)}.",
                                code="serial_not_in_stock")
    ahora, filas = _now(), []
    for s in limpios:
        fila = existentes.get(s)
        if fila is None:
            # Lo que había en bodega antes de este control: se registra al salir.
            fila = WarehouseSerial(organization_id=organization_id, item_id=item.id, serial=s,
                                   created_by_user_id=user.id if user else None)
            db.add(fila)
        fila.status, fila.location_id = SerialStatus.DELIVERED, location_id
        fila.project_id, fila.release_order_id, fila.release_line_id = order.project_id, order.id, line.id
        fila.delivered_at = ahora
        filas.append(fila)
    await db.flush()
    await _audit(db, organization_id, user, "warehouse.serials_delivered", item, limpios,
                 extra={"release_order_id": str(order.id), "number": order.number})
    return filas


async def return_to_stock(db: AsyncSession, *, organization_id, user, item: WarehouseItem,
                          serials: list[str] | None, cantidad, project_id, location_id) -> list[WarehouseSerial]:
    """Devolución: vuelven a bodega solo los seriales entregados a esa obra y
    que no se instalaron."""
    limpios = clean_list(item, serials)
    _check_count(item, limpios, whole_units(item, cantidad), "devuelta")
    existentes = await _by_serial(db, organization_id, item.id, limpios)
    for s in limpios:
        fila = existentes.get(s)
        if fila is None or fila.status != SerialStatus.DELIVERED or fila.project_id != project_id:
            estado = "no está registrado" if fila is None else f"está {_donde(fila)}"
            raise ConflictError(f"El serial {s} de «{item.name}» no salió para esta obra: {estado}.",
                                code="serial_not_delivered_here")
    for s in limpios:
        fila = existentes[s]
        fila.status, fila.location_id, fila.project_id = SerialStatus.IN_STOCK, location_id, None
    await db.flush()
    await _audit(db, organization_id, user, "warehouse.serials_returned", item, limpios,
                 extra={"project_id": str(project_id) if project_id else None})
    return [existentes[s] for s in limpios]


async def install(db: AsyncSession, *, organization_id, user, project, equipment, serial_id=None
                  ) -> WarehouseSerial | None:
    """Cruza el equipo instalado con el serial que salió de bodega.

    Con `serial_id` el técnico lo eligió de la lista de su obra. Sin él, se
    busca el serial escrito: si salió para esta obra se cruza solo; si está en
    bodega, en otra obra o ya instalado, se rechaza; si nunca pasó por bodega,
    queda escrito sin cruce (D-BOD-3)."""
    if serial_id is not None:
        fila = (await db.execute(select(WarehouseSerial).where(
            WarehouseSerial.id == serial_id, WarehouseSerial.organization_id == organization_id
        ).with_for_update())).scalar_one_or_none()
        if fila is None:
            raise NotFoundError("El serial no existe.", code="serial_not_found")
        candidatos = [fila]
    else:
        escrito = normalize(equipment.serial_number or "")
        if not escrito:
            return None
        candidatos = list((await db.execute(select(WarehouseSerial).where(
            WarehouseSerial.organization_id == organization_id, WarehouseSerial.serial == escrito
        ).with_for_update())).scalars().all())
        if not candidatos:
            return None
    fila = next((c for c in candidatos if c.status == SerialStatus.DELIVERED and c.project_id == project.id), None)
    if fila is None:
        c = candidatos[0]
        if c.status == SerialStatus.IN_STOCK:
            motivo = "sigue en bodega: debe salir con una orden de salida para esta obra"
        elif c.status == SerialStatus.INSTALLED:
            motivo = "ya está instalado" + (" en esta obra" if c.project_id == project.id else " en otra obra")
        else:
            motivo = "salió de bodega para otra obra"
        raise ConflictError(f"El serial {c.serial} {motivo}.", code="serial_not_available_here")
    fila.status, fila.installed_equipment_id, fila.installed_at = SerialStatus.INSTALLED, equipment.id, _now()
    equipment.serial_number = fila.serial
    await db.flush()
    return fila


async def uninstall(db: AsyncSession, *, organization_id, equipment_id) -> None:
    """Se borró el equipo instalado: su serial vuelve a «entregado» a la obra."""
    for fila in (await db.execute(select(WarehouseSerial).where(
            WarehouseSerial.organization_id == organization_id,
            WarehouseSerial.installed_equipment_id == equipment_id))).scalars().all():
        fila.status, fila.installed_equipment_id, fila.installed_at = SerialStatus.DELIVERED, None, None
    await db.flush()


async def linked_to_equipment(db: AsyncSession, organization_id, equipment_ids) -> dict:
    ids = list(equipment_ids)
    if not ids:
        return {}
    filas = (await db.execute(select(WarehouseSerial.installed_equipment_id, WarehouseSerial.id).where(
        WarehouseSerial.organization_id == organization_id,
        WarehouseSerial.installed_equipment_id.in_(ids)))).all()
    return {e: s for e, s in filas}


async def of_lines(db: AsyncSession, organization_id, line_ids) -> dict:
    """Los seriales que salieron con cada renglón de una orden."""
    ids = list(line_ids)
    if not ids:
        return {}
    por: dict = {}
    for fila in (await db.execute(select(WarehouseSerial).where(
            WarehouseSerial.organization_id == organization_id,
            WarehouseSerial.release_line_id.in_(ids)).order_by(WarehouseSerial.serial))).scalars().all():
        por.setdefault(fila.release_line_id, []).append(fila.serial)
    return por


def serials_stmt(organization_id, *, q: str | None = None, status: str | None = None, item_id=None,
                 project_id=None):
    stmt = select(WarehouseSerial).where(WarehouseSerial.organization_id == organization_id)
    if q and q.strip():
        patron = contains_pattern(normalize(q))
        nombres = select(WarehouseItem.id).where(WarehouseItem.organization_id == organization_id,
                                                 WarehouseItem.name.ilike(contains_pattern(q), escape=LIKE_ESCAPE))
        stmt = stmt.where(or_(WarehouseSerial.serial.ilike(patron, escape=LIKE_ESCAPE),
                              WarehouseSerial.item_id.in_(nombres)))
    if status:
        if status not in SERIAL_STATUSES:
            raise InvalidInputError("El estado del serial no existe.", code="invalid_serial_status")
        stmt = stmt.where(WarehouseSerial.status == status)
    if item_id:
        stmt = stmt.where(WarehouseSerial.item_id == item_id)
    if project_id:
        stmt = stmt.where(WarehouseSerial.project_id == project_id)
    return stmt.order_by(func.lower(WarehouseSerial.serial), WarehouseSerial.id)


async def serials_out(db: AsyncSession, organization_id, filas: list[WarehouseSerial]) -> list[dict]:
    from app.modules.field_ops.models import Project
    from app.modules.warehouse.models import WarehouseReleaseOrder

    items = {i.id: i for i in (await db.execute(select(WarehouseItem).where(
        WarehouseItem.id.in_({f.item_id for f in filas})))).scalars().all()} if filas else {}
    obras_ids = {f.project_id for f in filas if f.project_id}
    obras = {p.id: p.title for p in (await db.execute(select(Project).where(
        Project.id.in_(obras_ids)))).scalars().all()} if obras_ids else {}
    ordenes_ids = {f.release_order_id for f in filas if f.release_order_id}
    ordenes = {o.id: o.number for o in (await db.execute(select(WarehouseReleaseOrder).where(
        WarehouseReleaseOrder.id.in_(ordenes_ids)))).scalars().all()} if ordenes_ids else {}
    salida = []
    for f in filas:
        item = items.get(f.item_id)
        salida.append({
            "id": str(f.id), "serial": f.serial, "status": f.status,
            "status_label": SERIAL_STATUSES.get(f.status, f.status),
            "item_id": str(f.item_id), "item_name": item.name if item else None,
            "sku": item.sku if item else None, "brand": item.brand if item else None,
            "manufacturer_part": item.manufacturer_part if item else None,
            "project_id": str(f.project_id) if f.project_id else None,
            "project_title": obras.get(f.project_id),
            "release_order_id": str(f.release_order_id) if f.release_order_id else None,
            "release_number": ordenes.get(f.release_order_id),
            "installed_equipment_id": str(f.installed_equipment_id) if f.installed_equipment_id else None,
            "delivered_at": f.delivered_at.isoformat() if f.delivered_at else None,
            "installed_at": f.installed_at.isoformat() if f.installed_at else None,
        })
    return salida


async def _audit(db, organization_id, user, action, item, serials, *, extra: dict | None = None) -> None:
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id if user else None,
                             action=action, entity_type="warehouse_item", entity_id=str(item.id),
                             after_data={"item": item.name, "serials": serials, **(extra or {})})
