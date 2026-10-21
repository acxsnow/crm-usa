"""Del evento al aviso, y del aviso al correo o SMS (módulo 7).

1. `process_event()` recibe un evento de dominio, decide qué aviso es y a
   quién va, y crea el aviso en la app (`Notification`) más un envío pendiente
   (`NotificationDelivery`) por cada canal que la persona tenga activo.
2. `deliver_pending()` toma los envíos pendientes y los manda, con reintentos
   espaciados. Un correo que falla no deshace nada: el hecho ya ocurrió.
3. `daily_alerts()` revisa expedientes que llevan demasiado en aprobación y
   permisos por vencer.

Todo recibe la sesión: lo llaman las tareas de Celery (`app/workers`) y las
pruebas, sin pasar por la cola.
"""
import re
import uuid
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions
from app.core.config import get_settings
from app.modules.notifications.catalog import DEFAULT_PERMISSION, NOTICES, default_text
from app.modules.notifications.models import (
    MAX_ATTEMPTS,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationSettings,
    NotificationTemplate,
)

logger = structlog.get_logger(__name__)
_VAR = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def render(texto: str, contexto: dict) -> str:
    return _VAR.sub(lambda m: str(contexto.get(m.group(1)) or ""), texto or "").strip()


# ---------------------------------------------------------------------------
# Ajustes, plantillas y preferencias
# ---------------------------------------------------------------------------

async def get_settings_row(db: AsyncSession, organization_id) -> NotificationSettings:
    fila = (await db.execute(select(NotificationSettings).where(
        NotificationSettings.organization_id == organization_id))).scalar_one_or_none()
    if fila is None:
        fila = NotificationSettings(organization_id=organization_id, approval_alert_business_days=3,
                                    permit_expiry_alert_days=7, customer_sms_enabled=False)
        db.add(fila)
        await db.flush()
    return fila


async def template_for(db, organization_id, code: str, channel: str) -> tuple[str, str, bool]:
    """(asunto, cuerpo, activa). Lo editado por la organización o el texto por defecto."""
    fila = (await db.execute(select(NotificationTemplate).where(
        NotificationTemplate.organization_id == organization_id, NotificationTemplate.event == code,
        NotificationTemplate.channel == channel))).scalar_one_or_none()
    if fila is None:
        asunto, cuerpo = default_text(code, channel)
        return asunto, cuerpo, True
    return fila.subject or "", fila.body, fila.active


async def preference_for(db, user) -> NotificationPreference:
    fila = (await db.execute(select(NotificationPreference).where(
        NotificationPreference.user_id == user.id))).scalar_one_or_none()
    return fila or NotificationPreference(organization_id=user.organization_id, user_id=user.id,
                                          email_enabled=True, sms_enabled=False)


# ---------------------------------------------------------------------------
# Destinatarios y contexto de cada evento
# ---------------------------------------------------------------------------

async def _users_with(db, organization_id, permission: str) -> list:
    from app.modules.users.models import User, UserStatus

    usuarios = (await db.execute(select(User).where(
        User.organization_id == organization_id, User.status == UserStatus.active))).scalars().all()
    return [u for u in usuarios if permission in get_effective_permissions(u)]


async def _user(db, user_id) -> list:
    from app.modules.users.models import User, UserStatus

    if not user_id:
        return []
    u = await db.get(User, uuid.UUID(str(user_id)))
    return [u] if u is not None and u.status == UserStatus.active else []


async def _case_context(db, case_id) -> tuple:
    from app.modules.cases.models import Case, Program
    from app.modules.crm.models import Customer
    from app.modules.users.models import User

    case = await db.get(Case, uuid.UUID(str(case_id)))
    if case is None:
        return None, {}
    cliente = await db.get(Customer, case.customer_id) if case.customer_id else None
    programa = await db.get(Program, case.program_id) if case.program_id else None
    vendedor = await db.get(User, case.assigned_salesperson_id) if case.assigned_salesperson_id else None
    return case, {
        "expediente": case.case_number,
        "cliente": cliente.legal_name if cliente else (case.address_street or "sin cliente"),
        "programa": programa.name if programa else "sin programa",
        "vendedor": vendedor.full_name if vendedor else "El vendedor",
        "motivo": case.stage_reason or "",
        "direccion": ", ".join(x for x in (case.address_street, case.address_unit, case.address_city) if x),
    }


