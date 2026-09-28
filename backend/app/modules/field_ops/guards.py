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


async def guard_installation_complete(*, db, case, actor_id, reason):
    from app.modules.field_ops.installation import installation_gaps

    project = await project_for_case(db, case)
    faltan = await installation_gaps(db, project=project)
    if faltan:
        raise InvalidInputError(
            "No se puede pasar a «Instalado». Falta: " + "; ".join(faltan) + ".",
            code="installation_incomplete",
        )


async def guard_inspection_scheduled(*, db, case, actor_id, reason):
    from app.modules.field_ops.inspections import latest_result

    project = await project_for_case(db, case)
    if await latest_result(db, project.id) != "pending":
        raise InvalidInputError(
            "Agenda la inspección municipal antes de pasar a «Inspección pendiente».",
            code="inspection_not_scheduled",
        )


async def guard_inspection_passed(*, db, case, actor_id, reason):
    from app.modules.field_ops.inspections import latest_result

    project = await project_for_case(db, case)
    if await latest_result(db, project.id) != "passed":
        raise InvalidInputError(
            "La inspección municipal debe estar aprobada antes de pasar a cobro.",
            code="inspection_not_passed",
        )


async def guard_inspection_failed(*, db, case, actor_id, reason):
    from app.modules.field_ops.inspections import latest_result

    project = await project_for_case(db, case)
    if await latest_result(db, project.id) != "failed":
        raise InvalidInputError(
            "Solo una inspección fallida devuelve el expediente a «Listo para instalar».",
            code="inspection_not_failed",
        )
