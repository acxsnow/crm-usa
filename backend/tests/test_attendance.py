"""Turnos y asistencia de punta a punta por la API: malla, ventana
obligatoria, entrada y salida, pausas, sin señal, duplicados, novedades,
correcciones auditadas, aprobación y cierre de período.

La organización está en Phoenix (UTC−7 todo el año) y el reloj se fija: el
lunes 26 oct 2026 el turno es de 7:00 a 15:30 locales (14:00 a 22:30 UTC).
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.modules.attendance.models import AttendanceEvent, TimeEntryCorrection
from app.modules.field_ops import clock
from tests.field_helpers import approved_case_with_project, headers_for

API = "/api/v1/attendance"
LUNES = date(2026, 10, 26)
INICIO = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)


class Reloj:
    def __init__(self):
        self.ahora = INICIO - timedelta(minutes=30)

    def __call__(self):
        return self.ahora

    def ir(self, **kw):
        self.ahora = INICIO + timedelta(**kw)


@pytest.fixture
def reloj(monkeypatch):
    r = Reloj()
    monkeypatch.setattr(clock, "_utcnow", r)
    return r


@pytest.fixture
async def phoenix(db, seeded_org):
    seeded_org["org"].timezone = "America/Phoenix"
    await db.commit()
    return seeded_org


@pytest.fixture
def login(app_client):
    cache: dict[str, dict] = {}

    async def _login(user) -> dict:
        if user.email not in cache:
            cache[user.email] = await headers_for(app_client, user.email)
        return cache[user.email]

    return _login


async def _malla(app_client, h, user, *, desde=LUNES, hasta=LUNES, inicio="07:00", fin="15:30", **extra):
    r = await app_client.post(f"{API}/shifts", json={
        "user_ids": [str(user.id)], "date_from": desde.isoformat(), "date_to": hasta.isoformat(),
        "start_time": inicio, "end_time": fin, "break_minutes": 30, **extra}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


async def _evento(app_client, h, tipo, **extra):
    return await app_client.post(f"{API}/events", json={"event_type": tipo, **extra}, headers=h)


GPS = {"latitude": 33.4484, "longitude": -112.0740, "accuracy_m": 12, "location_status": "ok"}


async def test_la_ventana_obligatoria_aparece_con_turno_pendiente_y_se_va_al_marcar(
        app_client, login, reloj, phoenix, active_admin_staff_user, active_technician_user):
    oficina, tec = await login(active_admin_staff_user), await login(active_technician_user)
    sin_turno = (await app_client.get(f"{API}/me", headers=tec)).json()
    assert sin_turno["must_clock_in"] is False and sin_turno["shift"] is None

    malla = await _malla(app_client, oficina, active_technician_user)
    assert len(malla["created"]) == 1 and malla["created"][0]["scheduled_minutes"] == 480

    yo = (await app_client.get(f"{API}/me", headers=tec)).json()
    assert yo["must_clock_in"] is True
    assert yo["shift"]["starts_at"].startswith("2026-10-26T14:00")
    assert yo["user"]["full_name"] == active_technician_user.full_name and yo["timezone"] == "America/Phoenix"

    reloj.ir(minutes=25)
    r = await _evento(app_client, tec, "clock_in", client_event_id="cin-00000001", **GPS)
    assert r.status_code == 201, r.text
    yo = (await app_client.get(f"{API}/me", headers=tec)).json()
    assert yo["must_clock_in"] is False and yo["entry"]["status"] == "open"
    assert yo["late_minutes"] == 25 and yo["shift_status"] == "in_progress"


async def test_jornada_completa_con_pausa_desplazamientos_y_resumen(
        app_client, login, reloj, db, phoenix, active_admin_staff_user, active_technician_user):
    oficina, tec = await login(active_admin_staff_user), await login(active_technician_user)
    _, obra = await approved_case_with_project(db, phoenix["org"].id, technician_id=active_technician_user.id)
    await _malla(app_client, oficina, active_technician_user)
    reloj.ir(minutes=0)
    assert (await _evento(app_client, tec, "clock_in", client_event_id="e-00000001", **GPS)).status_code == 201
    reloj.ir(minutes=10)
    assert (await _evento(app_client, tec, "en_route", client_event_id="e-00000002", project_id=str(obra.id),
                          **GPS)).status_code == 201
    reloj.ir(minutes=40)
    llegue = await _evento(app_client, tec, "arrived", client_event_id="e-00000003", project_id=str(obra.id),
                           latitude=33.4255, longitude=-111.9400, location_status="ok")
    assert llegue.status_code == 201
    ev = (await db.execute(select(AttendanceEvent).where(AttendanceEvent.client_event_id == "e-00000003"))
          ).scalar_one()
    assert ev.distance_source == "straight_line" and 12 < ev.distance_km < 15
    reloj.ir(hours=4)
    assert (await _evento(app_client, tec, "pause_start", client_event_id="e-00000004",
                          note="Almuerzo")).status_code == 201
    assert (await _evento(app_client, tec, "pause_start", client_event_id="e-00000005")).json()["code"] \
        == "already_paused"
    reloj.ir(hours=4, minutes=30)
    assert (await _evento(app_client, tec, "pause_end", client_event_id="e-00000006")).status_code == 201
    reloj.ir(hours=8, minutes=30)
    resumen = (await app_client.get(f"{API}/me/summary", headers=tec)).json()
    assert (resumen["elapsed_minutes"], resumen["pause_minutes"], resumen["effective_minutes"]) == (510, 30, 480)
    assert resumen["scheduled_minutes"] == 480 and resumen["difference_minutes"] == 0
    assert [p["id"] for p in resumen["projects"]] == [str(obra.id)]
    r = await _evento(app_client, tec, "clock_out", client_event_id="e-00000007", note="Todo bien", **GPS)
    assert r.status_code == 201 and r.json()["entry"]["status"] == "closed"
    assert (await _evento(app_client, tec, "pause_start", client_event_id="e-00000008")).json()["code"] \
        == "no_open_entry"


async def test_no_hay_dos_turnos_abiertos_y_el_reintento_no_duplica(
        app_client, login, reloj, db, phoenix, active_technician_user):
    tec = await login(active_technician_user)
    primero = await _evento(app_client, tec, "clock_in", client_event_id="dup-00000001")
    assert primero.status_code == 201
    otra_vez = await _evento(app_client, tec, "clock_in", client_event_id="dup-00000001")
    assert otra_vez.status_code == 201 and otra_vez.json()["duplicate"] is True
    assert otra_vez.json()["event_id"] == primero.json()["event_id"]
    segundo_tel = await _evento(app_client, tec, "clock_in", client_event_id="dup-00000002")
    assert (segundo_tel.status_code, segundo_tel.json()["code"]) == (409, "entry_already_open")
    eventos = (await db.execute(select(AttendanceEvent).where(AttendanceEvent.event_type == "clock_in"))).all()
    assert len(eventos) == 1


async def test_la_cola_sin_senal_guarda_hora_del_telefono_y_de_llegada(
        app_client, login, reloj, db, phoenix, active_technician_user):
    tec = await login(active_technician_user)
    reloj.ir(hours=3)
    cola = [
        {"event_type": "clock_in", "client_event_id": "off-00000001",
         "device_at": (INICIO + timedelta(minutes=2)).isoformat(), "location_status": "unavailable"},
        {"event_type": "connectivity_lost", "client_event_id": "off-00000002",
         "device_at": (INICIO + timedelta(minutes=30)).isoformat()},
        {"event_type": "connectivity_restored", "client_event_id": "off-00000003",
         "device_at": (INICIO + timedelta(hours=2, minutes=50)).isoformat()},
        # La hora del teléfono en el futuro no se cree: manda la del servidor.
        {"event_type": "tracking", "client_event_id": "off-00000004",
         "device_at": (INICIO + timedelta(hours=9)).isoformat()},
    ]
    r = await app_client.post(f"{API}/events/batch", json={"events": cola}, headers=tec)
    assert r.status_code == 200, r.text
    assert [x["status"] for x in r.json()["results"]] == ["ok", "ok", "ok", "ok"]
    yo = (await app_client.get(f"{API}/me", headers=tec)).json()
    # La entrada cuenta desde la hora del teléfono, y queda marcada sin señal.
    assert yo["entry"]["clock_in_at"].startswith("2026-10-26T14:02") and yo["entry"]["clock_in_offline"] is True
    ev = (await db.execute(select(AttendanceEvent).where(AttendanceEvent.client_event_id == "off-00000001"))
          ).scalar_one()
    assert ev.location_status == "unavailable" and ev.latitude is None
    assert ev.received_at.replace(tzinfo=timezone.utc) - ev.occurred_at.replace(tzinfo=timezone.utc) \
        > timedelta(hours=2)
    futuro = (await db.execute(select(AttendanceEvent).where(AttendanceEvent.client_event_id == "off-00000004"))
              ).scalar_one()
    assert futuro.offline is False
    # Reenviar la misma cola (la red se cayó antes de la respuesta) no duplica.
    r = await app_client.post(f"{API}/events/batch", json={"events": cola}, headers=tec)
    assert [x["status"] for x in r.json()["results"]] == ["duplicate"] * 4
    # Una desconexión no resta horas: las efectivas son las del reloj.
    assert yo["entry"]["effective_minutes"] == 178


async def test_ubicacion_invalida_se_rechaza_y_sin_permiso_no_se_inventa(
        app_client, login, reloj, db, phoenix, active_technician_user):
    tec = await login(active_technician_user)
    r = await _evento(app_client, tec, "clock_in", latitude=200, longitude=5, location_status="ok")
    assert (r.status_code, r.json()["code"]) == (400, "invalid_location")
    r = await _evento(app_client, tec, "clock_in", client_event_id="deny-0001", location_status="denied")
    assert r.status_code == 201
    ev = (await db.execute(select(AttendanceEvent))).scalar_one()
    assert ev.location_status == "denied" and ev.latitude is None and ev.longitude is None


async def test_turno_nocturno_y_malla_por_grupo_con_choques(
        app_client, login, reloj, phoenix, active_admin_staff_user, active_technician_user, active_salesperson_user):
    oficina = await login(active_admin_staff_user)
    r = await _malla(app_client, oficina, active_technician_user, inicio="22:00", fin="06:00")
    t = r["created"][0]
    assert t["starts_at"].startswith("2026-10-27T05:00") and t["ends_at"].startswith("2026-10-27T13:00")
    grupo = await app_client.post(f"{API}/shifts", json={
        "user_ids": [str(active_technician_user.id), str(active_salesperson_user.id)],
        "date_from": "2026-10-26", "date_to": "2026-11-01", "weekdays": [0, 1, 2, 3, 4],
        "start_time": "07:00", "end_time": "15:30", "break_minutes": 30}, headers=oficina)
    assert grupo.status_code == 201
    # 5 días × 2 personas. El nocturno del lunes (22:00 a 6:00) no choca con
    # el diurno del lunes ni con el del martes, que empieza a las 7:00.
    assert len(grupo.json()["created"]) == 10 and grupo.json()["skipped"] == []
    otra = await app_client.post(f"{API}/shifts", json={
        "user_ids": [str(active_technician_user.id)], "date_from": "2026-10-26", "date_to": "2026-10-26",
        "start_time": "08:00", "end_time": "12:00"}, headers=oficina)
    assert len(otra.json()["skipped"]) == 1
    copia = await app_client.post(f"{API}/shifts/copy-week", json={
        "source_monday": "2026-10-26", "target_monday": "2026-11-02"}, headers=oficina)
    assert copia.status_code == 201 and copia.json()["created"] == 11
    lista = await app_client.get(f"{API}/shifts", params={"date_from": "2026-11-02", "date_to": "2026-11-08"},
                                 headers=oficina)
    assert len(lista.json()) == 11
    mal = await app_client.post(f"{API}/shifts", json={
        "user_ids": [str(active_technician_user.id)], "date_from": "2026-10-26", "date_to": "2027-03-01",
        "start_time": "07:00", "end_time": "15:00"}, headers=oficina)
    assert (mal.status_code, mal.json()["code"]) == (400, "invalid_range")


async def test_novedad_de_salida_olvidada_se_aprueba_con_correccion_auditada(
        app_client, login, reloj, db, phoenix, active_admin_staff_user, active_technician_user):
    oficina, tec = await login(active_admin_staff_user), await login(active_technician_user)
    await _malla(app_client, oficina, active_technician_user)
    reloj.ir(minutes=0)
    await _evento(app_client, tec, "clock_in", client_event_id="nov-00000001")
    reloj.ir(hours=12)
    tablero = (await app_client.get(f"{API}/live", headers=oficina)).json()
    assert tablero[0]["shift_status"] == "incomplete" and tablero[0]["verified"] is False
    entry_id = (await app_client.get(f"{API}/me", headers=tec)).json()["entry"]["id"]
    motivos = (await app_client.get(f"{API}/novelty-reasons", headers=tec)).json()
    olvido = next(m for m in motivos if m["code"] == "forgot")
    n = await app_client.post(f"{API}/novelties", json={
        "kind": "missed_clock_out", "reason_id": olvido["id"], "time_entry_id": entry_id,
        "requested_clock_out_at": (INICIO + timedelta(hours=8, minutes=30)).isoformat(),
        "description": "Se me descargó el celular"}, headers=tec)
    assert n.status_code == 201, n.text
    # El técnico no aprueba lo suyo (no tiene el permiso) y la oficina sí.
    assert (await app_client.post(f"{API}/novelties/{n.json()['id']}/approve", json={},
                                  headers=tec)).status_code == 403
    ok = await app_client.post(f"{API}/novelties/{n.json()['id']}/approve", json={"note": "Confirmado"},
                               headers=oficina)
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    detalle = (await app_client.get(f"{API}/entries/{entry_id}", headers=oficina)).json()
    assert detalle["status"] == "closed" and detalle["closed_by"] == "admin"
    assert detalle["effective_minutes"] == 510
    corr = (await db.execute(select(TimeEntryCorrection))).scalar_one()
    assert corr.before_data["clock_out_at"] is None and corr.after_data["clock_out_at"].startswith("2026-10-26T22:30")
    assert corr.reason.startswith("Novedad aprobada")
    rechazo_sin_nota = await app_client.post(f"{API}/novelties/{n.json()['id']}/reject", json={}, headers=oficina)
    assert rechazo_sin_nota.json()["code"] == "novelty_reviewed"


async def test_nadie_aprueba_ni_corrige_lo_propio(app_client, login, reloj, phoenix, active_admin_user):
    jefe = await login(active_admin_user)
    await _evento(app_client, jefe, "clock_in", client_event_id="self-0000001")
    reloj.ir(hours=8)
    r = await _evento(app_client, jefe, "clock_out", client_event_id="self-0000002")
    eid = r.json()["entry"]["id"]
    a = await app_client.post(f"{API}/entries/approve", json={"entry_ids": [eid]}, headers=jefe)
    assert a.json()["approved"] == [] and a.json()["errors"][0]["code"] == "self_review"
    c = await app_client.post(f"{API}/entries/{eid}/correct", json={
        "clock_in_at": (INICIO - timedelta(hours=2)).isoformat(), "reason": "más horas"}, headers=jefe)
    assert (c.status_code, c.json()["code"]) == (403, "self_review")


async def test_aprobar_cerrar_periodo_bloquea_y_reabrir_exige_motivo(
        app_client, login, reloj, phoenix, active_admin_staff_user, active_accounting_user, active_technician_user):
    oficina, conta, tec = (await login(active_admin_staff_user), await login(active_accounting_user),
                           await login(active_technician_user))
    await _malla(app_client, oficina, active_technician_user)
    reloj.ir(minutes=0)
    await _evento(app_client, tec, "clock_in", client_event_id="per-00000001")
    reloj.ir(hours=8, minutes=30)
    eid = (await _evento(app_client, tec, "clock_out", client_event_id="per-00000002")).json()["entry"]["id"]
    a = await app_client.post(f"{API}/entries/approve", json={"entry_ids": [eid]}, headers=oficina)
    assert a.json()["approved"] == [eid]

    reporte = (await app_client.get(f"{API}/payroll/report", params={"date_from": "2026-10-26",
                                                                     "date_to": "2026-11-01"}, headers=conta)).json()
    fila = next(f for f in reporte["rows"] if f["user_id"] == str(active_technician_user.id))
    assert (fila["scheduled_minutes"], fila["recorded_minutes"], fila["approved_minutes"]) == (480, 510, 510)
    assert fila["daily_overtime_minutes"] == 30 and fila["late_arrivals"] == 0

    p = await app_client.post(f"{API}/payroll/periods", json={"start_date": "2026-10-26", "end_date": "2026-11-01"},
                              headers=conta)
    assert p.status_code == 201
    # Administración no cierra períodos; Contabilidad sí.
    assert (await app_client.post(f"{API}/payroll/periods/{p.json()['id']}/close", json={},
                                  headers=oficina)).status_code == 403
    assert (await app_client.post(f"{API}/payroll/periods/{p.json()['id']}/close", json={},
                                  headers=conta)).json()["status"] == "closed"
    bloqueo = await app_client.post(f"{API}/entries/{eid}/unapprove", json={"reason": "revisar"}, headers=oficina)
    assert (bloqueo.status_code, bloqueo.json()["code"]) == (409, "period_closed")
    nuevo_turno = await app_client.post(f"{API}/shifts", json={
        "user_ids": [str(active_technician_user.id)], "date_from": "2026-10-28", "date_to": "2026-10-28",
        "start_time": "07:00", "end_time": "15:00"}, headers=oficina)
    assert nuevo_turno.json()["code"] == "period_closed"
    sin_motivo = await app_client.post(f"{API}/payroll/periods/{p.json()['id']}/reopen", json={}, headers=conta)
    assert sin_motivo.json()["code"] == "reason_required"
    reab = await app_client.post(f"{API}/payroll/periods/{p.json()['id']}/reopen",
                                 json={"reason": "Faltó una novedad"}, headers=conta)
    assert reab.json()["status"] == "open"
    hist = (await app_client.get(f"{API}/payroll/periods", headers=conta)).json()[0]["history"]
    assert [h["action"] for h in hist] == ["created", "closed", "reopened"]
    assert hist[-1]["reason"] == "Faltó una novedad"

    xlsx = await app_client.get(f"{API}/payroll/report.xlsx", params={"date_from": "2026-10-26",
                                                                      "date_to": "2026-11-01"}, headers=conta)
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    pdf = await app_client.get(f"{API}/payroll/report.pdf", params={"date_from": "2026-10-26",
                                                                    "date_to": "2026-11-01"}, headers=conta)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


async def test_el_panel_separa_turno_ubicacion_y_verificado(
        app_client, login, reloj, phoenix, active_admin_staff_user, active_technician_user, active_salesperson_user):
    oficina, tec = await login(active_admin_staff_user), await login(active_technician_user)
    await _malla(app_client, oficina, active_technician_user)
    await _malla(app_client, oficina, active_salesperson_user)
    reloj.ir(minutes=20)
    await _evento(app_client, tec, "clock_in", client_event_id="pan-00000001", **GPS)
    reloj.ir(hours=1)
    panel = (await app_client.get(f"{API}/dashboard", params={"date_from": "2026-10-26", "date_to": "2026-10-26"},
                                  headers=oficina)).json()
    k = panel["kpis"]
    assert (k["scheduled_people"], k["started"], k["pending_clock_in"], k["late_arrivals"]) == (2, 1, 1, 1)
    assert k["scheduled_minutes"] == 960 and k["compliance_pct"] is None
    tablero = {f["user_id"]: f for f in (await app_client.get(f"{API}/live", headers=oficina)).json()}
    t = tablero[str(active_technician_user.id)]
    assert t["entry_status"] == "open" and t["location"]["age_minutes"] == 40 and t["location"]["fresh"] is False
    assert t["verified"] is False
    # Sin marcar, el vendedor está «pendiente», no «ausente», y sin ubicación.
    v = tablero[str(active_salesperson_user.id)]
    assert v["shift_status"] == "pending" and v["location"] is None


async def test_marcacion_obligatoria_bloquea_la_obra_solo_si_esta_encendida(
        app_client, login, reloj, db, phoenix, active_admin_user, active_admin_staff_user, active_technician_user):
    jefe, oficina, tec = (await login(active_admin_user), await login(active_admin_staff_user),
                          await login(active_technician_user))
    _, obra = await approved_case_with_project(db, phoenix["org"].id, technician_id=active_technician_user.id)
    await _malla(app_client, oficina, active_technician_user)
    reloj.ir(minutes=5)
    tarea = {"title": "Revisar ductos"}
    assert (await app_client.post(f"/api/v1/projects/{obra.id}/tasks", json=tarea, headers=tec)).status_code == 201
    r = await app_client.put(f"{API}/settings", json={"require_clock_in_for_field_work": True}, headers=jefe)
    assert r.status_code == 200 and r.json()["require_clock_in_for_field_work"] is True
    bloqueado = await app_client.post(f"/api/v1/projects/{obra.id}/tasks", json=tarea, headers=tec)
    assert (bloqueado.status_code, bloqueado.json()["code"]) == (403, "shift_not_started")
    await _evento(app_client, tec, "clock_in", client_event_id="blk-00000001")
    assert (await app_client.post(f"/api/v1/projects/{obra.id}/tasks", json=tarea, headers=tec)).status_code == 201


async def test_el_tablero_muestra_el_turno_abierto_si_hay_dos_en_el_dia(
        app_client, login, reloj, phoenix, active_admin_staff_user, active_technician_user):
    oficina, tec = await login(active_admin_staff_user), await login(active_technician_user)
    await _malla(app_client, oficina, active_technician_user, inicio="07:00", fin="11:00")
    await _malla(app_client, oficina, active_technician_user, inicio="13:00", fin="17:00")
    reloj.ir(minutes=0)
    await _evento(app_client, tec, "clock_in", client_event_id="dos-0000001")
    reloj.ir(hours=4)
    await _evento(app_client, tec, "clock_out", client_event_id="dos-0000002")
    reloj.ir(hours=6)
    await _evento(app_client, tec, "clock_in", client_event_id="dos-0000003", **GPS)
    fila = (await app_client.get(f"{API}/live", headers=oficina)).json()[0]
    assert fila["entry_status"] == "open" and fila["shift"]["starts_at"].startswith("2026-10-26T20:00")
    assert fila["location"]["age_minutes"] == 0
