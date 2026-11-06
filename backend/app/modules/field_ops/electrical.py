"""Inspección eléctrica antes de la instalación (cliente, 5 nov 2026).

En TECH hay una primera cita del técnico con el cliente, aparte de la
instalación: dice si la casa es viable para el programa y a qué beneficios
aplica (cuántas toneladas, si califica para calentador de agua o cocina de
inducción). El diagnóstico de viabilidad eléctrica dejó de estar en el
formulario del vendedor: lo hace el técnico aquí.

- La agenda Administración (`dispatch.manage`) desde el expediente, con técnico
  y fecha; cuelga del expediente porque puede ir antes de la aprobación.
- El técnico asignado (`checklists.complete`) registra el resultado; quien
  despacha también puede, por si el técnico lo dicta por teléfono.
- No mueve la etapa del expediente ni la frena: «No viable» es un aviso para
  Administración (decisión provisional, por confirmar con el cliente).
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions
from app.modules.cases.models import Case
from app.modules.field_ops.clock import org_today
from app.modules.field_ops.models import ElectricalInspection
from app.modules.users.models import User
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError

VIABILITY = {"adequate": "Adecuada", "needs_upgrade": "Requiere adecuación", "not_viable": "No viable"}
AMPERAGE = {"50": "50 A", "70": "70 A", "100": "100 A", "125": "125 A", "150": "150 A", "200": "200 A",
            "other": "Otro / no se sabe"}
STATUS = {"scheduled": "Agendada", "done": "Hecha", "cancelled": "Cancelada"}
# Hasta dónde tiene sentido agendarla: después ya se está instalando.
OPEN_STAGES = {"new_prospect", "pending_approval", "on_hold", "approved", "permit_in_progress"}


async def _case(db: AsyncSession, organization_id, case_id) -> Case:
    case = (await db.execute(select(Case).where(Case.id == case_id, Case.organization_id == organization_id))
            ).scalar_one_or_none()
    if case is None:
        raise NotFoundError("El expediente no existe.", code="case_not_found")
    return case


async def get_inspection(db: AsyncSession, *, organization_id, inspection_id) -> ElectricalInspection:
    ins = (await db.execute(select(ElectricalInspection).where(
        ElectricalInspection.id == inspection_id, ElectricalInspection.organization_id == organization_id))
    ).scalar_one_or_none()
    if ins is None:
        raise NotFoundError("La inspección eléctrica no existe.", code="electrical_inspection_not_found")
    return ins


def _dispatches(user) -> bool:
    return "dispatch.manage" in get_effective_permissions(user)


def ensure_can_see(ins: ElectricalInspection, user) -> None:
    permisos = get_effective_permissions(user)
    if ins.technician_user_id == user.id or permisos & {"dispatch.manage", "cases.review", "cases.read_all"}:
        return
    raise ForbiddenError("Esta inspección eléctrica es de otro técnico.", code="electrical_inspection_forbidden")


async def list_for_case(db: AsyncSession, *, organization_id, case_id) -> list[ElectricalInspection]:
    await _case(db, organization_id, case_id)
    return list((await db.execute(select(ElectricalInspection).where(
        ElectricalInspection.organization_id == organization_id, ElectricalInspection.case_id == case_id)
        .order_by(ElectricalInspection.scheduled_date, ElectricalInspection.created_at))).scalars().all())


def inspections_stmt(*, organization_id, user, status: str | None = None):
    """El técnico ve las suyas; quien despacha, todas. Con el expediente para la dirección."""
    stmt = (select(ElectricalInspection, Case).join(Case, Case.id == ElectricalInspection.case_id)
            .where(ElectricalInspection.organization_id == organization_id))
    if not _dispatches(user):
        stmt = stmt.where(ElectricalInspection.technician_user_id == user.id)
    if status:
        stmt = stmt.where(ElectricalInspection.status == status)
    return stmt.order_by(ElectricalInspection.scheduled_date.desc(), ElectricalInspection.created_at.desc(),
                         ElectricalInspection.id)


async def schedule(db: AsyncSession, *, organization_id, user, case_id, technician_id, scheduled_date,
                   notes: str | None = None) -> ElectricalInspection:
    from app.modules.field_ops.installation import _require_installer

    case = await _case(db, organization_id, case_id)
    if case.stage_code not in OPEN_STAGES:
        raise ConflictError("La inspección eléctrica va antes de la instalación; este expediente ya pasó esa etapa.",
                            code="electrical_inspection_too_late")
    if scheduled_date < await org_today(db, organization_id):
        raise InvalidInputError("No se puede agendar en una fecha pasada.", code="schedule_in_past")
    await _require_installer(db, organization_id=organization_id, technician_id=technician_id)
    abierta = (await db.execute(select(ElectricalInspection.id).where(
        ElectricalInspection.case_id == case.id, ElectricalInspection.status == "scheduled"))).first()
    if abierta:
        raise ConflictError("El expediente ya tiene una inspección eléctrica agendada: cancélala o regístrale el "
                            "resultado antes de agendar otra.", code="electrical_inspection_open")
    ins = ElectricalInspection(organization_id=organization_id, case_id=case.id, technician_user_id=technician_id,
                               scheduled_date=scheduled_date, notes=(notes or "").strip() or None,
                               scheduled_by_user_id=user.id)
    db.add(ins)
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="electrical_inspections.scheduled", entity_type="ElectricalInspection",
                             entity_id=str(ins.id), after_data={"case_id": str(case.id),
                                                               "technician": str(technician_id),
                                                               "scheduled_date": scheduled_date.isoformat()})
    await db.commit()
    await db.refresh(ins)
    return ins


async def record_result(db: AsyncSession, *, organization_id, user, inspection_id, data: dict) -> ElectricalInspection:
    ins = await get_inspection(db, organization_id=organization_id, inspection_id=inspection_id)
    if ins.technician_user_id != user.id and not _dispatches(user):
        raise ForbiddenError("El resultado lo registra el técnico de la inspección.",
                             code="electrical_inspection_forbidden")
    if ins.status == "cancelled":
        raise ConflictError("La inspección está cancelada.", code="electrical_inspection_cancelled")
    if data["viability"] not in VIABILITY:
        raise InvalidInputError("Elige si la casa es viable.", code="electrical_viability_invalid")
    if data.get("panel_amperage") and data["panel_amperage"] not in AMPERAGE:
        raise InvalidInputError("Amperaje desconocido.", code="panel_amperage_invalid")
    tons = data.get("tons")
    if tons is not None and not (Decimal("0.5") <= Decimal(str(tons)) <= Decimal("10")):
        raise InvalidInputError("Las toneladas van de 0.5 a 10.", code="tons_invalid")
    if data["viability"] == "not_viable" and not (data.get("result_notes") or "").strip():
        raise InvalidInputError("Escribe por qué la casa no es viable.", code="not_viable_reason_required")
    antes = {"status": ins.status, "viability": ins.viability}
    for campo in ("panel_amperage", "viability", "tons", "water_heater_eligible", "induction_eligible"):
        setattr(ins, campo, data.get(campo))
    ins.result_notes = (data.get("result_notes") or "").strip() or None
    ins.status = "done"
    ins.completed_at = datetime.now(timezone.utc)
    ins.completed_by_user_id = user.id
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="electrical_inspections.result_recorded", entity_type="ElectricalInspection",
                             entity_id=str(ins.id), before_data=antes,
                             after_data={"status": "done", "viability": ins.viability,
                                         "tons": str(ins.tons) if ins.tons is not None else None})
    await db.commit()
    await db.refresh(ins)
    return ins


async def cancel(db: AsyncSession, *, organization_id, user, inspection_id, reason: str) -> ElectricalInspection:
    ins = await get_inspection(db, organization_id=organization_id, inspection_id=inspection_id)
    if ins.status != "scheduled":
        raise ConflictError("Solo se cancela una inspección agendada.", code="electrical_inspection_not_scheduled")
    motivo = (reason or "").strip()
    if len(motivo) < 5:
        raise InvalidInputError("Escribe por qué se cancela.", code="cancel_reason_required")
    ins.status = "cancelled"
    ins.cancel_reason = motivo
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="electrical_inspections.cancelled", entity_type="ElectricalInspection",
                             entity_id=str(ins.id), after_data={"reason": motivo})
    await db.commit()
    await db.refresh(ins)
    return ins


async def names(db: AsyncSession, ids) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict((await db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))).all())
