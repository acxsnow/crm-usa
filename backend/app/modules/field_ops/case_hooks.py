"""Enganche de operación de campo con el expediente.

El módulo de campo se suscribe a las transiciones que le importan **desde su
propio paquete**, en vez de que el motor del expediente sepa que existe. Así
ninguna cadena edita el archivo de la otra: `cases/stages.py` solo publica el
mecanismo (`register_effect`) y aquí se declara qué hacer.

- Efecto: al aprobarse el expediente se crea su proyecto de instalación
  (contrato `docs/contratos/case.md` §4).
- Guardas del módulo 5 (`guards.py`): ninguna etapa de campo se alcanza sin el
  hecho que la respalda (spec `2026-09-27-modulo-5-campo-design.md` §7).
"""
import structlog

from app.modules.cases import stages
from app.modules.field_ops.service import auto_create_project_from_case

logger = structlog.get_logger(__name__)

_registrado = False


async def _crear_proyecto(*, db, case, actor_id, reason=None):
    project = await auto_create_project_from_case(db, case=case, actor_id=actor_id)
    logger.info(
        "case.project_ready",
        case_id=str(case.id),
        case_number=case.case_number,
        project_id=str(project.id),
    )


def register() -> None:
    """Registra los enganches. Idempotente: llamarlo dos veces no duplica el
    efecto, que si no crearía el proyecto dos veces por aprobación."""
    global _registrado
    if _registrado:
        return

    # Un expediente puede llegar a aprobado por dos caminos: directo desde
    # revisión, o después de haber estado en la lista de espera del programa.
    # El efecto es idempotente, pero hay que registrarlo en los dos.
    stages.register_effect("pending_approval", "approved", _crear_proyecto)
    stages.register_effect("on_hold", "approved", _crear_proyecto)

    from app.modules.field_ops import guards

    stages.register_guard("approved", "permit_in_progress", guards.guard_has_permit)
    stages.register_guard("permit_in_progress", "ready_to_install", guards.guard_permits_cleared)

    from app.modules.field_ops.installation import on_installed

    stages.register_guard("ready_to_install", "installed", guards.guard_installation_complete)
    stages.register_effect("ready_to_install", "installed", on_installed)
    _registrado = True


def _reset_for_tests() -> None:
    """`stages.clear_effects()` vacía el registro del motor, así que la bandera
    local tiene que volver atrás o el siguiente `register()` no haría nada."""
    global _registrado
    _registrado = False
