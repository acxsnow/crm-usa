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
from app.shared.decimals import to_quantity
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from app.shared.text_search import LIKE_ESCAPE, contains_pattern

Q2 = Decimal("0.01")

RELEASE_SERIES = "SAL"


def _q(value) -> Decimal:
    return to_quantity(value)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

async def get_order(db: AsyncSession, organization_id, order_id, *, for_update: bool = False) -> WarehouseReleaseOrder:
    """Con `for_update` bloquea la fila hasta el commit y la relee de la base:
    dos personas que autorizan, rechazan o entregan la misma orden al tiempo
    se turnan, y la segunda ve el estado que dejó la primera (D-012)."""
    order = await db.get(WarehouseReleaseOrder, order_id, with_for_update=for_update, populate_existing=for_update)
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
                  pending_only: bool = False, own_user_id=None):
    stmt = select(WarehouseReleaseOrder).where(WarehouseReleaseOrder.organization_id == organization_id)
    if own_user_id:
        stmt = stmt.where(or_(WarehouseReleaseOrder.requested_by_user_id == own_user_id,
                              WarehouseReleaseOrder.technician_user_id == own_user_id))
    if pending_only:
        stmt = stmt.where(WarehouseReleaseOrder.status == ReleaseStatus.POR_AUTORIZAR)
    elif status:
        stmt = stmt.where(WarehouseReleaseOrder.status == status)
    if project_id:
        stmt = stmt.where(WarehouseReleaseOrder.project_id == project_id)
    if q:
        patron = contains_pattern(q)
        # También por el nombre de la obra, como el buscador global.
        from app.modules.field_ops.models import Project

        obras =select(Project.id).where(Project.organization_id == organization_id, Project.title.ilike(patron, escape=LIKE_ESCAPE))
        stmt = stmt.where(or_(WarehouseReleaseOrder.number.ilike(patron, escape=LIKE_ESCAPE),
                              WarehouseReleaseOrder.note.ilike(patron, escape=LIKE_ESCAPE),
                              WarehouseReleaseOrder.project_id.in_(obras)))
    # Lo que espera decisión primero, y dentro de cada grupo lo más reciente.
    return stmt.order_by(WarehouseReleaseOrder.status, WarehouseReleaseOrder.created_at.desc())


# ---------------------------------------------------------------------------
# Armar la orden
# ---------------------------------------------------------------------------

def _check_owner(order: WarehouseReleaseOrder, user) -> None:
    """El borrador lo arma quien lo pidió; bodega (`warehouse.manage`) puede
    corregir cualquiera. Así un técnico no edita ni envía la orden de otro."""
    from app.api.deps import get_effective_permissions

    if order.requested_by_user_id != user.id and "warehouse.manage" not in get_effective_permissions(user):
        raise ForbiddenError("Solo quien pidió la orden (o bodega) puede cambiarla.", code="release_not_owner")


async def get_own_draft(db: AsyncSession, organization_id, user, order_id) -> WarehouseReleaseOrder:
    order = await get_order(db, organization_id, order_id)
    _check_owner(order, user)
    return order


async def _check_project(db: AsyncSession, organization_id, user, project_id) -> None:
    """La obra para la que se pide material: una que la persona **trabaja** hoy
    (el técnico anterior la ve en solo lectura) y que no esté cerrada; material
    para una obra cerrada se carga a un costo que ya nadie revisa (ataque del 24
    oct, hallazgos A3 y A4)."""
    from app.modules.field_ops.access import get_workable_project
    from app.modules.field_ops.installation import CLOSED_STATUSES

    project = await get_workable_project(db, organization_id=organization_id, user=user, project_id=project_id)
    if project.status in CLOSED_STATUSES:
        raise ConflictError("La obra ya está cerrada: no se pide material para ella.", code="project_closed")


async def _check_refs(db: AsyncSession, organization_id, user, data: dict) -> None:
    """La obra tiene que ser una que la persona trabaja y el técnico, una persona
    activa de la organización: nada de ids ajenos colados en la orden."""
    from app.modules.users.models import User, UserStatus

    if data.get("project_id"):
        await _check_project(db, organization_id, user, data["project_id"])
    tecnico_id = data.get("technician_user_id")
    if tecnico_id and tecnico_id != user.id:
        tecnico = await db.get(User, tecnico_id)
        if tecnico is None or tecnico.organization_id != organization_id or tecnico.status != UserStatus.active:
            raise InvalidInputError("El técnico no existe o no está activo.", code="invalid_technician")


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
            "section": (linea.get("section") or "").strip() or None,
            "is_required": bool(linea.get("is_required")),
            "sort_order": posicion,
        })
    return limpias


