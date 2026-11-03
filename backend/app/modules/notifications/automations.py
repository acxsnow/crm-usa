"""Campañas automáticas por evento (como las de Housecall Pro): un mensaje que
sale solo N días después de cerrar una obra.

- «Gracias por confiar en nosotros» el día que se cierra la obra (0 días).
- «Ya toca el mantenimiento de tu aire» a los 180 días.

Usan todo lo de las campañas: solo a quien tiene permiso de mercadeo en ese
canal, SMS solo de 8 a. m. a 9 p. m. del cliente y con STOP, correo con baja.
Cada automatización tiene una campaña contenedora en estado «auto» donde caen
sus envíos, así se ven en la misma cola y en sus estadísticas.

Una obra se procesa una sola vez por automatización
(`CampaignAutomationSend`), y solo las cerradas desde que se activó: activarla
no les escribe de golpe a todos los clientes viejos.
"""
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications import campaigns as camp
from app.modules.notifications.models import (
    Campaign,
    CampaignAutomation,
    CampaignAutomationSend,
    CampaignRecipient,
)
from app.modules.notifications.service import render
from app.shared.audit import record_audit_event
from app.shared.errors import InvalidInputError, NotFoundError

logger = structlog.get_logger(__name__)

TRIGGERS = {
    "job_completed": "Al cerrar la obra",
    "maintenance_due": "Recordatorio de mantenimiento",
}
DEFAULT_DELAY = {"job_completed": 0, "maintenance_due": 180}
MAX_DELAY_DAYS = 730
AUTO_STATUS = "auto"
# Variables que puede usar el mensaje, además de {{nombre}}.
VARIABLES = ("nombre", "obra", "fecha_cierre")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def out(a: CampaignAutomation, stats: dict | None = None) -> dict:
    return {"id": str(a.id), "name": a.name, "trigger": a.trigger, "trigger_label": TRIGGERS.get(a.trigger, a.trigger),
            "delay_days": a.delay_days, "channel": a.channel, "subject": a.subject, "message": a.message,
            "active": a.active, "starts_on": a.starts_on.isoformat(), "campaign_id": str(a.campaign_id),
            "stats": stats or {}}


def _validate(data: dict) -> dict:
    trigger = data.get("trigger")
    if trigger not in TRIGGERS:
        raise InvalidInputError("El evento de la automatización no existe.", code="automation_trigger_unknown")
    canal = data.get("channel") or "sms"
    if canal not in camp.CHANNELS:
        raise InvalidInputError("El canal es sms, email o both.", code="campaign_channel_invalid")
    dias = data.get("delay_days")
    dias = DEFAULT_DELAY[trigger] if dias is None else int(dias)
    if not 0 <= dias <= MAX_DELAY_DAYS:
        raise InvalidInputError(f"Los días van de 0 a {MAX_DELAY_DAYS}.", code="automation_delay_invalid")
    mensaje = (data.get("message") or "").strip()
    if not mensaje:
        raise InvalidInputError("Escribe el mensaje.", code="campaign_message_required")
    asunto = (data.get("subject") or "").strip() or None
    if canal in ("email", "both") and not asunto:
        raise InvalidInputError("El correo necesita un asunto.", code="campaign_subject_required")
    nombre = (data.get("name") or "").strip() or TRIGGERS[trigger]
    return {"name": nombre[:255], "trigger": trigger, "delay_days": dias, "channel": canal, "subject": asunto,
            "message": mensaje, "active": data.get("active") is not False}


async def _pending(db: AsyncSession, a: CampaignAutomation) -> list[CampaignRecipient]:
    return list((await db.execute(select(CampaignRecipient).where(
        CampaignRecipient.campaign_id == a.campaign_id, CampaignRecipient.status == "pending"))).scalars().all())


async def _skip_pending(db: AsyncSession, a: CampaignAutomation, motivo: str) -> None:
    """Pausar o eliminar también detiene lo que ya estaba en cola."""
    for r in await _pending(db, a):
        r.status, r.last_error, r.next_attempt_at = "skipped", motivo, None


