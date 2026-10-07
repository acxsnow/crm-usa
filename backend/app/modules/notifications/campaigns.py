"""Campañas de productos por SMS y correo (spec `2026-10-07-campanas-sms-design.md`).

El dueño elige a quién escribir: clientes del sistema y contactos propios que
carga a mano o desde una lista (`MarketingContact`). Las reglas que no se
pueden saltar son ley de EE. UU.:

- **SMS (TCPA y 10DLC):** solo a números con permiso de mercadeo registrado
  (`MarketingConsent`); cada mensaje dice cómo darse de baja (STOP); solo de
  8 a. m. a 9 p. m. en la hora del cliente.
- **Correo (CAN-SPAM):** solo a correos con permiso (`EmailMarketingConsent`);
  cada correo lleva la dirección postal de la empresa y un enlace de baja.

El permiso va por número o correo, sin importar si es cliente o contacto
propio. Una baja solo la deshace la propia persona.
"""
import re
import secrets
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
    EmailMarketingConsent,
    MarketingConsent,
    MarketingContact,
    Product,
)
from app.modules.notifications.service import render
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError
from app.shared.normalize import normalize_phone

logger = structlog.get_logger(__name__)

CHANNELS = ("sms", "email", "both")
OPT_OUT_FOOTER = "Responde STOP para no recibir más."
# Solo palabras inequívocas: un "sí" puede ser respuesta a otra cosa.
START_WORDS = {"START", "UNSTOP"}
STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "ALTO", "PARAR", "BAJA", "CANCELAR"}
START_HOUR, END_HOUR = 8, 21
STATE_ZONES = {"AZ": "America/Phoenix", "CA": "America/Los_Angeles", "NV": "America/Los_Angeles"}
DEFAULT_ZONE = "America/Los_Angeles"
MAX_ATTEMPTS = 3
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str | None) -> str | None:
    e = (email or "").strip().lower()
    return e if _EMAIL.match(e) else None


def valid_phone(phone: str | None) -> str | None:
    tel = normalize_phone(phone)
    return tel if tel and len(tel) == 10 else None


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


def channels_of(campaign_channel: str) -> list[str]:
    return ["sms", "email"] if campaign_channel == "both" else [campaign_channel]


# ---------------------------------------------------------------------------
# Productos
# ---------------------------------------------------------------------------

async def get_product(db, organization_id, product_id) -> Product:
    p = await db.get(Product, product_id)
    if p is None or p.organization_id != organization_id:
        raise NotFoundError("El producto no existe.", code="product_not_found")
    return p


# ---------------------------------------------------------------------------
# Permisos
# ---------------------------------------------------------------------------

async def _sms_consents(db, organization_id) -> dict[str, MarketingConsent]:
    filas = (await db.execute(select(MarketingConsent).where(
        MarketingConsent.organization_id == organization_id))).scalars().all()
    return {c.phone: c for c in filas}


async def _email_consents(db, organization_id) -> dict[str, EmailMarketingConsent]:
    filas = (await db.execute(select(EmailMarketingConsent).where(
        EmailMarketingConsent.organization_id == organization_id))).scalars().all()
    return {c.email: c for c in filas}


async def _grant(db, organization_id, user, *, phone=None, email=None, customer_id=None, fuente: str,
                 sms_cache: dict, email_cache: dict) -> int:
    """Registra el permiso de un número y/o un correo. No reactiva bajas:
    quien se dio de baja solo vuelve si él mismo lo pide (START)."""
    total = 0
    if phone:
        c = sms_cache.get(phone)
        if c is None:
            c = MarketingConsent(organization_id=organization_id, phone=phone, status="none")
            db.add(c)
            sms_cache[phone] = c
        if c.status != "revoked":
            c.customer_id, c.status, c.source = customer_id, "granted", fuente[:255]
            c.granted_at, c.granted_by_user_id = _now(), user.id
            total += 1
    if email:
        e = email_cache.get(email)
        if e is None:
            e = EmailMarketingConsent(organization_id=organization_id, email=email, status="none",
                                      unsubscribe_token=secrets.token_urlsafe(32))
            db.add(e)
            email_cache[email] = e
        if e.status != "revoked":
            e.customer_id, e.status, e.source = customer_id, "granted", fuente[:255]
            e.granted_at, e.granted_by_user_id = _now(), user.id
            total += 1
    return total


