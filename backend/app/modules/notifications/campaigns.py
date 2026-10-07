"""Campañas de SMS de productos (spec `2026-10-07-campanas-sms-design.md`).

El dueño elige libremente a quién escribir entre los clientes con teléfono.
Tres reglas no se pueden saltar porque son la ley de EE. UU. (TCPA) y las
condiciones de los operadores (10DLC):

1. **Consentimiento.** Solo sale a números con permiso de mercadeo registrado
   (`MarketingConsent`), con su fuente y fecha. Se registra en la misma
   pantalla de la campaña.
2. **Baja.** Todo mensaje termina con "Responde STOP…"; quien responde STOP
   (webhook de Masiv o registro manual) queda fuera de inmediato, también de
   las campañas que ya estaban en cola.
3. **Horario.** Solo de 8 a. m. a 9 p. m. en la hora del cliente; fuera de
   ese rango el mensaje espera a las 8 a. m. del día siguiente.
"""
import re
import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.notifications.models import (
    Campaign,
    CampaignRecipient,
    MarketingConsent,
    Product,
)
from app.modules.notifications.service import render
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError
from app.shared.normalize import normalize_phone

logger = structlog.get_logger(__name__)

OPT_OUT_FOOTER = "Responde STOP para no recibir más."
START_WORDS = {"START", "UNSTOP", "YES", "SI", "ALTA"}
STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "ALTO", "PARAR", "BAJA", "CANCELAR"}
START_HOUR, END_HOUR = 8, 21
STATE_ZONES = {"AZ": "America/Phoenix", "CA": "America/Los_Angeles", "NV": "America/Los_Angeles"}
DEFAULT_ZONE = "America/Los_Angeles"
MAX_ATTEMPTS = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


def zone_for_state(state: str | None) -> str:
    return STATE_ZONES.get((state or "").upper(), DEFAULT_ZONE)


def next_allowed(moment: datetime, zone: str) -> datetime:
    """El primer instante, desde `moment`, dentro del horario permitido del cliente."""
    tz = ZoneInfo(zone)
    local = moment.astimezone(tz)
    if START_HOUR <= local.hour < END_HOUR:
        return moment
    dia = local.date() if local.hour < START_HOUR else local.date() + timedelta(days=1)
    return datetime.combine(dia, time(START_HOUR), tz).astimezone(timezone.utc)


def with_footer(texto: str) -> str:
    texto = (texto or "").strip()
    return texto if "STOP" in texto.upper() else f"{texto} {OPT_OUT_FOOTER}"


# ---------------------------------------------------------------------------
# Productos
# ---------------------------------------------------------------------------

async def get_product(db, organization_id, product_id) -> Product:
    p = await db.get(Product, product_id)
    if p is None or p.organization_id != organization_id:
        raise NotFoundError("El producto no existe.", code="product_not_found")
    return p


# ---------------------------------------------------------------------------
# Público y consentimiento
# ---------------------------------------------------------------------------

async def _consents(db, organization_id) -> dict[str, MarketingConsent]:
    filas = (await db.execute(select(MarketingConsent).where(
        MarketingConsent.organization_id == organization_id))).scalars().all()
    return {c.phone: c for c in filas}


