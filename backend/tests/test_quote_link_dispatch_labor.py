"""Cotización por enlace con opciones y firma, tablero de despacho y mano de
obra desde las horas aprobadas (spec 2026-10-31)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.modules.attendance.models import AttendanceEvent, TimeEntry, WorkShift
from app.modules.billing.models import Invoice, Quote
from app.modules.cases import stages
from app.modules.crm.models import Customer
from app.modules.field_ops import case_hooks
from app.modules.field_ops.models import Project
from app.modules.warehouse import labor
from app.shared import events as domain_events
from tests.field_helpers import approved_case_with_project, headers_for
from tests.test_cases_intake import firma_png

API = "/api/v1"
Q = f"{API}/billing/quotes"
LINEAS = [
    {"description": "Visita y diagnóstico", "quantity": 1, "unit_price": 100},
    {"description": "Reparación básica", "quantity": 1, "unit_price": 200, "option_key": "A"},
    {"description": "Cambio completo", "quantity": 1, "unit_price": 900, "option_key": "B"},
]
OPCIONES = [{"key": "A", "label": "Básica"}, {"key": "B", "label": "Premium"}]


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()
    domain_events.clear_subscribers()


@pytest.fixture
async def admin(app_client, active_admin_user):
    return await headers_for(app_client, "admin@acme-demo.com")


async def _cliente(db, org_id, email="ned@example.com"):
    c = Customer(organization_id=org_id, legal_name="Ned Flanders", email=email)
    db.add(c)
    await db.commit()
    return c


async def _enviada(app_client, h, customer_id, **extra):
    q = await app_client.post(Q, headers=h, json={"customer_id": str(customer_id), "title": "Reparar el aire",
                                                  "lines": LINEAS, "options": OPCIONES, **extra})
    assert q.status_code == 201, q.text
    r = await app_client.post(f"{Q}/{q.json()['id']}/send", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def _enlace(app_client, h, quote_id, email=False):
    r = await app_client.post(f"{Q}/{quote_id}/link", headers=h, json={"email": email})
    assert r.status_code == 200, r.text
    return r.json()["url"].rsplit("/", 1)[1], r.json()


async def test_opciones_totales_y_validaciones(app_client, db, seeded_org, admin):
    c = await _cliente(db, seeded_org["org"].id)
    q = await _enviada(app_client, admin, c.id)
    assert [(o["key"], float(o["total"])) for o in q["options"]] == [("A", 300.0), ("B", 1000.0)]
    # Una opción sin línea propia, o una línea de una opción que no existe, no pasan.
    r = await app_client.post(Q, headers=admin, json={"customer_id": str(c.id), "options": OPCIONES,
                                                      "lines": LINEAS[:2]})
    assert r.status_code == 400 and r.json()["code"] == "quote_option_empty"
    r = await app_client.post(Q, headers=admin, json={"customer_id": str(c.id), "lines": LINEAS})
    assert r.status_code == 400 and r.json()["code"] == "quote_option_unknown"
    # Aceptar desde la oficina también exige elegir.
    r = await app_client.post(f"{Q}/{q['id']}/accept", headers=admin, json={})
    assert r.status_code == 400 and r.json()["code"] == "quote_option_required"


async def test_el_cliente_ve_elige_firma_y_nacen_factura_y_obra(app_client, db, seeded_org, admin):
    c = await _cliente(db, seeded_org["org"].id)
    cliente_id = c.id
    q = await _enviada(app_client, admin, cliente_id)
    token, datos = await _enlace(app_client, admin, q["id"], email=True)
    assert datos["emailed_to"] == "ned@example.com"
    fila = await db.get(Quote, q["id"])
    assert token not in (fila.public_token_hash or "")

    vista = (await app_client.get(f"{API}/public/quotes/{token}")).json()
    assert vista["can_decide"] is True and vista["customer_name"] == "Ned Flanders" and len(vista["options"]) == 2
    r = await app_client.post(f"{API}/public/quotes/{token}/accept", json={
        "option": "Z", "signer_name": "Ned Flanders", "signature_base64": firma_png()})
    assert r.status_code == 400 and r.json()["code"] == "quote_option_required"
    r = await app_client.post(f"{API}/public/quotes/{token}/accept", json={
        "option": "B", "signer_name": "Ned Flanders", "signature_base64": firma_png()})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "accepted" and r.json()["can_decide"] is False and r.json()["accepted_option"] == "B"

    db.expire_all()
    fila = await db.get(Quote, q["id"])
    assert fila.decided_by == "customer" and fila.signer_name == "Ned Flanders" and fila.signature_path
    factura = (await db.execute(select(Invoice).where(Invoice.quote_id == fila.id))).scalar_one()
    assert factura.amount == Decimal("1000.00") and len(factura.lines) == 2
    assert not any(l.description == "Reparación básica" for l in factura.lines)
    obra = await db.get(Project, fila.project_id)
    assert obra.customer_id == cliente_id and obra.title == "Reparar el aire" and factura.project_id == obra.id
    # La oficina se entera.
    avisos = (await app_client.get(f"{API}/notifications", headers=admin)).json()
    assert any("Cotización aceptada" in (a.get("title") or "") for a in avisos)
    # No se decide dos veces.
    r = await app_client.post(f"{API}/public/quotes/{token}/reject", json={"reason": "cambié de idea"})
    assert r.status_code == 409


async def test_rechazo_enlace_nuevo_y_version_nueva_invalidan(app_client, db, seeded_org, admin):
    c = await _cliente(db, seeded_org["org"].id)
    q = await _enviada(app_client, admin, c.id)
    viejo, _ = await _enlace(app_client, admin, q["id"])
    nuevo, _ = await _enlace(app_client, admin, q["id"])
    assert (await app_client.get(f"{API}/public/quotes/{viejo}")).status_code == 404
    # Ajustar la cotización apaga el enlace de la versión anterior.
    await app_client.post(f"{Q}/{q['id']}/revise", headers=admin)
    assert (await app_client.get(f"{API}/public/quotes/{nuevo}")).status_code == 404

    q2 = await _enviada(app_client, admin, c.id)
    token, _ = await _enlace(app_client, admin, q2["id"])
    r = await app_client.post(f"{API}/public/quotes/{token}/reject", json={"reason": "Muy costosa"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    fila = await db.get(Quote, q2["id"])
    await db.refresh(fila)
    assert fila.rejection_reason == "Muy costosa" and fila.decided_by == "customer"


async def test_enlace_exige_permiso_correo_y_misma_organizacion(app_client, db, seeded_org, admin, active_technician_user):
    c = await _cliente(db, seeded_org["org"].id, email=None)
    q = await _enviada(app_client, admin, c.id)
    r = await app_client.post(f"{Q}/{q['id']}/link", headers=admin, json={"email": True})
    assert r.status_code == 400 and r.json()["code"] == "customer_email_missing"
    tec = await headers_for(app_client, active_technician_user.email)
    assert (await app_client.post(f"{Q}/{q['id']}/link", headers=tec, json={})).status_code == 403
    assert (await app_client.get(f"{API}/public/quotes/no-existe")).status_code == 404


async def test_tablero_por_tecnico_dia_y_sin_agendar(app_client, db, seeded_org, admin, active_technician_user):
    org = seeded_org["org"].id
    hoy = datetime.now(timezone.utc).date()
    manana = hoy + timedelta(days=1)
    _, sin_agenda = await approved_case_with_project(db, org)
    _, agendada = await approved_case_with_project(db, org)
    r = await app_client.patch(f"{API}/projects/{agendada.id}/schedule", headers=admin, json={
        "technician_user_id": str(active_technician_user.id), "scheduled_date": manana.isoformat()})
    assert r.status_code == 200, r.text
    inicio = datetime.combine(manana, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=14)
    db.add(WorkShift(organization_id=org, user_id=active_technician_user.id, shift_date=manana, starts_at=inicio,
                     ends_at=inicio + timedelta(hours=8)))
    await db.commit()

    r = await app_client.get(f"{API}/dispatch/board", headers=admin,
                             params={"date_from": hoy.isoformat(), "date_to": (hoy + timedelta(days=6)).isoformat()})
    assert r.status_code == 200, r.text
    tablero = r.json()
    assert len(tablero["days"]) == 7
    fila = next(t for t in tablero["technicians"] if t["id"] == str(active_technician_user.id))
    assert [j["project_id"] for j in fila["jobs"][manana.isoformat()]] == [str(agendada.id)]
    assert len(fila["shifts"][manana.isoformat()]) == 1
    ids = [j["project_id"] for j in tablero["unscheduled"]]
    assert str(sin_agenda.id) in ids and str(agendada.id) not in ids

    # El rango tiene tope y el técnico no ve el tablero.
    r = await app_client.get(f"{API}/dispatch/board", headers=admin,
                             params={"date_from": hoy.isoformat(), "date_to": (hoy + timedelta(days=40)).isoformat()})
    assert r.status_code == 400 and r.json()["code"] == "agenda_range_too_long"
    tec = await headers_for(app_client, active_technician_user.email)
    r = await app_client.get(f"{API}/dispatch/board", headers=tec,
                             params={"date_from": hoy.isoformat(), "date_to": hoy.isoformat()})
    assert r.status_code == 403


async def _turno(db, org, user_id, marcas, *, aprobado=None, estado="approved"):
    """`marcas`: [(tipo, proyecto, minutos desde la entrada)]. Turno de 8 h."""
    inicio = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)
    fin = inicio + timedelta(hours=8)
    t = TimeEntry(organization_id=org, user_id=user_id, work_date=inicio.date(), clock_in_at=inicio,
                  clock_in_received_at=inicio, clock_out_at=fin, clock_out_received_at=fin, status=estado,
                  approved_minutes=aprobado)
    db.add(t)
    await db.flush()
    for tipo, pid, mins in marcas:
        momento = inicio + timedelta(minutes=mins)
        db.add(AttendanceEvent(organization_id=org, user_id=user_id, time_entry_id=t.id, project_id=pid,
                               event_type=tipo, received_at=momento, occurred_at=momento))
    await db.commit()
    return t


async def test_mano_de_obra_sale_de_horas_aprobadas_por_tarifa(app_client, db, seeded_org, admin, active_technician_user):
    org = seeded_org["org"].id
    tec = active_technician_user.id
    _, obra1 = await approved_case_with_project(db, org)
    _, obra2 = await approved_case_with_project(db, org)
    # 2 h en la obra 1 (con viaje), 1 h en la 2 hasta cerrar el turno a la hora 8.
    await _turno(db, org, tec, [("en_route", obra1.id, 0), ("arrived", obra1.id, 30), ("left_site", obra1.id, 120),
                                ("arrived", obra2.id, 420)], aprobado=480)
    # Un turno sin aprobar no cuenta.
    await _turno(db, org, tec, [("arrived", obra1.id, 0), ("left_site", obra1.id, 60)], estado="closed")

    r = await app_client.put(f"{API}/jobcost/labor-rates/{tec}", headers=admin, json={"hourly_rate": "30"})
    assert r.status_code == 200, r.text
    assert (await app_client.get(f"{API}/jobcost/labor-rates", headers=admin)).status_code == 200
    costos = await labor.costs_by_project(db, org, {obra1.id, obra2.id})
    assert costos[obra1.id] == Decimal("60.00") and costos[obra2.id] == Decimal("30.00")
    detalle = (await app_client.get(f"{API}/projects/{obra1.id}/labor-hours", headers=admin)).json()
    assert detalle["rows"][0]["minutes"] == 120 and detalle["total"] == "60.00"

    # Suma a «Mano de obra» en el costo del trabajo.
    from app.modules.warehouse.costing import project_actual_costs

    assert (await project_actual_costs(db, org, {obra1.id}))[obra1.id]["labor"] == Decimal("60.00")

    # Sin tarifa no suma, y el detalle lo avisa.
    await app_client.put(f"{API}/jobcost/labor-rates/{tec}", headers=admin, json={"hourly_rate": None})
    assert await labor.costs_by_project(db, org, {obra1.id}) == {}
    detalle = (await app_client.get(f"{API}/projects/{obra1.id}/labor-hours", headers=admin)).json()
    assert detalle["missing_rate"] and detalle["total"] == "0.00"


async def test_aprobado_menor_a_lo_marcado_reparte_en_proporcion(db, seeded_org, active_technician_user):
    org = seeded_org["org"].id
    _, obra = await approved_case_with_project(db, org)
    await _turno(db, org, active_technician_user.id, [("arrived", obra.id, 0), ("left_site", obra.id, 240)], aprobado=120)
    minutos = await labor.minutes_by_project(db, org, {obra.id})
    assert round(minutos[obra.id][active_technician_user.id]) == 120


async def test_tarifas_con_permiso(app_client, active_technician_user):
    tec = await headers_for(app_client, active_technician_user.email)
    assert (await app_client.get(f"{API}/jobcost/labor-rates", headers=tec)).status_code == 403


async def test_tarifa_de_planta_y_por_trabajo_segun_el_cliente(app_client, db, seeded_org, admin, active_technician_user):
    org = seeded_org["org"].id
    tec = active_technician_user.id
    _, obra = await approved_case_with_project(db, org)
    await _turno(db, org, tec, [("arrived", obra.id, 0), ("left_site", obra.id, 120)], aprobado=480)
    planta = (await app_client.get(f"{API}/jobcost/plant-rate", headers=admin)).json()
    assert (planta["plant_hourly_rate"], planta["plant_daily_hours"], planta["plant_daily_value"]) == ("45.00", "8.00", "360.00")
    # Sin forma de pago no suma y se avisa.
    assert await labor.costs_by_project(db, org, {obra.id}) == {}
    assert (await app_client.get(f"{API}/projects/{obra.id}/labor-hours", headers=admin)).json()["missing_rate"]
    # Por hora: 2 h × 45.
    r = await app_client.put(f"{API}/attendance/pay-settings/{tec}", json={"pay_type": "hour"}, headers=admin)
    assert r.status_code == 200
    assert (await labor.costs_by_project(db, org, {obra.id}))[obra.id] == Decimal("90.00")
    # Una tarifa propia manda sobre la de planta.
    await app_client.put(f"{API}/jobcost/labor-rates/{tec}", json={"hourly_rate": "50"}, headers=admin)
    assert (await labor.costs_by_project(db, org, {obra.id}))[obra.id] == Decimal("100.00")
    # Por trabajo no suma por horas: su pago va por obra, y no se avisa como faltante.
    await app_client.put(f"{API}/attendance/pay-settings/{tec}", json={"pay_type": "job"}, headers=admin)
    assert await labor.costs_by_project(db, org, {obra.id}) == {}
    assert (await app_client.get(f"{API}/projects/{obra.id}/labor-hours", headers=admin)).json()["missing_rate"] == []
    # La tarifa de planta se puede cambiar.
    r = await app_client.put(f"{API}/jobcost/plant-rate", json={"hourly_rate": "47", "daily_hours": "8"}, headers=admin)
    assert r.json()["plant_daily_value"] == "376.00"


def test_plantillas_de_pedestal_con_las_cifras_del_cliente():
    from app.modules.warehouse.jobcost import DEFAULT_TEMPLATES

    linea = lambda nombre, cat: next(l for t in DEFAULT_TEMPLATES if t["name"] == nombre for l in t["lines"] if l["category"] == cat)  # noqa: E731
    assert linea("Pedestal (rebate) con personal propio", "labor")["value"] == "600"
    assert linea("Pedestal (rebate) con subcontratista", "contractor")["value"] == "1000"