def _check_source(source: str) -> str:
    fuente = (source or "").strip()
    if len(fuente) < 5:
        raise InvalidInputError("Escribe de dónde sale el permiso (por ejemplo «firmó en la visita»).",
                                code="consent_source_required")
    return fuente


# ---------------------------------------------------------------------------
# Contactos propios (no son clientes)
# ---------------------------------------------------------------------------

def parse_contacts(text: str) -> tuple[list[dict], list[str]]:
    """Una persona por línea: nombre, teléfono y/o correo, separados por coma,
    punto y coma o tabulación, en cualquier orden. Devuelve (válidos, líneas malas)."""
    validos, malas = [], []
    for linea in (text or "").splitlines():
        if not linea.strip():
            continue
        partes = [p.strip() for p in re.split(r"[,;\t]", linea) if p.strip()]
        tel = email = None
        nombre = []
        for p in partes:
            if normalize_email(p):
                email = normalize_email(p)
            elif valid_phone(p):
                tel = valid_phone(p)
            elif not re.fullmatch(r"[\d\s()+.-]+", p):
                nombre.append(p)
        if not tel and not email:
            malas.append(linea.strip()[:80])
            continue
        validos.append({"name": " ".join(nombre)[:255] or None, "phone": tel, "email": email})
    return validos, malas


async def import_contacts(db: AsyncSession, *, organization_id, user, text: str, source: str) -> dict:
    """Carga contactos propios y registra su permiso con la fuente indicada."""
    fuente = _check_source(source)
    validos, malas = parse_contacts(text)
    if not validos:
        raise InvalidInputError("No encontré ningún teléfono de 10 dígitos ni correo válido.", code="no_contacts")
    if len(validos) > 5000:
        raise InvalidInputError("Máximo 5.000 contactos por carga.", code="too_many_contacts")
    existentes = (await db.execute(select(MarketingContact).where(
        MarketingContact.organization_id == organization_id))).scalars().all()
    por_tel = {c.phone: c for c in existentes if c.phone}
    por_mail = {c.email: c for c in existentes if c.email}
    sms_cache, email_cache = await _sms_consents(db, organization_id), await _email_consents(db, organization_id)
    nuevos = actualizados = bajas = 0
    for v in validos:
        c = (v["phone"] and por_tel.get(v["phone"])) or (v["email"] and por_mail.get(v["email"]))
        if c is None:
            c = MarketingContact(organization_id=organization_id, name=v["name"], phone=v["phone"], email=v["email"],
                                 created_by_user_id=user.id)
            db.add(c)
            nuevos += 1
        else:
            c.name = v["name"] or c.name
            c.phone, c.email = v["phone"] or c.phone, v["email"] or c.email
            actualizados += 1
        if c.phone:
            por_tel[c.phone] = c
        if c.email:
            por_mail[c.email] = c
        if (v["phone"] and getattr(sms_cache.get(v["phone"]), "status", None) == "revoked") or \
                (v["email"] and getattr(email_cache.get(v["email"]), "status", None) == "revoked"):
            bajas += 1
        await _grant(db, organization_id, user, phone=v["phone"], email=v["email"], fuente=fuente,
                     sms_cache=sms_cache, email_cache=email_cache)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="campaigns.contacts_imported", entity_type="marketing_contact",
                             after_data={"new": nuevos, "updated": actualizados, "source": fuente})
    await db.commit()
    return {"created": nuevos, "updated": actualizados, "invalid": malas, "already_opted_out": bajas}


# ---------------------------------------------------------------------------
# Público
# ---------------------------------------------------------------------------

