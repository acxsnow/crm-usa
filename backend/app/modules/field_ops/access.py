"""Quién ve qué proyecto, y quién trabaja en él.

`projects.read_all` (la oficina) ve y trabaja todos los proyectos de su
organización. Quien solo tiene `projects.read_assigned` (el técnico):

- **Trabaja** la obra de la que es el responsable de hoy
  (`primary_technician_user_id`): evidencias, checklist, equipos, firmas,
  diario y pedidos de material.
- **Ve en solo lectura** las obras de las que fue responsable antes (el
  personal rota: el administrador cambia el técnico y el nuevo sigue donde el
  otro terminó) y aquellas a las que fue de ayudante en alguna jornada. Así el
  anterior sabe hasta dónde dejó y qué siguió el otro, sin poder cambiarlo
  (plan bodega-cierre, fase 5).

Un proyecto que no puede ver responde 404, no 403: confirmar que existe ya
sería revelar de más, igual que en el expediente. Uno que ve pero no trabaja
responde 403 con `project_read_only`.
"""
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions
from app.modules.field_ops.models import Project, ProjectTechnicianAssignment
from app.shared.errors import ForbiddenError, NotFoundError


def _sees_all(user) -> bool:
    return "projects.read_all" in get_effective_permissions(user)


def scope_projects_stmt(stmt, user):
    """Las obras que la persona ve: todas, o las suyas de hoy, de antes y de
    las que fue ayudante."""
    if _sees_all(user):
        return stmt
    from app.modules.warehouse.models import ProjectDayLog, ProjectDayLogHelper

    anteriores = select(ProjectTechnicianAssignment.project_id).where(
        ProjectTechnicianAssignment.technician_user_id == user.id)
    de_ayudante = (select(ProjectDayLog.project_id)
                   .join(ProjectDayLogHelper, ProjectDayLogHelper.day_log_id == ProjectDayLog.id)
                   .where(ProjectDayLogHelper.user_id == user.id))
    return stmt.where(or_(Project.primary_technician_user_id == user.id,
                          Project.id.in_(anteriores), Project.id.in_(de_ayudante)))


def can_work(project: Project, user) -> bool:
    """¿Llena esta obra? La oficina siempre; el técnico, si es el responsable de hoy."""
    return _sees_all(user) or project.primary_technician_user_id == user.id


def ensure_can_work(project: Project, user) -> None:
    if not can_work(project, user):
        raise ForbiddenError("Ves esta obra en solo lectura: el técnico responsable es otro.",
                             code="project_read_only")


async def get_visible_project(
    db: AsyncSession, *, organization_id: uuid.UUID, user, project_id: uuid.UUID
) -> Project:
    stmt = select(Project).where(
        Project.id == project_id, Project.organization_id == organization_id
    )
    project = (await db.execute(scope_projects_stmt(stmt, user))).scalar_one_or_none()
    if project is None:
        raise NotFoundError("El proyecto no existe.", code="project_not_found")
    return project


async def get_workable_project(
    db: AsyncSession, *, organization_id: uuid.UUID, user, project_id: uuid.UUID
) -> Project:
    """El proyecto, si la persona lo llena. El que solo lo ve recibe 403."""
    project = await get_visible_project(db, organization_id=organization_id, user=user, project_id=project_id)
    ensure_can_work(project, user)
    # Marcación obligatoria (turnos, spec 2026-10-24): apagada por defecto en
    # `attendance_settings`; encendida, quien tiene turno ahora y no marcó no llena.
    from app.modules.attendance.service import ensure_clocked_in

    await ensure_clocked_in(db, organization_id=organization_id, user=user)
    return project
