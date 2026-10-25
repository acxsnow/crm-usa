"""Rutas de cobro en línea y banca conectada. Cada ruta con su permiso; las
públicas son la página de pago (token aleatorio, solo su factura) y los
webhooks (firma de Stripe y de Plaid)."""
import json
import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions, get_organization_id, require_any_permission, require_permission
from app.core.rate_limit import is_rate_limited
from app.db.session import get_db
from app.modules.payments import bankfeed, collect, providers
from app.modules.users.models import User
from app.shared.errors import DomainError, InvalidInputError
from app.shared.pagination import paginate_list, pagination_params

router = APIRouter(tags=["payments"])

_collect = require_permission("payments.collect")
_bank = require_permission("bankfeeds.manage")
_any = require_any_permission("payments.collect", "bankfeeds.manage")


class LinkIn(BaseModel):
    kind: str = Field(default="full", pattern="^(full|deposit)$")
    amount: str | None = Field(default=None, max_length=20)
    send_email: bool = False
    send_sms: bool = False
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)


class ResendIn(BaseModel):
    send_email: bool = False
    send_sms: bool = False
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)


class ConnectIn(BaseModel):
    public_token: str = Field(min_length=10, max_length=255)
    institution_name: str = Field(default="Banco", max_length=255)
    institution_id: str | None = Field(default=None, max_length=80)


class VisibleIn(BaseModel):
    visible: bool


class AddIn(BaseModel):
    category: str = Field(max_length=30)
    project_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    memo: str | None = Field(default=None, max_length=500)


class MatchIn(BaseModel):
    matched_type: str = Field(pattern="^(expense|supplier_payment|invoice_payment)$")
    matched_id: uuid.UUID


class MemoIn(BaseModel):
    memo: str | None = Field(default=None, max_length=500)