async def _project_context(db, project_id) -> tuple:
    from app.modules.crm.models import Customer
    from app.modules.field_ops.models import Project

    p = await db.get(Project, uuid.UUID(str(project_id)))
    if p is None:
        return None, {}
    cliente = await db.get(Customer, p.customer_id) if p.customer_id else None
    return p, {
        "proyecto": p.title, "cliente": cliente.legal_name if cliente else p.title,
        "direccion": ", ".join(x for x in (getattr(p, "address_street", None), getattr(p, "address_city", None)) if x),
    }


async def _resolve(db, event: str, payload: dict) -> tuple[str | None, list, dict, str | None, tuple]:
    """(código del aviso, destinatarios, contexto, enlace, (tipo, id))."""
    org = payload.get("organization_id")
    if event == "case.submitted":
        case, ctx = await _case_context(db, payload["case_id"])
        if case is None:
            return None, [], {}, None, (None, None)
        return ("case.submitted", await _users_with(db, org, "cases.review"), ctx,
                f"/cases/{case.id}/review", ("case", str(case.id)))
    if event == "case.substatus_changed" and payload.get("substatus") == "returned":
        case, ctx = await _case_context(db, payload["case_id"])
        if case is None:
            return None, [], {}, None, (None, None)
        return ("case.returned", await _user(db, case.assigned_salesperson_id), ctx,
                f"/cases/{case.id}/form", ("case", str(case.id)))
    if event == "case.stage_changed" and payload.get("to_stage") in ("approved", "rejected", "on_hold"):
        case, ctx = await _case_context(db, payload["case_id"])
        if case is None:
            return None, [], {}, None, (None, None)
        if payload.get("reason"):
            ctx["motivo"] = payload["reason"]
        return (f"case.{payload['to_stage']}", await _user(db, case.assigned_salesperson_id), ctx,
                f"/cases/{case.id}/form", ("case", str(case.id)))
    if event == "installation.scheduled":
        p, ctx = await _project_context(db, payload["project_id"])
        if p is None:
            return None, [], {}, None, (None, None)
        ctx["fecha"] = payload.get("scheduled_date", "")
        return ("installation.scheduled", await _user(db, payload.get("technician_user_id")), ctx,
                f"/projects/{p.id}", ("project", str(p.id)))
    if event == "installation.closed":
        # A Administración, para que confirme el acta (spec 2026-10-19-actas-por-confirmar).
        p, ctx = await _project_context(db, payload["project_id"])
        if p is None:
            return None, [], {}, None, (None, None)
        cerro = payload.get("closed_by_user_id")
        tecnico = await _user(db, cerro)
        ctx["expediente"] = p.case_number or p.title
        ctx["tecnico"] = tecnico[0].full_name if tecnico else "El técnico"
        revisores = [u for u in await _users_with(db, org, DEFAULT_PERMISSION[event]) if str(u.id) != str(cerro)]
        return (event, revisores, ctx, f"/projects/{p.id}?paso=review", ("project", str(p.id)))
    if event == "project.returned_to_technician":
        p, ctx = await _project_context(db, payload["project_id"])
        if p is None:
            return None, [], {}, None, (None, None)
        ctx["motivo"] = payload.get("reason") or ""
        return ("project.returned_to_technician", await _user(db, p.primary_technician_user_id), ctx,
                f"/projects/{p.id}", ("project", str(p.id)))
    if event in ("claim.rejected", "claim.paid"):
        p, ctx = await _project_context(db, payload["project_id"])
        if p is None:
            return None, [], {}, None, (None, None)
        ctx["monto"] = f"${payload['amount']}" if payload.get("amount") else ""
        return (event, await _users_with(db, org, DEFAULT_PERMISSION[event]), ctx,
                f"/invoices/claims/{payload['claim_id']}", ("claim", payload["claim_id"]))
    if event in ("expense.submitted", "expense.reviewed"):
        from app.modules.finance.models import EXPENSE_CATEGORIES, Expense

        g = await db.get(Expense, uuid.UUID(str(payload["expense_id"])))
        if g is None:
            return None, [], {}, None, (None, None)
        quien = await _user(db, g.user_id)
        ctx = {"monto": f"${g.amount}", "categoria": EXPENSE_CATEGORIES.get(g.category, g.category),
               "descripcion": g.description, "persona": quien[0].full_name if quien else "", "motivo": g.review_notes or ""}
        if event == "expense.submitted":
            return ("expense.submitted", [u for u in await _users_with(db, org, "expenses.approve") if u.id != g.user_id],
                    ctx, "/expenses?tab=review", ("expense", str(g.id)))
        codigo = "expense.approved" if payload.get("status") == "approved" else "expense.rejected"
        return codigo, quien, ctx, "/expenses", ("expense", str(g.id))
    if event == "payable.pending_approval":
        from app.modules.finance.models import Supplier, SupplierInvoice

        inv = await db.get(SupplierInvoice, uuid.UUID(str(payload["invoice_id"])))
        if inv is None:
            return None, [], {}, None, (None, None)
        prov = await db.get(Supplier, inv.supplier_id)
        ctx = {"proveedor": prov.name if prov else "", "factura": inv.number, "monto": f"${inv.total}",
               "fecha": inv.due_date.isoformat()}
        return ("payable.pending_approval", await _users_with(db, org, "payables.approve"), ctx,
                "/payables", ("supplier_invoice", str(inv.id)))
    if event in ("payable.paid_now", "supplier.bank_changed"):
        return await _payables_alert(db, org, event, payload)
    if event == "warehouse.release_pending":
        return await _release_pending(db, org, payload)
    if event == "warehouse.release_delivered":
        return await _release_delivered(db, payload)
    if event == "warehouse.stock_low":
        from app.modules.warehouse.models import WarehouseItem

        item = await db.get(WarehouseItem, uuid.UUID(str(payload["item_id"])))
        if item is None:
            return None, [], {}, None, (None, None)
        return ("warehouse.stock_low", await _users_with(db, org, "warehouse.manage"),
                {"articulo": item.name, "existencia": payload.get("existencia", ""),
                 "minimo": payload.get("minimo", "")},
                "/warehouse?filtro=bajo", ("warehouse_item", str(item.id)))
    return None, [], {}, None, (None, None)


