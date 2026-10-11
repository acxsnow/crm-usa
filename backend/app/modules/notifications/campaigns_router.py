"""Rutas de campañas de SMS. Todo exige `notifications.manage` salvo el
webhook de Masiv, que se autentica con un token secreto en la URL."""
import hmac
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_permission
from app.core.config import get_settings
from app.db.session import get_db
from app.modules.notifications import campaigns as svc
from app.modules.notifications.models import (
    Campaign,
    CampaignRecipient,
    EmailMarketingConsent,
    MarketingConsent,
    MarketingContact,
    Product,
)
from app.modules.users.models import User
from app.shared.pagination import paginate, pagination_params
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
async def list_products(response: Response, pagination: tuple[int, int] = Depends(pagination_params),
                        db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_manage)) -> list[dict]:
    limit, offset = pagination
    filas = await paginate(db, select(Product).where(Product.organization_id == organization_id)
                           .order_by(Product.active.desc(), Product.name, Product.id),
                           limit=limit, offset=offset, response=response)
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
    selected: list[str] = Field(default=[], max_length=10000)  # claves "c:<id>" (cliente) o "k:<id>" (contacto)
    include_contacts: bool = True
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
    return {"summary": svc.summarize(filas, "sms"), "email_summary": svc.summarize(filas, "email"), "contacts": filas}


class ConsentIn(BaseModel):
    keys: list[str] = Field(default=[], max_length=10000)
    customer_ids: list[uuid.UUID] = Field(default=[], max_length=10000)
    channel: str = Field(default="sms", pattern="^(sms|email|both)$")
    source: str = Field(max_length=255)
    confirm: bool


@router.post("/campaigns/consents")
async def grant_consent(payload: ConsentIn, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_manage)) -> dict:
    if not payload.confirm:
        raise InvalidInputError("Confirma que esas personas aceptaron recibir promociones por SMS.",
                                code="consent_confirmation_required")
    claves = payload.keys + [f"c:{x}" for x in payload.customer_ids]
    if not claves:
        raise InvalidInputError("Elige a quién registrarle el permiso.", code="consent_keys_required")
    total = await svc.grant_consent(db, organization_id=organization_id, user=current_user, keys=claves,
                                    source=payload.source, channel=payload.channel)
    return {"granted": total}


class OptOutIn(BaseModel):
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    reason: str = Field(default="Pidió no recibir más", max_length=255)


@router.post("/campaigns/opt-outs")
async def manual_opt_out(payload: OptOutIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)) -> dict:
    if payload.email:
        await svc.email_opt_out(db, organization_id=organization_id, email=payload.email, reason=payload.reason)
    elif payload.phone and len(payload.phone) >= 7:
        await svc.opt_out(db, phone=payload.phone, reason=payload.reason, organization_id=organization_id)
    else:
        raise InvalidInputError("Escribe el teléfono o el correo.", code="opt_out_address_required")
    return {"ok": True}


@router.get("/campaigns/opt-outs")
async def list_opt_outs(response: Response, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        pagination: tuple[int, int] = Depends(pagination_params),
                        current_user: User = Depends(_manage)) -> list[dict]:
    """Bajas de SMS y de correo juntas, las más recientes primero. Paginado
    (`limit`/`offset`, total en X-Total-Count): las bajas solo se acumulan. Las
    dos tablas se unen en la base (UNION ALL) para ordenar y paginar juntas."""
    sms = select(literal("sms").label("channel"), MarketingConsent.phone.label("address"),
                 MarketingConsent.revoked_reason.label("reason"), MarketingConsent.revoked_at.label("at")).where(
        MarketingConsent.organization_id == organization_id, MarketingConsent.status == "revoked")
    correo = select(literal("email").label("channel"), EmailMarketingConsent.email.label("address"),
                    EmailMarketingConsent.revoked_reason.label("reason"),
                    EmailMarketingConsent.revoked_at.label("at")).where(
        EmailMarketingConsent.organization_id == organization_id, EmailMarketingConsent.status == "revoked")
    bajas = union_all(sms, correo).subquery()
    limit, offset = pagination
    response.headers["X-Total-Count"] = str((await db.execute(select(func.count()).select_from(bajas))).scalar_one())
    filas = (await db.execute(select(bajas).order_by(bajas.c.at.desc(), bajas.c.address)
                              .limit(limit).offset(offset))).all()
    return [{"channel": f.channel, "address": f.address, "phone": f.address if f.channel == "sms" else None,
             "reason": f.reason, "at": f.at.isoformat() if f.at else None} for f in filas]