async def audience(db: AsyncSession, organization_id, filters: dict | None = None) -> list[dict]:
    """Clientes y contactos propios con teléfono o correo que cumplen los filtros.

    Filtros (opcionales): `selected` (claves `c:<id>` / `k:<id>` elegidas a mano),
    `customer_ids`, `program_ids`, `stages`, `states`, `cities`, `tags`, `search`,
    `include_contacts` (por defecto sí). Los filtros de programa, etapa y lugar
    dejan fuera a los contactos propios, que no tienen esos datos."""
    from app.modules.cases.models import Case, Program
    from app.modules.crm.models import Customer

    f = filters or {}
    sms, mails = await _sms_consents(db, organization_id), await _email_consents(db, organization_id)
    filas: list[dict] = []
    clientes = (await db.execute(select(Customer).where(Customer.organization_id == organization_id))).scalars().all()
    casos = (await db.execute(select(Case).where(Case.organization_id == organization_id,
                                                 Case.customer_id.is_not(None))
                              .order_by(Case.updated_at.desc()))).scalars().all()
    ultimo: dict = {}
    for c in casos:
        ultimo.setdefault(c.customer_id, c)
    programas = {p.id: p.name for p in (await db.execute(select(Program).where(
        Program.organization_id == organization_id))).scalars().all()}
    for cl in clientes:
        tel, mail = valid_phone(cl.main_phone), normalize_email(cl.email)
        if not tel and not mail:
            continue
        caso = ultimo.get(cl.id)
        filas.append({
            "key": f"c:{cl.id}", "kind": "customer", "customer_id": str(cl.id), "contact_id": None,
            "name": cl.legal_name, "phone": tel, "email": mail,
            "state": caso.address_state if caso else None, "city": caso.address_city if caso else None,
            "program_id": str(caso.program_id) if caso and caso.program_id else None,
            "program": programas.get(caso.program_id) if caso else None,
            "stage": caso.stage_code if caso else None, "tags": cl.tags or [],
        })
    if f.get("include_contacts", True):
        for k in (await db.execute(select(MarketingContact).where(
                MarketingContact.organization_id == organization_id))).scalars().all():
            filas.append({"key": f"k:{k.id}", "kind": "contact", "customer_id": None, "contact_id": str(k.id),
                          "name": k.name or "Contacto", "phone": k.phone, "email": k.email, "state": None,
                          "city": None, "program_id": None, "program": None, "stage": None, "tags": []})
    for r in filas:
        r["consent"] = (sms[r["phone"]].status if r["phone"] in sms else "none") if r["phone"] else "no_phone"
        r["email_consent"] = (mails[r["email"]].status if r["email"] in mails else "none") if r["email"] else "no_email"
        if r["consent"] not in ("granted", "revoked", "no_phone"):
            r["consent"] = "none"
        if r["email_consent"] not in ("granted", "revoked", "no_email"):
            r["email_consent"] = "none"

    elegidos = set(f.get("selected") or []) | {f"c:{x}" for x in f.get("customer_ids") or []}
    buscar = (f.get("search") or "").strip().lower()
    salida = []
    for r in filas:
        if elegidos and r["key"] not in elegidos:
            continue
        if f.get("program_ids") and r["program_id"] not in {str(x) for x in f["program_ids"]}:
            continue
        if f.get("stages") and r["stage"] not in f["stages"]:
            continue
        if f.get("states") and (r["state"] or "").upper() not in {s.upper() for s in f["states"]}:
            continue
        if f.get("cities") and (r["city"] or "").lower() not in {c.lower() for c in f["cities"]}:
            continue
        if f.get("tags") and not set(f["tags"]) & set(r["tags"]):
            continue
        if buscar and buscar not in f"{r['name']} {r['phone'] or ''} {r['email'] or ''} {r['city'] or ''}".lower():
            continue
        salida.append(r)
    return salida


def summarize(filas: list[dict], channel: str = "sms") -> dict:
    campo = "email_consent" if channel == "email" else "consent"
    return {"total": len(filas), "with_consent": sum(1 for f in filas if f[campo] == "granted"),
            "without_consent": sum(1 for f in filas if f[campo] == "none"),
            "opted_out": sum(1 for f in filas if f[campo] == "revoked"),
            "no_address": sum(1 for f in filas if f[campo] in ("no_phone", "no_email"))}


async def grant_consent(db: AsyncSession, *, organization_id, user, keys: list[str], source: str,
                        channel: str = "sms") -> int:
    """Registra el permiso (SMS, correo o ambos) de clientes o contactos elegidos."""
    from app.modules.crm.models import Customer

    fuente = _check_source(source)
    sms_cache, email_cache = await _sms_consents(db, organization_id), await _email_consents(db, organization_id)
    total = 0
    for clave in keys:
        tipo, _, ident = str(clave).partition(":")
        if not ident:
            tipo, ident = "c", tipo  # compatibilidad: id de cliente suelto
        try:
            obj = await db.get(Customer if tipo == "c" else MarketingContact, uuid.UUID(ident))
        except ValueError:
            continue
        if obj is None or obj.organization_id != organization_id:
            continue
        tel = valid_phone(obj.main_phone if tipo == "c" else obj.phone)
        mail = normalize_email(obj.email)
        total += await _grant(db, organization_id, user, phone=tel if channel in ("sms", "both") else None,
                              email=mail if channel in ("email", "both") else None,
                              customer_id=obj.id if tipo == "c" else None, fuente=fuente,
                              sms_cache=sms_cache, email_cache=email_cache)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="campaigns.consent_granted", entity_type="marketing_consent",
                             after_data={"keys": len(keys), "channel": channel, "source": fuente})
    await db.commit()
    return total


