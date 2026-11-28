"""Varios programas por expediente (cliente, 28 nov 2026): el formulario se
llena una vez, una firma vale para todos, cada programa se aprueba aparte y solo
se cobra a los aprobados."""
import uuid

import pytest
from sqlalchemy import select

from app.modules.cases import multiprogram
from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.cases.models import CaseProgram
from tests.field_helpers import headers_for
from tests.test_billing_claims import _crear, _listo_para_cobrar, _programas, _registries  # noqa: F401


@pytest.fixture(autouse=True)
def _efectos_de_campo():
    """Otro archivo de pruebas puede dejar vacío el registro de efectos sin
    bajar la bandera de `case_hooks`: aquí se vuelve a registrar de cero."""
    from app.modules.field_ops import case_hooks

    case_hooks._reset_for_tests()
    case_hooks.register()
    yield


async def _con_adicional(db, org):
    progs = await _programas(db, org)
    case, project = await _listo_para_cobrar(db, org)
    await case_service.set_case_programs(db, case, primary_id=progs["TECH"].id, additional_ids=[progs["LADWP"].id])
    await db.commit()
    return progs, case, project


@pytest.mark.asyncio
async def test_solo_se_cobra_al_adicional_aprobado(app_client, db, seeded_org, active_admin_staff_user,
                                                   active_admin_user):
    org = seeded_org["org"].id
    progs, case, project = await _con_adicional(db, org)
    h = await headers_for(app_client, active_admin_staff_user.email)
    elig = (await app_client.get(f"/api/v1/projects/{project.id}/billing/eligibility", headers=h)).json()
    assert [p["program_code"] for p in elig["programs"]] == ["TECH"]
    r = await _crear(app_client, h, project.id, progs["LADWP"].id)
    assert r.status_code == 409 and r.json()["code"] == "program_not_of_case"

    ha = await headers_for(app_client, active_admin_user.email)
    url = f"/api/v1/cases/{case.id}/programs/{progs['LADWP'].id}/decision"
    r = await app_client.post(url, json={"decision": "approved", "approval_code": "LA-1"}, headers=ha)
    assert r.status_code == 200, r.text
    ladwp = next(p for p in r.json()["programs"] if p["code"] == "LADWP")
    assert ladwp["status"] == "approved" and ladwp["approval_code"] == "LA-1" and not ladwp["is_primary"]

    elig = (await app_client.get(f"/api/v1/projects/{project.id}/billing/eligibility", headers=h)).json()
    assert {p["program_code"] for p in elig["programs"]} == {"TECH", "LADWP"}
    assert (await _crear(app_client, h, project.id, progs["TECH"].id)).status_code == 201
    assert (await _crear(app_client, h, project.id, progs["LADWP"].id)).status_code == 201

    # Con cobro vivo, el adicional ni se quita ni se rechaza.
    r = await app_client.post(url, json={"decision": "rejected", "reason": "no"}, headers=ha)
    assert r.status_code == 409 and r.json()["code"] == "program_has_claim"
    r = await app_client.put(f"/api/v1/cases/{case.id}/programs", json={"program_ids": []}, headers=ha)
    assert r.status_code == 409 and r.json()["code"] == "program_has_claim"


@pytest.mark.asyncio
async def test_reglas_de_la_decision(app_client, db, seeded_org, active_admin_user):
    org = seeded_org["org"].id
    progs, case, _ = await _con_adicional(db, org)
    ha = await headers_for(app_client, active_admin_user.email)
    base = f"/api/v1/cases/{case.id}/programs"
    r = await app_client.post(f"{base}/{progs['TECH'].id}/decision", json={"decision": "approved"}, headers=ha)
    assert r.status_code == 409 and r.json()["code"] == "primary_program_follows_case"
    r = await app_client.post(f"{base}/{progs['LADWP'].id}/decision", json={"decision": "rejected"}, headers=ha)
    assert r.status_code == 400 and r.json()["code"] == "reason_required"
    r = await app_client.post(f"{base}/{progs['GOZERO'].id}/decision", json={"decision": "approved"}, headers=ha)
    assert r.status_code == 404
    r = await app_client.post(f"{base}/{progs['LADWP'].id}/decision",
                              json={"decision": "rejected", "reason": "No califica por ingresos"}, headers=ha)
    assert r.status_code == 200
    ladwp = next(p for p in r.json()["programs"] if p["code"] == "LADWP")
    assert ladwp["status"] == "rejected" and ladwp["decision_reason"] == "No califica por ingresos"