async def _omisiones(db, organization_id, omisiones: list[dict] | None) -> list[dict]:
    """Los obligatorios de la lista que quien arma la orden quitó. Cada uno
    necesita su motivo: es lo que quien autoriza revisa («ya hay en la
    camioneta», «este trabajo no lleva disconnect»…)."""
    limpias = []
    for omision in omisiones or []:
        motivo = (omision.get("reason") or "").strip()
        if not motivo:
            raise InvalidInputError("Para quitar un renglón obligatorio hay que decir por qué.",
                                    code="omission_reason_required")
        item = await _item_for_line(db, organization_id, omision["item_id"])
        limpias.append({"item_id": str(item.id), "item_name": item.name,
                        "spec_label": (omision.get("spec_label") or "").strip() or None, "reason": motivo})
    return limpias


async def create_order(db: AsyncSession, *, organization_id, user, data: dict) -> WarehouseReleaseOrder:
    lineas = _normalizar_lineas(data["lines"])
    for linea in lineas:
        await _item_for_line(db, organization_id, linea["item_id"])
    await _check_refs(db, organization_id, user, data)
    omisiones = await _omisiones(db, organization_id, data.get("omissions"))

    ubicacion = await wh.get_location(db, organization_id, data["location_id"]) if data.get("location_id") \
        else await wh.default_location(db, organization_id)
    # El material de una obra es para su técnico responsable: cuando la oficina
    # lo pide desde la obra, la orden queda a nombre de él, que es quien la ve en
    # su celular y marca «lo llevo».
    tecnico = data.get("technician_user_id")
    if not tecnico and data.get("project_id"):
        from app.modules.field_ops.models import Project

        tecnico = (await db.execute(select(Project.primary_technician_user_id).where(
            Project.id == data["project_id"], Project.organization_id == organization_id))).scalar_one_or_none()
    order = WarehouseReleaseOrder(
        organization_id=organization_id, status=ReleaseStatus.BORRADOR, location_id=ubicacion.id,
        project_id=data.get("project_id"), technician_user_id=tecnico or user.id,
        requested_by_user_id=user.id, needed_on=data.get("needed_on"),
        note=(data.get("note") or "").strip() or None, omissions=omisiones,
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
    order = await get_own_draft(db, organization_id, user, order_id)
    if order.status != ReleaseStatus.BORRADOR:
        raise InvalidInputError("Una orden ya enviada no se edita; recházala y haz otra.",
                                code="release_not_editable")
    lineas = _normalizar_lineas(data["lines"])
    for linea in lineas:
        await _item_for_line(db, organization_id, linea["item_id"])
    await _check_refs(db, organization_id, user, data)
    order.omissions = await _omisiones(db, organization_id, data.get("omissions"))

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
    order = await get_own_draft(db, organization_id, user, order_id)
    if order.status != ReleaseStatus.BORRADOR:
        raise InvalidInputError("Solo un borrador se manda a autorizar.", code="release_not_draft")
    if order.project_id:
        # El borrador se armó cuando la obra era suya; si rotó o se cerró, ya no sale.
        await _check_project(db, organization_id, user, order.project_id)
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
    order = await get_order(db, organization_id, order_id, for_update=True)
    if order.status != ReleaseStatus.POR_AUTORIZAR:
        raise InvalidInputError("Esta orden no está esperando autorización.", code="release_not_pending")
    # Separación de funciones: quien pide el material no se lo autoriza.
    if user.id in (order.requested_by_user_id, order.technician_user_id):
        raise ForbiddenError("Otra persona debe autorizar esta salida: tú la pediste.",
                             code="release_self_authorization")
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
    order = await get_order(db, organization_id, order_id, for_update=True)
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


async def deliver_order(db: AsyncSession, *, organization_id, user, order_id, note: str | None = None,
                        quantities: dict | None = None, serials: dict | None = None) -> dict:
    """Entrega el material: baja el saldo y carga lo entregado a la obra.

    `quantities` ({id de línea: cantidad}) es lo que Bodega confirma renglón por
    renglón (fase 2 del plan de cierre); sin él se entrega lo pedido. Nunca sale
    más de lo pedido ni más de lo que hay. Devuelve la orden y la lista de
    faltantes. Sin existencia no se bloquea (D-BOD-4).

    `serials` ({id de línea: [seriales]}) es obligatorio para los artículos con
    serial: uno por unidad que sale (D-007).
    """
    order = await get_order(db, organization_id, order_id, for_update=True)
    if order.status != ReleaseStatus.AUTORIZADA:
        raise InvalidInputError("Solo se entrega material de una orden autorizada.",
                                code="release_not_authorized")
    lineas = (await lines_of(db, organization_id, [order.id])).get(order.id, [])
    confirmadas = {str(k): v for k, v in (quantities or {}).items()}
    ajenas = set(confirmadas) - {str(l.id) for l in lineas}
    if ajenas:
        raise InvalidInputError("Una de las cantidades no es de esta orden.", code="release_line_not_found")
    seriales = {str(k): v for k, v in (serials or {}).items()}
    if set(seriales) - {str(l.id) for l in lineas}:
        raise InvalidInputError("Uno de los seriales no es de esta orden.", code="release_line_not_found")
    articulos = {i.id: i for i in (await db.execute(select(WarehouseItem).where(
        WarehouseItem.id.in_({l.item_id for l in lineas})))).scalars().all()} if lineas else {}
    ubicacion = await wh.get_location(db, organization_id, order.location_id)
    hoy = await org_today(db, organization_id)

    faltantes: list[dict] = []
    entregado_alguna = False
    for linea in lineas:
        pedida = _q(linea.quantity_requested)
        a_entregar = pedida
        if str(linea.id) in confirmadas:
            a_entregar = _q(confirmadas[str(linea.id)])
            if a_entregar < ZERO or a_entregar > pedida:
                raise InvalidInputError(f"Se entrega entre 0 y {pedida} de lo pedido en cada renglón.",
                                        code="invalid_delivered_quantity")
        disponible = await wh.stock_quantity(db, organization_id, item_id=linea.item_id,
                                             location_id=ubicacion.id)
        entregada = min(a_entregar, disponible) if disponible > ZERO else ZERO
        linea.quantity_delivered = _q(entregada)
        if entregada <= ZERO:
            motivo = "Bodega no lo entregó." if a_entregar <= ZERO else "No había existencia en bodega."
            faltantes.append({"line_id": str(linea.id), "item_id": str(linea.item_id),
                              "pedida": str(pedida), "entregada": "0.00", "motivo": motivo})
            continue
        if entregada < pedida:
            motivo = (f"Solo había {_q(entregada)} de {pedida}." if entregada < a_entregar
                      else f"Bodega entregó {_q(entregada)} de {pedida}.")
            faltantes.append({"line_id": str(linea.id), "item_id": str(linea.item_id),
                              "pedida": str(pedida), "entregada": str(_q(entregada)), "motivo": motivo})
        entregado_alguna = True
        movimiento = await wh.record_movement(
            db, organization_id=organization_id, user=user, item_id=linea.item_id, location_id=ubicacion.id,
            movement_type=MovementType.SALIDA, quantity=entregada,
            # El costo del día de la entrega: sin él, el costo de una obra ya
            # cerrada cambiaba al editar el costo del catálogo (D-018).
            unit_cost=articulos[linea.item_id].unit_cost if linea.item_id in articulos else None,
            reference=order.number or f"Orden {order.id}", note=linea.notes,
            project_id=order.project_id, movement_date=hoy,
            # La clave lleva la línea: reintentar la entrega devuelve el mismo
            # movimiento en vez de descontar otra vez.
            source_key=f"release:{order.number}:line:{linea.id}", commit=False)
        if order.project_id:
            await _cargar_a_la_obra(db, organization_id=organization_id, order=order, line_id=linea.id,
                                    item_id=linea.item_id, cantidad=_q(entregada))
        articulo = articulos.get(linea.item_id)
        if articulo is not None and articulo.has_serial:
            from app.modules.warehouse import serials as serial_svc

            await serial_svc.deliver(db, organization_id=organization_id, user=user, item=articulo,
                                     serials=seriales.get(str(linea.id)), cantidad=_q(entregada),
                                     location_id=ubicacion.id, order=order, line=linea)
        elif seriales.get(str(linea.id)):
            raise InvalidInputError(f"«{articulo.name if articulo else 'El artículo'}» no lleva serial.",
                                    code="serials_not_expected")

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
# «Lo llevo»: la checklist del técnico al cargar la camioneta (fase 2)
# ---------------------------------------------------------------------------

async def mark_loaded(db: AsyncSession, *, organization_id, user, order_id, line_id, loaded: bool) -> WarehouseReleaseOrder:
    """El técnico marca (o desmarca) que el renglón ya va en la camioneta.

    Solo sobre una orden entregada y solo lo que de verdad salió de bodega: lo
    que no se entregó no se puede cargar. La marca es del técnico de la orden o
    de quien la pidió; Bodega (`warehouse.manage`) puede corregirla.
    """
    from app.api.deps import get_effective_permissions

    order = await get_order(db, organization_id, order_id)
    if user.id not in (order.requested_by_user_id, order.technician_user_id) \
            and "warehouse.manage" not in get_effective_permissions(user):
        raise ForbiddenError("Solo el técnico de la orden marca lo que carga.", code="release_not_owner")
    if order.status != ReleaseStatus.ENTREGADA:
        raise InvalidInputError("Se marca lo que se carga cuando la orden ya está entregada.",
                                code="release_not_delivered")
    linea = next((l for l in (await lines_of(db, organization_id, [order.id])).get(order.id, [])
                  if str(l.id) == str(line_id)), None)
    if linea is None:
        raise NotFoundError("El renglón no es de esta orden.", code="release_line_not_found")
    if loaded and _q(linea.quantity_delivered or 0) <= ZERO:
        raise InvalidInputError("Ese renglón no se entregó: no hay qué cargar.", code="release_line_not_delivered")
    linea.loaded_at = _now() if loaded else None
    linea.loaded_by_user_id = user.id if loaded else None
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.release_line_loaded", entity_type="warehouse_release_order",
                             entity_id=str(order.id), after_data={"line_id": str(linea.id), "loaded": loaded})
    await db.commit()
    await db.refresh(order)
    return order


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
    from app.modules.warehouse import serials as serial_svc

    seriales = await serial_svc.of_lines(db, organization_id, [l.id for ls in agrupadas.values() for l in ls])
    return [order_out(o, agrupadas.get(o.id, []), items=items, location_name=ubicaciones.get(o.location_id),
                      serials=seriales) for o in orders]


