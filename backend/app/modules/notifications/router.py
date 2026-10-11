"""Rutas del módulo 7: avisos propios, preferencias y administración."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.notifications import service
from app.modules.notifications.catalog import NOTICES
from app.modules.notifications.models import (
    CHANNELS,
    DELIVERY_STATUSES,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationTemplate,
)
from app.modules.users.models import User
from app.shared.errors import InvalidInputError, NotFoundError
from app.shared.pagination import paginate, paginate_list, pagination_params

router = APIRouter(prefix="/notifications", tags=["notifications"])
# Administración tiene `notifications.manage` y no `read_own`: también ve los suyos.
_own = require_any_permission("notifications.read_own", "notifications.manage")
_manage = require_permission("notifications.manage")


def _out(n: Notification) -> dict:
    return {"id": str(n.id), "event": n.event, "title": n.title, "body": n.body, "link": n.link,
            "read": n.read_at is not None, "created_at": n.created_at.isoformat()}


# --- Mis avisos --------------------------------------------------------------

@router.get("")
async def my_notifications(unread: bool = False, limit: int = Query(30, ge=1, le=100), db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(_own)) -> dict:
    stmt = select(Notification).where(Notification.user_id == current_user.id)
    if unread:
        stmt = stmt.where(Notification.read_at.is_(None))
    filas = (await db.execute(stmt.order_by(Notification.created_at.desc()).limit(limit))).scalars().all()
    sin_leer = (await db.execute(select(func.count()).select_from(Notification).where(
        Notification.user_id == current_user.id, Notification.read_at.is_(None)))).scalar_one()
    return {"items": [_out(n) for n in filas], "unread": sin_leer}


@router.get("/unread-count")
async def unread_count(db: AsyncSession = Depends(get_db), current_user: User = Depends(_own)) -> dict:
    total = (await db.execute(select(func.count()).select_from(Notification).where(
        Notification.user_id == current_user.id, Notification.read_at.is_(None)))).scalar_one()
    return {"unread": total}


@router.post("/{notification_id}/read")
async def mark_read(notification_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    current_user: User = Depends(_own)) -> dict:
    n = await db.get(Notification, notification_id)
    # Lo ajeno responde 404: ni siquiera se confirma que existe.
    if n is None or n.user_id != current_user.id:
        raise NotFoundError("El aviso no existe.", code="notification_not_found")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        await db.commit()
    return _out(n)


@router.post("/read-all")
async def mark_all_read(db: AsyncSession = Depends(get_db), current_user: User = Depends(_own)) -> dict:
    await db.execute(update(Notification).where(Notification.user_id == current_user.id,
                                                Notification.read_at.is_(None))
                     .values(read_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"unread": 0}


class PreferenceIn(BaseModel):
    email_enabled: bool
    sms_enabled: bool
    sms_phone: str | None = Field(default=None, max_length=30)


@router.get("/preferences")
async def get_preferences(db: AsyncSession = Depends(get_db), current_user: User = Depends(_own)) -> dict:
    p = await service.preference_for(db, current_user)
    return {"email_enabled": p.email_enabled, "sms_enabled": p.sms_enabled, "sms_phone": p.sms_phone,
            "email": current_user.email}


@router.put("/preferences")
async def set_preferences(payload: PreferenceIn, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(_own)) -> dict:
    from app.shared.normalize import normalize_phone

    telefono = normalize_phone(payload.sms_phone) if payload.sms_phone else None
    if payload.sms_enabled and not telefono:
        raise InvalidInputError("Para recibir SMS escribe un celular válido.", code="sms_phone_required")
    p = (await db.execute(select(NotificationPreference).where(
        NotificationPreference.user_id == current_user.id))).scalar_one_or_none()
    if p is None:
        p = NotificationPreference(organization_id=current_user.organization_id, user_id=current_user.id)
        db.add(p)
    p.email_enabled, p.sms_enabled, p.sms_phone = payload.email_enabled, payload.sms_enabled, telefono
    await db.commit()
    return {"email_enabled": p.email_enabled, "sms_enabled": p.sms_enabled, "sms_phone": p.sms_phone,
            "email": current_user.email}


# --- Administración ----------------------------------------------------------

@router.get("/deliveries")
async def deliveries(response: Response, status: str | None = None, channel: str | None = None,
                     pagination: tuple[int, int] = Depends(pagination_params),
                     db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                     current_user: User = Depends(_manage)) -> list[dict]:
    """Historial de envíos por correo y SMS, con su estado. Paginado: crece con cada aviso."""
    stmt = select(NotificationDelivery, Notification).join(
        Notification, Notification.id == NotificationDelivery.notification_id).where(
        NotificationDelivery.organization_id == organization_id)
    if status in DELIVERY_STATUSES:
        stmt = stmt.where(NotificationDelivery.status == status)
    if channel in CHANNELS:
        stmt = stmt.where(NotificationDelivery.channel == channel)
    limit, offset = pagination
    filas = await paginate(db, stmt.order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc()),
                           limit=limit, offset=offset, response=response, scalars=False)
    return [{"id": str(d.id), "channel": d.channel, "to": d.to, "subject": d.subject, "status": d.status,
             "attempts": d.attempts, "last_error": d.last_error, "event": n.event,
             "notice_label": NOTICES.get(n.event, {}).get("label", n.event), "title": n.title,
             "created_at": d.created_at.isoformat(), "sent_at": d.sent_at.isoformat() if d.sent_at else None}
            for d, n in filas]


@router.post("/deliveries/{delivery_id}/resend")
async def resend(delivery_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                 organization_id: uuid.UUID = Depends(get_organization_id),
                 current_user: User = Depends(_manage)) -> dict:
    d = await service.resend(db, organization_id=organization_id, delivery_id=delivery_id)
    return {"id": str(d.id), "status": d.status, "attempts": d.attempts, "last_error": d.last_error}


@router.get("/templates")
async def templates(response: Response, pagination: tuple[int, int] = Depends(pagination_params),
                    db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_manage)) -> list[dict]:
    """Cada aviso con su texto vigente por canal (el editado o el de fábrica).
    Se recorta la lista de avisos antes de consultar los textos."""
    limit, offset = pagination
    salida = []
    for code, n in paginate_list(list(NOTICES.items()), limit=limit, offset=offset, response=response):
        canales = {}
        for canal in CHANNELS:
            asunto, cuerpo, activa = await service.template_for(db, organization_id, code, canal)
            editada = (await db.execute(select(NotificationTemplate.id).where(
                NotificationTemplate.organization_id == organization_id, NotificationTemplate.event == code,
                NotificationTemplate.channel == canal))).first() is not None
            canales[canal] = {"subject": asunto, "body": cuerpo, "active": activa, "customized": editada}
        salida.append({"code": code, "label": n["label"], "audience": n["audience"], "channels": canales})
    return salida


class TemplateIn(BaseModel):
    subject: str | None = Field(default=None, max_length=255)
    body: str = Field(min_length=1, max_length=2000)
    active: bool = True


@router.put("/templates/{code}/{channel}")
async def set_template(code: str, channel: str, payload: TemplateIn, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_manage)) -> dict:
    from app.shared.audit import record_audit_event

    if code not in NOTICES or channel not in CHANNELS:
        raise NotFoundError("Ese aviso o canal no existe.", code="template_not_found")
    if channel == "in_app" and not payload.active:
        raise InvalidInputError("El aviso en la app no se puede apagar.", code="in_app_required")
    fila = (await db.execute(select(NotificationTemplate).where(
        NotificationTemplate.organization_id == organization_id, NotificationTemplate.event == code,
        NotificationTemplate.channel == channel))).scalar_one_or_none()
    if fila is None:
        fila = NotificationTemplate(organization_id=organization_id, event=code, channel=channel)
        db.add(fila)
    fila.subject, fila.body, fila.active = payload.subject, payload.body.strip(), payload.active
    await record_audit_event(db, organization_id=organization_id, actor_user_id=current_user.id,
                             action="notifications.template_updated", entity_type="notification_template",
                             entity_id=f"{code}:{channel}", after_data={"active": payload.active})
    await db.commit()
    return {"code": code, "channel": channel, "subject": fila.subject, "body": fila.body, "active": fila.active}


@router.delete("/templates/{code}/{channel}", status_code=204)
async def reset_template(code: str, channel: str, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)):
    """Vuelve al texto de fábrica."""
    from fastapi import Response

    fila = (await db.execute(select(NotificationTemplate).where(
        NotificationTemplate.organization_id == organization_id, NotificationTemplate.event == code,
        NotificationTemplate.channel == channel))).scalar_one_or_none()
    if fila is not None:
        await db.delete(fila)
        await db.commit()
    return Response(status_code=204)


class SettingsIn(BaseModel):
    approval_alert_business_days: int = Field(ge=1, le=30)
    permit_expiry_alert_days: int = Field(ge=1, le=90)


@router.get("/settings")
async def get_settings_(db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_manage)) -> dict:
    from app.core.config import get_settings

    s = await service.get_settings_row(db, organization_id)
    await db.commit()
    cfg = get_settings()
    return {"approval_alert_business_days": s.approval_alert_business_days,
            "permit_expiry_alert_days": s.permit_expiry_alert_days,
            "customer_sms_enabled": s.customer_sms_enabled,
            "email_provider": cfg.EMAIL_PROVIDER, "sms_provider": cfg.SMS_PROVIDER}


@router.put("/settings")
async def set_settings(payload: SettingsIn, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_manage)) -> dict:
    s = await service.get_settings_row(db, organization_id)
    s.approval_alert_business_days = payload.approval_alert_business_days
    s.permit_expiry_alert_days = payload.permit_expiry_alert_days
    await db.commit()
    return await get_settings_(db=db, organization_id=organization_id, current_user=current_user)
