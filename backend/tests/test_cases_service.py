"""El expediente: creación, numeración y motor de transiciones.

La regla que sostiene todo lo demás: **nadie escribe `stage_code` a mano**. Toda
la mecánica —validar la transición, correr las guardas, escribir la fecha hito,
insertar el historial, auditar y emitir el evento— vive en `transition()`. Si
alguien asigna la etapa directo, el historial queda incompleto y los reportes
del PDF §7 mienten para siempre, porque `case_stage_events` no se puede
reconstruir.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.cases.models import Case, CaseStageEvent
from app.shared import events as domain_events
from app.shared.errors import InvalidInputError


@pytest.fixture(autouse=True)
def _clean_registries():
    """Guardas y suscriptores se registran al importar. Un test que registre los
    suyos debe dejar el registro como lo encontró."""
    yield
    stages.clear_guards()
    domain_events.clear_subscribers()


async def _new_case(db, org_id, actor_id=None, **kwargs):
    return await case_service.create_case(
        db,
        organization_id=org_id,
        actor_id=actor_id or uuid.uuid4(),
        address_street=kwargs.pop("address_street", "123 Main St"),
        address_unit=kwargs.pop("address_unit", "Spc 14"),
        address_city=kwargs.pop("address_city", "Phoenix"),
        address_state=kwargs.pop("address_state", "AZ"),
        address_zip=kwargs.pop("address_zip", "85001"),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------

async def test_a_case_is_born_without_a_customer(db, seeded_org):
    """El expediente ES la puerta. El vendedor toca y registra el resultado; el
    cliente aparece después, solo si abren."""
    case = await _new_case(db, seeded_org["org"].id, stage_code="no_contact")
    assert case.customer_id is None
    assert case.stage_code == "no_contact"


async def test_the_case_number_is_sequential_per_organization_and_year(db, seeded_org):
    org_id = seeded_org["org"].id
    primero = await _new_case(db, org_id, stage_code="no_contact")
    segundo = await _new_case(db, org_id, address_unit="Spc 15", stage_code="no_contact")

    anio = datetime.now(timezone.utc).year
    assert primero.case_number == f"CASE-{anio}-0001"
    assert segundo.case_number == f"CASE-{anio}-0002"


async def test_two_organizations_do_not_share_the_numbering(db, seeded_org, second_org):
    uno = await _new_case(db, seeded_org["org"].id, stage_code="no_contact")
    otro = await _new_case(db, second_org["org"].id, stage_code="no_contact")
    assert uno.case_number == otro.case_number  # cada una empieza en 0001
    assert uno.organization_id != otro.organization_id


async def test_the_address_is_normalized_to_recognize_the_same_door(db, seeded_org):
    """Iguala mayúsculas, puntuación y espacios de más."""
    org_id = seeded_org["org"].id
    uno = await _new_case(db, org_id, address_street="123 Main St.", stage_code="no_contact")
    otro = await _new_case(db, org_id, address_street="  123   MAIN  ST  ", stage_code="no_contact")
    assert uno.normalized_address == otro.normalized_address == "123 main st spc 14 phoenix 85001"


async def test_abbreviations_are_a_known_gap(db, seeded_org):
    """LIMITACIÓN CONOCIDA: `normalize_address` no expande abreviaturas, así que
    "123 Main St" y "123 Main Street" son dos puertas distintas.

    En venta puerta a puerta es justo la variación más común, y significa que un
    vendedor puede abrir un segundo expediente para una casa que ya tenía uno.
    No se arregla aquí porque `normalize_address` la comparten Lead, Opportunity
    y Customer, y cambiarla bajo presión de entrega afectaría la deduplicación de
    todos. Se resuelve en el módulo 2, con la pantalla del vendedor, que además
    puede avisar "esta puerta ya tiene expediente" antes de guardar.

    Este test documenta el comportamiento actual: el día que se arregle, falla y
    obliga a borrarlo."""
    org_id = seeded_org["org"].id
    uno = await _new_case(db, org_id, address_street="123 Main St", stage_code="no_contact")
    otro = await _new_case(db, org_id, address_street="123 Main Street", stage_code="no_contact")
    assert uno.normalized_address != otro.normalized_address


async def test_a_case_cannot_be_born_in_the_middle_of_the_flow(db, seeded_org):
    """Nacer en `approved` saltaría todo el historial: no habría forma de saber
    cuándo se envió ni quién lo aprobó."""
    with pytest.raises(InvalidInputError):
        await _new_case(db, seeded_org["org"].id, stage_code="approved")


async def test_creating_writes_the_first_history_entry(db, seeded_org):
    case = await _new_case(db, seeded_org["org"].id, stage_code="new_prospect")
    eventos = await case_service.list_stage_events(db, organization_id=case.organization_id, case_id=case.id)
    assert len(eventos) == 1
    assert eventos[0].from_stage_code is None
    assert eventos[0].to_stage_code == "new_prospect"


# ---------------------------------------------------------------------------
# Transiciones
# ---------------------------------------------------------------------------

async def test_an_allowed_transition_moves_the_case_and_writes_history(db, seeded_org):
    actor = uuid.uuid4()
    case = await _new_case(db, seeded_org["org"].id, stage_code="new_prospect")
    await case_service.transition(db, case=case, to_stage="pending_approval", actor_id=actor)

    assert case.stage_code == "pending_approval"
    eventos = await case_service.list_stage_events(db, organization_id=case.organization_id, case_id=case.id)
    assert [e.to_stage_code for e in eventos] == ["new_prospect", "pending_approval"]
    assert eventos[-1].from_stage_code == "new_prospect"
    assert eventos[-1].actor_user_id == actor


async def test_a_forbidden_transition_is_rejected_and_changes_nothing(db, seeded_org):
    case = await _new_case(db, seeded_org["org"].id, stage_code="new_prospect")
    with pytest.raises(InvalidInputError):
        await case_service.transition(db, case=case, to_stage="paid", actor_id=uuid.uuid4())

    assert case.stage_code == "new_prospect"
    eventos = await case_service.list_stage_events(db, organization_id=case.organization_id, case_id=case.id)
    assert len(eventos) == 1


async def test_the_milestone_date_is_written_by_the_transition(db, seeded_org):
    case = await _new_case(db, seeded_org["org"].id, stage_code="new_prospect")
    assert case.submitted_at is None
    await case_service.transition(db, case=case, to_stage="pending_approval", actor_id=uuid.uuid4())
    assert case.submitted_at is not None


async def test_the_reason_is_copied_onto_the_case_for_the_board(db, seeded_org):
    case = await _new_case(db, seeded_org["org"].id, stage_code="new_prospect")
    await case_service.transition(
        db, case=case, to_stage="not_interested", actor_id=uuid.uuid4(), reason="Ya tiene aire nuevo"
    )
    assert case.stage_reason == "Ya tiene aire nuevo"


async def test_a_guard_can_block_a_transition(db, seeded_org):
    """Cada cadena registra sus reglas desde su propio paquete. El módulo 5
    bloqueará `installed` si el checklist técnico no está completo."""

    def checklist_incompleto(**kwargs):
        raise InvalidInputError("El checklist técnico no está completo.", code="checklist_incomplete")

    stages.register_guard("ready_to_install", "installed", checklist_incompleto)

    case = await _new_case(db, seeded_org["org"].id, stage_code="new_prospect")
    for destino in ("pending_approval", "approved", "permit_in_progress", "ready_to_install"):
        await case_service.transition(db, case=case, to_stage=destino, actor_id=uuid.uuid4())

    with pytest.raises(InvalidInputError):
        await case_service.transition(db, case=case, to_stage="installed", actor_id=uuid.uuid4())
    assert case.stage_code == "ready_to_install"
    assert case.completed_at is None


async def test_a_guard_cannot_be_registered_for_a_transition_that_does_not_exist(db):
    with pytest.raises(KeyError):
        stages.register_guard("new_prospect", "paid", lambda **kw: None)


async def test_every_transition_emits_an_event(db, seeded_org):
    """El módulo 7 (notificaciones) se engancha aquí."""
    recibidos = []
    domain_events.subscribe("case.stage_changed", lambda name, payload: recibidos.append(payload))

    case = await _new_case(db, seeded_org["org"].id, stage_code="new_prospect")
    await case_service.transition(db, case=case, to_stage="pending_approval", actor_id=uuid.uuid4())

    assert len(recibidos) == 1
    assert recibidos[0]["to_stage"] == "pending_approval"
    assert recibidos[0]["case_id"] == str(case.id)


async def test_a_failing_subscriber_does_not_undo_the_transition(db, seeded_org):
    """El cambio de etapa es el hecho de negocio; que un aviso falle no puede
    deshacerlo."""

    def explota(name, payload):
        raise RuntimeError("el servidor de correo está caído")

    domain_events.subscribe("case.stage_changed", explota)
    case = await _new_case(db, seeded_org["org"].id, stage_code="new_prospect")
    await case_service.transition(db, case=case, to_stage="pending_approval", actor_id=uuid.uuid4())
    assert case.stage_code == "pending_approval"


# ---------------------------------------------------------------------------
# Sub-estados
# ---------------------------------------------------------------------------

async def test_a_returned_case_stays_in_the_same_stage(db, seeded_org):
    """La devolución NO retrocede de etapa. Si volviera a `new_prospect`, el
    contador de días de aprobación se reiniciaría y el reporte de tiempos
    mentiría."""
    case = await _new_case(db, seeded_org["org"].id, stage_code="new_prospect")
    await case_service.transition(db, case=case, to_stage="pending_approval", actor_id=uuid.uuid4())
    enviado_en = case.submitted_at

    await case_service.set_substatus(
        db, case=case, substatus="returned", actor_id=uuid.uuid4(), reason="Falta el recibo de luz"
    )
    assert case.stage_code == "pending_approval"
    assert case.substatus_code == "returned"
    assert case.submitted_at == enviado_en


async def test_a_substatus_that_does_not_belong_to_the_stage_is_rejected(db, seeded_org):
    case = await _new_case(db, seeded_org["org"].id, stage_code="new_prospect")
    await case_service.transition(db, case=case, to_stage="pending_approval", actor_id=uuid.uuid4())
    with pytest.raises(InvalidInputError):
        await case_service.set_substatus(
            db, case=case, substatus="install_scheduled", actor_id=uuid.uuid4()
        )


async def test_changing_the_stage_clears_the_previous_substatus(db, seeded_org):
    """`returned` no puede sobrevivir a la aprobación: sería un expediente
    aprobado y devuelto al mismo tiempo."""
    case = await _new_case(db, seeded_org["org"].id, stage_code="new_prospect")
    await case_service.transition(db, case=case, to_stage="pending_approval", actor_id=uuid.uuid4())
    await case_service.set_substatus(db, case=case, substatus="returned", actor_id=uuid.uuid4())
    await case_service.transition(db, case=case, to_stage="approved", actor_id=uuid.uuid4())
    assert case.substatus_code is None


# ---------------------------------------------------------------------------
# La regla del repo
# ---------------------------------------------------------------------------

def test_nobody_assigns_stage_code_outside_the_service():
    """Recorre `app/` buscando asignaciones directas a `stage_code`. Solo el
    service del expediente puede hacerlo."""
    import re
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1] / "app"
    permitido = app_dir / "modules" / "cases" / "service.py"
    # `(?!=)` excluye la comparación `Case.stage_code == x`, que es una consulta
    # legítima; lo que se persigue es la ASIGNACIÓN.
    patron = re.compile(r"\.stage_code\s*=(?!=)")

    culpables = [
        str(path.relative_to(app_dir))
        for path in app_dir.rglob("*.py")
        if path != permitido and patron.search(path.read_text(encoding="utf-8"))
    ]
    assert not culpables, f"estos archivos escriben stage_code directo: {culpables}"
