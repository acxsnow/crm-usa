"""Agenda con vistas «Pendientes» e «Historial» (spec 2026-10-16).

Pendientes: lo que falta por hacer, atrasado incluido, de lo más viejo a lo más
nuevo. Historial: lo cerrado o cancelado de un rango, de lo más nuevo a lo más
viejo. Sin `view`, la agenda sigue como antes (ver test_field_installation)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.modules.cases import stages
from app.modules.field_ops import case_hooks
from app.modules.field_ops.models import ProjectStatus
from tests.field_helpers import approved_case_with_project, headers_for

# El «hoy» del servidor (organización de prueba en UTC): con `date.today()` local,
# después de las 7 p. m. en Bogotá ya es mañana en UTC y la prueba fallaba por la hora.
HOY = datetime.now(timezone.utc).date()
URL = "/api/v1/dispatch/agenda"


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()


async def _orden(db, org_id, tecnico_id, dias, estado=ProjectStatus.scheduled):
    """Una orden del técnico agendada `dias` días desde hoy (negativo = pasado)."""
    _, project = await approved_case_with_project(db, org_id, technician_id=tecnico_id)
    project.scheduled_date = HOY + timedelta(days=dias)
    project.status = estado
    await db.commit()
    return project


async def test_pending_shows_overdue_first_then_today_and_upcoming(app_client, db, seeded_org, active_technician_user):
    org, tec = seeded_org["org"].id, active_technician_user.id
    atrasada = await _orden(db, org, tec, -20)          # semanas atrás y sin cerrar: tiene que salir
    hoy = await _orden(db, org, tec, 0)
    proxima = await _orden(db, org, tec, 5)
    await _orden(db, org, tec, 30)                       # pasa del «Hasta»
    await _orden(db, org, tec, -1, ProjectStatus.completed)
    await _orden(db, org, tec, 2, ProjectStatus.cancelled)

    headers = await headers_for(app_client, "tech@acme-demo.com")
    r = await app_client.get(URL, params={"view": "pending", "date_to": str(HOY + timedelta(days=14))}, headers=headers)
    assert r.status_code == 200, r.text
    filas = r.json()
    assert [f["project_id"] for f in filas] == [str(atrasada.id), str(hoy.id), str(proxima.id)]
    assert [f["days_late"] for f in filas] == [20, None, None]
    assert r.headers["x-total-count"] == "3"


async def test_history_shows_closed_newest_first_and_paginates(app_client, db, seeded_org, active_technician_user):
    org, tec = seeded_org["org"].id, active_technician_user.id
    vieja = await _orden(db, org, tec, -10, ProjectStatus.completed)
    cancelada = await _orden(db, org, tec, -5, ProjectStatus.cancelled)
    reciente = await _orden(db, org, tec, -1, ProjectStatus.completed)
    await _orden(db, org, tec, -3)                       # pendiente: no va al historial
    await _orden(db, org, tec, -60, ProjectStatus.completed)  # fuera del rango

    headers = await headers_for(app_client, "tech@acme-demo.com")
    rango = {"view": "history", "date_from": str(HOY - timedelta(days=30)), "date_to": str(HOY)}
    p1 = await app_client.get(URL, params={**rango, "limit": 2, "offset": 0}, headers=headers)
    p2 = await app_client.get(URL, params={**rango, "limit": 2, "offset": 2}, headers=headers)
    assert p1.headers["x-total-count"] == "3"
    ids = [f["project_id"] for f in p1.json() + p2.json()]
    assert ids == [str(reciente.id), str(cancelada.id), str(vieja.id)]
    assert all(f["days_late"] is None for f in p1.json() + p2.json())


async def test_the_technician_only_sees_their_own_in_both_views(app_client, db, seeded_org, active_technician_user):
    org = seeded_org["org"].id
    mia = await _orden(db, org, active_technician_user.id, 1)
    await _orden(db, org, None, 1)                        # sin técnico: no es suya
    headers = await headers_for(app_client, "tech@acme-demo.com")
    r = await app_client.get(URL, params={"view": "pending", "date_to": str(HOY + timedelta(days=7))}, headers=headers)
    assert [f["project_id"] for f in r.json()] == [str(mia.id)]


async def test_admin_sees_everyone_and_can_filter_by_technician(app_client, db, seeded_org, active_technician_user,
                                                               active_admin_staff_user):
    org = seeded_org["org"].id
    del_tecnico = await _orden(db, org, active_technician_user.id, 1)
    sin_tecnico = await _orden(db, org, None, 2)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    base = {"view": "pending", "date_to": str(HOY + timedelta(days=7))}
    todos = (await app_client.get(URL, params=base, headers=headers)).json()
    assert [f["project_id"] for f in todos] == [str(del_tecnico.id), str(sin_tecnico.id)]
    uno = (await app_client.get(URL, params={**base, "technician_id": str(active_technician_user.id)}, headers=headers)).json()
    assert [f["project_id"] for f in uno] == [str(del_tecnico.id)]


async def test_pending_needs_date_to_and_history_both_dates(app_client, db, seeded_org, active_technician_user):
    headers = await headers_for(app_client, "tech@acme-demo.com")
    assert (await app_client.get(URL, params={"view": "pending"}, headers=headers)).status_code in (400, 422)
    r = await app_client.get(URL, params={"view": "history", "date_to": str(HOY)}, headers=headers)
    assert r.status_code in (400, 422)