async def audience(db: AsyncSession, organization_id, filters: dict | None = None) -> list[dict]:
    """Clientes con teléfono que cumplen los filtros, un renglón por número.

    Filtros (todos opcionales): `customer_ids` (selección a mano), `program_ids`,
    `stages`, `states`, `cities`, `tags`, `search`."""
    from app.modules.cases.models import Case, Program
    from app.modules.crm.models import Customer

    f = filters or {}
    clientes = (await db.execute(select(Customer).where(
        Customer.organization_id == organization_id, Customer.main_phone.is_not(None)))).scalars().all()
    casos = (await db.execute(select(Case).where(Case.organization_id == organization_id,
                                                 Case.customer_id.is_not(None))
                              .order_by(Case.updated_at.desc()))).scalars().all()
    ultimo: dict = {}
    for c in casos:
        ultimo.setdefault(c.customer_id, c)
    programas = {p.id: p.name for p in (await db.execute(select(Program).where(
        Program.organization_id == organization_id))).scalars().all()}
    permisos = await _consents(db, organization_id)
    ids = {str(x) for x in f.get("customer_ids") or []}
    buscar = (f.get("search") or "").strip().lower()
    salida, vistos = [], set()
    for cl in clientes:
        tel = normalize_phone(cl.main_phone)
        if not tel or len(tel) != 10 or tel in vistos:
            continue
        caso = ultimo.get(cl.id)
        fila = {
            "customer_id": str(cl.id), "name": cl.legal_name, "phone": tel,
            "state": caso.address_state if caso else None, "city": caso.address_city if caso else None,
            "program_id": str(caso.program_id) if caso and caso.program_id else None,
            "program": programas.get(caso.program_id) if caso else None,
            "stage": caso.stage_code if caso else None, "tags": cl.tags or [],
            "consent": permisos[tel].status if tel in permisos else "none",
        }
        if ids and fila["customer_id"] not in ids:
            continue
        if f.get("program_ids") and fila["program_id"] not in {str(x) for x in f["program_ids"]}:
            continue
        if f.get("stages") and fila["stage"] not in f["stages"]:
            continue
        if f.get("states") and (fila["state"] or "").upper() not in {s.upper() for s in f["states"]}:
            continue
        if f.get("cities") and (fila["city"] or "").lower() not in {c.lower() for c in f["cities"]}:
            continue
        if f.get("tags") and not set(f["tags"]) & set(fila["tags"]):
            continue
        if buscar and buscar not in f"{fila['name']} {tel} {fila['city'] or ''}".lower():
            continue
        vistos.add(tel)
        salida.append(fila)
    return salida


def summarize(filas: list[dict]) -> dict:
    return {"total": len(filas), "with_consent": sum(1 for f in filas if f["consent"] == "granted"),
            "without_consent": sum(1 for f in filas if f["consent"] == "none"),
            "opted_out": sum(1 for f in filas if f["consent"] == "revoked")}


async def grant_consent(db: AsyncSession, *, organization_id, user, customer_ids: list, source: str) -> int:
    """Registra el permiso de mercadeo de esos clientes. Exige la fuente: es lo
    que se muestra si alguien reclama ("firmó en la visita del 3 de oct")."""
    from app.modules.crm.models import Customer

    fuente = (source or "").strip()
    if len(fuente) < 5:
        raise InvalidInputError("Escribe de dónde sale el permiso (por ejemplo «firmó en la visita»).",
                                code="consent_source_required")
    permisos = await _consents(db, organization_id)
    total = 0
    for cid in customer_ids:
        cl = await db.get(Customer, uuid.UUID(str(cid)))
        if cl is None or cl.organization_id != organization_id:
            continue
        tel = normalize_phone(cl.main_phone)
        if not tel:
            continue
        c = permisos.get(tel) or MarketingConsent(organization_id=organization_id, phone=tel)
        if c.status == "revoked":
            # Quien se dio de baja solo vuelve si él mismo responde START: nadie
            # en la oficina puede deshacer su STOP (TCPA).
            continue
        c.customer_id, c.status, c.source = cl.id, "granted", fuente[:255]
        c.granted_at, c.granted_by_user_id, c.revoked_at, c.revoked_reason = _now(), user.id, None, None
        if tel not in permisos:
            db.add(c)
            permisos[tel] = c
        total += 1
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="campaigns.consent_granted", entity_type="marketing_consent",
                             after_data={"customers": len(customer_ids), "source": fuente})
    await db.commit()
    return total