async def _payables_alert(db, org, event: str, payload: dict) -> tuple:
    """Controles de cuentas por pagar: van a quien aprueba pagos, menos a quien
    hizo el cambio (no se avisa a sí mismo)."""
    from app.modules.finance.models import Supplier, SupplierInvoice
    from app.modules.users.models import User

    autor = await db.get(User, uuid.UUID(str(payload["user_id"]))) if payload.get("user_id") else None
    if event == "payable.paid_now":
        inv = await db.get(SupplierInvoice, uuid.UUID(str(payload["invoice_id"])))
        if inv is None:
            return None, [], {}, None, (None, None)
        prov = await db.get(Supplier, inv.supplier_id)
        ctx = {"proveedor": prov.name if prov else "", "factura": inv.number, "monto": f"${inv.total}"}
        destino, entidad = "/payables", ("supplier_invoice", str(inv.id))
    else:
        prov = await db.get(Supplier, uuid.UUID(str(payload["supplier_id"])))
        if prov is None:
            return None, [], {}, None, (None, None)
        ctx = {"proveedor": prov.name}
        destino, entidad = "/payables?tab=suppliers", ("supplier", str(prov.id))
    ctx["persona"] = autor.full_name if autor else ""
    quienes = [u for u in await _users_with(db, org, "payables.approve") if not autor or u.id != autor.id]
    return event, quienes, ctx, destino, entidad


