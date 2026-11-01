"""La cotización que le llega al cliente (como en Housecall Pro): un enlace
público donde la ve, elige la opción, la firma y la acepta, o la rechaza.

- El enlace es un token aleatorio; se guarda solo su hash en la cotización.
  Generar uno nuevo invalida el anterior, y ajustar la cotización (versión
  nueva) también.
- Sirve mientras la cotización esté enviada y vigente. Después muestra cómo
  quedó (aceptada, rechazada, reemplazada o vencida) sin dejar decidir.
- Aceptar por el enlace hace lo mismo que aceptar desde la oficina
  (`quotes.accept_core`: factura en borrador y obra si no la tenía) y guarda
  además el nombre, la firma y la IP de quien aceptó.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_secure_token, hash_token
from app.modules.billing import quotes as quotes_service
from app.modules.billing.models import QUOTE_STATUS_LABELS, Invoice, Quote, QuoteStatus
from app.modules.field_ops.clock import org_today
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

MIN_NAME_LENGTH = 3


def public_url(raw_token: str) -> str:
    return f"{get_settings().FRONTEND_APP_URL.rstrip('/')}/cotizacion/{raw_token}"


async def create_link(db: AsyncSession, *, organization_id, user, quote_id, email: bool) -> dict:
    """Genera el enlace de una cotización enviada y, si se pide, lo manda al
    correo del cliente. Devuelve la URL (solo existe en esta respuesta)."""
    from app.modules.crm.models import Customer
    from app.modules.notifications.email import send_email
    from app.modules.organizations.models import Organization

    quote = await quotes_service.get_quote_or_404(db, organization_id=organization_id, quote_id=quote_id)
    estado = quote.status_on(await org_today(db, organization_id))
    if estado != QuoteStatus.sent:
        raise ConflictError("El enlace se genera para una cotización enviada y vigente.", code="quote_not_sent")
    cliente = await db.get(Customer, quote.customer_id)
    destino = (cliente.email or "").strip() if cliente else ""
    if email and not destino:
        raise InvalidInputError("El cliente no tiene correo registrado. Copia el enlace y compártelo.",
                                code="customer_email_missing")
    raw, digest = generate_secure_token()
    quote.public_token_hash = digest
    quote.viewed_at = None
    if email:
        quote.public_sent_to = destino
    await quotes_service._audit(db, organization_id, user, "quotes.link_created", quote,
                                {"emailed_to": destino if email else None})
    await db.commit()
    url = public_url(raw)
    enviado = None
    if email:
        org = await db.get(Organization, organization_id)
        ok = await send_email(to=destino, template="quote_link", context={
            "quote_link": url, "quote_number": quote.quote_number, "company": org.name if org else "",
            "customer_name": cliente.legal_name if cliente else "", "total": _money_text(quote),
            "valid_until": quote.valid_until.isoformat() if quote.valid_until else None})
        if not ok:
            raise ConflictError(f"El enlace quedó creado pero no se pudo enviar el correo a {destino}. "
                                "Revisa la configuración de correo o copia el enlace.", code="email_not_sent")
        enviado = destino
    return {"url": url, "emailed_to": enviado}


def _money_text(quote: Quote) -> str:
    if quote.options:
        return "desde $" + f"{min(o['total'] for o in quote.option_totals):,.2f}"
    return f"${quote.total:,.2f}"


async def _by_token(db: AsyncSession, raw_token: str) -> Quote:
    quote = (await db.execute(select(Quote).where(Quote.public_token_hash == hash_token(raw_token)))
             ).scalar_one_or_none()
    if quote is None:
        raise NotFoundError("El enlace no es válido o fue reemplazado por uno nuevo.", code="quote_link_not_found")
    return quote


async def public_view(db: AsyncSession, raw_token: str) -> dict:
    from app.modules.crm.models import Customer
    from app.modules.organizations.models import Organization

    quote = await _by_token(db, raw_token)
    hoy = await org_today(db, quote.organization_id)
    estado = quote.status_on(hoy)
    if quote.viewed_at is None and estado == QuoteStatus.sent:
        quote.viewed_at = datetime.now(timezone.utc)
        await db.commit()
    org = await db.get(Organization, quote.organization_id)
    cliente = await db.get(Customer, quote.customer_id)
    return {
        "company": org.name if org else "", "customer_name": cliente.legal_name if cliente else "",
        "quote_number": quote.quote_number, "version": quote.version, "title": quote.title,
        "status": estado, "status_label": QUOTE_STATUS_LABELS[estado], "can_decide": estado == QuoteStatus.sent,
        "valid_until": quote.valid_until, "notes": quote.notes, "sent_at": quote.sent_at,
        "options": [{"key": o["key"], "label": o["label"], "total": str(o["total"])} for o in quote.option_totals],
        "accepted_option": quote.accepted_option, "total": str(quote.total),
        "lines": [{"kind": l.kind, "description": l.description, "quantity": str(l.quantity),
                   "unit_price": str(l.unit_price), "amount": str(l.amount), "option_key": l.option_key}
                  for l in quote.lines],
        "signer_name": quote.signer_name, "decided_at": quote.decided_at,
    }


async def _notify(db: AsyncSession, quote: Quote, code: str, extra: dict) -> None:
    """Avisa a la oficina que el cliente decidió por el enlace."""
    from app.modules.crm.models import Customer
    from app.modules.notifications.catalog import DEFAULT_PERMISSION
    from app.modules.notifications.service import _users_with, notify

    cliente = await db.get(Customer, quote.customer_id)
    usuarios = await _users_with(db, quote.organization_id, DEFAULT_PERMISSION[code])
    await notify(db, organization_id=quote.organization_id, code=code, users=usuarios,
                 context={"cotizacion": quote.quote_number, "cliente": cliente.legal_name if cliente else "", **extra},
                 link=f"/invoices/quotes/{quote.id}", entity=("quote", str(quote.id)))


async def public_accept(db: AsyncSession, *, raw_token: str, option: str | None, signer_name: str,
                        signature_base64: str, ip_address: str | None) -> dict:
    from app.modules.field_ops.pdf import decode_signature_png
    from app.shared.files.storage import save_bytes

    quote = await _by_token(db, raw_token)
    nombre = (signer_name or "").strip()
    if len(nombre) < MIN_NAME_LENGTH:
        raise InvalidInputError("Escribe tu nombre completo para firmar.", code="signer_name_required")
    firma = decode_signature_png(signature_base64)
    invoice: Invoice = await quotes_service.accept_core(db, quote=quote, user=None, option=option,
                                                        decided_by="customer")
    quote.signer_name = nombre[:255]
    quote.signed_ip = (ip_address or "")[:64] or None
    quote.signature_path = save_bytes(organization_id=quote.organization_id, subfolder=f"quotes/{quote.id}",
                                      filename="customer_signature.png", data=firma)
    await _notify(db, quote, "quote.customer_accepted", {"monto": f"${quote.total:,.2f}"})
    await db.commit()
    quotes_service.emit_accepted(quote, invoice)
    return await public_view(db, raw_token)


async def public_reject(db: AsyncSession, *, raw_token: str, reason: str) -> dict:
    quote = await _by_token(db, raw_token)
    if quote.status_on(await org_today(db, quote.organization_id)) != QuoteStatus.sent:
        raise ConflictError("Esta cotización ya no se puede rechazar.", code="quote_not_sent")
    motivo = (reason or "").strip()
    if len(motivo) < quotes_service.MIN_REASON_LENGTH:
        raise InvalidInputError("Cuéntanos brevemente por qué no la aceptas.", code="quote_rejection_reason_required")
    quote.status = QuoteStatus.rejected
    quote.rejection_reason = motivo[:2000]
    quote.decided_at = datetime.now(timezone.utc)
    quote.decided_by = "customer"
    await quotes_service._audit(db, quote.organization_id, None, "quotes.rejected", quote,
                                {"reason": motivo, "by": "customer"})
    await _notify(db, quote, "quote.customer_rejected", {"motivo": motivo[:300]})
    await db.commit()
    return await public_view(db, raw_token)
