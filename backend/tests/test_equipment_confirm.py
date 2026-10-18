"""«Guardar equipos instalados» (spec 2026-10-18-guardar-equipos-y-avisos):
el paso se completa al guardar la lista, no al agregar el primer equipo."""
from tests.field_helpers import headers_for, installed_case, ready_to_install_case, resolve_whole_checklist

EQUIPO = {"equipment_type": "heat_pump_outdoor", "brand": "Carrier", "model": "25HCE4",
          "serial_number": "5219E12345", "quantity": 1, "unit_label": "Casa principal"}


async def _orden(app_client, db, seeded_org, technician):
    _, project = await ready_to_install_case(db, seeded_org["org"].id, technician_id=technician.id)
    return project, await headers_for(app_client, "tech@acme-demo.com")


async def _proyecto(app_client, project_id, headers):
    return (await app_client.get(f"/api/v1/projects/{project_id}", headers=headers)).json()


async def test_adding_equipment_does_not_save_the_list(app_client, db, seeded_org, active_technician_user):
    project, h = await _orden(app_client, db, seeded_org, active_technician_user)
    await app_client.post(f"/api/v1/projects/{project.id}/equipment", json=EQUIPO, headers=h)
    assert (await _proyecto(app_client, project.id, h))["equipment_confirmed_at"] is None


async def test_saving_needs_at_least_one_equipment(app_client, db, seeded_org, active_technician_user):
    project, h = await _orden(app_client, db, seeded_org, active_technician_user)
    resp = await app_client.post(f"/api/v1/projects/{project.id}/equipment/confirm", headers=h)
    assert resp.status_code == 400
    assert resp.json()["code"] == "no_equipment"


async def test_saving_marks_the_list_and_changing_it_undoes_that(app_client, db, seeded_org, active_technician_user):
    project, h = await _orden(app_client, db, seeded_org, active_technician_user)
    await app_client.post(f"/api/v1/projects/{project.id}/equipment", json=EQUIPO, headers=h)

    resp = await app_client.post(f"/api/v1/projects/{project.id}/equipment/confirm", headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["equipment_confirmed_at"] is not None

    # Agregar otro equipo cambia la lista: hay que volver a guardarla.
    otro = (await app_client.post(f"/api/v1/projects/{project.id}/equipment",
                                  json={**EQUIPO, "serial_number": "X2"}, headers=h)).json()
    assert (await _proyecto(app_client, project.id, h))["equipment_confirmed_at"] is None

    await app_client.post(f"/api/v1/projects/{project.id}/equipment/confirm", headers=h)
    # Quitar uno también.
    assert (await app_client.delete(f"/api/v1/equipment/{otro['id']}", headers=h)).status_code == 204
    assert (await _proyecto(app_client, project.id, h))["equipment_confirmed_at"] is None


async def test_closing_asks_to_save_the_equipment_list(app_client, db, seeded_org, active_technician_user):
    project, h = await _orden(app_client, db, seeded_org, active_technician_user)
    await resolve_whole_checklist(db, project.id)
    await app_client.post(f"/api/v1/projects/{project.id}/equipment", json=EQUIPO, headers=h)

    gaps = (await app_client.get(f"/api/v1/projects/{project.id}/installation/gaps", headers=h)).json()
    assert gaps["can_close"] is False
    assert any("Guardar la lista de equipos" in g for g in gaps["missing"])

    await app_client.post(f"/api/v1/projects/{project.id}/equipment/confirm", headers=h)
    gaps = (await app_client.get(f"/api/v1/projects/{project.id}/installation/gaps", headers=h)).json()
    assert gaps["can_close"] is True


async def test_another_technician_cannot_save_the_list(app_client, db, seeded_org, active_technician_user):
    _, project = await ready_to_install_case(db, seeded_org["org"].id)
    h = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.post(f"/api/v1/projects/{project.id}/equipment/confirm", headers=h)
    assert resp.status_code == 404


async def test_a_salesperson_cannot_save_the_list(app_client, db, seeded_org, active_salesperson_user):
    _, project = await ready_to_install_case(db, seeded_org["org"].id)
    h = await headers_for(app_client, active_salesperson_user.email)
    resp = await app_client.post(f"/api/v1/projects/{project.id}/equipment/confirm", headers=h)
    assert resp.status_code == 403


async def test_the_list_cannot_be_saved_after_closing(app_client, db, seeded_org, active_technician_user):
    _, project = await installed_case(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    h = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.post(f"/api/v1/projects/{project.id}/equipment/confirm", headers=h)
    assert resp.status_code == 409
    assert resp.json()["code"] == "installation_closed"
