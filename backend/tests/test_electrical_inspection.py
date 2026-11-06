"""Inspección eléctrica antes de la instalación (cliente, 5 nov 2026)."""
from datetime import date, timedelta

import pytest

from app.modules.cases import stages
from app.modules.field_ops import case_hooks
from tests.field_helpers import approved_case_with_project, headers_for, refreshed_case


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()


MANANA = (date.today() + timedelta(days=1)).isoformat()


async def _agendar(app_client, headers, case_id, tecnico_id, **extra):
    return await app_client.post(f"/api/v1/cases/{case_id}/electrical-inspections",
                                 json={"technician_user_id": str(tecnico_id), "scheduled_date": MANANA, **extra},
                                 headers=headers)


async def test_administration_schedules_and_the_technician_records_the_result(
        app_client, db, seeded_org, active_admin_staff_user, active_technician_user):
    case, _ = await approved_case_with_project(db, seeded_org["org"].id)
    adm = await headers_for(app_client, active_admin_staff_user.email)
    r = await _agendar(app_client, adm, case.id, active_technician_user.id, notes="Llamar antes")
    assert r.status_code == 201, r.text
    ins = r.json()
    assert (ins["status"], ins["technician_name"], ins["case_number"]) == ("scheduled", active_technician_user.full_name,
                                                                           case.case_number)
    # Una abierta a la vez.
    assert (await _agendar(app_client, adm, case.id, active_technician_user.id)).status_code == 409

    tec = await headers_for(app_client, active_technician_user.email)
    mias = (await app_client.get("/api/v1/electrical-inspections", headers=tec)).json()
    assert [i["id"] for i in mias] == [ins["id"]]

    r = await app_client.post(f"/api/v1/electrical-inspections/{ins['id']}/result", headers=tec, json={
        "viability": "adequate", "panel_amperage": "70", "tons": "2.5", "water_heater_eligible": True,
        "induction_eligible": False, "result_notes": "Panel de 70 A, cabe un aire de 2.5 t"})
    assert r.status_code == 200, r.text
    hecho = r.json()
    assert (hecho["status"], hecho["viability_label"], hecho["tons"], hecho["water_heater_eligible"]) == (
        "done", "Adecuada", "2.5", True)
    # No mueve la etapa del expediente.
    assert (await refreshed_case(db, case)).stage_code == "approved"
    lista = (await app_client.get(f"/api/v1/cases/{case.id}/electrical-inspections", headers=adm)).json()
    assert [i["status"] for i in lista] == ["done"]


async def test_not_viable_needs_the_reason(app_client, db, seeded_org, active_admin_staff_user, active_technician_user):
    case, _ = await approved_case_with_project(db, seeded_org["org"].id)
    adm = await headers_for(app_client, active_admin_staff_user.email)
    ins = (await _agendar(app_client, adm, case.id, active_technician_user.id)).json()
    tec = await headers_for(app_client, active_technician_user.email)
    url = f"/api/v1/electrical-inspections/{ins['id']}/result"
    r = await app_client.post(url, headers=tec, json={"viability": "not_viable"})
    assert r.status_code == 400 and r.json()["code"] == "not_viable_reason_required"
    r = await app_client.post(url, headers=tec, json={"viability": "not_viable", "result_notes": "Panel quemado"})
    assert r.status_code == 200


async def test_rules_of_who_and_when(app_client, db, seeded_org, active_admin_staff_user, active_technician_user,
                                     active_salesperson_user, second_org_admin_user):
    case, _ = await approved_case_with_project(db, seeded_org["org"].id)
    adm = await headers_for(app_client, active_admin_staff_user.email)
    vendedor = await headers_for(app_client, active_salesperson_user.email)
    # El vendedor no agenda ni ve la lista.
    assert (await _agendar(app_client, vendedor, case.id, active_technician_user.id)).status_code == 403
    assert (await app_client.get("/api/v1/electrical-inspections", headers=vendedor)).status_code == 403
    # Fecha pasada y técnico que no instala.
    r = await _agendar(app_client, adm, case.id, active_technician_user.id,
                       scheduled_date=(date.today() - timedelta(days=1)).isoformat())
    assert r.status_code == 400
    r = await _agendar(app_client, adm, case.id, active_salesperson_user.id)
    assert r.status_code == 400 and r.json()["code"] == "user_cannot_install"
    ins = (await _agendar(app_client, adm, case.id, active_technician_user.id)).json()
    # Otra organización no la ve.
    ajeno = await headers_for(app_client, second_org_admin_user.email)
    assert (await app_client.get(f"/api/v1/electrical-inspections/{ins['id']}", headers=ajeno)).status_code == 404
    # Cancelar pide motivo y libera para agendar otra.
    url = f"/api/v1/electrical-inspections/{ins['id']}/cancel"
    assert (await app_client.post(url, headers=adm, json={"reason": "x"})).status_code == 400
    assert (await app_client.post(url, headers=adm, json={"reason": "El cliente no estaba"})).status_code == 200
    assert (await _agendar(app_client, adm, case.id, active_technician_user.id)).status_code == 201


async def test_another_technician_cannot_record_the_result(app_client, db, seeded_org, active_admin_staff_user,
                                                           active_technician_user):
    from tests.conftest import _make_role_user

    otro = await _make_role_user(db, seeded_org, role_code="field_technician", email="otro.tec@acme-demo.com",
                                 full_name="Otro Técnico")
    case, _ = await approved_case_with_project(db, seeded_org["org"].id)
    adm = await headers_for(app_client, active_admin_staff_user.email)
    ins = (await _agendar(app_client, adm, case.id, active_technician_user.id)).json()
    tec2 = await headers_for(app_client, otro.email)
    r = await app_client.post(f"/api/v1/electrical-inspections/{ins['id']}/result", headers=tec2,
                              json={"viability": "adequate"})
    assert r.status_code == 403
    assert (await app_client.get(f"/api/v1/electrical-inspections/{ins['id']}", headers=tec2)).status_code == 403