@pytest.mark.asyncio
async def test_sin_permiso_de_aprobar_no_decide(app_client, db, seeded_org, active_salesperson_user):
    org = seeded_org["org"].id
    progs, case, _ = await _con_adicional(db, org)
    hv = await headers_for(app_client, active_salesperson_user.email)
    r = await app_client.post(f"/api/v1/cases/{case.id}/programs/{progs['LADWP'].id}/decision",
                              json={"decision": "approved"}, headers=hv)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_el_vendedor_elige_adicionales_solo_en_nuevo_prospecto(app_client, db, seeded_org,
                                                                     active_salesperson_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    case = await case_service.create_case(db, organization_id=org, actor_id=active_salesperson_user.id,
                                          stage_code="new_prospect", address_street="1 Main St",
                                          address_city="San Fernando", address_zip="91340",
                                          program_id=progs["TECH"].id,
                                          assigned_salesperson_id=active_salesperson_user.id)
    await db.commit()
    hv = await headers_for(app_client, active_salesperson_user.email)
    url = f"/api/v1/cases/{case.id}/programs"
    r = await app_client.put(url, json={"program_ids": [str(progs["GOZERO"].id)]}, headers=hv)
    assert r.status_code == 200, r.text
    assert [(p["code"], p["is_primary"]) for p in r.json()["programs"]] == [("TECH", True), ("GOZERO", False)]
    # Antes de enviar a revisión no hay nada que decidir.
    with pytest.raises(Exception):
        await multiprogram.decide(db, user=active_salesperson_user, case=case, program_id=progs["GOZERO"].id,
                                  decision="approved")
    caso = await case_service.get_case_or_404(db, organization_id=org, case_id=case.id)
    await case_service.transition(db, case=caso, to_stage="pending_approval", actor_id=uuid.uuid4(),
                                  actor_permissions=stages.SYSTEM_ACTOR)
    r = await app_client.put(url, json={"program_ids": []}, headers=hv)
    assert r.status_code == 409 and r.json()["code"] == "program_locked"


@pytest.mark.asyncio
async def test_el_principal_copia_la_decision_del_expediente(db, seeded_org):
    org = seeded_org["org"].id
    progs, case, _ = await _con_adicional(db, org)
    case.stage_code, case.approval_code = "approved", "TECH-9"
    await multiprogram.sync_primary(db, case, user_id=None)
    await db.commit()
    fila = (await db.execute(select(CaseProgram).where(CaseProgram.case_id == case.id,
                                                       CaseProgram.is_primary.is_(True)))).scalar_one()
    assert fila.status == "approved" and fila.approval_code == "TECH-9"
    assert await multiprogram.program_codes(db, case) == ["TECH", "LADWP"]


@pytest.mark.asyncio
async def test_quitar_un_adicional_y_cambiar_el_principal_lo_conserva(app_client, db, seeded_org, active_admin_user):
    org = seeded_org["org"].id
    progs, case, _ = await _con_adicional(db, org)
    ha = await headers_for(app_client, active_admin_user.email)
    url = f"/api/v1/cases/{case.id}/programs"
    r = await app_client.put(url, json={"program_ids": [str(progs["LADWP"].id), str(progs["GOZERO"].id)]},
                             headers=ha)
    assert [p["code"] for p in r.json()["programs"]] == ["TECH", "GOZERO", "LADWP"]
    r = await app_client.put(url, json={"program_ids": [str(progs["GOZERO"].id)]}, headers=ha)
    assert [p["code"] for p in r.json()["programs"]] == ["TECH", "GOZERO"]
    # Cambiar solo el principal no se lleva los adicionales.
    caso = await case_service.get_case_or_404(db, organization_id=org, case_id=case.id)
    await case_service.set_case_programs(db, caso, primary_id=progs["LADWP"].id)
    await db.commit()
    filas = (await db.execute(select(CaseProgram).where(CaseProgram.case_id == case.id))).scalars().all()
    assert {(f.program_id, f.is_primary) for f in filas} == {(progs["LADWP"].id, True), (progs["GOZERO"].id, False)}
