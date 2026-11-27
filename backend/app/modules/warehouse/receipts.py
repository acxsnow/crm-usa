"""Recepción de compras en bodega (cuestionario de bodega, respuestas 3 y 6).

Cómo se comporta:

- El supervisor (Administración, D-BOD-5) anota qué se pidió al proveedor y lo
  que llegó. Si llegó todo, se recibe de una vez; si llegaron 8 de 10, quedan
  2 pendientes y la recepción sigue abierta hasta que lleguen o se cierre con
  el faltante y su motivo.
- Cada llegada es una `entrada` del libro con la clave `receipt-line:…`, así
  que el saldo y el libro nunca se separan (todo pasa por `record_movement`).
- El costo de cada unidad es el de la factura más su parte del impuesto y del
  envío (repartidos según el valor de cada renglón). Con ese costo se
  recalcula el promedio ponderado del artículo.
- En contabilidad, lo recibido va a Inventario contra «Compras recibidas por
  facturar». Cuando Contabilidad asocia la factura del proveedor, esa factura
  salda la cuenta puente en lugar de cargar gastos (`accounting/posting.py`).
- Los equipos que se compran para una obra no pasan por aquí: van directo a la
  obra con la factura del proveedor (D-BOD-3).
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import ZERO, to_money
from app.modules.warehouse import service as wh
from app.modules.warehouse.catalogs import ITEM_UNITS, RECEIPT_STATUSES, MovementType, ReceiptStatus
from app.modules.warehouse.models import (
    WarehouseItem,
    WarehouseLocation,
    WarehouseMovement,
    WarehouseReceipt,
    WarehouseReceiptLine,
)
from app.shared.audit import record_audit_event
from app.shared.decimals import to_quantity
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

MAX_LINES = 200


def _now() -> datetime:
    return datetime.now(timezone.utc)


def line_key(line_id, n: int) -> str:
    """La llegada número `n` de un renglón. El prefijo lo reconoce contabilidad."""
    return f"receipt-line:{line_id}:{n}"


def _pending(line: WarehouseReceiptLine) -> Decimal:
    return max(to_quantity(line.ordered_quantity) - to_quantity(line.received_quantity), ZERO)


def _subtotal(receipt: WarehouseReceipt) -> Decimal:
    return to_money(sum((to_quantity(l.ordered_quantity) * to_money(l.unit_cost) for l in receipt.lines), ZERO))


def landed_unit_cost(receipt: WarehouseReceipt, line: WarehouseReceiptLine) -> Decimal:
    """Precio de la factura más su parte proporcional del impuesto y del envío."""
    base = to_money(line.unit_cost)
    subtotal = _subtotal(receipt)
    extra = to_money(receipt.tax) + to_money(receipt.shipping)
    if subtotal <= ZERO or extra <= ZERO:
        return base
    return to_money(base * (subtotal + extra) / subtotal)


async def get_receipt(db: AsyncSession, organization_id, receipt_id) -> WarehouseReceipt:
    fila = await db.get(WarehouseReceipt, receipt_id)
    if fila is None or fila.organization_id != organization_id:
        raise NotFoundError("La recepción no existe.", code="warehouse_receipt_not_found")
    return fila


def receipts_stmt(organization_id, *, status: str | None = None, q: str | None = None):
    stmt = select(WarehouseReceipt).where(WarehouseReceipt.organization_id == organization_id)
    if status == "pendientes":
        stmt = stmt.where(WarehouseReceipt.status == ReceiptStatus.ABIERTA)
    elif status == "sin_factura":
        stmt = stmt.where(WarehouseReceipt.status.in_((ReceiptStatus.RECIBIDA, ReceiptStatus.CERRADA,
                                                       ReceiptStatus.ABIERTA)),
                          WarehouseReceipt.supplier_invoice_id.is_(None))
    elif status:
        stmt = stmt.where(WarehouseReceipt.status == status)
    if q:
        from app.shared.text_search import LIKE_ESCAPE, contains_pattern
        from sqlalchemy import or_

        patron = contains_pattern(q)
        stmt = stmt.where(or_(WarehouseReceipt.number.ilike(patron, escape=LIKE_ESCAPE),
                              WarehouseReceipt.document_number.ilike(patron, escape=LIKE_ESCAPE),
                              WarehouseReceipt.supplier_name.ilike(patron, escape=LIKE_ESCAPE)))
    return stmt.order_by(WarehouseReceipt.created_at.desc())


async def _supplier(db, organization_id, supplier_id):
    from app.modules.finance.models import Supplier

    s = await db.get(Supplier, supplier_id)
    if s is None or s.organization_id != organization_id:
        raise NotFoundError("El proveedor no existe.", code="supplier_not_found")
    return s


async def create_receipt(db: AsyncSession, *, organization_id, user, data: dict) -> WarehouseReceipt:
    """Crea la recepción con lo pedido. Con `received` en cada renglón (lo que
    llegó hoy) recibe en el mismo paso: el caso de todos los días."""
    from app.modules.billing.numbering import next_number

    lineas = data.get("lines") or []
    if not lineas:
        raise InvalidInputError("La recepción necesita al menos un artículo.", code="receipt_without_lines")
    if len(lineas) > MAX_LINES:
        raise InvalidInputError(f"Una recepción lleva como máximo {MAX_LINES} renglones.", code="too_many_lines")
    nombre = (data.get("supplier_name") or "").strip() or None
    proveedor = None
    if data.get("supplier_id"):
        proveedor = await _supplier(db, organization_id, data["supplier_id"])
        nombre = proveedor.name
    if not nombre:
        raise InvalidInputError("Indica el proveedor.", code="supplier_required")
    if data.get("location_id"):
        ubicacion = await wh.get_location(db, organization_id, data["location_id"])
        if not ubicacion.active:
            raise InvalidInputError("Esa ubicación está desactivada.", code="location_inactive")
    else:
        ubicacion = await wh.default_location(db, organization_id)
    impuesto = wh._price(data.get("tax") or "0", "El impuesto")
    envio = wh._price(data.get("shipping") or "0", "El envío")

    vistos, renglones = set(), []
    for i, l in enumerate(lineas):
        item = await wh.get_item(db, organization_id, l["item_id"])
        if not item.active:
            raise InvalidInputError(f"«{item.name}» está desactivado.", code="item_inactive")
        if item.id in vistos:
            raise InvalidInputError(f"«{item.name}» aparece dos veces; suma las cantidades en un renglón.",
                                    code="receipt_duplicate_item")
        vistos.add(item.id)
        pedido = to_quantity(l["ordered_quantity"])
        if pedido <= ZERO:
            raise InvalidInputError(f"La cantidad pedida de «{item.name}» debe ser mayor que cero.",
                                    code="invalid_quantity")
        renglones.append(WarehouseReceiptLine(
            organization_id=organization_id, item_id=item.id, sort_order=i, ordered_quantity=pedido,
            received_quantity=ZERO, unit_cost=wh._price(l.get("unit_cost") or "0")))

    hoy = await wh._today(db, organization_id)
    receipt = WarehouseReceipt(
        organization_id=organization_id,
        number=await next_number(db, organization_id=organization_id, series="REC", year=hoy.year),
        supplier_id=proveedor.id if proveedor else None, supplier_name=nombre,
        document_number=(data.get("document_number") or "").strip() or None,
        document_date=data.get("document_date"), location_id=ubicacion.id, tax=impuesto, shipping=envio,
        status=ReceiptStatus.ABIERTA, note=(data.get("note") or "").strip() or None,
        created_by_user_id=user.id, lines=renglones)
    db.add(receipt)
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.receipt_created", entity_type="warehouse_receipt",
                             entity_id=str(receipt.id),
                             after_data={"number": receipt.number, "supplier": nombre, "lines": len(renglones)})

    llegadas = [{"line_id": r.id, "quantity": l.get("received"), "serials": l.get("serials")}
                for r, l in zip(renglones, lineas) if l.get("received") not in (None, "") and
                to_quantity(l.get("received")) > ZERO]
    if llegadas:
        await _receive(db, organization_id=organization_id, user=user, receipt=receipt, lines=llegadas,
                       received_on=data.get("received_on"), note=None)
    await db.commit()
    return await get_receipt(db, organization_id, receipt.id)


async def _receive(db, *, organization_id, user, receipt: WarehouseReceipt, lines: list[dict], received_on, note):
    if receipt.status != ReceiptStatus.ABIERTA:
        raise ConflictError("Esta recepción ya no está abierta.", code="receipt_not_open")
    por_id = {l.id: l for l in receipt.lines}
    vistos = set()
    for l in lines:
        renglon = por_id.get(l["line_id"])
        if renglon is None:
            raise NotFoundError("Ese renglón no es de esta recepción.", code="receipt_line_not_found")
        if renglon.id in vistos:
            raise InvalidInputError("Un renglón aparece dos veces.", code="receipt_duplicate_line")
        vistos.add(renglon.id)
    referencia = " · ".join(x for x in (receipt.number, receipt.document_number) if x)
    for l in lines:
        renglon = por_id[l["line_id"]]
        cantidad = to_quantity(l["quantity"])
        if cantidad <= ZERO:
            raise InvalidInputError("La cantidad recibida debe ser mayor que cero.", code="invalid_quantity")
        pendiente = _pending(renglon)
        item = await db.get(WarehouseItem, renglon.item_id)
        if cantidad > pendiente:
            raise InvalidInputError(
                f"De «{item.name}» faltan {pendiente} por llegar; no se pueden recibir {cantidad}. "
                "Si llegó de más, corrige lo pedido en una recepción nueva.", code="receipt_exceeds_pending")
        n = (await db.execute(select(func.count()).select_from(WarehouseMovement).where(
            WarehouseMovement.organization_id == organization_id,
            WarehouseMovement.source_key.like(f"receipt-line:{renglon.id}:%")))).scalar_one() + 1
        costo = landed_unit_cost(receipt, renglon)
        await wh.apply_average_cost(db, organization_id, item=item, quantity=cantidad, unit_cost=costo)
        await wh.record_movement(
            db, organization_id=organization_id, user=user, item_id=item.id, location_id=receipt.location_id,
            movement_type=MovementType.ENTRADA, quantity=cantidad, unit_cost=costo, reference=referencia[:120],
            note=note, movement_date=received_on, source_key=line_key(renglon.id, n), commit=False,
            serials=l.get("serials") or None)
        renglon.received_quantity = to_quantity(renglon.received_quantity) + cantidad
    if all(_pending(r) == ZERO for r in receipt.lines):
        receipt.status = ReceiptStatus.RECIBIDA
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.receipt_received", entity_type="warehouse_receipt",
                             entity_id=str(receipt.id),
                             after_data={"lines": [{"line_id": str(l["line_id"]), "quantity": str(l["quantity"])}
                                                   for l in lines], "status": receipt.status})


async def receive(db: AsyncSession, *, organization_id, user, receipt_id, lines: list[dict], received_on=None,
                  note: str | None = None) -> WarehouseReceipt:
    """Una llegada más de lo pendiente."""
    receipt = (await db.execute(select(WarehouseReceipt).where(
        WarehouseReceipt.id == receipt_id, WarehouseReceipt.organization_id == organization_id
    ).with_for_update())).scalar_one_or_none()
    if receipt is None:
        raise NotFoundError("La recepción no existe.", code="warehouse_receipt_not_found")
    if not lines:
        raise InvalidInputError("Indica qué llegó.", code="receipt_without_lines")
    await _receive(db, organization_id=organization_id, user=user, receipt=receipt, lines=lines,
                   received_on=received_on, note=(note or "").strip() or None)
    await db.commit()
    return await get_receipt(db, organization_id, receipt.id)


async def close(db: AsyncSession, *, organization_id, user, receipt_id, reason: str) -> WarehouseReceipt:
    """El proveedor no va a mandar lo que falta: se cierra con el motivo. Si no
    llegó nada, la recepción queda anulada."""
    receipt = await get_receipt(db, organization_id, receipt_id)
    if receipt.status != ReceiptStatus.ABIERTA:
        raise ConflictError("Esta recepción ya no está abierta.", code="receipt_not_open")
    motivo = (reason or "").strip()
    if not motivo:
        raise InvalidInputError("Indica por qué se cierra con faltante.", code="close_reason_required")
    nada = all(to_quantity(l.received_quantity) == ZERO for l in receipt.lines)
    receipt.status = ReceiptStatus.ANULADA if nada else ReceiptStatus.CERRADA
    receipt.close_reason, receipt.closed_at, receipt.closed_by_user_id = motivo, _now(), user.id
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.receipt_closed", entity_type="warehouse_receipt",
                             entity_id=str(receipt.id), after_data={"status": receipt.status, "reason": motivo})
    await db.commit()
    return await get_receipt(db, organization_id, receipt.id)


def invoice_candidates_stmt(organization_id, receipt: WarehouseReceipt):
    """Las facturas del mismo proveedor que se pueden asociar (no anuladas).
    Sin proveedor registrado no hay ninguna."""
    from sqlalchemy import false

    from app.modules.finance.models import SupplierInvoice

    stmt = select(SupplierInvoice).where(SupplierInvoice.organization_id == organization_id,
                                         SupplierInvoice.status != "void")
    stmt = stmt.where(SupplierInvoice.supplier_id == receipt.supplier_id) if receipt.supplier_id else stmt.where(false())
    return stmt.order_by(SupplierInvoice.invoice_date.desc(), SupplierInvoice.id)


def invoice_candidates_out(filas) -> list[dict]:
    return [{"id": str(f.id), "number": f.number, "invoice_date": f.invoice_date.isoformat(),
             "total": str(to_money(f.total)), "status": f.status} for f in filas]


async def link_invoice(db: AsyncSession, *, organization_id, user, receipt_id, supplier_invoice_id) -> WarehouseReceipt:
    """Contabilidad asocia la factura del proveedor (o la quita con `None`)."""
    from app.modules.finance.models import SupplierInvoice

    receipt = await get_receipt(db, organization_id, receipt_id)
    if receipt.status == ReceiptStatus.ANULADA:
        raise ConflictError("La recepción está anulada.", code="receipt_void")
    antes = receipt.supplier_invoice_id
    if supplier_invoice_id is not None:
        f = await db.get(SupplierInvoice, supplier_invoice_id)
        if f is None or f.organization_id != organization_id:
            raise NotFoundError("La factura del proveedor no existe.", code="supplier_invoice_not_found")
        if f.status == "void":
            raise ConflictError("Esa factura está anulada.", code="supplier_invoice_void")
        if receipt.supplier_id is None:
            raise InvalidInputError("Esta recepción no tiene un proveedor registrado; elige el proveedor primero.",
                                    code="receipt_without_supplier")
        if f.supplier_id != receipt.supplier_id:
            raise InvalidInputError("La factura es de otro proveedor.", code="supplier_mismatch")
    receipt.supplier_invoice_id = supplier_invoice_id
    receipt.invoice_linked_at = _now() if supplier_invoice_id else None
    receipt.invoice_linked_by_user_id = user.id if supplier_invoice_id else None
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.receipt_invoice_linked", entity_type="warehouse_receipt",
                             entity_id=str(receipt.id),
                             before_data={"supplier_invoice_id": str(antes) if antes else None},
                             after_data={"supplier_invoice_id": str(supplier_invoice_id) if supplier_invoice_id
                                         else None})
    await db.commit()
    return await get_receipt(db, organization_id, receipt.id)


async def set_supplier(db: AsyncSession, *, organization_id, user, receipt_id, supplier_id) -> WarehouseReceipt:
    """Pone el proveedor registrado a una recepción que se hizo con el nombre a
    mano (para poder asociarle la factura)."""
    receipt = await get_receipt(db, organization_id, receipt_id)
    if receipt.supplier_invoice_id is not None:
        raise ConflictError("Ya tiene factura asociada; quítala antes de cambiar el proveedor.",
                            code="receipt_invoice_linked")
    s = await _supplier(db, organization_id, supplier_id)
    receipt.supplier_id, receipt.supplier_name = s.id, s.name
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="warehouse.receipt_supplier_set", entity_type="warehouse_receipt",
                             entity_id=str(receipt.id), after_data={"supplier_id": str(s.id)})
    await db.commit()
    return await get_receipt(db, organization_id, receipt.id)


async def receipts_out(db: AsyncSession, organization_id, receipts: list[WarehouseReceipt], *,
                       with_costs: bool = True) -> list[dict]:
    if not receipts:
        return []
    from app.modules.finance.models import SupplierInvoice
    from app.modules.users.models import User

    item_ids = {l.item_id for r in receipts for l in r.lines}
    items = {i.id: i for i in (await db.execute(select(WarehouseItem).where(
        WarehouseItem.id.in_(item_ids)))).scalars().all()} if item_ids else {}
    lugares = {l.id: l.name for l in (await db.execute(select(WarehouseLocation).where(
        WarehouseLocation.id.in_({r.location_id for r in receipts})))).scalars().all()}
    facturas_ids = {r.supplier_invoice_id for r in receipts if r.supplier_invoice_id}
    facturas = {f.id: f for f in (await db.execute(select(SupplierInvoice).where(
        SupplierInvoice.id.in_(facturas_ids)))).scalars().all()} if facturas_ids else {}
    users_ids = {r.created_by_user_id for r in receipts if r.created_by_user_id}
    nombres = dict((await db.execute(select(User.id, User.full_name).where(
        User.id.in_(users_ids)))).all()) if users_ids else {}

    salida = []
    for r in receipts:
        lineas = []
        recibido = ZERO
        for l in r.lines:
            item = items.get(l.item_id)
            costo = landed_unit_cost(r, l)
            valor = to_money(to_quantity(l.received_quantity) * costo)
            recibido += valor
            lineas.append({
                "id": str(l.id), "item_id": str(l.item_id), "item_name": item.name if item else None,
                "sku": item.sku if item else None, "has_serial": bool(item and item.has_serial),
                "unit_label": ITEM_UNITS.get(item.unit, item.unit) if item else None,
                "ordered_quantity": str(to_quantity(l.ordered_quantity)),
                "received_quantity": str(to_quantity(l.received_quantity)),
                "pending_quantity": str(_pending(l)),
                "unit_cost": str(to_money(l.unit_cost)), "landed_unit_cost": str(costo),
                "received_value": str(valor),
            })
        f = facturas.get(r.supplier_invoice_id) if r.supplier_invoice_id else None
        fila = {
            "id": str(r.id), "number": r.number, "status": r.status,
            "status_label": RECEIPT_STATUSES.get(r.status, r.status),
            "supplier_id": str(r.supplier_id) if r.supplier_id else None, "supplier_name": r.supplier_name,
            "document_number": r.document_number,
            "document_date": r.document_date.isoformat() if r.document_date else None,
            "location_id": str(r.location_id), "location_name": lugares.get(r.location_id),
            "tax": str(to_money(r.tax)), "shipping": str(to_money(r.shipping)),
            "subtotal": str(_subtotal(r)),
            "total": str(to_money(_subtotal(r) + to_money(r.tax) + to_money(r.shipping))),
            "received_value": str(to_money(recibido)),
            "note": r.note, "close_reason": r.close_reason,
            "closed_at": r.closed_at.isoformat() if r.closed_at else None,
            "supplier_invoice_id": str(r.supplier_invoice_id) if r.supplier_invoice_id else None,
            "supplier_invoice_number": f.number if f else None,
            "supplier_invoice_total": str(to_money(f.total)) if f else None,
            "created_by_name": nombres.get(r.created_by_user_id),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "pending_lines": sum(1 for l in r.lines if _pending(l) > ZERO),
            "lines": lineas,
        }
        if not with_costs:
            for k in ("tax", "shipping", "subtotal", "total", "received_value", "supplier_invoice_total"):
                fila.pop(k, None)
            for l in fila["lines"]:
                for k in ("unit_cost", "landed_unit_cost", "received_value"):
                    l.pop(k, None)
        salida.append(fila)
    return salida
