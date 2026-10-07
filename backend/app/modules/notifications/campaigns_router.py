"""Rutas de campañas de SMS. Todo exige `notifications.manage` salvo el
webhook de Masiv, que se autentica con un token secreto en la URL."""
import hmac
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_permission
from app.core.config import get_settings
from app.db.session import get_db
from app.modules.notifications import campaigns as svc
from app.modules.notifications.models import Campaign, CampaignRecipient, MarketingConsent, Product
from app.modules.users.models import User
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

router = APIRouter(tags=["campaigns"])
_manage = require_permission("notifications.manage")


# --- Productos ---------------------------------------------------------------

class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    price: str | None = Field(default=None, max_length=50)
    active: bool = True


def _product(p: Product) -> dict:
    return {"id": str(p.id), "name": p.name, "description": p.description, "price": p.price, "active": p.active}


@router.get("/products")
async def list_products(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_manage)) -> list[dict]:
    filas = (await db.execute(select(Product).where(Product.organization_id == organization_id)
                              .order_by(Product.active.desc(), Product.name))).scalars().all()
    return [_product(p) for p in filas]


@router.post("/products", status_code=201)
async def create_product(payload: ProductIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)) -> dict:
    p = Product(organization_id=organization_id, **payload.model_dump())
    db.add(p)
    await db.commit()
    return _product(p)


@router.put("/products/{product_id}")
async def update_product(product_id: uuid.UUID, payload: ProductIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)) -> dict:
    p = await svc.get_product(db, organization_id, product_id)
    for k, v in payload.model_dump().items():
        setattr(p, k, v)
    await db.commit()
    return _product(p)


# --- Público y consentimiento -------------------------------------------------

class AudienceIn(BaseModel):
    customer_ids: list[uuid.UUID] = []
    program_ids: list[uuid.UUID] = []
    stages: list[str] = []
    states: list[str] = []
    cities: list[str] = []
    tags: list[str] = []
    search: str | None = Field(default=None, max_length=100)


@router.post("/campaigns/audience")
async def audience(payload: AudienceIn, db: AsyncSession = Depends(get_db),
                   organization_id: uuid.UUID = Depends(get_organization_id),
                   current_user: User = Depends(_manage)) -> dict:
    filas = await svc.audience(db, organization_id, payload.model_dump(mode="json"))
    return {"summary": svc.summarize(filas), "contacts": filas}


class ConsentIn(BaseModel):
    customer_ids: list[uuid.UUID] = Field(min_length=1, max_length=5000)
    source: str = Field(max_length=255)
    confirm: bool


@router.post("/campaigns/consents")
async def grant_consent(payload: ConsentIn, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_manage)) -> dict:
    if not payload.confirm:
        raise InvalidInputError("Confirma que esas personas aceptaron recibir promociones por SMS.",
                                code="consent_confirmation_required")
    total = await svc.grant_consent(db, organization_id=organization_id, user=current_user,
                                    customer_ids=payload.customer_ids, source=payload.source)
    return {"granted": total}


class OptOutIn(BaseModel):
    phone: str = Field(min_length=7, max_length=30)
    reason: str = Field(default="Pidió no recibir más", max_length=255)


@router.post("/campaigns/opt-outs")
async def manual_opt_out(payload: OptOutIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)) -> dict:
    await svc.opt_out(db, phone=payload.phone, reason=payload.reason, organization_id=organization_id)
    return {"ok": True}


@router.get("/campaigns/opt-outs")
async def list_opt_outs(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_manage)) -> list[dict]:
    filas = (await db.execute(select(MarketingConsent).where(
        MarketingConsent.organization_id == organization_id, MarketingConsent.status == "revoked")
        .order_by(MarketingConsent.revoked_at.desc()))).scalars().all()
    return [{"phone": c.phone, "reason": c.revoked_reason,
             "at": c.revoked_at.isoformat() if c.revoked_at else None} for c in filas]


# --- Campañas ------------------------------------------------------------------

class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    product_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=480)
    audience: AudienceIn = AudienceIn()


async def _out(db, c: Campaign) -> dict:
    return {"id": str(c.id), "name": c.name, "product_id": str(c.product_id) if c.product_id else None,
            "message": c.message, "audience": c.audience, "status": c.status,
            "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
            "finished_at": c.finished_at.isoformat() if c.finished_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "preview": await svc.preview_text(db, c), "stats": await svc.stats(db, c)}


@router.get("/campaigns")
async def list_campaigns(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)) -> list[dict]:
    filas = (await db.execute(select(Campaign).where(Campaign.organization_id == organization_id)
                              .order_by(Campaign.created_at.desc()))).scalars().all()
    return [await _out(db, c) for c in filas]


