"""`cases.service.import_case`: la segunda puerta de entrada (CompanyCam)."""
import pytest
from sqlalchemy import func, select

from app.modules.cases import service as case_service
from app.modules.cases.models import Case, CaseStageEvent
from app.shared import events as domain_events
from app.shared.audit_models import AuditEvent
from app.shared.errors import InvalidInputError


async def _import(db, org_id, ref="555", stage="on_hold", **kw):
    caso, creado = await case_service.import_case(
        db, organization_id=org_id, source="companycam", external_ref=ref, stage_code=stage,
        reason="Importado", address_street="1 Main St", address_unit="Spc 1", address_city="LA", **kw)
    await db.commit()
    return caso, creado


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["on_hold", "closed"])
async def test_import_case_nace_en_etapa_de_importacion(db, seeded_org, stage):
    caso, creado = await _import(db, seeded_org["org"].id, stage=stage)
    assert creado and caso.stage_code == stage and caso.case_number == "CC-555"
    assert caso.source == "companycam" and caso.external_ref == "555"
    eventos = (await db.execute(select(CaseStageEvent).where(CaseStageEvent.case_id == caso.id))).scalars().all()
    assert len(eventos) == 1 and eventos[0].imported is True and eventos[0].from_stage_code is None
    assert eventos[0].to_stage_code == stage


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["new_prospect", "approved", "no_contact", "paid"])
async def test_import_case_rechaza_etapas_del_flujo(db, seeded_org, stage):
    with pytest.raises(InvalidInputError):
        await case_service.import_case(db, organization_id=seeded_org["org"].id, source="companycam",
                                       external_ref="1", stage_code=stage)


@pytest.mark.asyncio
async def test_import_case_rechaza_source_visit(db, seeded_org):
    with pytest.raises(InvalidInputError):
        await case_service.import_case(db, organization_id=seeded_org["org"].id, source="visit",
                                       external_ref="1", stage_code="on_hold")


@pytest.mark.asyncio
async def test_import_case_es_idempotente(db, seeded_org):
    org_id = seeded_org["org"].id
    primero, c1 = await _import(db, org_id)
    segundo, c2 = await _import(db, org_id)
    assert c1 is True and c2 is False and primero.id == segundo.id
    assert (await db.execute(select(func.count(Case.id)))).scalar_one() == 1
    assert (await db.execute(select(func.count(CaseStageEvent.id)))).scalar_one() == 1


@pytest.mark.asyncio
async def test_import_case_sin_eventos_de_dominio_y_con_auditoria(db, seeded_org):
    recibidos = []
    for nombre in ("case.created", "case.stage_changed"):
        domain_events.subscribe(nombre, lambda p: recibidos.append(p))
    caso, _ = await _import(db, seeded_org["org"].id)
    assert recibidos == []
    acciones = (await db.execute(select(AuditEvent.action).where(AuditEvent.entity_id == str(caso.id)))).scalars().all()
    assert acciones == ["cases.imported"]
    domain_events.clear_subscribers()


@pytest.mark.asyncio
async def test_import_case_no_toca_el_correlativo(db, seeded_org):
    org_id = seeded_org["org"].id
    await _import(db, org_id)
    nativo = await case_service.create_case(db, organization_id=org_id, actor_id=None, stage_code="no_contact",
                                            address_street="2 Other St")
    assert nativo.case_number.endswith("-0001")


@pytest.mark.asyncio
async def test_import_case_conserva_fecha_de_origen(db, seeded_org):
    from datetime import datetime, timezone

    fecha = datetime(2026, 1, 2, tzinfo=timezone.utc)
    caso, _ = await _import(db, seeded_org["org"].id, created_at=fecha)
    ev = (await db.execute(select(CaseStageEvent).where(CaseStageEvent.case_id == caso.id))).scalar_one()
    assert caso.created_at.replace(tzinfo=timezone.utc) == fecha and ev.occurred_at.replace(tzinfo=timezone.utc) == fecha