async def _release_pending(db, org, payload: dict) -> tuple:
    """La salida que espera autorización: va a quien tiene el permiso, no al
    técnico que la pidió."""
    from app.modules.users.models import User
    from app.modules.warehouse.models import WarehouseReleaseLine, WarehouseReleaseOrder

    orden = await db.get(WarehouseReleaseOrder, uuid.UUID(str(payload["release_id"])))
    if orden is None:
        return None, [], {}, None, (None, None)
    obra = ""
    if orden.project_id:
        _, ctx_proyecto = await _project_context(db, orden.project_id)
        obra = ctx_proyecto.get("proyecto", "")
    solicitante = await db.get(User, orden.requested_by_user_id) if orden.requested_by_user_id else None
    renglones = len((await db.execute(select(WarehouseReleaseLine.id).where(
        WarehouseReleaseLine.order_id == orden.id))).all())
    ctx = {"orden": orden.number or "borrador", "obra": obra or "sin obra",
           "solicitante": solicitante.full_name if solicitante else "El técnico", "lineas": renglones}
    return ("warehouse.release_pending", await _users_with(db, org, DEFAULT_PERMISSION["warehouse.release_pending"]),
            ctx, "/warehouse/releases", ("warehouse_release", str(orden.id)))


async def _release_delivered(db, payload: dict) -> tuple:
    """Lo entregado (y lo que faltó) vuelve a quien armó la orden."""
    from app.modules.warehouse.models import WarehouseReleaseOrder

    orden = await db.get(WarehouseReleaseOrder, uuid.UUID(str(payload["release_id"])))
    if orden is None:
        return None, [], {}, None, (None, None)
    obra = ""
    if orden.project_id:
        _, ctx_proyecto = await _project_context(db, orden.project_id)
        obra = ctx_proyecto.get("proyecto", "")
    ctx = {"orden": orden.number or "", "obra": obra, "faltantes": orden.shortage_note or ""}
    return ("warehouse.release_delivered", await _user(db, orden.requested_by_user_id), ctx,
            f"/warehouse/releases/{orden.id}", ("warehouse_release", str(orden.id)))


# ---------------------------------------------------------------------------
# Crear avisos
# ---------------------------------------------------------------------------

async def notify(db: AsyncSession, *, organization_id, code: str, users: list, context: dict, link: str | None,
                 entity: tuple = (None, None), dedupe_key: str | None = None) -> list[Notification]:
    """Crea el aviso en la app y los envíos pendientes. No hace commit."""
    titulo_t, cuerpo_t, _ = await template_for(db, organization_id, code, "in_app")
    creados = []
    base_url = get_settings().FRONTEND_APP_URL.rstrip("/")
    for u in users:
        if dedupe_key and (await db.execute(select(Notification.id).where(
                Notification.user_id == u.id, Notification.dedupe_key == dedupe_key))).first():
            continue
        n = Notification(organization_id=organization_id, user_id=u.id, event=code,
                         title=render(titulo_t, context)[:255], body=render(cuerpo_t, context), link=link,
                         entity_type=entity[0], entity_id=entity[1], dedupe_key=dedupe_key, created_at=_now())
        db.add(n)
        await db.flush()
        pref = await preference_for(db, u)
        canales = []
        if pref.email_enabled and u.email:
            canales.append(("email", u.email))
        if pref.sms_enabled and pref.sms_phone:
            canales.append(("sms", pref.sms_phone))
        for canal, destino in canales:
            asunto_t, texto_t, activa = await template_for(db, organization_id, code, canal)
            if not activa:
                continue
            texto = render(texto_t, context)
            if canal == "email" and link:
                texto += f"\n\nÁbrelo en PAP.CRM: {base_url}{link}"
            db.add(NotificationDelivery(organization_id=organization_id, notification_id=n.id, channel=canal,
                                        to=destino, subject=render(asunto_t, context)[:255] or None, body=texto,
                                        status="pending", attempts=0, next_attempt_at=_now(), created_at=_now()))
        creados.append(n)
    return creados


async def process_event(db: AsyncSession, event: str, payload: dict) -> int:
    """Convierte un evento de dominio en avisos. Devuelve cuántos creó."""
    code, users, ctx, link, entity = await _resolve(db, event, payload)
    if code is None or not users:
        return 0
    creados = await notify(db, organization_id=uuid.UUID(str(payload["organization_id"])), code=code, users=users,
                           context=ctx, link=link, entity=entity)
    await db.commit()
    logger.info("notifications.created", notice=code, count=len(creados))
    return len(creados)


