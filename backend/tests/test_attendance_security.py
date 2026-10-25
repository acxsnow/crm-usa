"""Permisos, aislamiento por organización y privacidad de la ubicación en
turnos, nómina y mapa operativo."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.modules.attendance.mapdata import purge_old_locations
from app.modules.attendance.models import AttendanceEvent
from app.modules.field_ops import clock
from tests.field_helpers import approved_case_with_project, headers_for

API = "/api/v1"
AHORA = datetime(2026, 10, 26, 18, 0, tzinfo=timezone.utc)
GPS = {"latitude": 33.4484, "longitude": -112.0740, "location_status": "ok"}


@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    monkeypatch.setattr(clock, "_utcnow", lambda: AHORA)


@pytest.fixture
def login(app_client):
    from app.core.rate_limit import clear_all_buckets

    async def _login(user) -> dict:
        # Seis roles inician sesión desde la misma IP de prueba: sin esto,
        # el límite de intentos de login responde 429.
        clear_all_buckets()
        return await headers_for(app_client, user.email)
    return _login


ROLES = ["active_admin_user", "active_admin_staff_user", "active_technician_user", "active_accounting_user",
         "active_management_user", "active_salesperson_user"]

# (método, ruta, quién pasa la puerta del permiso)
MATRIZ = [
    ("GET", "/attendance/me", set(ROLES)),
    ("GET", "/attendance/shifts?date_from=2026-10-26&date_to=2026-10-26",
     {"active_admin_user", "active_admin_staff_user", "active_accounting_user", "active_management_user"}),
    ("GET", "/attendance/dashboard?date_from=2026-10-26&date_to=2026-10-26",
     {"active_admin_user", "active_admin_staff_user", "active_accounting_user", "active_management_user"}),
    ("GET", "/attendance/payroll/report?date_from=2026-10-26&date_to=2026-10-26",
     {"active_admin_user", "active_admin_staff_user", "active_accounting_user", "active_management_user"}),
    ("GET", "/attendance/entries?date_from=2026-10-26&date_to=2026-10-26",
     {"active_admin_user", "active_admin_staff_user", "active_accounting_user", "active_management_user"}),
    ("PUT", "/attendance/settings", {"active_admin_user", "active_admin_staff_user"}),
    ("POST", "/attendance/payroll/periods", {"active_admin_user", "active_accounting_user"}),
    ("GET", "/operations-map/people",
     {"active_admin_user", "active_admin_staff_user", "active_accounting_user", "active_management_user",
      "active_technician_user"}),
]


async def test_cada_ruta_pide_su_permiso(app_client, login, active_admin_user, active_admin_staff_user,
                                        active_technician_user, active_accounting_user, active_management_user,
                                        active_salesperson_user):
    usuarios = dict(zip(ROLES, [active_admin_user, active_admin_staff_user, active_technician_user,
                                active_accounting_user, active_management_user, active_salesperson_user]))
    for rol, usuario in usuarios.items():
        h = await login(usuario)
        for metodo, ruta, pasan in MATRIZ:
            cuerpo = {"start_date": "2026-10-01", "end_date": "2026-10-15"} if "periods" in ruta else {}
            r = await app_client.request(metodo, f"{API}{ruta}", headers=h,
                                         json=cuerpo if metodo != "GET" else None)
            if rol in pasan:
                assert r.status_code != 403, (rol, ruta, r.text)
            else:
                assert r.status_code == 403, (rol, ruta, r.status_code)


async def test_otra_organizacion_no_ve_ni_toca_nada(app_client, login, db, seeded_org, active_admin_user,
                                                   active_technician_user, second_org_admin_user):
    h, tec, otro = (await login(active_admin_user), await login(active_technician_user),
                    await login(second_org_admin_user))
    _, obra = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    t = await app_client.post(f"{API}/attendance/shifts", json={
        "user_ids": [str(active_technician_user.id)], "date_from": "2026-10-26", "date_to": "2026-10-26",
        "start_time": "17:00", "end_time": "23:00"}, headers=h)
    turno = t.json()["created"][0]["id"]
    r = await app_client.post(f"{API}/attendance/events", json={"event_type": "clock_in", **GPS}, headers=tec)
    eid = r.json()["entry"]["id"]
    # La otra organización no programa a una persona ajena ni ve sus datos.
    ajeno = await app_client.post(f"{API}/attendance/shifts", json={
        "user_ids": [str(active_technician_user.id)], "date_from": "2026-10-27", "date_to": "2026-10-27",
        "start_time": "07:00", "end_time": "15:00"}, headers=otro)
    assert (ajeno.status_code, ajeno.json()["code"]) == (400, "invalid_user")
    assert (await app_client.patch(f"{API}/attendance/shifts/{turno}", json={"notes": "x"},
                                   headers=otro)).status_code == 404
    assert (await app_client.get(f"{API}/attendance/entries/{eid}", headers=otro)).status_code == 404
    assert (await app_client.post(f"{API}/attendance/entries/{eid}/correct", json={"reason": "x"},
                                  headers=otro)).status_code == 404
    assert (await app_client.get(f"{API}/operations-map/people", headers=otro)).json() == []
    assert (await app_client.get(f"{API}/operations-map/projects/{obra.id}", headers=otro)).status_code == 404
    assert (await app_client.put(f"{API}/operations-map/projects/{obra.id}/location",
                                 json={"latitude": 33, "longitude": -112}, headers=otro)).status_code == 404
    live = (await app_client.get(f"{API}/attendance/live", headers=otro)).json()
    assert live == []
    panel = (await app_client.get(f"{API}/attendance/dashboard",
                                  params={"date_from": "2026-10-26", "date_to": "2026-10-26"}, headers=otro)).json()
    assert panel["kpis"]["scheduled_people"] == 0 and panel["by_person"] == []
    # Una obra ajena no sirve para un evento de desplazamiento.
    r = await app_client.post(f"{API}/attendance/events", json={"event_type": "clock_in"}, headers=otro)
    r = await app_client.post(f"{API}/attendance/events", json={"event_type": "en_route",
                                                                "project_id": str(obra.id)}, headers=otro)
    assert r.status_code == 404


async def test_la_ubicacion_ajena_solo_con_locations_view(app_client, login, db, seeded_org, active_admin_user,
                                                         active_technician_user, active_accounting_user,
                                                         active_management_user):
    tec, conta, gerencia = (await login(active_technician_user), await login(active_accounting_user),
                            await login(active_management_user))
    await app_client.post(f"{API}/attendance/events", json={"event_type": "clock_in", **GPS}, headers=tec)
    # Contabilidad ve el tablero, pero sin ubicación (no tiene locations.view).
    fila = (await app_client.get(f"{API}/attendance/live", headers=conta)).json()[0]
    assert fila["entry_status"] == "open" and fila["location"] is None
    assert (await app_client.get(f"{API}/operations-map/people", headers=conta)).json() == []
    # Gerencia sí la ve.
    gente = (await app_client.get(f"{API}/operations-map/people", headers=gerencia)).json()
    assert [g["user_id"] for g in gente] == [str(active_technician_user.id)] and gente[0]["shift_open"]
    # El técnico solo se ve a sí mismo, y su marcación sí trae su ubicación.
    yo = (await app_client.get(f"{API}/operations-map/people", headers=tec)).json()
    assert [g["user_id"] for g in yo] == [str(active_technician_user.id)]
    eid = (await app_client.get(f"{API}/attendance/me", headers=tec)).json()["entry"]["id"]
    detalle_conta = (await app_client.get(f"{API}/attendance/entries/{eid}", headers=conta)).json()
    assert "latitude" not in detalle_conta["events"][0]
    detalle_propio = (await app_client.get(f"{API}/attendance/entries/{eid}", headers=tec)).json()
    assert detalle_propio["events"][0]["latitude"] == 33.4484


async def test_un_tecnico_no_ve_marcaciones_ni_novedades_ajenas(
        app_client, login, db, seeded_org, active_technician_user, active_salesperson_user):
    tec, vend = await login(active_technician_user), await login(active_salesperson_user)
    r = await app_client.post(f"{API}/attendance/events", json={"event_type": "clock_in"}, headers=vend)
    eid = r.json()["entry"]["id"]
    assert (await app_client.get(f"{API}/attendance/entries/{eid}", headers=tec)).status_code == 404
    nov = await app_client.post(f"{API}/attendance/novelties", json={
        "kind": "correction", "time_entry_id": eid,
        "requested_clock_in_at": (AHORA - timedelta(hours=3)).isoformat()}, headers=tec)
    assert nov.status_code == 404
    await app_client.post(f"{API}/attendance/novelties", json={"kind": "other", "description": "x"}, headers=vend)
    assert (await app_client.get(f"{API}/attendance/novelties", headers=tec)).json() == []


async def test_la_retencion_borra_coordenadas_y_deja_el_evento(app_client, login, db, seeded_org,
                                                              active_admin_staff_user, active_technician_user):
    tec, oficina = await login(active_technician_user), await login(active_admin_staff_user)
    await app_client.post(f"{API}/attendance/events", json={"event_type": "clock_in", **GPS}, headers=tec)
    ev = (await db.execute(select(AttendanceEvent))).scalar_one()
    ev.occurred_at = AHORA - timedelta(days=91)
    await db.commit()
    assert await purge_old_locations(db) == 1
    await db.refresh(ev)
    assert (ev.latitude, ev.longitude, ev.location_status) == (None, None, "purged")
    # Borrado anticipado por persona, con auditoría.
    await app_client.post(f"{API}/attendance/events", json={"event_type": "tracking", **GPS}, headers=tec)
    r = await app_client.delete(f"{API}/attendance/users/{active_technician_user.id}/locations", headers=oficina)
    assert r.json() == {"purged": 1}
    assert (await app_client.delete(f"{API}/attendance/users/{active_technician_user.id}/locations",
                                    headers=tec)).status_code == 403