class AcceptIn(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    contains: str = Field(min_length=2, max_length=120)
    direction: str = Field(default="out", pattern="^(out|in|any)$")
    amount_min: str | None = Field(default=None, max_length=20)
    amount_max: str | None = Field(default=None, max_length=20)
    account_id: uuid.UUID | None = None
    category: str = Field(max_length=30)
    project_id: uuid.UUID | None = None
    auto_add: bool = False
    priority: int = Field(default=100, ge=0, le=1000)
    active: bool = True
    memo: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------

@router.get("/payments/status")
async def payments_status(current_user: User = Depends(_any)) -> dict:
    from app.core.config import get_settings

    return {"online_payments": providers.stripe_enabled(), "bank_feeds": providers.plaid_enabled(),
            "plaid_env": get_settings().PLAID_ENV}


# ---------------------------------------------------------------------------
# Cobro
# ---------------------------------------------------------------------------

async def _check_invoice_access(db, organization_id, user, invoice_id) -> None:
    """La oficina cobra cualquier factura; el técnico, solo las de las obras que trabaja."""
    if "invoices.record_payment" in get_effective_permissions(user):
        return
    from app.modules.billing.models import Invoice
    from app.modules.field_ops.access import get_workable_project

    inv = (await db.execute(select(Invoice).where(Invoice.id == invoice_id,
                                                  Invoice.organization_id == organization_id))).scalar_one_or_none()
    if inv is None or inv.project_id is None:
        from app.shared.errors import NotFoundError

        raise NotFoundError("La factura no existe.", code="invoice_not_found")
    await get_workable_project(db, organization_id=organization_id, user=user, project_id=inv.project_id)


async def _contact(db, organization_id, invoice_id, data) -> tuple[str | None, str | None]:
    from app.modules.billing.models import Invoice
    from app.modules.crm.models import Customer

    inv = (await db.execute(select(Invoice).where(Invoice.id == invoice_id,
                                                  Invoice.organization_id == organization_id))).scalar_one_or_none()
    cliente = await db.get(Customer, inv.customer_id) if inv else None
    email = (data.email or (cliente.email if cliente else None)) if data.send_email else None
    phone = (data.phone or (cliente.main_phone if cliente else None)) if data.send_sms else None
    if data.send_email and not email:
        raise InvalidInputError("El cliente no tiene correo; escríbelo.", code="email_required")
    if data.send_sms and not phone:
        raise InvalidInputError("El cliente no tiene celular; escríbelo.", code="phone_required")
    return email, phone


@router.get("/payments/projects/{project_id}/invoices")
async def project_open_invoices(project_id: uuid.UUID, response: Response, db: AsyncSession = Depends(get_db),
                                organization_id: uuid.UUID = Depends(get_organization_id),
                                pag: tuple[int, int] = Depends(pagination_params),
                                current_user: User = Depends(_collect)) -> list[dict]:
    """Lo que el técnico puede cobrar en la obra: facturas particulares emitidas con saldo."""
    from app.modules.billing.models import DocumentStatus, Invoice, InvoiceKind
    from app.modules.field_ops.access import get_visible_project

    await get_visible_project(db, organization_id=organization_id, user=current_user, project_id=project_id)
    filas = (await db.execute(select(Invoice).where(
        Invoice.organization_id == organization_id, Invoice.project_id == project_id,
        Invoice.kind == InvoiceKind.particular, Invoice.document_status == DocumentStatus.issued))).scalars().all()
    abiertas = [{"id": str(i.id), "invoice_number": i.invoice_number, "total": str(i.amount),
                 "paid": str(i.paid_amount), "balance": str(i.balance)} for i in filas if i.balance > 0]
    return paginate_list(abiertas, limit=pag[0], offset=pag[1], response=response)


@router.get("/invoices/{invoice_id}/payment-links")
async def list_payment_links(invoice_id: uuid.UUID, response: Response, db: AsyncSession = Depends(get_db),
                             organization_id: uuid.UUID = Depends(get_organization_id),
                             pag: tuple[int, int] = Depends(pagination_params),
                             current_user: User = Depends(_collect)) -> list[dict]:
    await _check_invoice_access(db, organization_id, current_user, invoice_id)
    return paginate_list(await collect.list_links(db, organization_id, invoice_id), limit=pag[0], offset=pag[1],
                         response=response)


@router.post("/invoices/{invoice_id}/payment-links", status_code=201)
async def create_payment_link(invoice_id: uuid.UUID, payload: LinkIn, db: AsyncSession = Depends(get_db),
                              organization_id: uuid.UUID = Depends(get_organization_id),
                              current_user: User = Depends(_collect)) -> dict:
    await _check_invoice_access(db, organization_id, current_user, invoice_id)
    email, phone = await _contact(db, organization_id, invoice_id, payload)
    return await collect.create_link(db, organization_id=organization_id, user=current_user, invoice_id=invoice_id,
                                     kind=payload.kind, amount=payload.amount, email=email, phone=phone)


@router.post("/payment-links/{link_id}/resend", status_code=201)
async def resend_payment_link(link_id: uuid.UUID, payload: ResendIn, db: AsyncSession = Depends(get_db),
                              organization_id: uuid.UUID = Depends(get_organization_id),
                              current_user: User = Depends(_collect)) -> dict:
    from app.modules.payments.models import PaymentLink

    link = (await db.execute(select(PaymentLink).where(PaymentLink.id == link_id,
                                                       PaymentLink.organization_id == organization_id))
            ).scalar_one_or_none()
    if link is None:
        from app.shared.errors import NotFoundError

        raise NotFoundError("El enlace no existe.", code="payment_link_not_found")
    await _check_invoice_access(db, organization_id, current_user, link.invoice_id)
    email, phone = await _contact(db, organization_id, link.invoice_id, payload)
    return await collect.resend(db, organization_id=organization_id, user=current_user, link_id=link_id, email=email,
                                phone=phone)


@router.post("/payment-links/{link_id}/revoke", status_code=204)
async def revoke_payment_link(link_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                              organization_id: uuid.UUID = Depends(get_organization_id),
                              current_user: User = Depends(_collect)) -> None:
    from app.modules.payments.models import PaymentLink
    from app.shared.audit import record_audit_event
    from app.shared.errors import NotFoundError

    link = (await db.execute(select(PaymentLink).where(PaymentLink.id == link_id,
                                                       PaymentLink.organization_id == organization_id))
            ).scalar_one_or_none()
    if link is None:
        raise NotFoundError("El enlace no existe.", code="payment_link_not_found")
    await _check_invoice_access(db, organization_id, current_user, link.invoice_id)
    if link.status in ("active", "processing"):
        link.status = "revoked"
    await record_audit_event(db, organization_id=organization_id, actor_user_id=current_user.id,
                             action="payments.link_revoked", entity_type="PaymentLink", entity_id=str(link.id))
    await db.commit()


# --- Página pública del cliente ------------------------------------------------

async def _limite_publico(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if await is_rate_limited(f"pay:ip:{ip}", max_attempts=60, window_seconds=60):
        from fastapi import HTTPException

        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera un minuto.")


@router.get("/public/pay/{token}")
async def public_pay_view(token: str, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    await _limite_publico(request)
    return await collect.public_view(db, token[:128])


@router.post("/public/pay/{token}/checkout")
async def public_pay_checkout(token: str, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    await _limite_publico(request)
    return await collect.public_checkout(db, token[:128])


# --- Webhooks ------------------------------------------------------------------

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    cuerpo = await request.body()
    providers.verify_stripe_signature(cuerpo, request.headers.get("Stripe-Signature"))
    try:
        evento = json.loads(cuerpo)
    except ValueError:
        raise InvalidInputError("Cuerpo inválido.", code="invalid_payload") from None
    return {"result": await collect.handle_stripe_event(db, evento)}


@router.post("/webhooks/plaid")
async def plaid_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    cuerpo = await request.body()
    await providers.verify_plaid_webhook(cuerpo, request.headers.get("Plaid-Verification"))
    try:
        evento = json.loads(cuerpo)
    except ValueError:
        raise InvalidInputError("Cuerpo inválido.", code="invalid_payload") from None
    if evento.get("webhook_type") == "TRANSACTIONS" and evento.get("item_id"):
        try:
            await bankfeed.sync_item(db, evento["item_id"])
        except DomainError:
            # Se registra en la conexión (last_error); Plaid no necesita reintentar.
            pass
    return {"result": "ok"}


# ---------------------------------------------------------------------------
# Banca conectada
# ---------------------------------------------------------------------------

@router.post("/bank-feeds/link-token")
async def bank_link_token(organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_bank)) -> dict:
    return {"link_token": await bankfeed.link_token(organization_id, current_user)}


@router.get("/bank-feeds/connections")
async def bank_connections(response: Response, db: AsyncSession = Depends(get_db),
                           organization_id: uuid.UUID = Depends(get_organization_id),
                           pag: tuple[int, int] = Depends(pagination_params),
                           current_user: User = Depends(_bank)) -> list[dict]:
    return paginate_list(await bankfeed.list_connections(db, organization_id), limit=pag[0], offset=pag[1],
                         response=response)


@router.post("/bank-feeds/connections", status_code=201)
async def bank_connect(payload: ConnectIn, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_bank)) -> dict:
    return await bankfeed.connect(db, organization_id=organization_id, user=current_user,
                                  public_token=payload.public_token, institution_name=payload.institution_name,
                                  institution_id=payload.institution_id)


@router.post("/bank-feeds/connections/{connection_id}/sync")
async def bank_sync(connection_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_bank)) -> dict:
    return await bankfeed.sync(db, organization_id=organization_id, connection_id=connection_id)


@router.delete("/bank-feeds/connections/{connection_id}", status_code=204)
async def bank_disconnect(connection_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_bank)) -> None:
    await bankfeed.disconnect(db, organization_id=organization_id, user=current_user, connection_id=connection_id)