@router.post("/campaigns", status_code=201)
async def create_campaign(payload: CampaignIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_manage)) -> dict:
    if payload.product_id:
        await svc.get_product(db, organization_id, payload.product_id)
    c = Campaign(organization_id=organization_id, name=payload.name, product_id=payload.product_id,
                 message=payload.message.strip(), audience=payload.audience.model_dump(mode="json"),
                 status="draft", created_by_user_id=current_user.id)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return await _out(db, c)


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_manage)) -> dict:
    return await _out(db, await svc.get_campaign(db, organization_id, campaign_id))


@router.put("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: uuid.UUID, payload: CampaignIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_manage)) -> dict:
    c = await svc.get_campaign(db, organization_id, campaign_id)
    if c.status != "draft":
        raise ConflictError("Una campaña lanzada ya no se edita.", code="campaign_not_draft")
    if payload.product_id:
        await svc.get_product(db, organization_id, payload.product_id)
    c.name, c.product_id, c.message = payload.name, payload.product_id, payload.message.strip()
    c.audience = payload.audience.model_dump(mode="json")
    await db.commit()
    await db.refresh(c)
    return await _out(db, c)


class LaunchIn(BaseModel):
    scheduled_at: datetime | None = None


@router.post("/campaigns/{campaign_id}/launch")
async def launch(campaign_id: uuid.UUID, payload: LaunchIn, db: AsyncSession = Depends(get_db),
                 organization_id: uuid.UUID = Depends(get_organization_id),
                 current_user: User = Depends(_manage)) -> dict:
    resumen = await svc.launch(db, organization_id=organization_id, user=current_user, campaign_id=campaign_id,
                               scheduled_at=payload.scheduled_at)
    c = await svc.get_campaign(db, organization_id, campaign_id)
    return {"summary": resumen, "campaign": await _out(db, c)}


@router.post("/campaigns/{campaign_id}/cancel")
async def cancel(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                 organization_id: uuid.UUID = Depends(get_organization_id),
                 current_user: User = Depends(_manage)) -> dict:
    return await _out(db, await svc.cancel(db, organization_id=organization_id, user=current_user,
                                           campaign_id=campaign_id))


class TestIn(BaseModel):
    phone: str = Field(min_length=7, max_length=30)


@router.post("/campaigns/{campaign_id}/test")
async def test_send(campaign_id: uuid.UUID, payload: TestIn, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_manage)) -> dict:
    """Prueba al número de quien arma la campaña (no pasa por el público)."""
    from app.shared.normalize import normalize_phone

    c = await svc.get_campaign(db, organization_id, campaign_id)
    tel = normalize_phone(payload.phone)
    if not tel or len(tel) != 10:
        raise InvalidInputError("Escribe un celular de EE. UU. de 10 dígitos.", code="invalid_phone")
    texto = await svc.preview_text(db, c, current_user.full_name)
    resultado = await svc._sms(tel, texto)
    return {"result": resultado, "text": texto}


@router.get("/campaigns/{campaign_id}/recipients")
async def recipients(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     current_user: User = Depends(_manage)) -> list[dict]:
    c = await svc.get_campaign(db, organization_id, campaign_id)
    filas = (await db.execute(select(CampaignRecipient).where(CampaignRecipient.campaign_id == c.id)
                              .order_by(CampaignRecipient.name))).scalars().all()
    return [{"id": str(r.id), "name": r.name, "phone": r.phone, "status": r.status, "attempts": r.attempts,
             "last_error": r.last_error, "next_attempt_at": r.next_attempt_at.isoformat() if r.next_attempt_at else None,
             "sent_at": r.sent_at.isoformat() if r.sent_at else None} for r in filas]


# --- Webhook de Masiv: respuestas entrantes (STOP) -----------------------------

@router.post("/webhooks/masiv/inbound")
async def masiv_inbound(request: Request, token: str = "", db: AsyncSession = Depends(get_db)) -> dict:
    """Masiv reenvía aquí las respuestas de los clientes. Se autentica con
    `MASIV_WEBHOOK_TOKEN` en la URL (`?token=…`). Acepta JSON o formulario con
    el número en `from`/`msisdn`/`phone` y el texto en `message`/`text`/`body`."""
    esperado = get_settings().MASIV_WEBHOOK_TOKEN
    if not esperado or not hmac.compare_digest(token, esperado):
        raise NotFoundError("No encontrado.", code="not_found")
    try:
        datos = await request.json()
    except Exception:
        datos = dict(await request.form())
    tel = next((str(datos[k]) for k in ("from", "msisdn", "phone", "sender") if datos.get(k)), "")
    texto = next((str(datos[k]) for k in ("message", "text", "body") if datos.get(k)), "")
    baja = await svc.handle_inbound(db, phone=tel, text=texto)
    return {"ok": True, "opted_out": baja}