async def opt_out(db: AsyncSession, *, phone: str, reason: str, organization_id=None) -> int:
    """Baja de un número. Sin organización (webhook) aplica en todas: el
    número dijo STOP a la cuenta de SMS, no a una organización en particular."""
    tel = normalize_phone(phone)
    if not tel:
        return 0
    stmt = select(MarketingConsent).where(MarketingConsent.phone == tel)
    if organization_id is not None:
        stmt = stmt.where(MarketingConsent.organization_id == organization_id)
    filas = list((await db.execute(stmt)).scalars().all())
    if organization_id is not None and not filas:
        filas = [MarketingConsent(organization_id=organization_id, phone=tel)]
        db.add(filas[0])
    for c in filas:
        c.status, c.revoked_at, c.revoked_reason = "revoked", _now(), reason[:255]
    # Lo que ya estaba en cola para ese número no sale.
    pend = select(CampaignRecipient).where(CampaignRecipient.phone == tel, CampaignRecipient.status == "pending")
    if organization_id is not None:
        pend = pend.where(CampaignRecipient.organization_id == organization_id)
    for r in (await db.execute(pend)).scalars().all():
        r.status, r.last_error, r.next_attempt_at = "skipped", "Se dio de baja (STOP)", None
    await db.commit()
    return len(filas)


async def handle_inbound(db: AsyncSession, *, phone: str, text: str) -> bool:
    palabra = re.sub(r"[^A-Z]", "", (text or "").strip().upper().split(" ")[0] if text else "")
    if palabra in START_WORDS:
        await opt_in_again(db, phone=phone, word=palabra)
        return False
    if palabra not in STOP_WORDS:
        return False
    await opt_out(db, phone=phone, reason=f"Respondió {palabra}")
    logger.info("campaigns.opt_out", phone_tail=(normalize_phone(phone) or "")[-4:])
    return True


# ---------------------------------------------------------------------------
# Campañas
# ---------------------------------------------------------------------------

async def get_campaign(db, organization_id, campaign_id) -> Campaign:
    c = await db.get(Campaign, campaign_id)
    if c is None or c.organization_id != organization_id:
        raise NotFoundError("La campaña no existe.", code="campaign_not_found")
    return c


async def _context(db, campaign: Campaign, nombre: str | None) -> dict:
    ctx = {"nombre": (nombre or "").split(" ")[0] if nombre else ""}
    if campaign.product_id:
        p = await db.get(Product, campaign.product_id)
        if p is not None:
            ctx.update({"producto": p.name, "precio": p.price or ""})
    return ctx


async def preview_text(db, campaign: Campaign, nombre: str = "María") -> str:
    return with_footer(render(campaign.message, await _context(db, campaign, nombre)))


async def launch(db: AsyncSession, *, organization_id, user, campaign_id, scheduled_at: datetime | None = None) -> dict:
    """Arma la lista de envío con quienes tienen permiso y la pone en cola."""
    c = await get_campaign(db, organization_id, campaign_id)
    if c.status != "draft":
        raise ConflictError("La campaña ya se lanzó.", code="campaign_not_draft")
    filas = await audience(db, organization_id, c.audience)
    con_permiso = [f for f in filas if f["consent"] == "granted"]
    if not con_permiso:
        raise InvalidInputError("Ningún contacto del público tiene permiso de mercadeo registrado.",
                                code="campaign_no_consented_recipients")
    inicio = max(scheduled_at or _now(), _now())
    for f in con_permiso:
        zona = zone_for_state(f["state"])
        db.add(CampaignRecipient(
            organization_id=organization_id, campaign_id=c.id, customer_id=uuid.UUID(f["customer_id"]),
            name=f["name"], phone=f["phone"], timezone=zona, status="pending", attempts=0,
            body=with_footer(render(c.message, await _context(db, c, f["name"]))),
            next_attempt_at=next_allowed(inicio, zona)))
    c.status, c.scheduled_at = "scheduled", inicio
    resumen = {**summarize(filas), "queued": len(con_permiso)}
    c.audience = {**(c.audience or {}), "launch_summary": resumen}
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="campaigns.launched",
                             entity_type="campaign", entity_id=str(c.id), after_data=resumen)
    await db.commit()
    return resumen