# ---------------------------------------------------------------------------
# Bajas
# ---------------------------------------------------------------------------

async def _skip_pending(db, *, channel: str, address: str, organization_id=None) -> None:
    stmt = select(CampaignRecipient).where(CampaignRecipient.channel == channel, CampaignRecipient.address == address,
                                           CampaignRecipient.status == "pending")
    if organization_id is not None:
        stmt = stmt.where(CampaignRecipient.organization_id == organization_id)
    for r in (await db.execute(stmt)).scalars().all():
        motivo = "Se dio de baja (STOP)" if channel == "sms" else "Se dio de baja del correo"
        r.status, r.last_error, r.next_attempt_at = "skipped", motivo, None


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
    await _skip_pending(db, channel="sms", address=tel, organization_id=organization_id)
    await db.commit()
    return len(filas)


async def email_opt_out(db: AsyncSession, *, organization_id, email: str, reason: str) -> None:
    mail = normalize_email(email)
    if not mail:
        raise InvalidInputError("Ese correo no es válido.", code="invalid_email")
    c = (await db.execute(select(EmailMarketingConsent).where(
        EmailMarketingConsent.organization_id == organization_id,
        EmailMarketingConsent.email == mail))).scalar_one_or_none()
    if c is None:
        c = EmailMarketingConsent(organization_id=organization_id, email=mail,
                                  unsubscribe_token=secrets.token_urlsafe(32))
        db.add(c)
    c.status, c.revoked_at, c.revoked_reason = "revoked", _now(), reason[:255]
    await _skip_pending(db, channel="email", address=mail, organization_id=organization_id)
    await db.commit()


async def unsubscribe_by_token(db: AsyncSession, token: str) -> bool:
    """El enlace de baja de un correo. Idempotente."""
    c = (await db.execute(select(EmailMarketingConsent).where(
        EmailMarketingConsent.unsubscribe_token == token))).scalar_one_or_none()
    if c is None:
        return False
    if c.status != "revoked":
        c.status, c.revoked_at, c.revoked_reason = "revoked", _now(), "Enlace de baja del correo"
        await _skip_pending(db, channel="email", address=c.email, organization_id=c.organization_id)
        await db.commit()
    return True


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


async def opt_in_again(db: AsyncSession, *, phone: str, word: str) -> int:
    """El cliente responde START: vuelve a quedar con permiso donde se había dado de baja."""
    tel = normalize_phone(phone)
    if not tel:
        return 0
    # Solo donde ya había dado permiso y se dio de baja por SMS. Una baja pedida
    # por otro medio (registro manual) o una organización donde nunca dio
    # permiso no se reactivan con un START.
    filas = (await db.execute(select(MarketingConsent).where(
        MarketingConsent.phone == tel, MarketingConsent.status == "revoked",
        MarketingConsent.granted_at.is_not(None), MarketingConsent.revoked_reason.like("Respondió %")))).scalars().all()
    for c in filas:
        c.status, c.source, c.granted_at = "granted", f"El cliente respondió {word}", _now()
        c.revoked_at, c.revoked_reason, c.granted_by_user_id = None, None, None
    await db.commit()
    return len(filas)


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
    texto = render(campaign.message, await _context(db, campaign, nombre))
    return with_footer(texto) if campaign.channel in ("sms", "both") else texto


async def preview_subject(db, campaign: Campaign, nombre: str = "María") -> str:
    return render(campaign.subject or campaign.name, await _context(db, campaign, nombre))