# --- Contactos propios -------------------------------------------------------

class ImportIn(BaseModel):
    text: str = Field(min_length=3, max_length=500_000)
    source: str = Field(max_length=255)
    confirm: bool


@router.get("/campaigns/contacts")
async def list_contacts(response: Response, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        pagination: tuple[int, int] = Depends(pagination_params),
                        current_user: User = Depends(_manage)) -> list[dict]:
    """Paginado (`limit`/`offset`, total en X-Total-Count): se importan en masa."""
    limit, offset = pagination
    filas = await paginate(db, select(MarketingContact).where(MarketingContact.organization_id == organization_id)
                           .order_by(MarketingContact.created_at.desc(), MarketingContact.id.desc()),
                           limit=limit, offset=offset, response=response)
    return [{"id": str(k.id), "name": k.name, "phone": k.phone, "email": k.email} for k in filas]


@router.post("/campaigns/contacts/import")
async def import_contacts(payload: ImportIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_manage)) -> dict:
    """Pegar una lista: una persona por línea con nombre, teléfono y/o correo."""
    if not payload.confirm:
        raise InvalidInputError("Confirma que estas personas aceptaron recibir promociones.",
                                code="consent_confirmation_required")
    return await svc.import_contacts(db, organization_id=organization_id, user=current_user, text=payload.text,
                                     source=payload.source)


@router.delete("/campaigns/contacts/{contact_id}", status_code=204)
async def delete_contact(contact_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)):
    """Quita el contacto de la lista. Su baja (si la pidió) se conserva."""
    from fastapi import Response

    k = await db.get(MarketingContact, contact_id)
    if k is None or k.organization_id != organization_id:
        raise NotFoundError("El contacto no existe.", code="contact_not_found")
    await db.delete(k)
    await db.commit()
    return Response(status_code=204)


# --- Campañas ------------------------------------------------------------------

class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    product_id: uuid.UUID | None = None
    channel: str = Field(default="sms", pattern="^(sms|email|both)$")
    subject: str | None = Field(default=None, max_length=255)
    # Un SMS largo llega a 3 partes (480); el correo admite más texto.
    message: str = Field(min_length=1, max_length=5000)
    audience: AudienceIn = AudienceIn()


async def _out(db, c: Campaign) -> dict:
    return {"id": str(c.id), "name": c.name, "product_id": str(c.product_id) if c.product_id else None,
            "channel": c.channel, "subject": c.subject, "preview_subject": await svc.preview_subject(db, c),
            "message": c.message, "audience": c.audience, "status": c.status,
            "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
            "finished_at": c.finished_at.isoformat() if c.finished_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "preview": await svc.preview_text(db, c), "stats": await svc.stats(db, c)}


def _check_length(payload: "CampaignIn") -> None:
    if payload.channel in ("sms", "both") and len(payload.message) > 480:
        raise InvalidInputError("Por SMS el mensaje admite hasta 480 caracteres (3 SMS).", code="sms_too_long")


@router.get("/campaigns")
async def list_campaigns(response: Response, pagination: tuple[int, int] = Depends(pagination_params),
                         db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)) -> list[dict]:
    limit, offset = pagination
    filas = await paginate(db, select(Campaign).where(Campaign.organization_id == organization_id)
                           .order_by(Campaign.created_at.desc(), Campaign.id.desc()),
                           limit=limit, offset=offset, response=response)
    return [await _out(db, c) for c in filas]


