"""Cobrar una factura en línea, como en Housecall Pro.

1. «Cobrar» en la factura crea un enlace (total pendiente o anticipo) y lo
   manda por correo o SMS, o lo muestra como QR en el celular del técnico.
2. El cliente abre `/pagar/<token>`: ve su factura y paga con tarjeta, Apple
   Pay, Google Pay o desde su banco (ACH) en la página de Stripe.
3. Stripe avisa por webhook firmado y el pago entra solo a la factura, con la
   comisión y la tarjeta (marca y últimos 4) como referencia. ACH queda «en
   camino» hasta que el banco lo confirma (2 a 4 días hábiles).
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.billing.models import DocumentStatus, Invoice, InvoiceKind, InvoicePayment
from app.modules.billing.money import to_money
from app.modules.crm.models import Customer
from app.modules.payments import providers
from app.modules.payments.models import PaymentLink, ProviderEvent
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

METODOS = {"card": "Tarjeta", "us_bank_account": "Cuenta bancaria (ACH)", "link": "Link (Stripe)"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def pay_url(token: str) -> str:
    return f"{get_settings().FRONTEND_APP_URL.rstrip('/')}/pagar/{token}"


async def _invoice(db: AsyncSession, organization_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    inv = (await db.execute(select(Invoice).where(Invoice.id == invoice_id,
                                                  Invoice.organization_id == organization_id))).scalar_one_or_none()
    if inv is None:
        raise NotFoundError("La factura no existe.", code="invoice_not_found")
    return inv


def _cobrable(inv: Invoice) -> None:
    if inv.kind != InvoiceKind.particular:
        raise ConflictError("El cobro en línea es para el trabajo particular; el programa paga su cobro aparte.",
                            code="invoice_not_particular")
    if inv.document_status != DocumentStatus.issued:
        raise ConflictError("Emite la factura antes de cobrarla.", code="invoice_not_issued")
    if inv.balance <= 0:
        raise ConflictError("La factura ya está pagada.", code="invoice_already_paid")


def link_out(l: PaymentLink, inv: Invoice | None = None) -> dict:
    return {"id": str(l.id), "invoice_id": str(l.invoice_id), "kind": l.kind,
            "amount": str(l.amount) if l.amount is not None else None,
            "amount_due": str(min(l.amount, inv.balance) if (inv and l.amount is not None) else (inv.balance if inv else l.amount)),
            "status": l.status, "sent_to_email": l.sent_to_email, "sent_to_phone": l.sent_to_phone,
            "last_sent_at": l.last_sent_at.isoformat() if l.last_sent_at else None,
            "opened_at": l.opened_at.isoformat() if l.opened_at else None,
            "paid_at": l.paid_at.isoformat() if l.paid_at else None,
            "created_at": l.created_at.isoformat() if l.created_at else None}


async def create_link(db: AsyncSession, *, organization_id: uuid.UUID, user, invoice_id: uuid.UUID, kind: str,
                      amount=None, email: str | None, phone: str | None) -> dict:
    """Crea el enlace (y anula el anterior de la misma factura, como Housecall
    Pro: siempre hay un solo enlace vigente). Devuelve la URL una sola vez."""
    inv = await _invoice(db, organization_id, invoice_id)
    _cobrable(inv)
    monto = None
    if kind == "deposit":
        monto = to_money(amount)
        if monto <= 0 or monto > inv.balance:
            raise InvalidInputError(f"El anticipo debe ser mayor que cero y hasta el saldo ({inv.balance}).",
                                    code="invalid_deposit")
    elif kind != "full":
        raise InvalidInputError("Tipo de cobro no válido.", code="invalid_kind")
    for previo in (await db.execute(select(PaymentLink).where(
            PaymentLink.organization_id == organization_id, PaymentLink.invoice_id == inv.id,
            PaymentLink.status == "active"))).scalars():
        previo.status = "revoked"
    token = secrets.token_urlsafe(32)
    link = PaymentLink(organization_id=organization_id, invoice_id=inv.id, token_hash=_hash(token), kind=kind,
                       amount=monto, status="active", created_by_user_id=user.id)
    db.add(link)
    await db.flush()
    url = pay_url(token)
    await _send(db, link, inv, url, email=email, phone=phone)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="payments.link_created", entity_type="Invoice", entity_id=str(inv.id),
                             after_data={"kind": kind, "amount": str(monto or inv.balance),
                                         "email": bool(link.sent_to_email), "sms": bool(link.sent_to_phone)})
    await db.commit()
    return {**link_out(link, inv), "url": url}


async def _send(db, link: PaymentLink, inv: Invoice, url: str, *, email: str | None, phone: str | None) -> None:
    from app.modules.organizations.models import Organization

    org = await db.get(Organization, inv.organization_id)
    monto = link.amount if link.amount is not None else inv.balance
    nombre = org.name if org else "Delta HVAC"
    concepto = "el anticipo de la factura" if link.kind == "deposit" else "la factura"
    if email:
        from app.modules.notifications.email import send_text_email

        cuerpo = (f"Hola,\n\n{nombre} te envía {concepto} {inv.invoice_number} por ${monto:,.2f}.\n\n"
                  f"Revísala y págala con tarjeta o desde tu banco aquí:\n{url}\n\nGracias por tu confianza.\n{nombre}")
        await send_text_email(to=email, subject=f"{nombre}: factura {inv.invoice_number} · ${monto:,.2f}", body=cuerpo)
        link.sent_to_email = email
    if phone:
        from app.modules.notifications.sms import send_sms

        await send_sms(to=phone, message=f"{nombre}: {concepto} {inv.invoice_number} por ${monto:,.2f}. Paga aquí: {url}")
        link.sent_to_phone = phone
    if email or phone:
        link.last_sent_at = _now()


async def resend(db: AsyncSession, *, organization_id, user, link_id: uuid.UUID, email: str | None,
                 phone: str | None) -> dict:
    """Reenviar: como el token no se guarda, se emite uno nuevo y el anterior deja de servir."""
    link = (await db.execute(select(PaymentLink).where(PaymentLink.id == link_id,
                                                       PaymentLink.organization_id == organization_id))
            ).scalar_one_or_none()
    if link is None:
        raise NotFoundError("El enlace no existe.", code="payment_link_not_found")
    return await create_link(db, organization_id=organization_id, user=user, invoice_id=link.invoice_id,
                             kind=link.kind, amount=link.amount, email=email, phone=phone)


async def list_links(db: AsyncSession, organization_id, invoice_id) -> list[dict]:
    inv = await _invoice(db, organization_id, invoice_id)
    filas = (await db.execute(select(PaymentLink).where(
        PaymentLink.organization_id == organization_id, PaymentLink.invoice_id == inv.id)
        .order_by(PaymentLink.created_at.desc()))).scalars().all()
    return [link_out(l, inv) for l in filas]


# ---------------------------------------------------------------------------
# Página pública del cliente
# ---------------------------------------------------------------------------

async def _by_token(db: AsyncSession, token: str) -> tuple[PaymentLink, Invoice]:
    link = (await db.execute(select(PaymentLink).where(PaymentLink.token_hash == _hash(token)))).scalar_one_or_none()
    if link is None or link.status == "revoked":
        raise NotFoundError("Este enlace ya no es válido. Pide uno nuevo a la empresa.", code="payment_link_invalid")
    inv = await db.get(Invoice, link.invoice_id)
    if inv is None or inv.organization_id != link.organization_id:
        raise NotFoundError("Este enlace ya no es válido.", code="payment_link_invalid")
    return link, inv


async def public_view(db: AsyncSession, token: str) -> dict:
    """Lo que ve el cliente: su factura y cuánto se le pide. Nada interno
    (sin costos, notas ni datos de otras facturas)."""
    from app.modules.organizations.models import Organization

    link, inv = await _by_token(db, token)
    if link.opened_at is None:
        link.opened_at = _now()
        await db.commit()
    org = await db.get(Organization, inv.organization_id)
    cliente = await db.get(Customer, inv.customer_id)
    pedido = min(link.amount, inv.balance) if link.amount is not None else inv.balance
    estado = "paid" if inv.balance <= 0 else ("processing" if link.status == "processing" else "open")
    return {
        "company": org.name if org else "", "invoice_number": inv.invoice_number,
        "customer_name": cliente.legal_name if cliente else "",
        "issue_date": inv.issue_date.isoformat() if inv.issue_date else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "lines": [{"description": l.description, "quantity": str(l.quantity), "amount": str(l.amount),
                   "kind": l.kind} for l in inv.lines],
        "subtotal": str(inv.subtotal), "rebates": str(inv.rebate_total), "total": str(to_money(inv.amount)),
        "paid": str(inv.paid_amount), "balance": str(inv.balance), "amount_requested": str(max(pedido, Decimal("0"))),
        "kind": link.kind, "status": estado, "online_enabled": providers.stripe_enabled(),
    }


async def public_checkout(db: AsyncSession, token: str) -> dict:
    """Abre un pago nuevo de Stripe por lo que se pide hoy y devuelve su URL."""
    link, inv = await _by_token(db, token)
    if inv.balance <= 0:
        raise ConflictError("Esta factura ya está pagada. ¡Gracias!", code="invoice_already_paid")
    if link.status == "processing":
        raise ConflictError("Ya hay un pago desde tu banco en camino. Te avisaremos cuando se confirme.",
                            code="payment_processing")
    monto = min(link.amount, inv.balance) if link.amount is not None else inv.balance
    cliente = await db.get(Customer, inv.customer_id)
    base = f"{get_settings().FRONTEND_APP_URL.rstrip('/')}/pagar/{token}"
    meta = {"organization_id": str(inv.organization_id), "invoice_id": str(inv.id), "link_id": str(link.id)}
    concepto = f"Factura {inv.invoice_number}" + (" · anticipo" if link.kind == "deposit" else "")
    sesion = await providers.stripe_request("POST", "/v1/checkout/sessions", {
        "mode": "payment", "success_url": f"{base}?pagado=1", "cancel_url": base,
        "client_reference_id": str(inv.id), "customer_email": (cliente.email if cliente and cliente.email else None),
        "payment_method_types": ["card", "us_bank_account"],
        "line_items": [{"quantity": 1, "price_data": {"currency": "usd", "unit_amount": providers.cents(monto),
                                                      "product_data": {"name": concepto}}}],
        "metadata": meta, "payment_intent_data": {"metadata": meta, "description": concepto},
        "locale": "es",
    })
    link.stripe_session_id = sesion.get("id")
    await db.commit()
    return {"url": sesion["url"]}


# ---------------------------------------------------------------------------
# Webhook de Stripe
# ---------------------------------------------------------------------------

async def handle_stripe_event(db: AsyncSession, evento: dict) -> str:
    """Procesa un evento ya verificado. Idempotente por el id del evento."""
    tipo, obj = evento.get("type", ""), (evento.get("data") or {}).get("object") or {}
    meta = obj.get("metadata") or {}
    try:
        org_id = uuid.UUID(meta.get("organization_id", ""))
    except ValueError:
        org_id = None
    if org_id is None and tipo.startswith("charge."):
        org_id = await _org_of_payment_intent(db, obj.get("payment_intent"))
    if org_id is None:
        return "ignored"
    db.add(ProviderEvent(organization_id=org_id, provider="stripe", event_id=evento["id"], event_type=tipo,
                         received_at=_now(), summary={"object": obj.get("id")}))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return "duplicate"

    if tipo == "checkout.session.completed":
        if obj.get("payment_status") == "paid":
            await _record_from_session(db, org_id, obj)
        else:
            await _set_link(db, org_id, meta.get("link_id"), "processing")
    elif tipo == "checkout.session.async_payment_succeeded":
        await _record_from_session(db, org_id, obj)
    elif tipo == "checkout.session.async_payment_failed":
        await _set_link(db, org_id, meta.get("link_id"), "active")
        await _notify(db, org_id, "payment.failed", meta.get("invoice_id"),
                      providers.from_cents(obj.get("amount_total")), "cuenta bancaria (ACH)")
    elif tipo == "charge.refunded":
        await _record_refund(db, org_id, obj)
    elif tipo in ("charge.updated", "charge.succeeded"):
        await _fill_fee(db, obj)
    elif tipo == "charge.dispute.created":
        pago = await _payment_by_intent(db, obj.get("payment_intent"))
        if pago:
            await _notify(db, org_id, "payment.disputed", str(pago.invoice_id), providers.from_cents(obj.get("amount")),
                          "tarjeta")
    await db.commit()
    return "ok"


async def _org_of_payment_intent(db, intent_id) -> uuid.UUID | None:
    pago = await _payment_by_intent(db, intent_id)
    if pago is None:
        return None
    inv = await db.get(Invoice, pago.invoice_id)
    return inv.organization_id if inv else None


async def _payment_by_intent(db, intent_id) -> InvoicePayment | None:
    if not intent_id:
        return None
    return (await db.execute(select(InvoicePayment).where(InvoicePayment.provider == "stripe",
                                                          InvoicePayment.external_id == intent_id))).scalars().first()


async def _set_link(db, org_id, link_id, estado: str) -> None:
    try:
        lid = uuid.UUID(str(link_id))
    except ValueError:
        return
    link = await db.get(PaymentLink, lid)
    if link and link.organization_id == org_id and link.status != "revoked":
        link.status = estado
        if estado == "paid":
            link.paid_at = _now()


async def _record_from_session(db, org_id: uuid.UUID, sesion: dict) -> None:
    meta = sesion.get("metadata") or {}
    intent_id = sesion.get("payment_intent")
    if await _payment_by_intent(db, intent_id):
        return
    try:
        inv = await _invoice(db, org_id, uuid.UUID(meta.get("invoice_id", "")))
    except ValueError:
        return
    monto = providers.from_cents(sesion.get("amount_total"))
    metodo, referencia, comision = "Tarjeta (en línea)", intent_id, None
    try:
        intent = await providers.stripe_request("GET", f"/v1/payment_intents/{intent_id}",
                                                {"expand": ["latest_charge.balance_transaction"]})
        cargo = intent.get("latest_charge") or {}
        detalle = cargo.get("payment_method_details") or {}
        if detalle.get("type") == "card":
            tarjeta = detalle.get("card") or {}
            metodo = f"Tarjeta {str(tarjeta.get('brand', '')).capitalize()} ····{tarjeta.get('last4', '')}".strip()
        elif detalle.get("type") == "us_bank_account":
            banco = detalle.get("us_bank_account") or {}
            metodo = f"ACH {banco.get('bank_name', '')} ····{banco.get('last4', '')}".strip()
        bt = cargo.get("balance_transaction") or {}
        if isinstance(bt, dict) and bt.get("fee") is not None:
            comision = providers.from_cents(bt.get("fee"))
    except Exception:  # noqa: BLE001 — el pago se registra aunque no se lea el detalle
        pass
    from app.modules.field_ops import clock

    inv.payments.append(InvoicePayment(amount=monto, paid_at=await clock.org_today(db, org_id), method=metodo[:100],
                                       reference=referencia, provider="stripe", external_id=intent_id,
                                       fee_amount=comision, notes="Pago en línea por enlace"))
    await db.flush()
    if inv.balance <= 0 and inv.paid_at is None:
        inv.paid_at = _now()
    await _set_link(db, org_id, meta.get("link_id"), "paid")
    await record_audit_event(db, organization_id=org_id, actor_user_id=None, action="payments.received_online",
                             entity_type="Invoice", entity_id=str(inv.id),
                             after_data={"amount": str(monto), "method": metodo, "fee": str(comision or "")})
    await _notify(db, org_id, "payment.received", str(inv.id), monto, metodo)


async def _fill_fee(db, cargo: dict) -> None:
    """Stripe asocia la comisión al cargo unos segundos después del pago y lo
    avisa con `charge.updated`: ahí se completa la comisión que faltaba."""
    pago = await _payment_by_intent(db, cargo.get("payment_intent"))
    bt = cargo.get("balance_transaction")
    if pago is None or pago.fee_amount is not None or not bt:
        return
    if isinstance(bt, str):
        try:
            bt = await providers.stripe_request("GET", f"/v1/balance_transactions/{bt}")
        except Exception:  # noqa: BLE001 — sin la comisión el pago sigue bien registrado
            return
    if isinstance(bt, dict) and bt.get("fee") is not None:
        pago.fee_amount = providers.from_cents(bt["fee"])


async def _record_refund(db, org_id: uuid.UUID, cargo: dict) -> None:
    pago = await _payment_by_intent(db, cargo.get("payment_intent"))
    if pago is None:
        return
    inv = await db.get(Invoice, pago.invoice_id)
    ya = sum((-p.amount for p in inv.payments if p.provider == "stripe_refund"
              and p.external_id == cargo.get("payment_intent")), Decimal("0"))
    total = providers.from_cents(cargo.get("amount_refunded"))
    delta = (total - ya).quantize(Decimal("0.01"))
    if delta <= 0:
        return
    from app.modules.field_ops import clock

    inv.payments.append(InvoicePayment(amount=-delta, paid_at=await clock.org_today(db, org_id),
                                       method="Reembolso (en línea)", reference=cargo.get("id"),
                                       provider="stripe_refund", external_id=cargo.get("payment_intent"),
                                       notes="Reembolso hecho en Stripe"))
    await db.flush()
    if inv.balance > 0:
        inv.paid_at = None
    await record_audit_event(db, organization_id=org_id, actor_user_id=None, action="payments.refunded",
                             entity_type="Invoice", entity_id=str(inv.id), after_data={"amount": str(delta)})


async def _notify(db, org_id, code: str, invoice_id, monto: Decimal, metodo: str) -> None:
    from app.modules.notifications.catalog import DEFAULT_PERMISSION
    from app.modules.notifications.service import _users_with, notify

    try:
        inv = await db.get(Invoice, uuid.UUID(str(invoice_id)))
    except ValueError:
        return
    if inv is None:
        return
    cliente = await db.get(Customer, inv.customer_id)
    usuarios = await _users_with(db, org_id, DEFAULT_PERMISSION[code])
    await notify(db, organization_id=org_id, code=code, users=usuarios,
                 context={"factura": inv.invoice_number, "monto": f"${monto:,.2f}", "metodo": metodo,
                          "cliente": cliente.legal_name if cliente else "", "saldo": f"${inv.balance:,.2f}"},
                 link=f"/invoices?factura={inv.id}", entity=("invoice", str(inv.id)))
