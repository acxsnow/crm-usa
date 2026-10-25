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


async def test_ubicar_por_direccion_las_obras_sin_gps(app_client, db, seeded_org, second_org, monkeypatch,
                                                      active_admin_staff_user, active_technician_user):
    """«No tienen coordenadas de la visita»: la oficina las ubica por dirección
    (Censo de EE. UU.) sin tocar las que ya tienen punto ni las de otra
    organización; lo que el servicio no encuentra queda para fijar a mano."""
    from app.core.config import get_settings
    from app.shared import geocoding

    llamadas = []

    async def censo_falso(street, city, state, zip_code):
        llamadas.append(street)
        return None if street == "1 Calle Inexistente" else (33.4775, -112.0476)

    monkeypatch.setattr(get_settings(), "GEOCODER", "census")
    monkeypatch.setattr(geocoding, "geocode", censo_falso)
    oficina = await headers_for(app_client, active_admin_staff_user.email)
    tec = await headers_for(app_client, active_technician_user.email)
    org = seeded_org["org"].id
    con_gps = await _obra(db, org, active_technician_user.id, 34.28, -118.44, "Con GPS")
    sin = await _obra(db, org, active_technician_user.id, titulo="Sin GPS")
    perdida = await _obra(db, org, active_technician_user.id, titulo="Perdida")
    perdida.address_street = "1 Calle Inexistente"
    ajena = await _obra(db, second_org["org"].id, None, titulo="Ajena")
    await db.commit()

    # El técnico no ubica obras.
    assert (await app_client.post(f"{API}/projects/geocode", json={}, headers=tec)).status_code == 403
    r = await app_client.post(f"{API}/projects/geocode", json={}, headers=oficina)
    assert r.status_code == 200, r.text
    assert [o["id"] for o in r.json()["located"]] == [str(sin.id)]
    assert [o["id"] for o in r.json()["not_found"]] == [str(perdida.id)]
    assert len(llamadas) == 2  # ni la que tiene GPS ni la de otra organización
    await db.refresh(con_gps)
    await db.refresh(ajena)
    assert (con_gps.latitude, con_gps.longitude) == (34.28, -118.44)
    assert ajena.latitude is None
    mapa = (await app_client.get(f"{API}/projects", headers=oficina)).json()
    assert [p["id"] for p in mapa["unlocated"]] == [str(perdida.id)]

    # Una sola obra por id; una ajena no se toca aunque se pida.
    r = await app_client.post(f"{API}/projects/geocode", json={"project_ids": [str(ajena.id)]}, headers=oficina)
    assert r.json() == {"located": [], "not_found": []}

    # Apagado en el servidor: lo dice y no consulta nada.
    monkeypatch.setattr(get_settings(), "GEOCODER", "off")
    r = await app_client.post(f"{API}/projects/geocode", json={}, headers=oficina)
    assert r.status_code == 400 and r.json()["code"] == "geocoder_off"


async def test_geocodificador_del_censo_lee_la_respuesta(monkeypatch):
    """La lectura de la respuesta real del Censo (x = longitud, y = latitud) y
    que un fallo de red no revienta: devuelve None."""
    import httpx

    from app.core.config import get_settings
    from app.shared import geocoding

    monkeypatch.setattr(get_settings(), "GEOCODER", "census")

    def responder(request):
        assert "Marge" not in str(request.url)  # solo viaja la dirección
        return httpx.Response(200, json={"result": {"addressMatches": [
            {"coordinates": {"x": -112.047578, "y": 33.477568}}]}})

    real = httpx.AsyncClient

    monkeypatch.setattr(geocoding.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(responder), **kw))
    assert await geocoding.geocode("2701 N 16th St", "Phoenix", "AZ", "85006") == (33.477568, -112.047578)
    assert await geocoding.geocode(None, "Phoenix", "AZ", "85006") is None

    monkeypatch.setattr(geocoding.httpx, "AsyncClient", lambda **kw: real(
        transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("sin red"))), **kw))
    assert await geocoding.geocode("2701 N 16th St", "Phoenix", "AZ", "85006") is None