async def _requeue_pending(db: AsyncSession, a: CampaignAutomation) -> None:
    """Con el texto editado, lo pendiente no sale con el texto viejo: se saca de
    la cola y sus obras vuelven a procesarse en la próxima corrida."""
    from app.modules.field_ops.models import Project

    pendientes = await _pending(db, a)
    clientes = {r.customer_id for r in pendientes if r.customer_id}
    for r in pendientes:
        await db.delete(r)
    await db.flush()
    if clientes:
        await db.execute(sql_delete(CampaignAutomationSend).where(
            CampaignAutomationSend.automation_id == a.id, CampaignAutomationSend.result == "queued",
            CampaignAutomationSend.project_id.in_(select(Project.id).where(Project.customer_id.in_(clientes)))))


async def get(db: AsyncSession, organization_id, automation_id) -> CampaignAutomation:
    a = await db.get(CampaignAutomation, automation_id)
    if a is None or a.organization_id != organization_id:
        raise NotFoundError("La automatización no existe.", code="automation_not_found")
    return a


async def create(db: AsyncSession, *, organization_id, user, data: dict) -> CampaignAutomation:
    datos = _validate(data)
    contenedora = Campaign(organization_id=organization_id, name=f"Automática: {datos['name']}",
                           channel=datos["channel"], subject=datos["subject"], message=datos["message"],
                           audience={"automation": True}, status=AUTO_STATUS, created_by_user_id=user.id)
    db.add(contenedora)
    await db.flush()
    a = CampaignAutomation(organization_id=organization_id, campaign_id=contenedora.id, starts_on=_now(),
                           created_by_user_id=user.id, **datos)
    db.add(a)
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="campaigns.automation_created", entity_type="campaign_automation",
                             entity_id=str(a.id), after_data={k: v for k, v in datos.items() if k != "message"})
    await db.commit()
    return a


async def update(db: AsyncSession, *, organization_id, user, automation_id, data: dict) -> CampaignAutomation:
    a = await get(db, organization_id, automation_id)
    datos = _validate({**out(a), **{k: v for k, v in data.items() if v is not None}})
    antes = a.active
    texto_cambio = (datos["message"], datos["subject"], datos["channel"]) != (a.message, a.subject, a.channel)
    for k, v in datos.items():
        setattr(a, k, v)
    if a.active and not antes:
        # Reactivar no recupera lo cerrado mientras estuvo apagada.
        a.starts_on = _now()
    contenedora = await db.get(Campaign, a.campaign_id)
    contenedora.channel, contenedora.subject, contenedora.message = a.channel, a.subject, a.message
    if antes and not a.active:
        await _skip_pending(db, a, "Automatización pausada")
    elif texto_cambio:
        await _requeue_pending(db, a)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="campaigns.automation_updated", entity_type="campaign_automation",
                             entity_id=str(a.id), after_data={"active": a.active, "delay_days": a.delay_days})
    await db.commit()
    return a


async def delete(db: AsyncSession, *, organization_id, user, automation_id) -> None:
    a = await get(db, organization_id, automation_id)
    contenedora = await db.get(Campaign, a.campaign_id)
    await _skip_pending(db, a, "Automatización eliminada")
    contenedora.status, contenedora.finished_at = "cancelled", _now()
    await db.delete(a)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="campaigns.automation_deleted", entity_type="campaign_automation",
                             entity_id=str(automation_id))
    await db.commit()


async def stats(db: AsyncSession, a: CampaignAutomation) -> dict:
    from sqlalchemy import func

    procesadas = dict((await db.execute(select(CampaignAutomationSend.result, func.count()).where(
        CampaignAutomationSend.automation_id == a.id).group_by(CampaignAutomationSend.result))).all())
    cola = await camp.stats(db, await db.get(Campaign, a.campaign_id))
    return {"jobs": procesadas, "messages": cola}


