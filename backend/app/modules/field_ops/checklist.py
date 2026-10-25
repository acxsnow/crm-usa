"""Checklist técnico: condiciones de la instalación, "No aplica" y qué falta.

Reglas (spec D5.3, requerimientos §8):

- Un ítem cuenta como obligatorio si `is_required` y, cuando tiene condición,
  esa condición está marcada en el proyecto. Retirar un furnace a gas vuelve
  obligatoria la foto de la desconexión; si no se retira, no se pide.
- "No aplica" solo en ítems que lo admiten y siempre con motivo.
- Completar un ítem que exige evidencia pide al menos una evidencia de ese ítem.
- Con la instalación cerrada, el checklist queda congelado: es lo que se
  inspeccionó y lo que se cobra.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.field_ops.access import get_workable_project
from app.modules.field_ops.catalogs import INSTALLATION_CONDITIONS
from app.modules.field_ops.models import (
    ChecklistTemplate,
    Evidence,
    Project,
    ProjectChecklistItem,
    ProjectStatus,
)
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError

MIN_REASON_LENGTH = 3


def ensure_installation_open(project: Project) -> None:
    if project.status == ProjectStatus.completed:
        raise ConflictError(
            "La instalación ya está cerrada; lo registrado en ella no se modifica.",
            code="installation_closed",
        )
    if project.status == ProjectStatus.cancelled:
        raise ConflictError("La obra está cancelada; ya no se registra nada en ella.", code="project_cancelled")


async def select_template_for_case(db: AsyncSession, *, case) -> ChecklistTemplate | None:
    """La plantilla del programa del expediente, si la tiene. `None` le dice
    al llamador que use la plantilla por defecto de la organización."""
    if case.program_id is None:
        return None
    return (
        await db.execute(
            select(ChecklistTemplate)
            .where(
                ChecklistTemplate.organization_id == case.organization_id,
                ChecklistTemplate.program_id == case.program_id,
            )
            .order_by(ChecklistTemplate.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def set_installation_conditions(
    db: AsyncSession, *, organization_id: uuid.UUID, user, project_id: uuid.UUID,
    conditions: list[str],
) -> Project:
    project = await get_workable_project(
        db, organization_id=organization_id, user=user, project_id=project_id
    )
    ensure_installation_open(project)

    desconocidas = sorted(set(conditions) - INSTALLATION_CONDITIONS.keys())
    if desconocidas:
        raise InvalidInputError(
            f"Condiciones desconocidas: {', '.join(desconocidas)}.",
            code="unknown_installation_condition",
        )

    antes = list(project.installation_conditions or [])
    project.installation_conditions = sorted(set(conditions))
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="projects.conditions_changed", entity_type="Project", entity_id=str(project.id),
        before_data={"installation_conditions": antes},
        after_data={"installation_conditions": project.installation_conditions},
    )
    await db.commit()
    await db.refresh(project)
    return project


async def update_checklist_item(
    db: AsyncSession, *, organization_id: uuid.UUID, user, item_id: uuid.UUID,
    is_complete: bool | None, not_applicable: bool | None, reason: str | None,
) -> ProjectChecklistItem:
    item = (
        await db.execute(
            select(ProjectChecklistItem)
            .join(Project, Project.id == ProjectChecklistItem.project_id)
            .where(ProjectChecklistItem.id == item_id, Project.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("El ítem del checklist no existe.", code="checklist_item_not_found")
    # Misma regla de visibilidad que el proyecto: un técnico no marca la orden
    # de otro.
    project = await get_workable_project(
        db, organization_id=organization_id, user=user, project_id=item.project_id
    )
    ensure_installation_open(project)
    # Lo que marcó otro técnico (el anterior, si el personal rotó) lo cambia
    # solo la oficina: el nuevo sigue donde el otro terminó, no lo deshace.
    from app.modules.field_ops.access import _sees_all

    if item.completed_by_user_id and item.completed_by_user_id != user.id and not _sees_all(user):
        raise ForbiddenError("Esa línea la marcó otro técnico: solo la oficina la cambia.",
                             code="checklist_item_by_other")

    ahora = datetime.now(timezone.utc)
    if not_applicable:
        if not item.allows_not_applicable:
            raise InvalidInputError(
                f"«{item.label}» no admite «No aplica».", code="not_applicable_not_allowed"
            )
        motivo = (reason or "").strip()
        if len(motivo) < MIN_REASON_LENGTH:
            raise InvalidInputError(
                "Para marcar «No aplica» hay que escribir el motivo.",
                code="not_applicable_reason_required",
            )
        item.not_applicable = True
        item.not_applicable_reason = motivo
        item.is_complete = False
        item.completed_at = ahora
        item.completed_by_user_id = user.id
    elif is_complete:
        if item.requires_evidence and not await _has_evidence(db, item.id):
            raise InvalidInputError(
                f"«{item.label}» necesita al menos una foto o video antes de marcarse como completo.",
                code="checklist_item_requires_evidence",
            )
        item.is_complete = True
        item.not_applicable = False
        item.not_applicable_reason = None
        item.completed_at = ahora
        item.completed_by_user_id = user.id
    else:
        # Desmarcar: vuelve a pendiente, sea que estaba completo o en "No aplica".
        item.is_complete = False
        item.not_applicable = False
        item.not_applicable_reason = None
        item.completed_at = None
        item.completed_by_user_id = None

    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="checklists.item_updated", entity_type="ProjectChecklistItem", entity_id=str(item.id),
        after_data={
            "is_complete": item.is_complete,
            "not_applicable": item.not_applicable,
            "reason": item.not_applicable_reason,
        },
    )
    await db.commit()
    await db.refresh(item)
    return item


async def checklist_gaps(db: AsyncSession, *, project: Project) -> list[str]:
    """Las etiquetas de los ítems obligatorios que faltan, en orden. Lista vacía
    = checklist completo. Es lo que se le muestra al técnico al intentar cerrar,
    en vez de un "no se puede" sin explicación."""
    items = (
        await db.execute(
            select(ProjectChecklistItem)
            .where(ProjectChecklistItem.project_id == project.id)
            .order_by(ProjectChecklistItem.sort_order)
        )
    ).scalars().all()
    condiciones = list(project.installation_conditions or [])
    return [
        item.label
        for item in items
        if item.counts_as_required(condiciones) and not item.is_resolved
    ]


async def _has_evidence(db: AsyncSession, item_id: uuid.UUID) -> bool:
    return (
        await db.execute(
            select(Evidence.id)
            .where(Evidence.checklist_item_id == item_id, Evidence.deleted_at.is_(None))
            .limit(1)
        )
    ).first() is not None
