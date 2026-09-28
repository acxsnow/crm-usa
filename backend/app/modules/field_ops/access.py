"""Quién ve qué proyecto.

Una sola regla para todo el módulo: `projects.read_all` ve todos los proyectos
de su organización; quien solo tiene `projects.read_assigned` (el técnico) ve
los que tiene asignados. Un proyecto que no puede ver responde 404, no 403:
confirmar que existe ya sería revelar de más, igual que en el expediente.

Los comandos de campo (cerrar instalación, registrar equipos, marcar el
checklist) usan esta misma regla, así que un técnico no puede actuar sobre la
orden de otro aunque tenga el permiso de la acción.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions
from app.modules.field_ops.models import Project
from app.shared.errors import NotFoundError


def scope_projects_stmt(stmt, user):
    if "projects.read_all" not in get_effective_permissions(user):
        stmt = stmt.where(Project.primary_technician_user_id == user.id)
    return stmt


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
