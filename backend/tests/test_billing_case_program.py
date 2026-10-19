"""El cobro de una instalación es al programa de su expediente: el paso de
cobro no ofrece los demás y la API no deja crear uno a otro programa."""
from tests.field_helpers import headers_for
from tests.test_billing_claims import _crear, _listo_para_cobrar, _programas, _registries  # noqa: F401


async def test_a_case_with_a_program_only_offers_and_bills_that_program(
        app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    case, project = await _listo_para_cobrar(db, org)
    case.program_id = progs["TECH"].id
    await db.commit()
    h = await headers_for(app_client, active_admin_staff_user.email)

    cuerpo = (await app_client.get(f"/api/v1/projects/{project.id}/billing/eligibility", headers=h)).json()
    assert [p["program_code"] for p in cuerpo["programs"]] == ["TECH"]
    assert cuerpo["case_program_id"] == str(progs["TECH"].id)

    # LADWP también aplica por la dirección, pero no es el programa del expediente.
    r = await _crear(app_client, h, project.id, progs["LADWP"].id)
    assert r.status_code == 409 and r.json()["code"] == "program_not_of_case"
    assert (await _crear(app_client, h, project.id, progs["TECH"].id)).status_code == 201


async def test_a_project_without_a_case_program_still_lists_every_program(
        app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)  # el expediente no tiene programa
    h = await headers_for(app_client, active_admin_staff_user.email)
    cuerpo = (await app_client.get(f"/api/v1/projects/{project.id}/billing/eligibility", headers=h)).json()
    assert {p["program_code"] for p in cuerpo["programs"]} == {"TECH", "LADWP", "GOZERO"}
    assert cuerpo["case_program_id"] is None
