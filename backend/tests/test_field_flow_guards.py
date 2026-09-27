"""Guardas asíncronas del motor de etapas (hallazgo COD-08).

Las reglas del tramo de campo consultan la base: checklist completo, permisos
vigentes, inspección aprobada. Una guarda síncrona no puede hacer consultas con
una sesión asíncrona, así que el motor tiene que esperar a las que lo sean. Las
síncronas siguen funcionando igual.
"""
import uuid

import pytest
from sqlalchemy import func, select

from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.cases.models import Case
from app.shared.errors import InvalidInputError


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()


async def _new_prospect(db, org_id):
    return await case_service.create_case(
        db, organization_id=org_id, actor_id=uuid.uuid4(),
        stage_code="new_prospect", address_street="123 Main St",
    )


async def test_an_async_guard_can_query_the_database_and_block(db, seeded_org):
    consultas = []

    async def cuenta_expedientes(*, db, case, actor_id, reason):
        total = (await db.execute(select(func.count(Case.id)))).scalar_one()
        consultas.append(total)
        raise InvalidInputError("bloqueado por la guarda", code="blocked")

    stages.register_guard("new_prospect", "pending_approval", cuenta_expedientes)
    case = await _new_prospect(db, seeded_org["org"].id)

    with pytest.raises(InvalidInputError, match="bloqueado por la guarda"):
        await case_service.transition(
            db, case=case, to_stage="pending_approval", actor_id=uuid.uuid4(),
            actor_permissions=stages.SYSTEM_ACTOR,
        )
    assert consultas == [1]


async def test_an_async_guard_that_passes_lets_the_transition_through(db, seeded_org):
    async def deja_pasar(**kwargs):
        return None

    stages.register_guard("new_prospect", "pending_approval", deja_pasar)
    case = await _new_prospect(db, seeded_org["org"].id)
    case = await case_service.transition(
        db, case=case, to_stage="pending_approval", actor_id=uuid.uuid4(),
        actor_permissions=stages.SYSTEM_ACTOR,
    )
    assert case.stage_code == "pending_approval"


async def test_sync_guards_still_work(db, seeded_org):
    def bloquea(**kwargs):
        raise InvalidInputError("síncrona", code="blocked")

    stages.register_guard("new_prospect", "pending_approval", bloquea)
    case = await _new_prospect(db, seeded_org["org"].id)
    with pytest.raises(InvalidInputError, match="síncrona"):
        await case_service.transition(
            db, case=case, to_stage="pending_approval", actor_id=uuid.uuid4(),
            actor_permissions=stages.SYSTEM_ACTOR,
        )
