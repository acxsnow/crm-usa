"""Inspección municipal, un intento por fila (spec D5.6).

- Se agenda con la instalación cerrada; solo una pendiente a la vez. Con el
  expediente en `installed`, lo pasa a `inspection_pending`.
- Aprobada: sub-estado `inspection_approved`. Pasar a cobro es del módulo 6; la
  guarda de este módulo lo exige.
- Fallida: el expediente vuelve a `ready_to_install` (transición provisional del
  mapa, pendiente de respuesta del cliente) y el proyecto se reabre para el
  re-trabajo. El intento fallido se conserva.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.field_ops.access import get_visible_project
from app.modules.field_ops.case_flow import advance_case, case_for_project, mark_substatus
from app.modules.field_ops.catalogs import InspectionResult
from app.modules.field_ops.models import Inspection, Project, ProjectStatus
from app.shared import events as domain_events
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError


async def inspections_of(db: AsyncSession, project_id: uuid.UUID) -> list[Inspection]:
    """En orden de agenda: el último es el intento vigente."""
    return list(
        (
            await db.execute(
                select(Inspection)
                .where(Inspection.project_id == project_id)
                .order_by(Inspection.scheduled_for, Inspection.created_at)
            )
        ).scalars().all()
    )


async def latest_result(db: AsyncSession, project_id: uuid.UUID) -> str | None:
    intentos = await inspections_of(db, project_id)
    return intentos[-1].result if intentos else None


async def list_inspections(db, *, organization_id, user, project_id) -> list[Inspection]:
    await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    return await inspections_of(db, project_id)


async def schedule_inspection(
    db, *, organization_id, user, project_id, scheduled_for: datetime, inspector_name: str | None
) -> Inspection:
    project = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    if project.status != ProjectStatus.completed:
        raise ConflictError(
            "La inspección se agenda con la instalación cerrada.", code="installation_not_closed"
        )
    if any(i.result == InspectionResult.pending for i in await inspections_of(db, project.id)):
        raise ConflictError(
            "Este proyecto ya tiene una inspección pendiente; registra su resultado primero.",
            code="inspection_already_pending",
        )

    inspeccion = Inspection(
        organization_id=organization_id, project_id=project.id,
        scheduled_for=scheduled_for, inspector_name=inspector_name,
        result=InspectionResult.pending,
    )
    db.add(inspeccion)
    await db.flush()
    inspeccion_id = inspeccion.id
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="inspections.scheduled", entity_type="Inspection", entity_id=str(inspeccion_id),
        after_data={"project_id": str(project.id), "scheduled_for": scheduled_for.isoformat()},
    )
    await advance_case(db, project=project, to_stage="inspection_pending", user=user,
                       reason="Inspección municipal agendada")
    await db.commit()
    return await _reload(db, inspeccion_id)


async def record_inspection_result(
    db, *, organization_id, user, inspection_id, result: str, observations: str | None,
    inspector_name: str | None,
) -> Inspection:
    inspeccion = (
        await db.execute(
            select(Inspection).where(Inspection.id == inspection_id, Inspection.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if inspeccion is None:
        raise NotFoundError("La inspección no existe.", code="inspection_not_found")
    project = await get_visible_project(
        db, organization_id=organization_id, user=user, project_id=inspeccion.project_id
    )
    if inspeccion.result != InspectionResult.pending:
        raise ConflictError("Esta inspección ya tiene resultado.", code="inspection_already_recorded")
    if result not in (InspectionResult.passed, InspectionResult.failed):
        raise InvalidInputError("El resultado debe ser «aprobada» o «fallida».", code="invalid_inspection_result")
    if result == InspectionResult.failed and len((observations or "").strip()) < 3:
        raise InvalidInputError(
            "Una inspección fallida necesita las observaciones del inspector: es lo que hay que corregir.",
            code="inspection_observations_required",
        )

    inspeccion.result = result
    inspeccion.observations = (observations or "").strip() or None
    inspeccion.inspector_name = inspector_name or inspeccion.inspector_name
    inspeccion.result_recorded_at = datetime.now(timezone.utc)
    inspeccion.recorded_by_user_id = user.id
    inspeccion_id, project_id = inspeccion.id, project.id
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="inspections.result_recorded", entity_type="Inspection", entity_id=str(inspeccion_id),
        after_data={"result": result, "observations": inspeccion.observations},
    )

    if result == InspectionResult.passed:
        await mark_substatus(db, project=project, stage="inspection_pending",
                             substatus="inspection_approved", user=user, reason="Inspección aprobada")
    elif await case_for_project(db, project) is None:
        reopen_project(project)  # proyecto heredado, sin expediente
    else:
        # El efecto de la transición reabre el proyecto, así el camino manual y
        # este terminan igual.
        await advance_case(db, project=project, to_stage="ready_to_install", user=user,
                           reason=f"Inspección fallida: {inspeccion.observations}")
    await db.commit()

    domain_events.emit(
        "inspection.recorded",
        {"inspection_id": str(inspeccion_id), "project_id": str(project_id),
         "organization_id": str(organization_id), "result": result},
    )
    return await _reload(db, inspeccion_id)


def reopen_project(project: Project) -> None:
    """Inspección fallida: la orden vuelve a campo para el re-trabajo."""
    project.status = ProjectStatus.scheduled
    project.completed_date = None


async def on_inspection_failed(*, db, case, actor_id, reason=None) -> None:
    project = (
        await db.execute(select(Project).where(Project.case_id == case.id))
    ).scalar_one_or_none()
    if project is not None:
        reopen_project(project)


async def _reload(db, inspection_id) -> Inspection:
    db.expire_all()
    return (await db.execute(select(Inspection).where(Inspection.id == inspection_id))).scalar_one()