async def cancel(db: AsyncSession, *, organization_id, user, campaign_id) -> Campaign:
    c = await get_campaign(db, organization_id, campaign_id)
    if c.status in ("sent", "cancelled"):
        raise ConflictError("La campaña ya terminó.", code="campaign_finished")
    for r in (await db.execute(select(CampaignRecipient).where(
            CampaignRecipient.campaign_id == c.id, CampaignRecipient.status == "pending"))).scalars().all():
        r.status, r.last_error, r.next_attempt_at = "skipped", "Campaña cancelada", None
    c.status, c.finished_at = "cancelled", _now()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="campaigns.cancelled",
                             entity_type="campaign", entity_id=str(c.id))
    await db.commit()
    return c


async def _sms(to: str, body: str) -> str:
    """'sent' o 'test' (modo de prueba). Lanza si el proveedor falla."""
    if get_settings().SMS_PROVIDER != "masiv":
        logger.info("campaigns.sms_test_mode", phone_tail=to[-4:], length=len(body))
        return "test"
    from app.modules.notifications.sms import send_sms

    await send_sms(to=f"+1{to}", message=body)
    return "sent"


async def send_due(db: AsyncSession, limit: int = 200) -> int:
    ahora = _now()
    filas = (await db.execute(select(CampaignRecipient, Campaign).join(
        Campaign, Campaign.id == CampaignRecipient.campaign_id).where(
        CampaignRecipient.status == "pending", CampaignRecipient.next_attempt_at <= ahora,
        Campaign.status.in_(("scheduled", "sending"))).limit(limit))).all()
    tocadas = set()
    for r, c in filas:
        tocadas.add(c.id)
        if c.status == "scheduled":
            c.status, c.started_at = "sending", ahora
        permiso = (await db.execute(select(MarketingConsent).where(
            MarketingConsent.organization_id == r.organization_id, MarketingConsent.phone == r.phone))).scalar_one_or_none()
        if permiso is None or permiso.status != "granted":
            r.status, r.last_error, r.next_attempt_at = "skipped", "Sin permiso de mercadeo vigente", None
            continue
        permitido = next_allowed(ahora, r.timezone)
        if permitido > ahora:  # fuera de horario: espera a las 8 a. m. del cliente
            r.next_attempt_at = permitido
            continue
        r.attempts += 1
        try:
            resultado = await _sms(r.phone, r.body)
        except Exception as exc:
            r.last_error = f"{type(exc).__name__}: {exc}"[:500]
            if r.attempts >= MAX_ATTEMPTS:
                r.status, r.next_attempt_at = "failed", None
            else:
                r.next_attempt_at = ahora + timedelta(minutes=5 * r.attempts)
        else:
            if resultado == "test":
                r.status, r.last_error = "skipped", "Modo de prueba: SMS_PROVIDER no es masiv, no se envió."
            else:
                r.status, r.sent_at, r.last_error = "sent", ahora, None
            r.next_attempt_at = None
    await db.flush()
    for cid in tocadas:
        quedan = (await db.execute(select(func.count()).select_from(CampaignRecipient).where(
            CampaignRecipient.campaign_id == cid, CampaignRecipient.status == "pending"))).scalar_one()
        if quedan == 0:
            c = await db.get(Campaign, cid)
            c.status, c.finished_at = "sent", ahora
    await db.commit()
    return len(filas)


async def stats(db, campaign: Campaign) -> dict:
    filas = (await db.execute(select(CampaignRecipient.status, func.count()).where(
        CampaignRecipient.campaign_id == campaign.id).group_by(CampaignRecipient.status))).all()
    cuenta = {k: 0 for k in ("pending", "sent", "failed", "skipped")}
    cuenta.update({s: n for s, n in filas})
    return cuenta


async def opt_in_again(db: AsyncSession, *, phone: str, word: str) -> int:
    """El cliente responde START: vuelve a quedar con permiso donde se había dado de baja."""
    tel = normalize_phone(phone)
    if not tel:
        return 0
    filas = (await db.execute(select(MarketingConsent).where(MarketingConsent.phone == tel,
                                                             MarketingConsent.status == "revoked"))).scalars().all()
    for c in filas:
        c.status, c.source, c.granted_at = "granted", f"El cliente respondió {word}", _now()
        c.revoked_at, c.revoked_reason, c.granted_by_user_id = None, None, None
    await db.commit()
    return len(filas)
