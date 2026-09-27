"""Efectos automáticos al cambiar de etapa.

Una **guarda** decide si la transición puede ocurrir; un **efecto** hace algo
porque ocurrió. El caso real del contrato (`docs/contratos/case.md` §4): al
entrar a `approved` se crea el proyecto de instalación, una sola vez.

Los efectos son `async` y corren **dentro de la misma transacción** que el
cambio de etapa: si crear el proyecto falla, el expediente no queda aprobado.
Lo contrario dejaría expedientes aprobados sin proyecto, y nadie se enteraría
hasta que el técnico no encontrara nada que instalar.
"""
import uuid

import pytest
from sqlalchemy import select

from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.field_ops.models import Project
from app.shared.errors import InvalidInputError


@pytest.fixture(autouse=True)
def _clean_registries():
    from app.modules.field_ops import case_hooks

    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()


async def _un_cliente(db, org_id):
    """`Project.customer_id` es obligatorio, y un expediente aprobado siempre
    tiene cliente: alguien abrió la puerta y dio sus datos."""
    from app.modules.crm.models import Customer

    cliente = Customer(organization_id=org_id, legal_name="Marge Simpson")
    db.add(cliente)
    await db.flush()
    return cliente


async def _case_en(db, org_id, etapa, actor=None):
    """Abre un expediente y lo lleva hasta `etapa` por el camino válido."""
    actor = actor or uuid.uuid4()
    cliente = await _un_cliente(db, org_id)
    case = await case_service.create_case(
        db, organization_id=org_id, actor_id=actor, stage_code="new_prospect",
        customer_id=cliente.id,
        address_street="123 Main St", address_unit="Spc 14",
        address_city="Phoenix", address_state="AZ", address_zip="85001",
    )
    camino = {"pending_approval": ["pending_approval"], "approved": ["pending_approval", "approved"]}
    for destino in camino.get(etapa, []):
        case = await case_service.transition(db, case=case, to_stage=destino, actor_id=actor)
    return case


# ---------------------------------------------------------------------------
# El mecanismo
# ---------------------------------------------------------------------------

async def test_an_effect_runs_after_the_stage_changed(db, seeded_org):
    vistos = []

    async def anotar(**kwargs):
        vistos.append(kwargs["case"].stage_code)

    stages.register_effect("new_prospect", "pending_approval", anotar)
    await _case_en(db, seeded_org["org"].id, "pending_approval")
    # Ve la etapa NUEVA: el efecto reacciona a un hecho consumado.
    assert vistos == ["pending_approval"]


async def test_an_effect_that_fails_undoes_the_transition(db, seeded_org):
    """Si el efecto revienta, el expediente no puede quedar movido: sería un
    expediente aprobado sin el proyecto que la aprobación debía crear."""

    async def explota(**kwargs):
        raise InvalidInputError("no se pudo crear el proyecto", code="boom")

    stages.register_effect("new_prospect", "pending_approval", explota)
    case = await case_service.create_case(
        db, organization_id=seeded_org["org"].id, actor_id=uuid.uuid4(),
        stage_code="new_prospect", address_street="123 Main St",
    )
    # Se guarda el identificador ANTES: el rollback expira el objeto, y leerle
    # un atributo después dispararía una carga fuera del contexto asíncrono.
    case_id = case.id
    org_id = seeded_org["org"].id

    with pytest.raises(InvalidInputError):
        await case_service.transition(
            db, case=case, to_stage="pending_approval", actor_id=uuid.uuid4()
        )
    await db.rollback()

    vuelto = await case_service.get_case_or_404(db, organization_id=org_id, case_id=case_id)
    assert vuelto.stage_code == "new_prospect"

    # Y el historial tampoco registró el cambio que no ocurrió.
    eventos = await case_service.list_stage_events(db, organization_id=org_id, case_id=case_id)
    assert [e.to_stage_code for e in eventos] == ["new_prospect"]


async def test_an_effect_cannot_be_registered_for_a_transition_that_does_not_exist(db):
    with pytest.raises(KeyError):
        stages.register_effect("new_prospect", "paid", lambda **kw: None)


# ---------------------------------------------------------------------------
# El efecto real: aprobar crea el proyecto
# ---------------------------------------------------------------------------

async def test_approving_a_case_creates_its_installation_project(db, seeded_org):
    """Contrato §4: al entrar a `approved` se crea el `Project`."""
    from app.modules.field_ops import case_hooks  # registra el efecto al importar

    case_hooks.register()
    org_id = seeded_org["org"].id
    case = await _case_en(db, org_id, "approved")

    proyectos = (
        await db.execute(select(Project).where(Project.case_id == case.id))
    ).scalars().all()
    assert len(proyectos) == 1
    proyecto = proyectos[0]
    assert proyecto.organization_id == org_id
    assert proyecto.address_street == "123 Main St"
    assert proyecto.address_unit == "Spc 14"
    # El título usa el número del expediente: es lo que la gente se dice por teléfono.
    assert case.case_number in proyecto.title


async def test_the_project_carries_the_default_checklist(db, seeded_org):
    from app.modules.field_ops import case_hooks
    from app.modules.field_ops.models import ProjectChecklistItem

    case_hooks.register()
    case = await _case_en(db, seeded_org["org"].id, "approved")
    proyecto = (
        await db.execute(select(Project).where(Project.case_id == case.id))
    ).scalar_one()
    items = (
        await db.execute(
            select(ProjectChecklistItem).where(ProjectChecklistItem.project_id == proyecto.id)
        )
    ).scalars().all()
    assert items, "el proyecto se creó sin checklist técnico"


async def test_approving_twice_does_not_create_two_projects(db, seeded_org):
    """`on_hold → approved` puede pasar después de `pending_approval → approved`
    si el expediente fue a espera y volvió. No puede duplicar el proyecto."""
    from app.modules.field_ops import case_hooks

    case_hooks.register()
    org_id = seeded_org["org"].id
    actor = uuid.uuid4()
    case = await _case_en(db, org_id, "approved", actor)

    # Cierre administrativo y reapertura no son posibles; se simula el camino
    # on_hold volviendo a llamar al efecto, que es lo que debe ser idempotente.
    from app.modules.field_ops.service import auto_create_project_from_case

    await auto_create_project_from_case(db, case=case, actor_id=actor)
    proyectos = (
        await db.execute(select(Project).where(Project.case_id == case.id))
    ).scalars().all()
    assert len(proyectos) == 1


async def test_a_case_that_never_gets_approved_has_no_project(db, seeded_org):
    from app.modules.field_ops import case_hooks

    case_hooks.register()
    case = await _case_en(db, seeded_org["org"].id, "pending_approval")
    proyectos = (
        await db.execute(select(Project).where(Project.case_id == case.id))
    ).scalars().all()
    assert proyectos == []


async def test_approving_a_case_without_a_customer_says_what_is_missing(db, seeded_org):
    """Un expediente sin cliente no puede generar proyecto. El mensaje dice qué
    falta en vez de reventar con un error de base de datos."""
    from app.modules.field_ops import case_hooks

    case_hooks.register()
    actor = uuid.uuid4()
    case = await case_service.create_case(
        db, organization_id=seeded_org["org"].id, actor_id=actor,
        stage_code="new_prospect", address_street="123 Main St",
    )
    case = await case_service.transition(
        db, case=case, to_stage="pending_approval", actor_id=actor
    )
    with pytest.raises(InvalidInputError) as exc:
        await case_service.transition(db, case=case, to_stage="approved", actor_id=actor)
    assert "no tiene cliente" in str(exc.value)
