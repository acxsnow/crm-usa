"""Plantillas de checklist por programa (pendiente del módulo 5)."""
from app.modules.programs import service as programs
from tests.test_field_ops import _admin_headers

URL = "/api/v1/checklist-templates"


async def _programas(db, org_id):
    await programs.install_defaults(db, organization_id=org_id)
    return {p.code: p for p in await programs.list_programs(db, organization_id=org_id)}


async def test_a_program_has_one_template_that_can_be_edited(app_client, db, seeded_org, active_admin_user):
    headers = await _admin_headers(app_client, active_admin_user)
    tech = (await _programas(db, seeded_org["org"].id))["TECH_CLEAN_CA"]
    cuerpo = {"name": "Instalación TECH", "program_id": str(tech.id),
              "items": [{"label": "Foto del equipo instalado", "requires_evidence": True,
                         "evidence_category": "new_equipment", "sort_order": 1}]}
    r = await app_client.post(URL, json=cuerpo, headers=headers)
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    r = await app_client.post(URL, json={**cuerpo, "name": "Otra"}, headers=headers)
    assert r.status_code == 409 and r.json()["code"] == "program_template_exists"

    cuerpo["items"] = [{"label": "Prueba de presión", "sort_order": 1},
                       {"label": "Foto del termostato", "sort_order": 2, "allows_not_applicable": True}]
    r = await app_client.put(f"{URL}/{tid}", json=cuerpo, headers=headers)
    assert r.status_code == 200, r.text
    assert [i["label"] for i in r.json()["items"]] == ["Prueba de presión", "Foto del termostato"]

    r = await app_client.put(f"{URL}/{tid}", json={**cuerpo, "items": [{"label": "x", "evidence_category": "nada"}]},
                             headers=headers)
    assert r.status_code == 422


async def test_deleting_a_template_leaves_applied_projects_alone(app_client, db, seeded_org, active_admin_user):
    from tests.test_field_ops import _create_customer_and_project

    headers = await _admin_headers(app_client, active_admin_user)
    _, project_id, template_id = await _create_customer_and_project(app_client, headers)
    antes = (await app_client.get(f"/api/v1/projects/{project_id}/checklist", headers=headers)).json()
    assert (await app_client.delete(f"{URL}/{template_id}", headers=headers)).status_code == 204
    despues = (await app_client.get(f"/api/v1/projects/{project_id}/checklist", headers=headers)).json()
    assert len(despues) == len(antes) > 0
    assert (await app_client.delete(f"{URL}/{template_id}", headers=headers)).status_code == 404


async def test_only_checklist_managers_edit_templates(app_client, db, seeded_org, active_admin_user,
                                                      active_salesperson_user):
    from tests.field_helpers import headers_for

    headers = await _admin_headers(app_client, active_admin_user)
    tid = (await app_client.post(URL, json={"name": "Por defecto", "items": []}, headers=headers)).json()["id"]
    vendedor = await headers_for(app_client, "vendedor@acme-demo.com")
    assert (await app_client.put(f"{URL}/{tid}", json={"name": "X", "items": []}, headers=vendedor)).status_code == 403
    assert (await app_client.delete(f"{URL}/{tid}", headers=vendedor)).status_code == 403