@router.patch("/bank-feeds/accounts/{account_id}")
async def bank_account_visible(account_id: uuid.UUID, payload: VisibleIn, db: AsyncSession = Depends(get_db),
                               organization_id: uuid.UUID = Depends(get_organization_id),
                               current_user: User = Depends(_bank)) -> dict:
    return await bankfeed.set_account_visible(db, organization_id=organization_id, user=current_user,
                                              account_id=account_id, visible=payload.visible)


@router.get("/bank-feeds/counts")
async def bank_counts(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_bank)) -> dict:
    return await bankfeed.counts(db, organization_id)


@router.get("/bank-feeds/transactions")
async def bank_transactions(response: Response, status: str = Query("review", pattern="^(review|categorized|excluded)$"),
                            account_id: uuid.UUID | None = None, q: str | None = Query(default=None, max_length=80),
                            db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            pag: tuple[int, int] = Depends(pagination_params),
                            current_user: User = Depends(_bank)) -> list[dict]:
    filas, total = await bankfeed.list_transactions(db, organization_id=organization_id, status=status,
                                                    account_id=account_id, q=q, limit=pag[0], offset=pag[1])
    response.headers["X-Total-Count"] = str(total)
    return filas


@router.get("/bank-feeds/transactions/{tx_id}/candidates")
async def bank_candidates(tx_id: uuid.UUID, response: Response, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          pag: tuple[int, int] = Depends(pagination_params),
                          current_user: User = Depends(_bank)) -> list[dict]:
    t = await bankfeed.get_tx(db, organization_id, tx_id)
    return paginate_list(await bankfeed.candidates(db, organization_id, t), limit=pag[0], offset=pag[1],
                         response=response)


