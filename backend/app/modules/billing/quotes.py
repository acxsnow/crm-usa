"""Trabajo particular: cotización con versiones → factura → pagos (spec D6.7).

Separado del cobro de rebate: lo paga el cliente, cuelga del cliente (y, si
aplica, de una instalación) y **nunca mueve el expediente**.

    borrador ──enviar──▶ enviada ──aceptar──▶ aceptada (crea la factura en borrador)
        ▲                   │ └──rechazar──▶ rechazada
        └──── ajustar ──────┘   (la versión anterior queda "reemplazada")

- Ajustar crea la versión siguiente con las mismas líneas para editar; la
  anterior queda como historial y ya no se toca.
- "Vencida" no se guarda: es una enviada cuya vigencia pasó, a la fecha de la
  organización.
- Aceptar crea la factura particular en borrador con las mismas líneas; se
  ajusta y se emite (número FAC) desde facturas.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import (
    DRAFT_INVOICE_NUMBER,
    DocumentStatus,
    Invoice,
    InvoiceKind,
    InvoiceLine,
    Quote,
    QuoteLine,
    QuoteStatus,
)
from app.modules.billing.numbering import next_number
from app.modules.billing.service import build_lines, collectible_amount
from app.modules.field_ops.clock import org_today
from app.shared import events as domain_events
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

MIN_REASON_LENGTH = 3


async def create_quote(db: AsyncSession, *, organization_id: uuid.UUID, user, data: dict) -> Quote:
    customer_id, project_id = await _customer_and_project(db, organization_id, data)
    lineas = _lines(data.get("lines") or [])
    hoy = await org_today(db, organization_id)
    _check_valid_until(data.get("valid_until"), hoy)
    quote = Quote(
        organization_id=organization_id, customer_id=customer_id, project_id=project_id,
        quote_number=await next_number(db, organization_id=organization_id, series="COT", year=hoy.year),
        version=1, status=QuoteStatus.draft, title=data.get("title"), valid_until=data.get("valid_until"),
        notes=data.get("notes"), created_by_user_id=user.id, lines=lineas,
    )
    db.add(quote)
    await db.flush()
    await _audit(db, organization_id, user, "quotes.created", quote, {"total": str(quote.total)})
    await db.commit()
    return await get_quote_or_404(db, organization_id=organization_id, quote_id=quote.id)


async def update_quote(db, *, organization_id, user, quote_id, changes: dict) -> Quote:
    """Solo un borrador se edita. Una enviada se ajusta con una versión nueva."""
    quote = await get_quote_or_404(db, organization_id=organization_id, quote_id=quote_id)
    if quote.status != QuoteStatus.draft:
        raise ConflictError("Solo se edita un borrador. Para cambiar una cotización enviada, ajústala "
                            "(crea la versión siguiente).", code="quote_not_draft")
    if changes.get("lines") is not None:
        nuevas = _lines(changes["lines"])
        quote.lines.clear()
        await db.flush()
        quote.lines.extend(nuevas)
    if "valid_until" in changes:
        _check_valid_until(changes["valid_until"], await org_today(db, organization_id))
    for campo in ("title", "valid_until", "notes"):
        if campo in changes:
            setattr(quote, campo, changes[campo])
    await _audit(db, organization_id, user, "quotes.updated", quote, {"total": str(quote.total)})
    await db.commit()
    return await get_quote_or_404(db, organization_id=organization_id, quote_id=quote.id)


async def send_quote(db, *, organization_id, user, quote_id) -> Quote:
    quote = await get_quote_or_404(db, organization_id=organization_id, quote_id=quote_id)
    if quote.status != QuoteStatus.draft:
        raise ConflictError("Solo se envía un borrador.", code="quote_not_draft")
    if quote.total <= 0:
        raise InvalidInputError("El total de la cotización debe ser mayor que cero.", code="quote_total_invalid")
    quote.status = QuoteStatus.sent
    quote.sent_at = datetime.now(timezone.utc)
    await _audit(db, organization_id, user, "quotes.sent", quote, {})
    await db.commit()
    domain_events.emit("quote.sent", _payload(quote, organization_id))
    return await get_quote_or_404(db, organization_id=organization_id, quote_id=quote.id)


async def revise_quote(db, *, organization_id, user, quote_id) -> Quote:
    """Crea la versión siguiente (borrador) con las mismas líneas. La versión
    de la que parte queda reemplazada y como historial."""
    quote = await get_quote_or_404(db, organization_id=organization_id, quote_id=quote_id)
    if quote.status not in (QuoteStatus.sent, QuoteStatus.rejected):
        raise ConflictError("Se ajusta una cotización enviada o rechazada; un borrador se edita directamente.",
                            code="quote_not_revisable")
    nueva = Quote(
        organization_id=organization_id, customer_id=quote.customer_id, project_id=quote.project_id,
        quote_number=quote.quote_number, version=quote.version + 1, previous_version_id=quote.id,
        status=QuoteStatus.draft, title=quote.title, valid_until=quote.valid_until, notes=quote.notes,
        created_by_user_id=user.id,
        lines=[QuoteLine(sort_order=l.sort_order, kind=l.kind, description=l.description,
                         service_code=l.service_code, quantity=l.quantity, unit_price=l.unit_price,
                         amount=l.amount) for l in quote.lines],
    )
    quote.status = QuoteStatus.superseded
    db.add(nueva)
    await db.flush()
    await _audit(db, organization_id, user, "quotes.revised", nueva, {"from_version": quote.version})
    await db.commit()
    return await get_quote_or_404(db, organization_id=organization_id, quote_id=nueva.id)


async def accept_quote(db, *, organization_id, user, quote_id) -> tuple[Quote, Invoice]:
    """El cliente aceptó: la cotización queda aceptada y nace la factura
    particular en borrador con las mismas líneas."""
    quote = await get_quote_or_404(db, organization_id=organization_id, quote_id=quote_id)
    hoy = await org_today(db, organization_id)
    estado = quote.status_on(hoy)
    if estado == "expired":
        raise ConflictError("La cotización está vencida. Ajústala con una vigencia nueva.", code="quote_expired")
    if estado != QuoteStatus.sent:
        raise ConflictError("Solo se acepta una cotización enviada.", code="quote_not_sent")
    lineas = [InvoiceLine(sort_order=l.sort_order, kind=l.kind, description=l.description,
                          service_code=l.service_code, quantity=l.quantity, unit_price=l.unit_price,
                          amount=l.amount) for l in quote.lines]
    case_id = None
    if quote.project_id:
        from app.modules.field_ops.models import Project

        case_id = (await db.execute(select(Project.case_id).where(Project.id == quote.project_id))).scalar_one()
    invoice = Invoice(
        organization_id=organization_id, kind=InvoiceKind.particular, customer_id=quote.customer_id,
        project_id=quote.project_id, case_id=case_id, quote_id=quote.id, invoice_number=DRAFT_INVOICE_NUMBER,
        amount=collectible_amount(InvoiceKind.particular, lineas), document_status=DocumentStatus.draft,
        notes=quote.notes, lines=lineas,
    )
    db.add(invoice)
    quote.status = QuoteStatus.accepted
    quote.decided_at = datetime.now(timezone.utc)
    await db.flush()
    await _audit(db, organization_id, user, "quotes.accepted", quote, {"invoice_id": str(invoice.id)})
    await db.commit()
    domain_events.emit("quote.accepted", {**_payload(quote, organization_id), "invoice_id": str(invoice.id)})
    from app.modules.billing.service import get_invoice_or_404

    return (await get_quote_or_404(db, organization_id=organization_id, quote_id=quote.id),
            await get_invoice_or_404(db, organization_id=organization_id, invoice_id=invoice.id))


async def reject_quote(db, *, organization_id, user, quote_id, reason: str) -> Quote:
    quote = await get_quote_or_404(db, organization_id=organization_id, quote_id=quote_id)
    if quote.status != QuoteStatus.sent:
        raise ConflictError("Solo se rechaza una cotización enviada.", code="quote_not_sent")
    motivo = (reason or "").strip()
    if len(motivo) < MIN_REASON_LENGTH:
        raise InvalidInputError("Escribe por qué el cliente no la aceptó.", code="quote_rejection_reason_required")
    quote.status = QuoteStatus.rejected
    quote.rejection_reason = motivo
    quote.decided_at = datetime.now(timezone.utc)
    await _audit(db, organization_id, user, "quotes.rejected", quote, {"reason": motivo})
    await db.commit()
    return await get_quote_or_404(db, organization_id=organization_id, quote_id=quote.id)


# ---------------------------------------------------------------------------
# Consultar
# ---------------------------------------------------------------------------

async def get_quote_or_404(db: AsyncSession, *, organization_id: uuid.UUID, quote_id: uuid.UUID) -> Quote:
    quote = (
        await db.execute(
            select(Quote).where(Quote.id == quote_id, Quote.organization_id == organization_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if quote is None:
        raise NotFoundError("La cotización no existe.", code="quote_not_found")
    return quote


async def list_quotes(db, *, organization_id, customer_id=None, project_id=None, status=None,
                      include_history: bool = False, limit: int | None = None,
                      offset: int = 0) -> tuple[list[Quote], date, int]:
    """Por defecto, solo la versión vigente de cada cotización. Devuelve
    (página, hoy, total). Sin filtro de estado se pagina en la base; el estado
    («vencida») se calcula con la fecha de hoy, así que con ese filtro se
    filtra primero y se recorta después."""
    stmt = select(Quote).where(Quote.organization_id == organization_id).order_by(
        Quote.created_at.desc(), Quote.id.desc())
    if customer_id:
        stmt = stmt.where(Quote.customer_id == customer_id)
    if project_id:
        stmt = stmt.where(Quote.project_id == project_id)
    if not include_history:
        stmt = stmt.where(Quote.status != QuoteStatus.superseded)
    hoy = await org_today(db, organization_id)
    if status:
        # Uno o varios estados separados por coma («rejected,expired»).
        buscados = {s.strip() for s in status.split(",") if s.strip()}
        quotes = [q for q in (await db.execute(stmt)).scalars().all() if q.status_on(hoy) in buscados]
        fin = None if limit is None else offset + limit
        return quotes[offset:fin], hoy, len(quotes)
    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all()), hoy, total


async def quotes_summary(db, *, organization_id) -> dict[str, dict]:
    """Cantidad y total por estado de las cotizaciones vigentes (sin el
    historial de versiones), para los totales y filtros de la pestaña. Se
    calcula aquí porque la lista va paginada y el estado depende de hoy."""
    quotes, hoy, _ = await list_quotes(db, organization_id=organization_id)
    resumen: dict[str, dict] = {}
    for q in quotes:
        fila = resumen.setdefault(q.status_on(hoy), {"count": 0, "total": Decimal("0")})
        fila["count"] += 1
        fila["total"] += q.total
    return resumen


async def versions_of(db, quote: Quote) -> list[Quote]:
    return list(
        (
            await db.execute(
                select(Quote).where(Quote.organization_id == quote.organization_id,
                                    Quote.quote_number == quote.quote_number).order_by(Quote.version)
            )
        ).scalars().all()
    )


async def invoice_of(db, quote: Quote) -> Invoice | None:
    return (
        await db.execute(select(Invoice).where(Invoice.quote_id == quote.id).order_by(Invoice.created_at.desc()))
    ).scalars().first()


# ---------------------------------------------------------------------------

def _lines(datos: list[dict]) -> list[QuoteLine]:
    if not datos:
        raise InvalidInputError("La cotización necesita al menos una línea.", code="quote_lines_required")
    return build_lines(datos, line_cls=QuoteLine)


def _check_valid_until(valid_until: date | None, hoy: date) -> None:
    if valid_until is not None and valid_until < hoy:
        raise InvalidInputError("La vigencia no puede terminar antes de hoy.", code="invalid_valid_until")


async def _customer_and_project(db, organization_id, data) -> tuple[uuid.UUID, uuid.UUID | None]:
    from app.modules.crm.models import Customer
    from app.modules.field_ops.models import Project

    project = None
    if data.get("project_id"):
        project = (
            await db.execute(select(Project).where(Project.id == data["project_id"],
                                                   Project.organization_id == organization_id))
        ).scalar_one_or_none()
        if project is None:
            raise NotFoundError("El proyecto no existe.", code="project_not_found")
    customer_id = data.get("customer_id") or (project.customer_id if project else None)
    if customer_id is None:
        raise InvalidInputError("Indica el cliente de la cotización.", code="quote_customer_required")
    existe = (
        await db.execute(select(Customer.id).where(Customer.id == customer_id,
                                                   Customer.organization_id == organization_id))
    ).scalar_one_or_none()
    if existe is None:
        raise NotFoundError("El cliente no existe.", code="customer_not_found")
    if project is not None and project.customer_id != customer_id:
        raise InvalidInputError("La instalación es de otro cliente.", code="quote_project_customer_mismatch")
    return customer_id, project.id if project else None


def _payload(quote: Quote, organization_id) -> dict:
    return {"quote_id": str(quote.id), "quote_number": quote.quote_number, "version": quote.version,
            "organization_id": str(organization_id)}


async def _audit(db, organization_id, user, action, quote: Quote, data: dict) -> None:
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id, action=action,
        entity_type="Quote", entity_id=str(quote.id),
        after_data={"quote_number": quote.quote_number, "version": quote.version, **data},
    )