@router.post("/campaigns", status_code=201)
async def create_campaign(payload: CampaignIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_manage)) -> dict:
    if payload.product_id:
        await svc.get_product(db, organization_id, payload.product_id)
    _check_length(payload)
    c = Campaign(organization_id=organization_id, name=payload.name, product_id=payload.product_id,
                 channel=payload.channel, subject=(payload.subject or "").strip() or None,
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
    _check_length(payload)
    c.name, c.product_id, c.message = payload.name, payload.product_id, payload.message.strip()
    c.channel, c.subject = payload.channel, (payload.subject or "").strip() or None
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
    phone: str | None = Field(default=None, max_length=30)
    channel: str = Field(default="sms", pattern="^(sms|email)$")


@router.post("/campaigns/{campaign_id}/test")
async def test_send(campaign_id: uuid.UUID, payload: TestIn, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_manage)) -> dict:
    """Prueba al número de quien arma la campaña (no pasa por el público)."""
    from app.shared.normalize import normalize_phone

    from app.modules.notifications.service import preference_for

    c = await svc.get_campaign(db, organization_id, campaign_id)
    if payload.channel == "email":
        # La prueba por correo va al correo de quien la pide, nunca a otro.
        from app.modules.notifications.service import render

        texto = render(c.message, await svc._context(db, c, current_user.full_name))
        resultado = await svc._email(current_user.email, await svc.preview_subject(db, c, current_user.full_name),
                                     texto, "prueba-sin-baja")
        return {"result": resultado, "text": texto, "to": current_user.email}
    tel = normalize_phone(payload.phone)
    # Solo a tu propio celular registrado: si no, la prueba serviría para
    # escribirle a cualquiera sin su permiso.
    propio = normalize_phone((await preference_for(db, current_user)).sms_phone)
    if not tel or tel != propio:
        raise InvalidInputError("La prueba solo va a tu celular registrado en Notificaciones → «Cómo me avisan».",
                                code="test_phone_not_own")
    texto = await svc.preview_text(db, c, current_user.full_name)
    resultado = await svc._sms(tel, texto)
    return {"result": resultado, "text": texto}


@router.get("/campaigns/{campaign_id}/recipients")
async def recipients(campaign_id: uuid.UUID, response: Response, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     pagination: tuple[int, int] = Depends(pagination_params),
                     current_user: User = Depends(_manage)) -> list[dict]:
    """Paginado (`limit`/`offset`, total en X-Total-Count): una campaña puede
    tener miles de destinatarios."""
    c = await svc.get_campaign(db, organization_id, campaign_id)
    limit, offset = pagination
    filas = await paginate(db, select(CampaignRecipient).where(CampaignRecipient.campaign_id == c.id)
                           .order_by(CampaignRecipient.name, CampaignRecipient.id),
                           limit=limit, offset=offset, response=response)
    return [{"id": str(r.id), "name": r.name, "channel": r.channel, "address": r.address, "phone": r.phone,
             "status": r.status, "attempts": r.attempts,
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



# --- Enlace de baja de los correos (público) -----------------------------------

_BAJA_HTML = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{titulo}</title></head>
<body style="font-family:Arial,sans-serif;max-width:480px;margin:15vh auto;padding:0 16px;color:#171514">
<h1 style="font-size:22px">{titulo}</h1><p>{texto}</p></body></html>"""


_CONFIRMAR_HTML = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Darme de baja</title></head>
<body style="font-family:Arial,sans-serif;max-width:480px;margin:15vh auto;padding:0 16px;color:#171514">
<h1 style="font-size:22px">¿No quieres recibir más promociones por correo?</h1>
<form method="post"><button type="submit" style="font:inherit;padding:12px 20px;border:0;border-radius:8px;
background:#cf1d2b;color:#fff;cursor:pointer">Sí, darme de baja</button></form></body></html>"""


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe_page(token: str):
    """Abrir el enlace NO da de baja: los escáneres de enlaces del correo
    (Outlook, antivirus) lo abren solos. Muestra un botón que hace el POST."""
    return HTMLResponse(_CONFIRMAR_HTML)


@router.post("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe(token: str, db: AsyncSession = Depends(get_db)):
    """Da de baja ese correo. Público: lo usa quien recibió el correo (botón de
    la página o baja con un clic de Gmail/Outlook, List-Unsubscribe-Post). El
    token es aleatorio y solo da de baja ese correo."""
    ok = len(token) >= 20 and await svc.unsubscribe_by_token(db, token)
    if not ok:
        return HTMLResponse(_BAJA_HTML.format(titulo="Enlace no válido",
                                              texto="Este enlace de baja no existe o ya no es válido."), status_code=404)
    return HTMLResponse(_BAJA_HTML.format(titulo="Listo, te dimos de baja",
                                          texto="No volverás a recibir nuestras promociones por correo."))