@router.post("/bank-feeds/transactions/{tx_id}/add")
async def bank_add(tx_id: uuid.UUID, payload: AddIn, db: AsyncSession = Depends(get_db),
                   organization_id: uuid.UUID = Depends(get_organization_id),
                   current_user: User = Depends(_bank)) -> dict:
    return await bankfeed.add(db, organization_id=organization_id, user=current_user, tx_id=tx_id,
                              category=payload.category, project_id=payload.project_id, person_id=payload.person_id,
                              memo=payload.memo)


@router.post("/bank-feeds/transactions/{tx_id}/match")
async def bank_match(tx_id: uuid.UUID, payload: MatchIn, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     current_user: User = Depends(_bank)) -> dict:
    return await bankfeed.match(db, organization_id=organization_id, user=current_user, tx_id=tx_id,
                                matched_type=payload.matched_type, matched_id=payload.matched_id)


@router.post("/bank-feeds/transactions/{tx_id}/exclude")
async def bank_exclude(tx_id: uuid.UUID, payload: MemoIn, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_bank)) -> dict:
    return await bankfeed.exclude(db, organization_id=organization_id, user=current_user, tx_id=tx_id,
                                  memo=payload.memo)


@router.post("/bank-feeds/transactions/{tx_id}/undo")
async def bank_undo(tx_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_bank)) -> dict:
    return await bankfeed.undo(db, organization_id=organization_id, user=current_user, tx_id=tx_id)


@router.post("/bank-feeds/transactions/accept")
async def bank_accept(payload: AcceptIn, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_bank)) -> dict:
    return await bankfeed.accept_suggested(db, organization_id=organization_id, user=current_user, tx_ids=payload.ids)


@router.get("/bank-feeds/rules")
async def bank_rules(response: Response, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     pag: tuple[int, int] = Depends(pagination_params),
                     current_user: User = Depends(_bank)) -> list[dict]:
    return paginate_list(await bankfeed.list_rules(db, organization_id), limit=pag[0], offset=pag[1],
                         response=response)


@router.post("/bank-feeds/rules", status_code=201)
async def bank_rule_create(payload: RuleIn, db: AsyncSession = Depends(get_db),
                           organization_id: uuid.UUID = Depends(get_organization_id),
                           current_user: User = Depends(_bank)) -> dict:
    return await bankfeed.save_rule(db, organization_id=organization_id, user=current_user, data=payload.model_dump())


@router.put("/bank-feeds/rules/{rule_id}")
async def bank_rule_update(rule_id: uuid.UUID, payload: RuleIn, db: AsyncSession = Depends(get_db),
                           organization_id: uuid.UUID = Depends(get_organization_id),
                           current_user: User = Depends(_bank)) -> dict:
    return await bankfeed.save_rule(db, organization_id=organization_id, user=current_user,
                                    data=payload.model_dump(), rule_id=rule_id)


@router.delete("/bank-feeds/rules/{rule_id}", status_code=204)
async def bank_rule_delete(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                           organization_id: uuid.UUID = Depends(get_organization_id),
                           current_user: User = Depends(_bank)) -> None:
    await bankfeed.delete_rule(db, organization_id=organization_id, user=current_user, rule_id=rule_id)
