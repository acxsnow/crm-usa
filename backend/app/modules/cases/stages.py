"""Las etapas del expediente y las transiciones permitidas entre ellas.

Este archivo es el mapa del flujo operativo de Delta HVAC
(`docs/Delta_HVAC_Flujo_de_Trabajo_Operativo.pdf`, §3) y contiene **todas** las
transiciones desde el día uno, incluidas las que ejecuta la Cadena B. Es
deliberado: así el mapa completo está a la vista desde el principio y nadie
tiene que editar el archivo de otro para que sus etapas funcionen. Lo que cada
cadena sí registra desde su propio paquete son las **guardas**
(`register_guard`), que son las reglas de negocio de esa etapa.

Es lógica pura, sin base de datos ni HTTP: se prueba en un segundo.

Quién es dueño de cada tramo, según `docs/contratos/case.md` §4:

- José, módulo 2: creación → `pending_approval`.
- Mateo, módulo 4: `pending_approval` → `approved` | `rejected` | `on_hold`.
- Mateo, módulo 5: `approved` → instalación → `inspection_pending`.
- Mateo, módulo 6: `billing_in_progress` → `paid` → `closed`.
- Compartido: cualquier etapa → `closed` (cierre administrativo).
"""
from typing import Callable

# Orden del flujo. Las tres primeras son salidas tempranas: la puerta puede
# terminar ahí en el primer toque, sin que nunca haya existido un cliente.
STAGES: tuple[str, ...] = (
    "no_contact",
    "not_interested",
    "not_eligible",
    "new_prospect",
    "pending_approval",
    "approved",
    "rejected",
    "on_hold",
    "permit_in_progress",
    "ready_to_install",
    "installed",
    "inspection_pending",
    "billing_in_progress",
    "paid",
    "closed",
)

STAGE_LABELS: dict[str, str] = {
    "no_contact": "Sin contacto",
    "not_interested": "No interesado",
    "not_eligible": "No califica",
    "new_prospect": "Nuevo prospecto",
    "pending_approval": "Pendiente de aprobación",
    "approved": "Aprobado",
    "rejected": "Rechazado",
    "on_hold": "En espera",
    "permit_in_progress": "Permiso en trámite",
    "ready_to_install": "Listo para instalar",
    "installed": "Instalado",
    "inspection_pending": "Inspección pendiente",
    "billing_in_progress": "En proceso de cobro",
    "paid": "Pagado",
    "closed": "Cerrado",
}

# Un expediente nace en una de estas cuatro. El vendedor toca la puerta y el
# resultado ya es el estado inicial: no abrió, no le interesa, no califica, o
# abrió y seguimos.
INITIAL_STAGES: set[str] = {
    "no_contact",
    "not_interested",
    "not_eligible",
    "new_prospect",
}

# Sub-estados por etapa. Los define el dueño de la etapa y sirven para el
# detalle interno sin mover el expediente de sitio en el tablero.
SUBSTATUSES: dict[str, set[str]] = {
    "pending_approval": {
        "pending_review",
        # La devolución NO retrocede de etapa: el vendedor corrige aquí mismo y
        # vuelve a `pending_review`. Si retrocediera a `new_prospect`, el
        # contador de días de aprobación se reiniciaría y el reporte de tiempos
        # del PDF §7 mentiría.
        "returned",
        "ready_to_submit",
        "submitted_to_program",
        "program_review",
    },
    "ready_to_install": {"install_scheduled"},
    "inspection_pending": {"inspection_approved"},
    "billing_in_progress": {"invoice_pending", "submitted", "rejected_by_program"},
}

# La fecha hito que escribe la ENTRADA a cada etapa. Una etapa escribe como
# máximo una, y ninguna fecha la escriben dos etapas: si no, el valor
# dependería del orden en que se pasó por ellas y nadie sabría cuál ganó.
# `scheduled_install_date` no está aquí a propósito: la fija el módulo 5 como
# dato de agenda, no como consecuencia de un cambio de etapa.
STAGE_MILESTONE: dict[str, str] = {
    "new_prospect": "first_contact_at",
    "pending_approval": "submitted_at",
    "approved": "approved_at",
    "installed": "completed_at",
    "closed": "closed_at",
}


# El permiso que exige ENTRAR a cada etapa. Es la separación de funciones del
# flujo del cliente puesta en código: el vendedor manda a revisión, pero no
# aprueba; quien aprueba no instala; quien instala no cobra.
#
# Va aquí y no en el router porque `transition()` es la única puerta de entrada
# y también se llama desde tareas y scripts, donde no hay petición HTTP que
# validar. Hallazgo SEG-07.
STAGE_PERMISSION: dict[str, str] = {
    # Salidas tempranas y apertura: son del vendedor en la calle.
    "no_contact": "cases.create",
    "not_interested": "cases.create",
    "not_eligible": "cases.create",
    "new_prospect": "cases.create",
    # El vendedor envía a revisión.
    "pending_approval": "cases.submit",
    # Administración decide. El vendedor NO puede llegar aquí: es el punto
    # exacto que SEG-07 dejaba abierto.
    "approved": "cases.approve",
    "rejected": "cases.approve",
    "on_hold": "cases.approve",
    # Campo.
    "permit_in_progress": "permits.manage",
    "ready_to_install": "dispatch.manage",
    "installed": "checklists.complete",
    "inspection_pending": "inspections.manage",
    # Cobro.
    "billing_in_progress": "billing.submit",
    "paid": "invoices.record_payment",
    # Cierre administrativo, desde cualquier etapa.
    "closed": "cases.close_admin",
}

