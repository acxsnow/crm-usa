"""Confirmación del acta por Administración y devolución al técnico (módulo 6,
spec D6.6).

Es el paso "información recibida y confirmada" del proceso real de Delta HVAC:
antes de cobrar, alguien de Administración revisa lo que registró el técnico.
Si algo está mal (una foto que no se lee, un serial equivocado), se lo
devuelve con el motivo: el acta se reabre, el técnico corrige y la vuelve a
cerrar, y queda pendiente de confirmar otra vez.

El expediente NO retrocede: se reabre el acta, no la etapa. Así el reporte de
tiempos dice la verdad y un expediente que ya está en cobro sigue en cobro.
"""
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cases.models import Case
from app.modules.crm.models import Customer
from app.modules.field_ops.access import get_visible_project
from app.modules.field_ops.models import Project, ProjectReview, ProjectStatus
from app.modules.users.models import User
from app.shared import events as domain_events
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError

MIN_REASON_LENGTH = 3


def add_review(db: AsyncSession, *, project: Project, action: str, reason: str | None, actor_id) -> ProjectReview:
    review = ProjectReview(
        organization_id=project.organization_id, project_id=project.id,
        action=action, reason=reason, actor_user_id=actor_id,
    )
    db.add(review)
    return review


def pending_reviews_stmt(organization_id) -> Select:
    """«Actas por confirmar» (spec 2026-10-19-actas-por-confirmar): instalaciones
    cerradas cuya última revisión no es una confirmación, la más vieja primero.
    Una devuelta que el técnico vuelve a cerrar entra de nuevo."""
    ultima = (
        select(ProjectReview.action)
        .where(ProjectReview.project_id == Project.id)
        .order_by(ProjectReview.created_at.desc())
        .limit(1)
        .correlate(Project)
        .scalar_subquery()
    )
    return (
        select(Project.id, Project.case_id, Case.case_number, Project.title, Customer.legal_name,
               User.full_name, Project.completed_date)
        .outerjoin(Case, Case.id == Project.case_id)
        .outerjoin(Customer, Customer.id == Project.customer_id)
        .outerjoin(User, User.id == Project.primary_technician_user_id)
        .where(Project.organization_id == organization_id, Project.status == ProjectStatus.completed,
               or_(ultima.is_(None), ultima != "confirmed"))
        .order_by(Project.completed_date.asc().nulls_last(), Project.id)
    )


def reopen_for_correction(project: Project) -> None:
    """El acta vuelve a campo: checklist, equipos y materiales editables."""
    project.status = ProjectStatus.scheduled
    project.completed_date = None


async def confirm_technician_info(db: AsyncSession, *, organization_id, user, project_id) -> Project:
    project = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    if project.status != ProjectStatus.completed:
        raise ConflictError(
            "El técnico todavía no ha cerrado el acta; se confirma cuando esté cerrada.",
            code="acta_not_closed",
        )
    if project.technician_info_confirmed:
        raise ConflictError("La información técnica ya está confirmada.", code="acta_already_confirmed")
    add_review(db, project=project, action="confirmed", reason=None, actor_id=user.id)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="projects.technician_info_confirmed", entity_type="Project", entity_id=str(project.id),
    )
    project_id_ = project.id
    await db.commit()
    domain_events.emit("project.technician_info_confirmed",
                       {"project_id": str(project_id_), "organization_id": str(organization_id)})
    return await _reload(db, project)


async def return_to_technician(db: AsyncSession, *, organization_id, user, project_id, reason: str) -> Project:
    project = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    motivo = (reason or "").strip()
    if len(motivo) < MIN_REASON_LENGTH:
        raise InvalidInputError("Escribe qué debe corregir el técnico.", code="return_reason_required")
    if project.status != ProjectStatus.completed:
        raise ConflictError("El acta ya está abierta; el técnico puede corregirla.", code="acta_already_open")
    reopen_for_correction(project)
    add_review(db, project=project, action="returned", reason=motivo, actor_id=user.id)
    await record_audit_event(
        db, organization_id=organization_id, actor_user_id=user.id,
        action="projects.returned_to_technician", entity_type="Project", entity_id=str(project.id),
        after_data={"reason": motivo},
    )
    project_id_ = project.id
    await db.commit()
    domain_events.emit("project.returned_to_technician",
                       {"project_id": str(project_id_), "organization_id": str(organization_id), "reason": motivo})
    return await _reload(db, project)


def was_reopened_for_correction(project: Project) -> bool:
    """El acta está abierta por una devolución o reapertura, no por primera
    vez. Permite volver a cerrarla con el expediente más adelante."""
    return bool(project.reviews) and project.reviews[-1].action in ("returned", "reopened")


async def _reload(db, project: Project) -> Project:
    """Recarga solo el proyecto (con su historial de revisiones). No expira la
    sesión entera: el usuario de la petición vive en ella y sus permisos se
    leen después."""
    await db.refresh(project, attribute_names=["reviews", "status", "completed_date", "case"])
    return project