# ---------------------------------------------------------------------------
# Enviar (la cola)
# ---------------------------------------------------------------------------

class SkipDelivery(Exception):
    """No se envía y no se reintenta (por ejemplo, SMS en modo de prueba)."""


async def _send(d: NotificationDelivery) -> None:
    settings = get_settings()
    if d.channel == "email":
        from app.modules.notifications.email import send_text_email

        await send_text_email(to=d.to, subject=d.subject or "Aviso de PAP.CRM", body=d.body)
    elif d.channel == "sms":
        if settings.SMS_PROVIDER != "masiv":
            raise SkipDelivery("Modo de prueba: SMS_PROVIDER no es masiv, no se envió.")
        from app.modules.notifications.sms import send_sms

        await send_sms(to=d.to, message=d.body)


async def deliver(db: AsyncSession, d: NotificationDelivery) -> None:
    d.attempts += 1
    try:
        await _send(d)
    except SkipDelivery as exc:
        d.status, d.last_error, d.next_attempt_at = "skipped", str(exc)[:500], None
    except Exception as exc:  # el proveedor falló: se reintenta más tarde
        d.last_error = f"{type(exc).__name__}: {exc}"[:500]
        if d.attempts >= MAX_ATTEMPTS:
            d.status, d.next_attempt_at = "failed", None
        else:
            d.next_attempt_at = _now() + timedelta(minutes=2 ** d.attempts)
        logger.warning("notifications.delivery_failed", delivery_id=str(d.id), channel=d.channel,
                       attempts=d.attempts, error=d.last_error)
    else:
        d.status, d.sent_at, d.last_error, d.next_attempt_at = "sent", _now(), None, None


async def deliver_pending(db: AsyncSession, limit: int = 50) -> int:
    pendientes = (await db.execute(select(NotificationDelivery).where(
        NotificationDelivery.status == "pending", NotificationDelivery.next_attempt_at <= _now())
        .order_by(NotificationDelivery.next_attempt_at).limit(limit))).scalars().all()
    for d in pendientes:
        await deliver(db, d)
        await db.commit()
    return len(pendientes)


async def resend(db: AsyncSession, *, organization_id, delivery_id) -> NotificationDelivery:
    from app.shared.errors import NotFoundError

    d = await db.get(NotificationDelivery, delivery_id)
    if d is None or d.organization_id != organization_id:
        raise NotFoundError("El envío no existe.", code="delivery_not_found")
    d.status, d.attempts, d.next_attempt_at = "pending", 0, _now()
    await deliver(db, d)
    await db.commit()
    await db.refresh(d)
    return d


# ---------------------------------------------------------------------------
# Alertas diarias
# ---------------------------------------------------------------------------

def business_days_between(inicio: date, fin: date) -> int:
    """Días hábiles (lunes a viernes) transcurridos desde `inicio` hasta `fin`."""
    if fin <= inicio:
        return 0
    dias, d = 0, inicio
    while d < fin:
        d += timedelta(days=1)
        if d.weekday() < 5:
            dias += 1
    return dias


