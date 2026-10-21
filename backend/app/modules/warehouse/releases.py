"""Órdenes de salida de bodega (punto 1 del cuestionario del 19 de octubre).

La regla que sostiene este archivo: **el material sale solo por una orden
autorizada y entregada**. Nadie baja el saldo a mano (la ruta de movimientos
rechaza `salida`), y la entrega es idempotente por dos vías —el estado tiene que
ser `autorizada`, y cada movimiento lleva una clave `source_key` con el número
de la orden y el id de la línea— así que entregar dos veces no descuenta dos
veces.

D-BOD-4: si no hay existencia no se bloquea la entrega. Se entrega lo que hay,
la orden queda con el motivo escrito en `shortage_note` y la respuesta lista los
faltantes, que es lo que el técnico necesita saber para comprar o esperar.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import ZERO
from app.modules.billing.numbering import next_number
from app.modules.field_ops.clock import org_today
from app.modules.warehouse import service as wh
from app.modules.warehouse.catalogs import (
    ITEM_UNITS,
    LineOrigin,
    MovementType,
    ReleaseStatus,
)
from app.modules.warehouse.models import (
    WarehouseItem,
    WarehouseLocation,
    WarehouseReleaseLine,
    WarehouseReleaseOrder,
)
from app.shared import events as domain_events
from app.shared.audit import record_audit_event
from app.shared.errors import InvalidInputError, NotFoundError

Q2 = Decimal("0.01")

RELEASE_SERIES = "SAL"


def _q(value) -> Decimal:
    return (Decimal(str(value)) if value is not None else ZERO).quantize(Q2)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

async def get_order(db: AsyncSession, organization_id, order_id) -> WarehouseReleaseOrder:
    order = await db.get(WarehouseReleaseOrder, order_id)
    if order is None or order.organization_id != organization_id:
        raise NotFoundError("La orden de salida no existe.", code="release_order_not_found")
    return order


async def lines_of(db: AsyncSession, organization_id, order_ids) -> dict:
    """Líneas de varias órdenes, agrupadas. Se lee aparte porque la relación
    está en `lazy="raise"`: nada se carga sin pedirlo."""
    ids = list(order_ids)
    if not ids:
        return {}
    filas = (await db.execute(select(WarehouseReleaseLine).where(
        WarehouseReleaseLine.organization_id == organization_id,
        WarehouseReleaseLine.order_id.in_(ids),
    ).order_by(WarehouseReleaseLine.sort_order, WarehouseReleaseLine.created_at))).scalars().all()
    agrupadas: dict = {}
    for linea in filas:
        agrupadas.setdefault(linea.order_id, []).append(linea)
    return agrupadas


def releases_stmt(organization_id, *, status: str | None = None, project_id=None, q: str | None = None,
                  pending_only: bool = False):
    stmt = select(WarehouseReleaseOrder).where(WarehouseReleaseOrder.organization_id == organization_id)
    if pending_only:
        stmt = stmt.where(WarehouseReleaseOrder.status == ReleaseStatus.POR_AUTORIZAR)
    elif status:
        stmt = stmt.where(WarehouseReleaseOrder.status == status)
    if project_id:
        stmt = stmt.where(WarehouseReleaseOrder.project_id == project_id)
    if q:
        patron = f"%{q.strip()}%"
        stmt = stmt.where(or_(WarehouseReleaseOrder.number.ilike(patron), WarehouseReleaseOrder.note.ilike(patron)))
    # Lo que espera decisión primero, y dentro de cada grupo lo más reciente.
    return stmt.order_by(WarehouseReleaseOrder.status, WarehouseReleaseOrder.created_at.desc())


# ---------------------------------------------------------------------------
# Armar la orden
# ---------------------------------------------------------------------------

async def _item_for_line(db, organization_id, item_id) -> WarehouseItem:
    return await wh.get_item(db, organization_id, item_id)


def _normalizar_lineas(lineas: list[dict]) -> list[dict]:
    limpias = []
    for posicion, linea in enumerate(lineas):
        cantidad = _q(linea["quantity"])
        if cantidad <= ZERO:
            raise InvalidInputError("Toda línea necesita una cantidad mayor que cero.", code="invalid_line_quantity")
        limpias.append({
            "item_id": linea["item_id"], "quantity_requested": cantidad,
            "spec_label": (linea.get("spec_label") or "").strip() or None,
            "notes": (linea.get("notes") or "").strip() or None,
            "origin": linea.get("origin") or LineOrigin.MANUAL,
            "sort_order": posicion,
        })
    return limpias


async def create_order(db: AsyncSession, *, organization_id, user, data: dict) -> WarehouseReleaseOrder:
    lineas = _normalizar_lineas(data["lines"])
    for linea in lineas:
        await _item_for_line(db, organization_id, linea["item_id"])

    ubicacion = await wh.get_location(db, organization_id, data["location_id"]) if data.get("location_id") \
        else await wh.default_location(db, organization_id)
    order = WarehouseReleaseOrder(
        organization_id=organization_id, status=ReleaseStatus.BORRADOR, location_id=ubicacion.id,
        project_id=data.get("project_id"), technician_user_id=data.get("technician_user_id") or user.id,
        requested_by_user_id=user.id, needed_on=data.get("needed_on"),
        note=(data.get("note") or "").strip() or None,
    )
    db.add(order)
    await db.flush()
    _add_lines(db, organization_id, order, lineas)
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.release_created", entity_type="warehouse_release_order",
                             entity_id=str(order.id), after_data={"lineas": len(lineas)})
    await db.commit()
    await db.refresh(order)
    return order


def _add_lines(db, organization_id, order, lineas: list[dict]) -> None:
    for linea in lineas:
        db.add(WarehouseReleaseLine(organization_id=organization_id, order_id=order.id, **linea))


async def update_order(db: AsyncSession, *, organization_id, user, order_id, data: dict) -> WarehouseReleaseOrder:
    """Se puede corregir mientras sea borrador. Una vez enviada, la orden es lo
    que el autorizador está mirando: cambiarla por debajo lo volvería un blanco
    móvil."""
    order = await get_order(db, organization_id, order_id)
    if order.status != ReleaseStatus.BORRADOR:
        raise InvalidInputError("Una orden ya enviada no se edita; recházala y haz otra.",
                                code="release_not_editable")
    lineas = _normalizar_lineas(data["lines"])
    for linea in lineas:
        await _item_for_line(db, organization_id, linea["item_id"])

    for previa in (await lines_of(db, organization_id, [order.id])).get(order.id, []):
        await db.delete(previa)
    order.project_id = data.get("project_id")
    order.technician_user_id = data.get("technician_user_id") or order.technician_user_id
    order.needed_on = data.get("needed_on")
    order.note = (data.get("note") or "").strip() or None
    if data.get("location_id"):
        order.location_id = (await wh.get_location(db, organization_id, data["location_id"])).id
    await db.flush()
    _add_lines(db, organization_id, order, lineas)
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.release_updated", entity_type="warehouse_release_order",
                             entity_id=str(order.id), after_data={"lineas": len(lineas)})
    await db.commit()
    await db.refresh(order)
    return order


# ---------------------------------------------------------------------------
# Flujo: borrador → por autorizar → autorizada / rechazada → entregada
# ---------------------------------------------------------------------------

async def submit_order(db: AsyncSession, *, organization_id, user, order_id) -> WarehouseReleaseOrder:
    order = await get_order(db, organization_id, order_id)
    if order.status != ReleaseStatus.BORRADOR:
        raise InvalidInputError("Solo un borrador se manda a autorizar.", code="release_not_draft")
    lineas = (await lines_of(db, organization_id, [order.id])).get(order.id, [])
    if not lineas:
        raise InvalidInputError("La orden no tiene material: no hay nada que autorizar.", code="release_without_lines")
    anio = (await org_today(db, organization_id)).year
    order.number = await next_number(db, organization_id=organization_id, series=RELEASE_SERIES, year=anio)
    order.status = ReleaseStatus.POR_AUTORIZAR
    order.submitted_at = _now()
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.release_submitted", entity_type="warehouse_release_order",
                             entity_id=str(order.id), after_data={"number": order.number})
    await db.commit()
    await db.refresh(order)
    domain_events.emit("warehouse.release_pending", {"release_id": str(order.id),
                                                    "organization_id": str(organization_id)})
    return order


async def authorize_order(db: AsyncSession, *, organization_id, user, order_id) -> WarehouseReleaseOrder:
    order = await get_order(db, organization_id, order_id)
    if order.status != ReleaseStatus.POR_AUTORIZAR:
        raise InvalidInputError("Esta orden no está esperando autorización.", code="release_not_pending")
    order.status = ReleaseStatus.AUTORIZADA
    order.authorized_by_user_id = user.id
    order.authorized_at = _now()
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.release_authorized", entity_type="warehouse_release_order",
                             entity_id=str(order.id), after_data={"number": order.number})
    await db.commit()
    await db.refresh(order)
    return order


async def reject_order(db: AsyncSession, *, organization_id, user, order_id, reason: str) -> WarehouseReleaseOrder:
    motivo = (reason or "").strip()
    if not motivo:
        raise InvalidInputError("Para rechazar hay que decir por qué.", code="reject_reason_required")
    order = await get_order(db, organization_id, order_id)
    if order.status != ReleaseStatus.POR_AUTORIZAR:
        raise InvalidInputError("Esta orden no está esperando autorización.", code="release_not_pending")
    order.status = ReleaseStatus.RECHAZADA
    order.authorized_by_user_id = user.id
    order.authorized_at = _now()
    order.reject_reason = motivo
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.release_rejected", entity_type="warehouse_release_order",
                             entity_id=str(order.id), after_data={"number": order.number, "motivo": motivo})
    await db.commit()
    await db.refresh(order)
    return order


async def deliver_order(db: AsyncSession, *, organization_id, user, order_id, note: str | None = None) -> dict:
    """Entrega el material: baja el saldo y carga lo entregado a la obra.

    Devuelve la orden y la lista de faltantes (lo pedido que no se pudo
    entregar). Sin existencia no se bloquea (D-BOD-4).
    """
    order = await get_order(db, organization_id, order_id)
    if order.status != ReleaseStatus.AUTORIZADA:
        raise InvalidInputError("Solo se entrega material de una orden autorizada.",
                                code="release_not_authorized")
    lineas = (await lines_of(db, organization_id, [order.id])).get(order.id, [])
    ubicacion = await wh.get_location(db, organization_id, order.location_id)
    hoy = await org_today(db, organization_id)

    faltantes: list[dict] = []
    entregado_alguna = False
    for linea in lineas:
        pedida = _q(linea.quantity_requested)
        disponible = await wh.stock_quantity(db, organization_id, item_id=linea.item_id,
                                             location_id=ubicacion.id)
        entregada = min(pedida, disponible) if disponible > ZERO else ZERO
        linea.quantity_delivered = _q(entregada)
        if entregada <= ZERO:
            faltantes.append({"line_id": str(linea.id), "item_id": str(linea.item_id),
                              "pedida": str(pedida), "entregada": "0.00",
                              "motivo": "No había existencia en bodega."})
            continue
        if entregada < pedida:
            faltantes.append({"line_id": str(linea.id), "item_id": str(linea.item_id),
                              "pedida": str(pedida), "entregada": str(_q(entregada)),
                              "motivo": f"Solo había {_q(entregada)} de {pedida}."})
        entregado_alguna = True
        movimiento = await wh.record_movement(
            db, organization_id=organization_id, user=user, item_id=linea.item_id, location_id=ubicacion.id,
            movement_type=MovementType.SALIDA, quantity=entregada,
            reference=order.number or f"Orden {order.id}", note=linea.notes,
            project_id=order.project_id, movement_date=hoy,
            # La clave lleva la línea: reintentar la entrega devuelve el mismo
            # movimiento en vez de descontar otra vez.
            source_key=f"release:{order.number}:line:{linea.id}", commit=False)
        if order.project_id:
            await _cargar_a_la_obra(db, organization_id=organization_id, order=order, line_id=linea.id,
                                    item_id=linea.item_id, cantidad=_q(entregada))

    order.status = ReleaseStatus.ENTREGADA
    order.delivered_by_user_id = user.id
    order.delivered_at = _now()
    resumen = " ".join(f["motivo"] for f in faltantes) if faltantes else None
    if note and note.strip():
        resumen = f"{resumen} {note.strip()}".strip() if resumen else note.strip()
    order.shortage_note = resumen
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.release_delivered", entity_type="warehouse_release_order",
                             entity_id=str(order.id),
                             after_data={"number": order.number, "faltantes": len(faltantes)})
    await db.commit()
    await db.refresh(order)
    if entregado_alguna:
        domain_events.emit("warehouse.release_delivered", {"release_id": str(order.id),
                                                          "organization_id": str(organization_id)})
    return {"order": order, "faltantes": faltantes}


async def _cargar_a_la_obra(db, *, organization_id, order, line_id, item_id, cantidad) -> None:
    """Suma el material entregado a «Lo que la orden necesita» del proyecto.

    Es lo que hace que el acta y el costo real de la obra vean lo que salió de
    bodega, y que se pueda decir de qué orden salió cada cosa.
    """
    from app.modules.field_ops.models import ProjectMaterial

    item = await db.get(WarehouseItem, item_id)
    ya = (await db.execute(select(ProjectMaterial).where(
        ProjectMaterial.organization_id == organization_id,
        ProjectMaterial.warehouse_release_line_id == line_id))).scalars().first()
    if ya is not None:
        return
    db.add(ProjectMaterial(
        organization_id=organization_id, project_id=order.project_id,
        description=item.name if item else "Material de bodega",
        sku=item.sku if item else None, quantity=cantidad,
        unit=ITEM_UNITS.get(item.unit) if item else None,
        notes=(f"De bodega · {order.number}" if order.number else "De bodega"),
        warehouse_release_line_id=line_id,
    ))
    await db.flush()


# ---------------------------------------------------------------------------
# Salidas para las pantallas
# ---------------------------------------------------------------------------

async def orders_out(db: AsyncSession, organization_id, orders: list[WarehouseReleaseOrder]) -> list[dict]:
    """Órdenes con sus líneas y los nombres que la pantalla necesita, en dos
    consultas y sin cargar relaciones por el camino."""
    if not orders:
        return []
    agrupadas = await lines_of(db, organization_id, [o.id for o in orders])
    item_ids = {l.item_id for ls in agrupadas.values() for l in ls}
    items = {i.id: i for i in (await db.execute(select(WarehouseItem).where(
        WarehouseItem.id.in_(item_ids)))).scalars().all()} if item_ids else {}
    ubicaciones = {l.id: l.name for l in (await db.execute(select(WarehouseLocation).where(
        WarehouseLocation.id.in_({o.location_id for o in orders})))).scalars().all()}
    return [order_out(o, agrupadas.get(o.id, []), items=items, location_name=ubicaciones.get(o.location_id))
            for o in orders]


def line_out(linea: WarehouseReleaseLine, *, item: WarehouseItem | None = None) -> dict:
    pedida = _q(linea.quantity_requested)
    entregada = None if linea.quantity_delivered is None else _q(linea.quantity_delivered)
    return {
        "id": str(linea.id), "item_id": str(linea.item_id),
        "item_name": item.name if item else None,
        "sku": item.sku if item else None,
        "unit": item.unit if item else None,
        "unit_label": ITEM_UNITS.get(item.unit, item.unit) if item else None,
        "unit_cost": str(item.unit_cost) if item else None,
        "quantity_requested": str(pedida),
        "quantity_delivered": None if entregada is None else str(entregada),
        "pending_quantity": str(pedida - entregada) if entregada is not None and entregada < pedida else "0.00",
        "spec_label": linea.spec_label, "notes": linea.notes, "origin": linea.origin,
    }


def order_out(order: WarehouseReleaseOrder, lineas: list[WarehouseReleaseLine], *, items: dict | None = None,
              location_name: str | None = None) -> dict:
    catalogo = items or {}
    return {
        "id": str(order.id), "number": order.number, "status": order.status,
        "project_id": str(order.project_id) if order.project_id else None,
        "location_id": str(order.location_id), "location_name": location_name,
        "requested_by_user_id": str(order.requested_by_user_id) if order.requested_by_user_id else None,
        "technician_user_id": str(order.technician_user_id) if order.technician_user_id else None,
        "needed_on": order.needed_on.isoformat() if order.needed_on else None,
        "note": order.note,
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
        "authorized_by_user_id": str(order.authorized_by_user_id) if order.authorized_by_user_id else None,
        "authorized_at": order.authorized_at.isoformat() if order.authorized_at else None,
        "reject_reason": order.reject_reason,
        "delivered_by_user_id": str(order.delivered_by_user_id) if order.delivered_by_user_id else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "shortage_note": order.shortage_note,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "lines": [line_out(l, item=catalogo.get(l.item_id)) for l in lineas],
    }


async def pending_count(db: AsyncSession, organization_id) -> int:
    """Cuántas órdenes esperan autorización: el número que ve el autorizador."""
    return int((await db.execute(select(func.count()).select_from(WarehouseReleaseOrder).where(
        WarehouseReleaseOrder.organization_id == organization_id,
        WarehouseReleaseOrder.status == ReleaseStatus.POR_AUTORIZAR))).scalar_one())
