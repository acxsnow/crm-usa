"""El único punto donde el trabajo de campo mueve el expediente (spec D5.1).

Los comandos de campo registran un hecho (permiso aprobado, instalación cerrada,
inspección agendada) y, si ese hecho completa la etapa, avanzan el expediente
aquí, **dentro de la misma transacción**: `transition()` hace el commit, así que
el hecho y el cambio de etapa se guardan juntos o no se guarda ninguno.

Por qué no se llama a `transition()` con los permisos del usuario:
`transition()` exige que quien actúa sea el vendedor dueño o tenga
`cases.read_all` (SEG-07). Esa regla es del vendedor; el técnico no es dueño del
expediente, así que nunca podría cerrar su instalación. Los comandos de campo ya
autorizaron con su propia regla (permiso de la acción y proyecto asignado, ver
`access.py`), y aquí se exige además **el permiso que el mapa pide para entrar a
la etapa** (`stages.permission_for`). Si el usuario no lo tiene, el hecho se
guarda igual y el expediente no avanza: lo moverá quien sí pueda. La separación
de funciones del flujo del cliente sigue intacta.

`stages.SYSTEM_ACTOR` solo salta la regla de dueño; el mapa de transiciones, las
guardas y los efectos corren igual, y el historial y la auditoría registran el
`actor_id` real.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions
from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.cases.models import Case
from app.modules.field_ops.models import Project
from app.shared.errors import InvalidInputError


async def case_for_project(db: AsyncSession, project: Project) -> Case | None:
    """`None` para los proyectos heredados que no cuelgan de un expediente:
    los comandos funcionan igual y simplemente no hay etapa que mover."""
    if project.case_id is None:
        return None
    return (
        await db.execute(
            select(Case).where(
                Case.id == project.case_id, Case.organization_id == project.organization_id
            )
        )
    ).scalar_one_or_none()


async def project_for_case(db: AsyncSession, case: Case) -> Project:
    """Para las guardas: un expediente del tramo de campo sin proyecto es un
    dato roto, y el mensaje lo dice en vez de fallar con un error opaco."""
    project = (
        await db.execute(
            select(Project).where(
                Project.case_id == case.id, Project.organization_id == case.organization_id
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise InvalidInputError(
            f"El expediente {case.case_number} no tiene proyecto de instalación.",
            code="case_without_project",
        )
    return project


def _may_enter(user, stage: str) -> bool:
    return stages.permission_for(stage) in get_effective_permissions(user)


async def advance_case(
    db: AsyncSession, *, project: Project, to_stage: str, user, reason: str | None = None
) -> bool:
    """Mueve el expediente del proyecto a `to_stage` si corresponde.

    No hace nada, sin error, cuando: el proyecto no tiene expediente, el
    expediente no está en una etapa desde la que se llegue a `to_stage` (ya
    avanzó o todavía no llega), o el usuario no tiene el permiso de esa etapa.
    Devuelve si lo movió. Las guardas sí pueden lanzar: si bloquean, el hecho
    tampoco se guarda y el usuario ve por qué."""
    case = await case_for_project(db, project)
    if case is None or not stages.is_allowed(case.stage_code, to_stage):
        return False
    if case.stage_code == to_stage or not _may_enter(user, to_stage):
        return False
    await case_service.transition(
        db, case=case, to_stage=to_stage, actor_id=user.id,
        actor_permissions=stages.SYSTEM_ACTOR, reason=reason,
    )
    return True


async def mark_substatus(
    db: AsyncSession, *, project: Project, stage: str, substatus: str, user,
    reason: str | None = None,
) -> bool:
    """Marca el sub-estado si el expediente está en `stage`. Misma regla que
    `advance_case`: exige el permiso de la etapa y no falla si no aplica."""
    case = await case_for_project(db, project)
    if case is None or case.stage_code != stage or case.substatus_code == substatus:
        return False
    if not _may_enter(user, stage):
        return False
    await case_service.set_substatus(
        db, case=case, substatus=substatus, actor_id=user.id,
        actor_permissions=stages.SYSTEM_ACTOR, reason=reason,
    )
    return True