async def daily_alerts(db: AsyncSession, organization_id) -> int:
    from app.modules.cases.models import Case
    from app.modules.field_ops.clock import local_date, org_today, org_zone
    from app.modules.field_ops.models import Permit, Project

    ajustes = await get_settings_row(db, organization_id)
    hoy = await org_today(db, organization_id)
    zona = await org_zone(db, organization_id)
    total = 0
    revisores = await _users_with(db, organization_id, "cases.review")
    casos = (await db.execute(select(Case).where(Case.organization_id == organization_id,
                                                 Case.stage_code == "pending_approval",
                                                 Case.submitted_at.is_not(None)))).scalars().all()
    for c in casos:
        dias = business_days_between(local_date(c.submitted_at, zona), hoy)
        if dias < ajustes.approval_alert_business_days:
            continue
        _, ctx = await _case_context(db, c.id)
        ctx["dias"] = dias
        total += len(await notify(db, organization_id=organization_id, code="case.approval_overdue", users=revisores,
                                  context=ctx, link=f"/cases/{c.id}/review", entity=("case", str(c.id)),
                                  dedupe_key=f"approval_overdue:{c.id}:{hoy.isoformat()}"))
    limite = hoy + timedelta(days=ajustes.permit_expiry_alert_days)
    gestores = await _users_with(db, organization_id, "permits.manage")
    permisos = (await db.execute(select(Permit).join(Project, Project.id == Permit.project_id).where(
        Project.organization_id == organization_id, Permit.expires_on.is_not(None),
        Permit.expires_on >= hoy, Permit.expires_on <= limite, Permit.status != "not_required"))).scalars().all()
    for pm in permisos:
        p, ctx = await _project_context(db, pm.project_id)
        ctx.update({"permiso": pm.permit_number or pm.jurisdiction, "fecha": pm.expires_on.isoformat()})
        total += len(await notify(db, organization_id=organization_id, code="permit.expiring", users=gestores,
                                  context=ctx, link=f"/projects/{pm.project_id}", entity=("permit", str(pm.id)),
                                  dedupe_key=f"permit_expiring:{pm.id}"))
    total += await _finance_alerts(db, organization_id, hoy)
    await db.commit()
    return total


async def _finance_alerts(db, organization_id, hoy) -> int:
    """Facturas de proveedor por vencer y licencias o seguros de proveedor por vencer."""
    from app.modules.finance.expenses import settings_of
    from app.modules.finance.models import Supplier, SupplierInvoice
    from app.modules.finance.payables import balance

    ajustes = await settings_of(db, organization_id)
    total = 0
    gestores = {u.id: u for perm in ("payables.manage", "payables.approve")
                for u in await _users_with(db, organization_id, perm)}
    limite = hoy + timedelta(days=ajustes.due_alert_days)
    facturas = (await db.execute(select(SupplierInvoice).where(
        SupplierInvoice.organization_id == organization_id,
        SupplierInvoice.status.in_(("pending_approval", "approved", "partially_paid")),
        SupplierInvoice.due_date >= hoy, SupplierInvoice.due_date <= limite))).scalars().all()
    nombres = {p.id: p.name for p in (await db.execute(select(Supplier).where(
        Supplier.organization_id == organization_id))).scalars().all()}
    for inv in facturas:
        ctx = {"proveedor": nombres.get(inv.supplier_id, ""), "factura": inv.number, "monto": f"${balance(inv)}",
               "fecha": inv.due_date.isoformat()}
        total += len(await notify(db, organization_id=organization_id, code="payable.due_soon",
                                  users=list(gestores.values()), context=ctx, link="/payables",
                                  entity=("supplier_invoice", str(inv.id)), dedupe_key=f"payable_due:{inv.id}"))
    limite_doc = hoy + timedelta(days=ajustes.document_alert_days)
    proveedores = await _users_with(db, organization_id, "suppliers.manage")
    for prov in (await db.execute(select(Supplier).where(Supplier.organization_id == organization_id,
                                                         Supplier.active.is_(True)))).scalars().all():
        for doc, vence in (("Licencia", prov.license_expires_on), ("Seguro", prov.insurance_expires_on)):
            if vence and hoy <= vence <= limite_doc:
                total += len(await notify(db, organization_id=organization_id, code="supplier.document_expiring",
                                          users=proveedores, context={"proveedor": prov.name, "documento": doc,
                                                                      "fecha": vence.isoformat()},
                                          link="/payables?tab=suppliers", entity=("supplier", str(prov.id)),
                                          dedupe_key=f"supplier_doc:{prov.id}:{doc}:{vence.isoformat()}"))
    return total


async def daily_alerts_all(db: AsyncSession) -> int:
    from app.modules.organizations.models import Organization

    total = 0
    for org_id in (await db.execute(select(Organization.id))).scalars().all():
        try:
            total += await daily_alerts(db, org_id)
        except IntegrityError:
            await db.rollback()
    return total
