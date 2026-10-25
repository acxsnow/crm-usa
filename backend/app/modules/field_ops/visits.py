"""Visitas fallidas, límite de reagendamiento y cancelación de la obra (D-001).

El camino diario que faltaba: el técnico llega y no puede instalar.

- **Visita fallida** (la registra el técnico responsable, o la oficina): motivo
  del catálogo, nota obligatoria y GPS. La obra queda sin fecha y vuelve a
  «por agendar» con el mismo técnico; el expediente no cambia de etapa, solo
  su sub-estado pasa a «Visita fallida». El material se queda donde está.
- **Límite**: cada organización fija cuántas visitas fallidas se reagendan sin
  pedir permiso (`field_ops_settings`, 2 por defecto). Al llegar, agendar se
  bloquea hasta que Administración autorice otro intento o cancele la obra.
- **Cancelar** (Administración, `projects.close`): motivo obligatorio. No se
  cancela con salidas de bodega por autorizar o por entregar, ni con material
  entregado sin reintegrar a menos que se diga qué pasó con él. La obra queda
  en solo lectura y el expediente se cierra por `advance_case` (cierre
  administrativo), si quien cancela tiene ese permiso.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.field_ops.access import get_visible_project, get_workable_project
from app.modules.field_ops.case_flow import advance_case, mark_substatus
from app.modules.field_ops.catalogs import VISIT_FAILURE_REASONS
from app.modules.field_ops.checklist import ensure_installation_open
from app.modules.field_ops.clock import org_today
from app.modules.field_ops.models import (
    FieldOpsSettings,
    Project,
    ProjectStatus,
    ProjectTechnicianAssignment,
    ProjectVisitAttempt,
)
from app.shared import events as domain_events
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError

DEFAULT_MAX_FAILED_VISITS = 2
# Un límite de 0 bloquearía la primera reagenda; más de 10 ya no es un límite.
MIN_FAILED_VISITS, MAX_FAILED_VISITS = 1, 10
MIN_TEXT = 5


def _texto(valor: str | None, *, campo: str, code: str) -> str:
    limpio = (valor or "").strip()
    if len(limpio) < MIN_TEXT:
        raise InvalidInputError(f"Escribe {campo} (al menos {MIN_TEXT} caracteres).", code=code)
    return limpio


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

async def get_settings(db: AsyncSession, organization_id: uuid.UUID) -> FieldOpsSettings:
    fila = (await db.execute(select(FieldOpsSettings).where(
        FieldOpsSettings.organization_id == organization_id))).scalar_one_or_none()
    if fila is None:
        fila = FieldOpsSettings(organization_id=organization_id, max_failed_visits=DEFAULT_MAX_FAILED_VISITS)
        db.add(fila)
        await db.flush()
    return fila


def settings_out(s: FieldOpsSettings) -> dict:
    return {"max_failed_visits": s.max_failed_visits,
            "min_failed_visits": MIN_FAILED_VISITS, "max_allowed": MAX_FAILED_VISITS}


async def update_settings(db: AsyncSession, *, organization_id, user, max_failed_visits: int) -> dict:
    if not MIN_FAILED_VISITS <= max_failed_visits <= MAX_FAILED_VISITS:
        raise InvalidInputError(
            f"El límite de visitas fallidas va de {MIN_FAILED_VISITS} a {MAX_FAILED_VISITS}.",
            code="invalid_visit_limit")
    s = await get_settings(db, organization_id)
    antes = s.max_failed_visits
    s.max_failed_visits = max_failed_visits
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="field_ops.settings_updated", entity_type="FieldOpsSettings", entity_id=str(s.id),
        before_data={"max_failed_visits": antes}, after_data={"max_failed_visits": max_failed_visits})
    await db.commit()
    return settings_out(s)


def visit_limit(project: Project, settings: FieldOpsSettings) -> int:
    return settings.max_failed_visits + project.extra_visits_authorized


async def ensure_can_reschedule(db: AsyncSession, project: Project) -> None:
    """Lo llama la «Orden liberada» antes de agendar: con el límite alcanzado,
    decide Administración (otro intento o cancelar), no la agenda."""
    if not project.failed_visits_count:
        return
    limite = visit_limit(project, await get_settings(db, project.organization_id))
    if project.failed_visits_count >= limite:
        raise ConflictError(
            f"La obra ya tuvo {project.failed_visits_count} visitas fallidas (límite {limite}). "
            "Para agendarla otra vez, autoriza otro intento o cancela la obra.",
            code="visit_limit_reached")


async def visit_status(db: AsyncSession, project: Project) -> dict:
    limite = visit_limit(project, await get_settings(db, project.organization_id))
    return {"failed_visits": project.failed_visits_count, "limit": limite,
            "limit_reached": project.failed_visits_count >= limite,
            "extra_visits_authorized": project.extra_visits_authorized}


# ---------------------------------------------------------------------------
# Visita fallida
# ---------------------------------------------------------------------------

async def record_failed_visit(db: AsyncSession, *, organization_id, user, project_id, reason_code: str,
                              notes: str | None, latitude: float | None = None,
                              longitude: float | None = None) -> dict:
    project = await get_workable_project(db, organization_id=organization_id, user=user, project_id=project_id)
    ensure_installation_open(project)
    if reason_code not in VISIT_FAILURE_REASONS:
        raise InvalidInputError("Elige por qué no se pudo hacer la visita.", code="unknown_visit_reason")
    nota = _texto(notes, campo="qué pasó", code="visit_notes_required")
    if project.scheduled_date is None:
        raise ConflictError("La obra no tiene una visita agendada: no hay visita que marcar como fallida.",
                            code="no_scheduled_visit")

    fecha = project.scheduled_date
    db.add(ProjectVisitAttempt(
        organization_id=organization_id, project_id=project.id,
        technician_user_id=project.primary_technician_user_id, recorded_by_user_id=user.id,
        scheduled_date=fecha, reason_code=reason_code, notes=nota, latitude=latitude, longitude=longitude))
    project.failed_visits_count += 1
    project.scheduled_date = None
    if project.status == ProjectStatus.scheduled:
        project.status = ProjectStatus.planning
    estado = await visit_status(db, project)
    motivo = VISIT_FAILURE_REASONS[reason_code]
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="projects.visit_failed", entity_type="Project", entity_id=str(project.id),
        before_data={"scheduled_date": fecha.isoformat()},
        after_data={"reason": reason_code, "notes": nota, "failed_visits": estado["failed_visits"],
                    "limit": estado["limit"], "latitude": latitude, "longitude": longitude})
    await mark_substatus(db, project=project, stage="ready_to_install", substatus="visit_failed", user=user,
                         reason=f"{motivo}: {nota}")
    project_id_ = project.id
    await db.commit()
    domain_events.emit("installation.visit_failed", {
        "project_id": str(project_id_), "organization_id": str(organization_id),
        "recorded_by_user_id": str(user.id), "reason": motivo, "notes": nota,
        "scheduled_date": fecha.isoformat(), "failed_visits": estado["failed_visits"],
        "limit": estado["limit"], "limit_reached": estado["limit_reached"]})
    return estado


async def list_failed_visits(db: AsyncSession, *, organization_id, user, project_id):
    await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    return (select(ProjectVisitAttempt)
            .where(ProjectVisitAttempt.organization_id == organization_id,
                   ProjectVisitAttempt.project_id == project_id)
            .order_by(ProjectVisitAttempt.created_at, ProjectVisitAttempt.id)
            # La fila recién creada en la misma sesión trae `created_at` sin
            # cargar (lo pone la base): se relee para no cargarlo perezosamente.
            .execution_options(populate_existing=True))


def attempt_out(a: ProjectVisitAttempt, nombres: dict) -> dict:
    return {"id": str(a.id), "scheduled_date": a.scheduled_date.isoformat() if a.scheduled_date else None,
            "reason_code": a.reason_code, "reason_label": VISIT_FAILURE_REASONS.get(a.reason_code, a.reason_code),
            "notes": a.notes, "latitude": a.latitude, "longitude": a.longitude,
            "technician_name": nombres.get(a.technician_user_id),
            "recorded_by_name": nombres.get(a.recorded_by_user_id),
            "created_at": a.created_at.isoformat() if a.created_at else None}


async def authorize_extra_visit(db: AsyncSession, *, organization_id, user, project_id, reason: str | None) -> dict:
    project = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    ensure_installation_open(project)
    motivo = _texto(reason, campo="por qué se autoriza otro intento", code="extra_visit_reason_required")
    estado = await visit_status(db, project)
    if not estado["limit_reached"]:
        raise ConflictError("La obra todavía no llega al límite de visitas fallidas: se agenda normalmente.",
                            code="visit_limit_not_reached")
    project.extra_visits_authorized += 1
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="projects.extra_visit_authorized", entity_type="Project", entity_id=str(project.id),
        after_data={"reason": motivo, "extra_visits_authorized": project.extra_visits_authorized,
                    "failed_visits": project.failed_visits_count})
    estado = await visit_status(db, project)
    await db.commit()
    return estado


# ---------------------------------------------------------------------------
# Cancelación
# ---------------------------------------------------------------------------

async def material_in_field(db: AsyncSession, organization_id, project_id) -> list[dict]:
    """Lo que bodega entregó para la obra y no ha vuelto: salidas menos
    devoluciones, por artículo (la salida se guarda negativa, como en
    `warehouse/costing.py`)."""
    from app.modules.warehouse.catalogs import MovementType
    from app.modules.warehouse.models import WarehouseItem, WarehouseMovement

    filas = (await db.execute(
        select(WarehouseMovement.item_id, func.sum(WarehouseMovement.quantity))
        .where(WarehouseMovement.organization_id == organization_id,
               WarehouseMovement.project_id == project_id,
               WarehouseMovement.movement_type.in_((MovementType.SALIDA, MovementType.DEVOLUCION)))
        .group_by(WarehouseMovement.item_id))).all()
    afuera = {item_id: -Decimal(str(total or 0)) for item_id, total in filas}
    afuera = {k: v for k, v in afuera.items() if v > 0}
    if not afuera:
        return []
    items = {i.id: i for i in (await db.execute(select(WarehouseItem).where(
        WarehouseItem.id.in_(list(afuera))))).scalars().all()}
    return [{"item_id": str(k), "item_name": items[k].name if k in items else "Artículo",
             "sku": items[k].sku if k in items else None, "unit": items[k].unit if k in items else None,
             "quantity": str(v.quantize(Decimal("0.01")))}
            for k, v in sorted(afuera.items(), key=lambda kv: items[kv[0]].name if kv[0] in items else "")]


async def open_releases(db: AsyncSession, organization_id, project_id) -> list[dict]:
    """Salidas que todavía pueden mover material hacia la obra. Los borradores
    no cuentan: con la obra cancelada ya no se pueden enviar (`_check_project`)."""
    from app.modules.warehouse.catalogs import RELEASE_STATUSES, ReleaseStatus
    from app.modules.warehouse.models import WarehouseReleaseOrder

    ordenes = (await db.execute(select(WarehouseReleaseOrder).where(
        WarehouseReleaseOrder.organization_id == organization_id,
        WarehouseReleaseOrder.project_id == project_id,
        WarehouseReleaseOrder.status.in_((ReleaseStatus.POR_AUTORIZAR, ReleaseStatus.AUTORIZADA)))
        .order_by(WarehouseReleaseOrder.created_at))).scalars().all()
    return [{"id": str(o.id), "number": o.number, "status": o.status, "status_label": RELEASE_STATUSES[o.status]}
            for o in ordenes]


async def cancellation_check(db: AsyncSession, *, organization_id, user, project_id) -> dict:
    """Lo que la pantalla muestra antes de cancelar: qué lo impide y qué falta resolver."""
    project = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    return {"can_cancel": project.status not in (ProjectStatus.completed, ProjectStatus.cancelled),
            "open_releases": await open_releases(db, organization_id, project.id),
            "material_in_field": await material_in_field(db, organization_id, project.id),
            **await visit_status(db, project)}


async def cancel_project(db: AsyncSession, *, organization_id, user, project_id, reason: str | None,
                         material_note: str | None = None) -> Project:
    project = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    if project.status == ProjectStatus.completed:
        raise ConflictError("La instalación ya se cerró: la obra no se cancela.", code="installation_closed")
    if project.status == ProjectStatus.cancelled:
        raise ConflictError("La obra ya está cancelada.", code="project_cancelled")
    motivo = _texto(reason, campo="por qué se cancela la obra", code="cancel_reason_required")

    abiertas = await open_releases(db, organization_id, project.id)
    if abiertas:
        lista = ", ".join(f"{o['number'] or 'sin número'} ({o['status_label']})" for o in abiertas)
        raise ConflictError(f"Primero resuelve las salidas de bodega abiertas de la obra: {lista}. "
                            "Recházalas o entrégalas antes de cancelar.", code="open_releases")
    afuera = await material_in_field(db, organization_id, project.id)
    nota_material = (material_note or "").strip()
    if afuera and len(nota_material) < MIN_TEXT:
        lista = "; ".join(f"{m['quantity']} × {m['item_name']}" for m in afuera)
        raise ConflictError(f"Hay material entregado a la obra sin reintegrar: {lista}. Regístralo como "
                            "devolución a bodega, o explica qué pasó con él para cancelar.",
                            code="material_pending_return")

    hoy = await org_today(db, organization_id)
    antes = {"status": project.status.value,
             "scheduled_date": project.scheduled_date.isoformat() if project.scheduled_date else None}
    project.status = ProjectStatus.cancelled
    project.cancelled_at = datetime.now(timezone.utc)
    project.cancelled_by_user_id = user.id
    project.cancel_reason = motivo
    tecnico_id = project.primary_technician_user_id
    # El técnico de hoy deja de ser responsable: la ve en solo lectura, como el
    # anterior de una rotación.
    abierto = (await db.execute(select(ProjectTechnicianAssignment).where(
        ProjectTechnicianAssignment.project_id == project.id,
        ProjectTechnicianAssignment.ended_on.is_(None)))).scalars().first()
    if abierto is not None:
        abierto.ended_on = max(hoy, abierto.started_on)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="projects.cancelled", entity_type="Project", entity_id=str(project.id),
        before_data=antes,
        after_data={"reason": motivo, "material_in_field": afuera, "material_note": nota_material or None})
    project_id_ = project.id
    await advance_case(db, project=project, to_stage="closed", user=user, reason=f"Obra cancelada: {motivo}")
    await db.commit()
    domain_events.emit("project.cancelled", {
        "project_id": str(project_id_), "organization_id": str(organization_id),
        "technician_user_id": str(tecnico_id) if tecnico_id else None, "reason": motivo,
        "cancelled_by_user_id": str(user.id)})
    db.expire_all()
    return (await db.execute(select(Project).where(Project.id == project_id_))).scalar_one()