def line_out(linea: WarehouseReleaseLine, *, item: WarehouseItem | None = None,
             serials: list[str] | None = None) -> dict:
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
        "section": linea.section, "is_required": linea.is_required,
        "loaded": linea.loaded_at is not None,
        "loaded_at": linea.loaded_at.isoformat() if linea.loaded_at else None,
        "has_serial": bool(item.has_serial) if item else False,
        "serials": serials or [],
    }


def _carga(lineas: list[WarehouseReleaseLine]) -> dict:
    """Cuánto de lo entregado ya va en la camioneta, y qué obligatorios faltan."""
    entregadas = [l for l in lineas if _q(l.quantity_delivered or 0) > ZERO]
    return {
        "loadable": len(entregadas),
        "loaded": sum(1 for l in entregadas if l.loaded_at is not None),
        "required_pending": sum(1 for l in entregadas if l.is_required and l.loaded_at is None),
    }


def order_out(order: WarehouseReleaseOrder, lineas: list[WarehouseReleaseLine], *, items: dict | None = None,
              location_name: str | None = None, serials: dict | None = None) -> dict:
    catalogo, por_linea = items or {}, serials or {}
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
        "omissions": order.omissions or [],
        "loading": _carga(lineas) if order.status == ReleaseStatus.ENTREGADA else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "lines": [line_out(l, item=catalogo.get(l.item_id), serials=por_linea.get(l.id)) for l in lineas],
    }


async def pending_count(db: AsyncSession, organization_id) -> int:
    """Cuántas órdenes esperan autorización: el número que ve el autorizador."""
    return int((await db.execute(select(func.count()).select_from(WarehouseReleaseOrder).where(
        WarehouseReleaseOrder.organization_id == organization_id,
        WarehouseReleaseOrder.status == ReleaseStatus.POR_AUTORIZAR))).scalar_one())
