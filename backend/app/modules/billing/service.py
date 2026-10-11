"""Facturas: el documento común al cobro de rebate y al trabajo particular
(spec D6.1, D6.8).

- Dinero en `Decimal` (billing/money.py) y numeración por serie y año
  (billing/numbering.py).
- El estado del pago no se guarda: sale de los pagos y de la fecha de la
  organización (`field_ops/clock.py`), así que no hace falta una tarea que lo
  "actualice" y nunca queda desincronizado (cierra COD-10).
- Una factura emitida no se edita; se anula y se emite otra (D6.3).
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import DocumentStatus, Invoice, InvoiceKind, InvoiceLine, InvoicePayment, LINE_KINDS
from app.modules.billing.money import ZERO, money_sum, to_money
from app.modules.billing.numbering import next_number
from app.modules.field_ops.clock import org_today
from app.modules.field_ops.models import Project
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

ALLOWED_ATTACHMENT_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif", "application/pdf"}
MAX_ATTACHMENT_SIZE_BYTES = 15 * 1024 * 1024
MAX_ATTACHMENTS_PER_INVOICE = 20
DUE_SOON_DAYS = 7


def validate_attachment(*, content_type: str | None, size_bytes: int, existing_count: int) -> None:
    if content_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
        raise InvalidInputError(
            "Solo se aceptan fotos, escaneos o PDF como soporte de la factura.", code="invalid_attachment_type"
        )
    if size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
        raise InvalidInputError("El archivo supera el límite de 15 MB.", code="attachment_too_large")
    if existing_count >= MAX_ATTACHMENTS_PER_INVOICE:
        raise InvalidInputError(
            "Esta factura ya tiene el máximo de adjuntos permitidos.", code="too_many_attachments"
        )


# ---------------------------------------------------------------------------
# Líneas y totales
# ---------------------------------------------------------------------------

def build_lines(lines: list[dict], line_cls=InvoiceLine) -> list:
    """Arma las líneas calculando el importe en el servidor: el cliente manda
    cantidad y precio, nunca el importe."""
    armadas = []
    for orden, datos in enumerate(lines):
        kind = datos.get("kind") or "service"
        if kind not in LINE_KINDS:
            raise InvalidInputError(f"El tipo de línea «{kind}» no existe.", code="unknown_line_kind")
        cantidad = to_money(datos.get("quantity", 1))
        precio = to_money(datos["unit_price"])
        if cantidad <= 0:
            raise InvalidInputError("La cantidad de cada línea debe ser mayor que cero.", code="invalid_quantity")
        if precio < 0:
            raise InvalidInputError("El precio de una línea no puede ser negativo.", code="invalid_price")
        armadas.append(
            line_cls(
                sort_order=orden, kind=kind, description=datos["description"],
                service_code=datos.get("service_code"), quantity=cantidad, unit_price=precio,
                amount=to_money(cantidad * precio),
            )
        )
    return armadas


def collectible_amount(kind: str, lines: list[InvoiceLine]) -> Decimal:
    """Lo cobrable (ver `Invoice`): en rebate, los rebates; en particular, el
    subtotal menos los rebates."""
    rebates = money_sum(l.amount for l in lines if l.kind == "rebate")
    if kind == InvoiceKind.rebate:
        return rebates
    return money_sum(l.amount for l in lines if l.kind != "rebate") - rebates


# ---------------------------------------------------------------------------
# Crear, consultar y pagar
# ---------------------------------------------------------------------------

async def create_invoice(db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, data: dict) -> Invoice:
    """Factura particular emitida (la de rebate la crea el cobro, D6.3).

    Acepta líneas o, como las facturas anteriores al módulo 6, solo un monto:
    en ese caso se guarda como una línea de servicio para que el documento
    tenga siempre detalle."""
    project = None
    if data.get("project_id"):
        project = (
            await db.execute(
                select(Project).where(Project.id == data["project_id"], Project.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise NotFoundError("El proyecto no existe.", code="project_not_found")
    customer_id = data.get("customer_id") or (project.customer_id if project else None)
    if customer_id is None:
        raise InvalidInputError("Indica el cliente o el proyecto de la factura.", code="invoice_customer_required")

    lineas_datos = data.get("lines") or []
    if not lineas_datos:
        if data.get("amount") is None:
            raise InvalidInputError("La factura necesita líneas o un monto.", code="invoice_amount_required")
        lineas_datos = [{"kind": "service", "description": data.get("notes") or "Servicio", "quantity": 1,
                         "unit_price": data["amount"]}]
    lineas = build_lines(lineas_datos)
    monto = collectible_amount(InvoiceKind.particular, lineas)
    if monto <= 0:
        raise InvalidInputError("El total de la factura debe ser mayor que cero.", code="invoice_amount_invalid")

    hoy = await org_today(db, organization_id)
    numero = await next_number(db, organization_id=organization_id, series="FAC", year=hoy.year)
    invoice = Invoice(
        organization_id=organization_id, kind=InvoiceKind.particular, customer_id=customer_id,
        project_id=project.id if project else None, case_id=project.case_id if project else None,
        invoice_number=numero, funder_program=data.get("funder_program"), amount=monto,
        document_status=DocumentStatus.issued, issue_date=data.get("issue_date") or hoy,
        due_date=data.get("due_date"), notes=data.get("notes"), lines=lineas,
    )
    db.add(invoice)
    await db.flush()
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="invoices.created", entity_type="Invoice", entity_id=str(invoice.id),
        after_data={"invoice_number": numero, "amount": str(monto), "kind": invoice.kind},
    )
    await db.commit()
    return await get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice.id)


async def get_invoice_or_404(db: AsyncSession, *, organization_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    invoice = (
        await db.execute(select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id))
    ).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("La factura no existe.", code="invoice_not_found")
    return invoice


async def list_invoices(
    db: AsyncSession, *, organization_id: uuid.UUID, status_filter: str | None = None,
    project_id: uuid.UUID | None = None, kind: str | None = None,
) -> tuple[list[Invoice], date]:
    """Devuelve las facturas y el "hoy" de la organización con el que se
    calculó su estado de pago, para que quien serializa use el mismo día."""
    stmt = select(Invoice).where(Invoice.organization_id == organization_id).order_by(Invoice.created_at.desc())
    if project_id:
        stmt = stmt.where(Invoice.project_id == project_id)
    if kind:
        stmt = stmt.where(Invoice.kind == kind)
    invoices = list((await db.execute(stmt)).scalars().all())
    hoy = await org_today(db, organization_id)
    if status_filter:
        invoices = [i for i in invoices if i.payment_status_on(hoy) == status_filter]
    return invoices, hoy


async def mark_sent(db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    """Registra que la factura se le envió al cliente o al programa. No cambia
    su estado: el estado de pago lo dicen los pagos."""
    invoice = await get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)
    if invoice.document_status != DocumentStatus.issued:
        raise ConflictError("Solo una factura emitida se puede marcar como enviada.", code="invoice_not_issued")
    invoice.sent_at = datetime.now(timezone.utc)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="invoices.sent", entity_type="Invoice", entity_id=str(invoice.id),
    )
    await db.commit()
    return await get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice.id)


async def record_payment(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, invoice_id: uuid.UUID, data: dict,
) -> Invoice:
    invoice = await get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)
    if invoice.document_status != DocumentStatus.issued:
        raise ConflictError("Solo se registran pagos sobre una factura emitida.", code="invoice_not_issued")
    monto = to_money(data["amount"])
    if monto <= 0:
        raise InvalidInputError("El pago debe ser mayor que cero.", code="invalid_payment_amount")

    invoice.payments.append(InvoicePayment(
        amount=monto, paid_at=data["paid_at"], method=data.get("method"),
        reference=data.get("reference"), notes=data.get("notes"),
    ))
    await db.flush()
    if invoice.balance <= 0 and invoice.paid_at is None:
        invoice.paid_at = datetime.now(timezone.utc)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="invoices.payment_recorded", entity_type="Invoice", entity_id=str(invoice.id),
        after_data={"amount": str(monto), "balance": str(invoice.balance)},
    )
    await db.commit()
    return await get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice.id)


async def void_invoice(db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID, invoice_id: uuid.UUID,
                       reason: str) -> Invoice:
    """Anula una factura con motivo. Una factura con pagos no se anula: el
    dinero recibido tiene que quedar contra algún documento."""
    invoice = await get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)
    if invoice.document_status == DocumentStatus.void:
        raise ConflictError("La factura ya está anulada.", code="invoice_already_void")
    if invoice.payments:
        raise ConflictError("No se puede anular una factura que tiene pagos registrados.", code="invoice_has_payments")
    if len((reason or "").strip()) < 3:
        raise InvalidInputError("Escribe el motivo de la anulación.", code="void_reason_required")
    invoice.document_status = DocumentStatus.void
    invoice.void_reason = reason.strip()
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="invoices.voided", entity_type="Invoice", entity_id=str(invoice.id),
        after_data={"reason": invoice.void_reason},
    )
    await db.commit()
    return await get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice.id)


# ---------------------------------------------------------------------------
# Borrador: la factura que sale de una cotización aceptada se ajusta y se emite
# ---------------------------------------------------------------------------

async def replace_draft_lines(db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID,
                              invoice_id: uuid.UUID, lines: list[dict]) -> Invoice:
    invoice = await get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)
    if invoice.document_status != DocumentStatus.draft:
        raise ConflictError("Una factura emitida no se edita: anúlala y emite otra.", code="invoice_not_draft")
    if not lines:
        raise InvalidInputError("La factura necesita al menos una línea.", code="invoice_lines_required")
    nuevas = build_lines(lines)
    invoice.lines.clear()
    await db.flush()
    invoice.lines.extend(nuevas)
    invoice.amount = collectible_amount(invoice.kind, nuevas)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="invoices.draft_lines_updated", entity_type="Invoice", entity_id=str(invoice.id),
        after_data={"amount": str(invoice.amount), "lines": len(nuevas)},
    )
    await db.commit()
    return await _fresh(db, organization_id, invoice.id)


async def issue_invoice(db: AsyncSession, *, organization_id: uuid.UUID, actor_id: uuid.UUID,
                        invoice_id: uuid.UUID, due_date: date | None) -> Invoice:
    """Emite un borrador: le asigna número FAC y lo congela."""
    invoice = await get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice_id)
    if invoice.document_status != DocumentStatus.draft:
        raise ConflictError("La factura ya está emitida o anulada.", code="invoice_not_draft")
    if to_money(invoice.amount) <= 0:
        raise InvalidInputError("El total de la factura debe ser mayor que cero.", code="invoice_amount_invalid")
    hoy = await org_today(db, organization_id)
    vence = due_date or invoice.due_date
    if vence is not None and vence < hoy:
        raise InvalidInputError("El vencimiento no puede ser anterior a hoy.", code="invalid_due_date")
    invoice.invoice_number = await next_number(db, organization_id=organization_id, series="FAC", year=hoy.year)
    invoice.document_status = DocumentStatus.issued
    invoice.issue_date = hoy
    invoice.due_date = vence
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=actor_id,
        action="invoices.issued", entity_type="Invoice", entity_id=str(invoice.id),
        after_data={"invoice_number": invoice.invoice_number, "amount": str(invoice.amount)},
    )
    await db.commit()
    return await _fresh(db, organization_id, invoice.id)


async def _fresh(db, organization_id, invoice_id) -> Invoice:
    return (
        await db.execute(
            select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()


# ---------------------------------------------------------------------------
# Tablero financiero y conteo de vencidas
# ---------------------------------------------------------------------------

async def finance_dashboard(db: AsyncSession, *, organization_id: uuid.UUID) -> dict:
    invoices, hoy = await list_invoices(db, organization_id=organization_id)
    emitidas = [i for i in invoices if i.document_status == DocumentStatus.issued]
    vencidas = [i for i in emitidas if i.payment_status_on(hoy) == "overdue"]
    limite = hoy + timedelta(days=DUE_SOON_DAYS)
    por_vencer = [
        i for i in emitidas
        if i.payment_status_on(hoy) in ("unpaid", "partial") and i.due_date and hoy <= i.due_date <= limite
    ]
    # Lo cobrado en el mes (programas y particulares), sumado en la base: el
    # Inicio lo mostraba trayendo todas las facturas al navegador.
    cobrado_mes = (await db.execute(
        select(func.coalesce(func.sum(InvoicePayment.amount), 0))
        .join(Invoice, Invoice.id == InvoicePayment.invoice_id)
        .where(Invoice.organization_id == organization_id,
               InvoicePayment.paid_at >= hoy.replace(day=1), InvoicePayment.paid_at <= hoy)
    )).scalar_one()
    return {
        "total_invoiced": money_sum(i.amount for i in emitidas),
        "total_paid": money_sum(i.paid_amount for i in emitidas),
        "total_outstanding": money_sum(max(i.balance, ZERO) for i in emitidas),
        "total_overdue": money_sum(i.balance for i in vencidas),
        "invoice_count": len(emitidas),
        "overdue_count": len(vencidas),
        "due_soon_count": len(por_vencer),
        "paid_this_month": money_sum([Decimal(cobrado_mes)]),
    }


async def count_overdue_invoices(db: AsyncSession) -> int:
    """Para el registro de la tarea diaria de Celery. Antes esa tarea cambiaba
    el estado a "vencida"; ahora el estado se calcula al leer, así que solo
    cuenta. Recorre todas las organizaciones a propósito: es mantenimiento y no
    devuelve contenido de ninguna."""
    from app.modules.organizations.models import Organization

    total = 0
    for org_id in (await db.execute(select(Organization.id))).scalars().all():
        invoices, hoy = await list_invoices(db, organization_id=org_id)
        total += sum(1 for i in invoices if i.payment_status_on(hoy) == "overdue")
    return total