async def _due_projects(db: AsyncSession, a: CampaignAutomation, hoy) -> list:
    from app.modules.field_ops.models import Project, ProjectStatus

    hechas = select(CampaignAutomationSend.project_id).where(CampaignAutomationSend.automation_id == a.id)
    limite = hoy - timedelta(days=a.delay_days)
    return list((await db.execute(select(Project).where(
        Project.organization_id == a.organization_id, Project.status == ProjectStatus.completed,
        Project.completed_date.is_not(None), Project.completed_date <= limite,
        Project.completed_date >= a.starts_on.date(), Project.id.not_in(hechas))
        .order_by(Project.completed_date).limit(500))).scalars().all())


async def run_due(db: AsyncSession) -> int:
    """Pone en la cola los mensajes que ya tocan. La corre Celery cada hora;
    `send_due` de campañas los manda respetando permisos y horario. Cada
    automatización va en su propia transacción: si una falla se registra y las
    de las demás organizaciones siguen."""
    from app.modules.field_ops.clock import org_today

    ids = [(i, org) for i, org in (await db.execute(select(CampaignAutomation.id, CampaignAutomation.organization_id)
                                                    .where(CampaignAutomation.active.is_(True)))).all()]
    encoladas = 0
    for automation_id, organization_id in ids:
        try:
            a = await db.get(CampaignAutomation, automation_id)
            hoy = await org_today(db, a.organization_id)
            encoladas += await _run_one(db, a, hoy)
            await db.commit()
        except Exception as exc:  # noqa: BLE001 — una automatización rota no frena a las otras
            await db.rollback()
            logger.warning("automations.run_failed", automation_id=str(automation_id),
                           organization_id=str(organization_id), error_type=type(exc).__name__, error=str(exc))
    return encoladas


async def _run_one(db: AsyncSession, a: CampaignAutomation, hoy) -> int:
    from app.modules.crm.models import Customer

    obras = await _due_projects(db, a, hoy)
    if not obras:
        return 0
    encoladas = 0
    sms, mails = await camp._sms_consents(db, a.organization_id), await camp._email_consents(db, a.organization_id)
    for p in obras:
        cliente = await db.get(Customer, p.customer_id)
        tel = camp.valid_phone(cliente.main_phone) if cliente else None
        mail = camp.normalize_email(cliente.email) if cliente else None
        ctx = {"nombre": (cliente.legal_name or "").split(" ")[0] if cliente else "", "obra": p.title,
               "fecha_cierre": p.completed_date.strftime("%m/%d/%Y")}
        zona = camp.zone_for_state(p.address_state)
        ahora = _now()
        resultado = "no_contact" if not (tel or mail) else "no_consent"
        for canal in camp.channels_of(a.channel):
            direccion = mail if canal == "email" else tel
            permisos = mails if canal == "email" else sms
            if not direccion or direccion not in permisos or permisos[direccion].status != "granted":
                continue
            ya = (await db.execute(select(CampaignRecipient.id).where(
                CampaignRecipient.campaign_id == a.campaign_id, CampaignRecipient.channel == canal,
                CampaignRecipient.address == direccion))).first()
            if ya:
                # Una persona recibe cada automatización una sola vez por canal
                # (la cola no repite dirección por campaña), aunque tenga dos obras.
                resultado = "already_sent"
                continue
            cuerpo = render(a.message, ctx)
            # El título de la obra entra al asunto: sin saltos de línea y dentro del límite de la columna.
            asunto = " ".join(render(a.subject or "", ctx).split())[:255] if canal == "email" else None
            db.add(CampaignRecipient(
                organization_id=a.organization_id, campaign_id=a.campaign_id, customer_id=p.customer_id,
                name=cliente.legal_name if cliente else None, channel=canal, address=direccion,
                phone=tel if canal == "sms" else None, email=mail if canal == "email" else None,
                timezone=zona, status="pending", attempts=0, subject=asunto,
                body=camp.with_footer(cuerpo) if canal == "sms" else cuerpo,
                next_attempt_at=camp.next_allowed(ahora, zona) if canal == "sms" else ahora))
            resultado = "queued"
            encoladas += 1
        db.add(CampaignAutomationSend(organization_id=a.organization_id, automation_id=a.id, project_id=p.id,
                                      result=resultado, processed_at=_now()))
    return encoladas
