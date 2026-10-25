"""Mapa operativo: obras con y sin coordenadas, fijar la ubicación de la obra,
minimapa con distancia en línea recta y orden sugerido del día."""
from datetime import date, datetime, timezone

import pytest

from app.modules.field_ops import clock
from tests.field_helpers import approved_case_with_project, headers_for

API = "/api/v1/operations-map"
HOY = date(2026, 10, 26)


@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    monkeypatch.setattr(clock, "_utcnow", lambda: datetime(2026, 10, 26, 16, 0, tzinfo=timezone.utc))


async def _obra(db, org_id, tecnico_id, lat=None, lng=None, titulo="Obra"):
    _, p = await approved_case_with_project(db, org_id, technician_id=tecnico_id)
    p.latitude, p.longitude, p.title, p.scheduled_date = lat, lng, titulo, HOY
    await db.commit()
    return p


async def test_obras_ubicadas_y_sin_ubicar_y_fijar_tocando_el_mapa(
        app_client, db, seeded_org, active_admin_staff_user, active_technician_user):
    oficina = await headers_for(app_client, active_admin_staff_user.email)
    tec = await headers_for(app_client, active_technician_user.email)
    ubicada = await _obra(db, seeded_org["org"].id, active_technician_user.id, 33.45, -112.07, "Ubicada")
    sin = await _obra(db, seeded_org["org"].id, active_technician_user.id, titulo="Sin coordenadas")
    r = (await app_client.get(f"{API}/projects", headers=oficina)).json()
    assert [p["id"] for p in r["projects"]] == [str(ubicada.id)]
    assert [p["id"] for p in r["unlocated"]] == [str(sin.id)]
    assert r["projects"][0]["technician_name"] == active_technician_user.full_name
    # El técnico ve sus obras en el mapa pero no cambia su ubicación.
    assert len((await app_client.get(f"{API}/projects", headers=tec)).json()["projects"]) == 1
    assert (await app_client.put(f"{API}/projects/{sin.id}/location", json={"latitude": 33.4, "longitude": -112.0},
                                 headers=tec)).status_code == 403
    assert (await app_client.put(f"{API}/projects/{sin.id}/location", json={"latitude": 0, "longitude": 0},
                                 headers=oficina)).status_code == 400
    ok = await app_client.put(f"{API}/projects/{sin.id}/location", json={"latitude": 33.42, "longitude": -111.94},
                              headers=oficina)
    assert ok.status_code == 200
    assert len((await app_client.get(f"{API}/projects", headers=oficina)).json()["projects"]) == 2
    # Filtro por cliente con comodines y byte nulo: no revienta.
    for q in ("%", "_", "Marge\x00"):
        assert (await app_client.get(f"{API}/projects", params={"customer": q}, headers=oficina)).status_code == 200


async def test_minimapa_y_orden_sugerido_del_dia(app_client, db, seeded_org, active_admin_staff_user,
                                                 active_technician_user):
    oficina = await headers_for(app_client, active_admin_staff_user.email)
    tec = await headers_for(app_client, active_technician_user.email)
    lejos = await _obra(db, seeded_org["org"].id, active_technician_user.id, 33.60, -112.30, "Lejos")
    cerca = await _obra(db, seeded_org["org"].id, active_technician_user.id, 33.45, -112.08, "Cerca")
    await app_client.post("/api/v1/attendance/events", json={
        "event_type": "clock_in", "latitude": 33.4484, "longitude": -112.0740, "location_status": "ok"}, headers=tec)
    mini = (await app_client.get(f"{API}/projects/{lejos.id}", headers=oficina)).json()
    assert mini["located"] and mini["technician"]["location"]["age_minutes"] == 0
    assert 25 < mini["straight_line_km"] < 35 and mini["directions_url"].startswith("https://www.google.com/maps")
    ruta = (await app_client.get(f"{API}/route", params={"on_date": HOY.isoformat(),
                                                          "user_id": str(active_technician_user.id)},
                                 headers=oficina)).json()
    assert [s["title"] for s in ruta["stops"]] == ["Cerca", "Lejos"]
    assert ruta["distance_source"] == "straight_line" and ruta["total_km"] > 0
