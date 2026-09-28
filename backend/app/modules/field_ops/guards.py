"""Guardas del tramo de campo en el motor de etapas (spec §7).

Protegen el camino manual (`POST /cases/{id}/transition`, que usa
Administración): nadie puede pasar un expediente a una etapa de campo si el
hecho que la respalda no está registrado. Los comandos de campo pasan por las
mismas guardas, así que las dos vías dicen lo mismo.

Se registran en `case_hooks.register()`. Todas son `async` porque consultan la
base (COD-08).
"""
from app.modules.field_ops.case_flow import project_for_case
from app.modules.field_ops.permits import all_cleared, permits_of
from app.shared.errors import InvalidInputError


async def guard_has_permit(*, db, case, actor_id, reason):
    project = await project_for_case(db, case)
    if not await permits_of(db, project.id):
        raise InvalidInputError(
            "Registra el permiso municipal antes de pasar a «Permiso en trámite».",
            code="permit_missing",
        )


async def guard_permits_cleared(*, db, case, actor_id, reason):
    project = await project_for_case(db, case)
    if not all_cleared(await permits_of(db, project.id)):
        raise InvalidInputError(
            "Todos los permisos deben estar aprobados y vigentes, o marcados como no "
            "requeridos, antes de pasar a «Listo para instalar».",
            code="permits_not_cleared",
        )
