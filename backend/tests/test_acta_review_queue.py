"""«Actas por confirmar» (spec 2026-10-19-actas-por-confirmar)."""
from datetime import date

from tests.field_helpers import headers_for, installed_case

COLA = "/api/v1/acta-reviews/pending"


async def _cerrada(db, org_id, technician_id, cerrada_el: date):
    _, project = await installed_case(db, org_id, technician_id=technician_id)
    project.completed_date = cerrada_el
    await db.commit()
    return project


async def test_closed_actas_wait_oldest_first_and_leave_when_confirmed(
        app_client, db, seeded_org, active_admin_staff_user, active_technician_user):
    org = seeded_org["org"].id
    nueva = await _cerrada(db, org, active_technician_user.id, date(2026, 10, 15))
    vieja = await _cerrada(db, org, active_technician_user.id, date(2026, 10, 10))
    h = await headers_for(app_client, active_admin_staff_user.email)

    r = await app_client.get(COLA, headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["X-Total-Count"] == "2"
    filas = r.json()
    assert [f["project_id"] for f in filas] == [str(vieja.id), str(nueva.id)]
    assert filas[0]["case_number"] == vieja.case_number
    assert filas[0]["completed_date"] == "2026-10-10"
    assert filas[0]["technician_name"] and filas[0]["customer_name"]
    assert filas[0]["days_waiting"] >= filas[1]["days_waiting"] + 5

    assert (await app_client.post(f"/api/v1/projects/{vieja.id}/review/confirm", headers=h)).status_code == 200
    filas = (await app_client.get(COLA, headers=h)).json()
    assert [f["project_id"] for f in filas] == [str(nueva.id)]


async def test_the_queue_is_for_reviewers_of_the_same_organization(
        app_client, db, seeded_org, active_technician_user, second_org_admin_user):
    await _cerrada(db, seeded_org["org"].id, active_technician_user.id, date(2026, 10, 10))
    tecnico = await headers_for(app_client, "tech@acme-demo.com")
    assert (await app_client.get(COLA, headers=tecnico)).status_code == 403
    otra = await headers_for(app_client, second_org_admin_user.email)
    r = await app_client.get(COLA, headers=otra)
    assert r.status_code == 200 and r.json() == []