# Quien tiene esto puede hacer cualquier transición sin pasar por el mapa de
# permisos: migraciones y tareas del sistema, que no actúan en nombre de nadie.
SYSTEM_ACTOR = frozenset({"__system__"})


def permission_for(to_stage: str) -> str:
    return STAGE_PERMISSION[to_stage]


def _build_transitions() -> dict[str, set[str]]:
    """Arma el mapa. Se construye en una función para poder agregar en un solo
    sitio las reglas que valen para todas las etapas."""
    allowed: dict[str, set[str]] = {
        # Salidas tempranas. Las tres reabren: volver al parque y encontrar a
        # alguien es lo normal, y el expediente de esa puerta ya existe.
        "no_contact": {"no_contact", "not_interested", "not_eligible", "new_prospect"},
        "not_interested": {"new_prospect"},
        "not_eligible": {"new_prospect"},
        # Vendedor (José, módulo 2).
        "new_prospect": {"pending_approval", "not_interested", "not_eligible"},
        # Administración (Mateo, módulo 4).
        "pending_approval": {"approved", "rejected", "on_hold"},
        "on_hold": {"approved", "rejected"},
        "rejected": {"pending_approval"},
        # Campo (Mateo, módulo 5).
        # Instalar antes de sacar el permiso es como se trabaja en la práctica
        # (el permiso se saca antes o después; módulo 6, D6.4).
        "approved": {"permit_in_progress", "ready_to_install"},
        "permit_in_progress": {"ready_to_install"},
        "ready_to_install": {"installed"},
        # Un programa que no exige inspección (TECH) pasa directo a cobro.
        "installed": {"inspection_pending", "billing_in_progress"},
        "inspection_pending": {
            "billing_in_progress",
            # PROVISIONAL: qué pasa cuando la inspección falla está pendiente de
            # respuesta del cliente (`docs/contratos/case.md`, pendientes). Por
            # ahora vuelve a instalación para el re-trabajo. Si el cliente pide
            # distinguirlo en los reportes, se agrega la etapa `inspection_failed`
            # y se cambia esta línea.
            "ready_to_install",
        },
        # Cobro (Mateo, módulo 6).
        "billing_in_progress": {"paid"},
        "paid": {"closed"},
        # Fin de la línea. Un expediente cerrado no se reabre: se abre uno nuevo
        # para esa puerta, y así el historial de cada intento queda separado.
        "closed": set(),
    }
    # Cierre administrativo desde cualquier etapa. Quién puede hacerlo lo
    # restringe el permiso `cases.close_admin`, no este mapa.
    for code in STAGES:
        if code != "closed":
            allowed[code].add("closed")
    return allowed


ALLOWED_TRANSITIONS: dict[str, set[str]] = _build_transitions()


def is_allowed(from_stage: str, to_stage: str) -> bool:
    """Si la transición existe en el mapa.

    Lanza `KeyError` ante una etapa de origen desconocida en vez de devolver
    `False`: un código mal escrito parecería una transición prohibida y el error
    quedaría escondido."""
    if to_stage not in STAGES:
        raise KeyError(f"etapa de destino desconocida: {to_stage}")
    return to_stage in ALLOWED_TRANSITIONS[from_stage]


# ---------------------------------------------------------------------------
# Guardas
# ---------------------------------------------------------------------------

Guard = Callable[..., None]

# (from_stage, to_stage) -> guardas registradas. Cada cadena registra las suyas
# desde su propio paquete, al importarse. Una guarda lanza `InvalidInputError`
# —o la excepción de dominio que corresponda— para bloquear la transición.
#
# Ejemplo (módulo 5, Mateo):
#     register_guard("ready_to_install", "installed", checklist_completo)
_GUARDS: dict[tuple[str, str], list[Guard]] = {}


def register_guard(from_stage: str, to_stage: str, fn: Guard) -> None:
    if not is_allowed(from_stage, to_stage):
        raise KeyError(
            f"no se puede registrar una guarda para una transición que no existe: "
            f"{from_stage} -> {to_stage}"
        )
    _GUARDS.setdefault((from_stage, to_stage), []).append(fn)


def guards_for(from_stage: str, to_stage: str) -> list[Guard]:
    return _GUARDS.get((from_stage, to_stage), [])


def clear_guards() -> None:
    """Solo para pruebas: las guardas se registran al importar, así que un test
    que registre la suya debe poder dejar el registro como lo encontró."""
    _GUARDS.clear()


# ---------------------------------------------------------------------------
# Efectos
# ---------------------------------------------------------------------------

# Una **guarda** decide si la transición puede ocurrir; un **efecto** hace algo
# porque ocurrió. El caso del contrato: al entrar a `approved` se crea el
# proyecto de instalación.
#
# Los efectos son `async` y corren DENTRO de la transacción del cambio de
# etapa, antes del commit: si el efecto falla, la transición no queda hecha.
# Lo contrario dejaría expedientes aprobados sin proyecto, y nadie se enteraría
# hasta que el técnico no encontrara nada que instalar.
#
# Ejemplo (módulo 5, Mateo):
#     register_effect("pending_approval", "approved", crear_proyecto)
_EFFECTS: dict[tuple[str, str], list[Callable]] = {}


def register_effect(from_stage: str, to_stage: str, fn: Callable) -> None:
    if not is_allowed(from_stage, to_stage):
        raise KeyError(
            f"no se puede registrar un efecto para una transición que no existe: "
            f"{from_stage} -> {to_stage}"
        )
    _EFFECTS.setdefault((from_stage, to_stage), []).append(fn)


def effects_for(from_stage: str, to_stage: str) -> list[Callable]:
    return _EFFECTS.get((from_stage, to_stage), [])


def clear_effects() -> None:
    """Solo para pruebas."""
    _EFFECTS.clear()
