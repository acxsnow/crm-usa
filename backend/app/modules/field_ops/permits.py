"""Permiso municipal (spec D5.5). Solo registro: el trámite se hace en el portal
de la ciudad.

- El primer permiso registrado con el expediente en `approved` lo pasa a
  `permit_in_progress`.
- Cuando todos los permisos del proyecto quedan despejados (aprobados y
  vigentes, o `not_required` con motivo), pasa a `ready_to_install`.
"""
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.field_ops.access import get_visible_project
from app.modules.field_ops.case_flow import advance_case
from app.modules.field_ops.catalogs import PERMIT_STATUS_LABELS, PermitStatus
from app.modules.field_ops.models import Permit, Project
from app.shared import events as domain_events
from app.shared.audit import record_audit_event
from app.shared.errors import InvalidInputError, NotFoundError


async def permits_of(db: AsyncSession, project_id: uuid.UUID) -> list[Permit]:
    return list(
        (
            await db.execute(
                select(Permit).where(Permit.project_id == project_id).order_by(Permit.created_at)
            )
        ).scalars().all()
    )


def all_cleared(permits: list[Permit]) -> bool:
    return bool(permits) and all(p.is_cleared for p in permits)


async def list_permits(db: AsyncSession, *, organization_id: uuid.UUID, user, project_id: uuid.UUID) -> list[Permit]:
    await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    return await permits_of(db, project_id)


async def record_permit(
    db: AsyncSession, *, organization_id: uuid.UUID, user, project_id: uuid.UUID, data: dict
) -> Permit:
    project = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    permit = Permit(organization_id=organization_id, project_id=project.id, **data)
    _validate(permit)
    db.add(permit)
    await db.flush()
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="permits.recorded", entity_type="Permit", entity_id=str(permit.id),
        after_data=_snapshot(permit),
    )
    return await _finish(db, project=project, permit=permit, user=user)


async def update_permit(
    db: AsyncSession, *, organization_id: uuid.UUID, user, permit_id: uuid.UUID, changes: dict
) -> Permit:
    permit = (
        await db.execute(
            select(Permit).where(Permit.id == permit_id, Permit.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if permit is None:
        raise NotFoundError("El permiso no existe.", code="permit_not_found")
    project = await get_visible_project(
        db, organization_id=organization_id, user=user, project_id=permit.project_id
    )
    antes = _snapshot(permit)
    for campo, valor in changes.items():
        setattr(permit, campo, valor)
    _validate(permit)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="permits.updated", entity_type="Permit", entity_id=str(permit.id),
        before_data=antes, after_data=_snapshot(permit),
    )
    return await _finish(db, project=project, permit=permit, user=user)


async def _finish(db: AsyncSession, *, project: Project, permit: Permit, user) -> Permit:
    """Avanza el expediente hasta donde los permisos lo permitan y guarda todo
    junto. Pueden ser dos pasos si el permiso se registra ya aprobado."""
    permit_id, org_id, estado = permit.id, permit.organization_id, permit.status
    await advance_case(db, project=project, to_stage="permit_in_progress", user=user,
                       reason="Permiso municipal radicado")
    if all_cleared(await permits_of(db, project.id)):
        await advance_case(db, project=project, to_stage="ready_to_install", user=user,
                           reason="Permisos municipales despejados")
    await db.commit()

    domain_events.emit(
        "permit.recorded",
        {"permit_id": str(permit_id), "project_id": str(project.id),
         "organization_id": str(org_id), "status": str(estado)},
    )
    return (
        await db.execute(select(Permit).where(Permit.id == permit_id))
    ).scalar_one()


def _validate(permit: Permit) -> None:
    if permit.status not in PERMIT_STATUS_LABELS:
        raise InvalidInputError(f"El estado «{permit.status}» no existe.", code="unknown_permit_status")
    if not (permit.jurisdiction or "").strip():
        raise InvalidInputError("Indica la ciudad o el condado que emite el permiso.", code="permit_jurisdiction_required")
    if permit.status == PermitStatus.approved and permit.approved_on is None:
        raise InvalidInputError("Un permiso aprobado necesita la fecha de aprobación.", code="permit_approval_date_required")
    if permit.status == PermitStatus.not_required and len((permit.not_required_reason or "").strip()) < 3:
        raise InvalidInputError(
            "Si la instalación no requiere permiso, escribe el motivo.",
            code="permit_not_required_reason_required",
        )
    if permit.approved_on and permit.expires_on and permit.expires_on < permit.approved_on:
        raise InvalidInputError(
            "La fecha de vencimiento no puede ser anterior a la de aprobación.",
            code="permit_dates_inconsistent",
        )
    if permit.filed_on and permit.filed_on > date.today():
        raise InvalidInputError("La fecha de radicación no puede estar en el futuro.", code="permit_filed_in_future")


def _snapshot(permit: Permit) -> dict:
    return {
        "status": str(permit.status),
        "permit_number": permit.permit_number,
        "jurisdiction": permit.jurisdiction,
        "approved_on": permit.approved_on.isoformat() if permit.approved_on else None,
        "expires_on": permit.expires_on.isoformat() if permit.expires_on else None,
    }