async def launch(db: AsyncSession, *, organization_id, user, campaign_id, scheduled_at: datetime | None = None) -> dict:
    """Arma la lista de envío con quienes tienen permiso, por canal, y la pone en cola."""
    c = await get_campaign(db, organization_id, campaign_id)
    if c.status != "draft":
        raise ConflictError("La campaña ya se lanzó.", code="campaign_not_draft")
    canales = channels_of(c.channel)
    if "email" in canales:
        if not (c.subject or "").strip():
            raise InvalidInputError("La campaña por correo necesita un asunto.", code="campaign_subject_required")
        if get_settings().MARKETING_EMAIL_PROVIDER == "smtp":
            from app.modules.notifications.marketing_email import MarketingEmailConfigurationError, check_ready

            try:
                check_ready()
            except MarketingEmailConfigurationError as exc:
                raise InvalidInputError(f"El correo de campañas no está listo. {exc}",
                                        code="marketing_email_not_ready") from None
    filas = await audience(db, organization_id, c.audience)
    inicio = max(scheduled_at or _now(), _now())
    resumen, en_cola, vistos = {}, 0, set()
    for canal in canales:
        resumen[canal] = summarize(filas, canal)
        campo = "email_consent" if canal == "email" else "consent"
        for f in filas:
            direccion = f["email"] if canal == "email" else f["phone"]
            if f[campo] != "granted" or (canal, direccion) in vistos:
                continue
            vistos.add((canal, direccion))
            zona = zone_for_state(f["state"])
            ctx = await _context(db, c, f["name"])
            cuerpo = render(c.message, ctx)
            db.add(CampaignRecipient(
                organization_id=organization_id, campaign_id=c.id,
                customer_id=uuid.UUID(f["customer_id"]) if f["customer_id"] else None,
                contact_id=uuid.UUID(f["contact_id"]) if f["contact_id"] else None,
                name=f["name"], channel=canal, address=direccion,
                phone=f["phone"] if canal == "sms" else None, email=f["email"] if canal == "email" else None,
                timezone=zona, status="pending", attempts=0,
                subject=render(c.subject or "", ctx) if canal == "email" else None,
                body=with_footer(cuerpo) if canal == "sms" else cuerpo,
                next_attempt_at=next_allowed(inicio, zona) if canal == "sms" else inicio))
            en_cola += 1
    if en_cola == 0:
        raise InvalidInputError("Nadie del público tiene permiso de mercadeo registrado para este canal.",
                                code="campaign_no_consented_recipients")
    c.status, c.scheduled_at = "scheduled", inicio
    total = {"queued": en_cola, "by_channel": resumen,
             "without_consent": sum(r["without_consent"] for r in resumen.values()),
             "opted_out": sum(r["opted_out"] for r in resumen.values())}
    c.audience = {**(c.audience or {}), "launch_summary": total}
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id, action="campaigns.launched",
                             entity_type="campaign", entity_id=str(c.id), after_data=total)
    await db.commit()
    return total


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

    await send_sms(to=to, message=body)
    return "sent"


async def _email(to: str, subject: str, body: str, token: str) -> str:
    from app.modules.notifications.marketing_email import send_marketing_email

    return await send_marketing_email(to=to, subject=subject, body=body, unsubscribe_token=token)


async def _current_consent(db, r: CampaignRecipient):
    if r.channel == "email":
        return (await db.execute(select(EmailMarketingConsent).where(
            EmailMarketingConsent.organization_id == r.organization_id,
            EmailMarketingConsent.email == r.address))).scalar_one_or_none()
    return (await db.execute(select(MarketingConsent).where(
        MarketingConsent.organization_id == r.organization_id, MarketingConsent.phone == r.address))).scalar_one_or_none()


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
        permiso = await _current_consent(db, r)
        if permiso is None or permiso.status != "granted":
            r.status, r.last_error, r.next_attempt_at = "skipped", "Sin permiso de mercadeo vigente", None
            continue
        if r.channel == "sms":
            permitido = next_allowed(ahora, r.timezone)
            if permitido > ahora:  # fuera de horario: espera a las 8 a. m. del cliente
                r.next_attempt_at = permitido
                continue
        r.attempts += 1
        try:
            if r.channel == "email":
                resultado = await _email(r.address, r.subject or c.name, r.body, permiso.unsubscribe_token)
            else:
                resultado = await _sms(r.address, r.body)
        except Exception as exc:
            r.last_error = f"{type(exc).__name__}: {exc}"[:500]
            if r.attempts >= MAX_ATTEMPTS:
                r.status, r.next_attempt_at = "failed", None
            else:
                r.next_attempt_at = ahora + timedelta(minutes=5 * r.attempts)
        else:
            if resultado == "test":
                proveedor = "MARKETING_EMAIL_PROVIDER no es smtp" if r.channel == "email" else "SMS_PROVIDER no es masiv"
                r.status, r.last_error = "skipped", f"Modo de prueba: {proveedor}, no se envió."
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
