"""Bandeja «Por revisar» (spec 2026-10-19-bandeja-por-revisar): la cola de
inspección municipal y los cobros por crear."""
from datetime import date, datetime, timezone

from app.modules.field_ops.models import Inspection
from tests.field_helpers import headers_for, installed_case, ready_to_install_case

INSPECCION = "/api/v1/inspection-queue"
COBROS = "/api/v1/billing/to-create"


async def _cerrada(db, org_id, cerrada_el: date):
    _, project = await installed_case(db, org_id)
    project.completed_date = cerrada_el
    await db.commit()
    return project


def _inspeccion(project, result: str, dia: int) -> Inspection:
    return Inspection(organization_id=project.organization_id, project_id=project.id, result=result,
                      scheduled_for=datetime(2026, 10, dia, 15, tzinfo=timezone.utc))


async def test_the_inspection_queue_lists_closed_installations_still_without_a_passed_inspection(
        app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    sin_agendar = await _cerrada(db, org, date(2026, 10, 5))
    agendada = await _cerrada(db, org, date(2026, 10, 7))
    fallida = await _cerrada(db, org, date(2026, 10, 6))
    aprobada = await _cerrada(db, org, date(2026, 10, 4))
    await ready_to_install_case(db, org)  # sin cerrar: no entra
    db.add_all([_inspeccion(agendada, "pending", 21), _inspeccion(fallida, "failed", 12),
                _inspeccion(aprobada, "passed", 10)])
    await db.commit()

    h = await headers_for(app_client, active_admin_staff_user.email)
    r = await app_client.get(INSPECCION, headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["X-Total-Count"] == "3"
    filas = r.json()
    assert [(f["project_id"], f["status"]) for f in filas] == [
        (str(sin_agendar.id), "unscheduled"), (str(fallida.id), "failed"), (str(agendada.id), "scheduled")]
    assert filas[0]["case_number"] == sin_agendar.case_number and filas[0]["scheduled_for"] is None
    assert filas[2]["scheduled_for"].startswith("2026-10-21")
    assert filas[0]["days_since_close"] >= filas[1]["days_since_close"]


async def test_the_inspection_queue_is_for_who_manages_inspections(
        app_client, db, seeded_org, active_technician_user, second_org_admin_user):
    await _cerrada(db, seeded_org["org"].id, date(2026, 10, 5))
    tecnico = await headers_for(app_client, "tech@acme-demo.com")
    assert (await app_client.get(INSPECCION, headers=tecnico)).status_code == 403
    otra = await headers_for(app_client, second_org_admin_user.email)
    r = await app_client.get(INSPECCION, headers=otra)
    assert r.status_code == 200 and r.json() == []


async def test_claims_to_create_is_the_same_list_as_billing(
        app_client, db, seeded_org, active_admin_staff_user, active_accounting_user, active_technician_user):
    org = seeded_org["org"].id
    confirmada = await _cerrada(db, org, date(2026, 10, 5))
    await _cerrada(db, org, date(2026, 10, 6))  # sin confirmar: todavía no se cobra
    admin = await headers_for(app_client, active_admin_staff_user.email)
    assert (await app_client.post(f"/api/v1/projects/{confirmada.id}/review/confirm", headers=admin)).status_code == 200

    conta = await headers_for(app_client, active_accounting_user.email)
    r = await app_client.get(COBROS, headers=conta)
    assert r.status_code == 200, r.text
    assert r.headers["X-Total-Count"] == "1"
    assert [f["project_id"] for f in r.json()] == [str(confirmada.id)]
    tablero = (await app_client.get("/api/v1/billing/dashboard", headers=conta)).json()
    assert [f["project_id"] for f in tablero["to_create"]] == [str(confirmada.id)]

    tecnico = await headers_for(app_client, "tech@acme-demo.com")
    assert (await app_client.get(COBROS, headers=tecnico)).status_code == 403
