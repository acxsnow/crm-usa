"""Lote 3, fase E: turnos, asistencia y mapa (TUR-001 a TUR-010) y tiempos de respuesta (PER-001).

PYTHONPATH=/app:/tmp python /tmp/lote3e.py → /tmp/lote3e.json
"""
import json
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from qa_comun import API, aprobar_rapido, chk, cliente, e, esc, guardar, limpiar, prep_p03, seguro, sql

for i in (5, 6, 7, 8, 9, 10):
    e.USERS[f"t{i:02d}"] = f"tecnico{i:02d}@demo-org.com"
c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia", "carlos")}
admin, adm, v, tec, conta, ger = c["admin"], c["adm"], c["vendedor"], c["tecnico"], c["conta"], c["gerencia"]
ZONA = ZoneInfo(tec.get("/attendance/me").json().get("timezone") or "America/Bogota")


def ahora():
    return datetime.now(ZONA)


def hhmm(dt):
    return dt.strftime("%H:%M")


def tur001():
    t = [cliente(f"t{i:02d}") for i in (5, 6, 7, 8, 9)]
    lunes = (ahora().date() + timedelta(days=7 - ahora().weekday()))
    r = e.expect("Turno 7:00–16:00 de lunes a viernes para 5 técnicos", adm.post("/attendance/shifts", json={
        "user_ids": [x.me["id"] for x in t], "date_from": lunes.isoformat(),
        "date_to": (lunes + timedelta(days=6)).isoformat(), "weekdays": [0, 1, 2, 3, 4],
        "start_time": "07:00", "end_time": "16:00", "break_minutes": 60, "notes": f"QA {e.RUN} TUR-001"}), 201) or {}
    creados = r.get("created")
    chk(f"Quedan 25 turnos en la malla ({creados})", (creados if isinstance(creados, int) else len(creados or [])) == 25,
        json.dumps(r)[:200])
    malla = adm.get("/attendance/shifts", params={"date_from": lunes.isoformat(),
                                                   "date_to": (lunes + timedelta(days=6)).isoformat(), "limit": 200}).json()
    filas = malla if isinstance(malla, list) else malla.get("items") or malla.get("rows") or []
    chk(f"La malla de la semana los muestra ({len(filas)})", len(filas) >= 25, len(filas))
    r = adm.post("/attendance/shifts", json={"user_ids": [t[0].me["id"]], "date_from": lunes.isoformat(),
                                             "date_to": lunes.isoformat(), "start_time": "15:00", "end_time": "18:00"})
    cuerpo = r.json() if r.content else {}
    rechazado = r.status_code in (400, 409, 422) or (r.status_code == 201 and not cuerpo.get("created")
                                                     and cuerpo.get("skipped"))
    chk("Un turno que se cruza con otro del mismo técnico se rechaza", rechazado, f"{r.status_code} {r.text[:200]}")


def tur003():
    """Turnos que empezaron hace 5, 10 y 15 minutos; los tres marcan ahora."""
    t = {m: cliente(n) for m, n in ((5, "t08"), (10, "t09"), (15, "t10"))}
    hoy = ahora().date().isoformat()
    for minutos, cli in t.items():
        ini = ahora() - timedelta(minutes=minutos)
        r = adm.post("/attendance/shifts", json={"user_ids": [cli.me["id"]], "date_from": hoy, "date_to": hoy,
                                                 "start_time": hhmm(ini), "end_time": hhmm(ini + timedelta(hours=4)),
                                                 "notes": f"QA {e.RUN} TUR-003"})
        chk(f"Turno que empezó hace {minutos} min", r.status_code == 201, r.text[:150])
        r = cli.post("/attendance/events", json={"event_type": "clock_in", "latitude": 33.45, "longitude": -112.07,
                                                 "accuracy_m": 10, "location_status": "ok"})
        chk(f"Marca entrada (hace {minutos} min)", r.status_code == 201, f"{r.status_code} {r.text[:150]}")
    panel = adm.get("/attendance/dashboard", params={"date_from": hoy, "date_to": hoy}).json()
    personas = {p.get("user_id"): p for p in (panel.get("people") or panel.get("rows") or [])}
    estados = {m: (personas.get(cli.me["id"]) or {}).get("statuses") for m, cli in t.items()}
    chk("A 5 y 10 min: a tiempo; a 15 min: tarde (tolerancia de 10 min)",
        "late" not in (estados[5] or []) and "late" not in (estados[10] or []) and "late" in (estados[15] or []),
        estados)
    for cli in t.values():
        cli.post("/attendance/events", json={"event_type": "clock_out", "note": "QA TUR-003"})


def tur004():
    t = cliente("t07")
    hoy = ahora().date().isoformat()
    ini = ahora() - timedelta(hours=3)
    adm.post("/attendance/shifts", json={"user_ids": [t.me["id"]], "date_from": hoy, "date_to": hoy,
                                         "start_time": hhmm(ini), "end_time": hhmm(ini + timedelta(hours=2)),
                                         "notes": f"QA {e.RUN} TUR-004"})
    panel = adm.get("/attendance/dashboard", params={"date_from": hoy, "date_to": hoy}).json()
    p = next((x for x in (panel.get("people") or panel.get("rows") or []) if x.get("user_id") == t.me["id"]), {})
    chk("Sin marcar y con el turno vencido aparece como ausente", "missed" in (p.get("statuses") or []), p.get("statuses"))
    razones = adm.get("/attendance/novelty-reasons").json()
    razon = next((r for r in razones if "médica" in (r.get("label") or r.get("name") or "").lower()), None)
    if razon is None:
        razon = adm.post("/attendance/novelty-reasons", json={"label": "Cita médica", "name": "Cita médica"}).json()
    turno = next((x for x in t.get("/attendance/me/shifts", params={"date_from": hoy, "date_to": hoy}).json()
                  if isinstance(x, dict)), {})
    n = t.post("/attendance/novelties", json={"kind": "absence", "reason_id": razon.get("id"), "work_date": hoy,
                                              "shift_id": turno.get("id"),
                                              "description": "Cita médica, 3 horas"})
    chk("Registrar la novedad «Cita médica» (3 horas)", n.status_code == 201, f"{n.status_code} {n.text[:200]}")
    if n.status_code == 201:
        e.expect("Administración aprueba la novedad", adm.post(f"/attendance/novelties/{n.json()['id']}/approve",
                                                              json={"note": "QA"}), 200)
    panel = adm.get("/attendance/dashboard", params={"date_from": hoy, "date_to": hoy}).json()
    p = next((x for x in (panel.get("people") or panel.get("rows") or []) if x.get("user_id") == t.me["id"]), {})
    nov = [x for x in adm.get("/attendance/novelties", params={"limit": 50}).json()
           if x.get("user_id") == t.me["id"]]
    chk("Queda justificado con el motivo", nov and nov[0].get("status") == "approved"
        and "médica" in json.dumps(nov[0], ensure_ascii=False).lower(), f"{p.get('statuses')} {str(nov[:1])[:200]}")


def tur005():
    ajustes = adm.get("/attendance/settings").json()
    chk(f"Reglas de nómina: pausas pagadas={ajustes.get('paid_pauses')} (para toda la organización), extras desde "
        f"{ajustes.get('daily_overtime_after_minutes')} min al día y {ajustes.get('weekly_overtime_after_minutes')} a la "
        f"semana", True, json.dumps(ajustes)[:300])
    perfil = admin.get(f"/users/{tec.me['id']}/profile").json()
    clave = [k for k in json.dumps(perfil).lower().split('"') if any(p in k for p in ("pay_", "paid_by", "per_job",
                                                                                      "hourly", "por_trabajo"))]
    chk("Se puede decir si a un técnico se le paga por hora/día o por trabajo (decisión de Don Aldo)", bool(clave),
        f"campos del perfil: {sorted(perfil)[:20]}")
    hoy = ahora().date().isoformat()
    rep = conta.get("/attendance/payroll/report", params={"date_from": hoy, "date_to": hoy}).json()
    texto = json.dumps(rep)[:400]
    chk("Las extras se declaran en horas y el jefe pone el valor", any(k in texto for k in ("overtime_value",
                                                                                           "declared_overtime")),
        texto)


def tur008():
    cli = cliente("t06")
    for evento in ("clock_in", "clock_out"):
        cli.post("/attendance/events", json={"event_type": evento, "latitude": 33.45, "longitude": -112.07,
                                             "accuracy_m": 10, "location_status": "ok"})
    ids = sql(f"select id from attendance_events where user_id = '{cli.me['id']}' and latitude is not null "
              f"order by occurred_at limit 2").split("\n")
    chk("Hay dos puntos con ubicación", len(ids) == 2 and all(ids), ids)
    sql(f"update attendance_events set occurred_at = now() - interval '91 days' where id = '{ids[0]}'")
    sql(f"update attendance_events set occurred_at = now() - interval '89 days' where id = '{ids[1]}'")
    salida = e.worker("from app.modules.attendance import mapdata\nprint(await mapdata.purge_old_locations(db))")
    chk(f"La limpieza corre ({(salida.splitlines() or ['?'])[-1]})", "Traceback" not in salida, salida[-200:])
    viejo = sql(f"select latitude is null from attendance_events where id = '{ids[0]}'")
    nuevo = sql(f"select latitude is null from attendance_events where id = '{ids[1]}'")
    chk("El punto de 91 días pierde la ubicación", viejo == "True", viejo)
    chk("El de 89 días la conserva", nuevo == "False", nuevo)
    r = admin.delete(f"/attendance/users/{cli.me['id']}/locations")
    chk("Borrado manual de las ubicaciones del usuario", r.status_code in (200, 204), f"{r.status_code} {r.text[:120]}")
    quedan = sql(f"select count(*) from attendance_events where user_id = '{cli.me['id']}' and latitude is not null")
    chk("No le queda ninguna ubicación", quedan == "0", quedan)
    r = c["carlos"].delete(f"/attendance/users/{cli.me['id']}/locations")
    chk("Un técnico no borra ubicaciones de otro (403)", r.status_code == 403, r.status_code)


def tur009():
    filas = adm.get("/technician-monitor").json()
    chk(f"El monitor trae a los técnicos ({len(filas)})", len(filas) >= 15, len(filas))
    malas = []
    for f in filas:
        asignados = sql(f"select count(*) from projects where primary_technician_user_id = '{f['user_id']}' "
                        f"and status in ('planning', 'scheduled', 'in_progress')")
        if str(f["casos_asignados"]) != asignados:
            malas.append(f"{f['full_name']}: monitor {f['casos_asignados']} vs base {asignados}")
    chk("Los casos asignados coinciden con las obras abiertas de cada uno", not malas, "; ".join(malas)[:400])
    r = c["carlos"].get("/technician-monitor")
    chk("Carlos (técnico) no abre el monitor", r.status_code == 403, r.status_code)


def tur010():
    carlos = c["carlos"]
    hoy = ahora().date().isoformat()
    rutas = ["/attendance/dashboard", "/attendance/live", "/operations-map/people", "/operations-map/projects",
             "/attendance/payroll/report", "/attendance/entries", "/attendance/people"]
    codigos = {p: carlos.get(p, params={"date_from": hoy, "date_to": hoy}).status_code for p in rutas}
    chk("Asistencia, mapa y nómina de otros → 403 para Carlos", set(codigos.values()) == {403}, codigos)
    chk("Su propio turno sí lo ve", carlos.get("/attendance/me").status_code == 200, "")


def tur007():
    _, pid = aprobar_rapido(v, adm, admin, 371, "AZ", "AZ_EFFICIENCY")
    mapa = adm.get("/operations-map/projects").json()
    sin = {p.get("id") or p.get("project_id") for p in mapa.get("unlocated", [])}
    chk("La obra con dirección inventada aparece «sin ubicar»", pid in sin, len(sin))
    r = adm.post("/operations-map/projects/geocode")
    chk(f"Ubicar las obras sin coordenadas ({r.status_code})", r.status_code in (200, 201, 202), r.text[:250])
    cuerpo = r.json() if r.status_code in (200, 201, 202) else {}
    intentadas = cuerpo.get("attempted") or cuerpo.get("tried") or cuerpo.get("processed")
    chk(f"Máximo 25 por intento (anotar: {intentadas})", intentadas is None or int(intentadas) <= 25, json.dumps(cuerpo)[:200])
    mapa = adm.get("/operations-map/projects").json()
    chk("La inventada sigue avisando que no tiene coordenadas",
        pid in {p.get("id") or p.get("project_id") for p in mapa.get("unlocated", [])}, "")
    r = adm.put(f"/operations-map/projects/{pid}/location", json={"latitude": 33.4484, "longitude": -112.074})
    chk("Se puede ubicar a mano", r.status_code == 200, f"{r.status_code} {r.text[:120]}")


def per001():
    hoy = e.HOY.isoformat()
    rutas = [("Inicio", "/auth/me", {}), ("Expedientes", "/case-board", {}), ("Por revisar", "/documents/review-queue", {}),
             ("Proyectos", "/projects", {}), ("Agenda", "/dispatch/agenda", {"date_from": hoy, "date_to": hoy}),
             ("Existencias", "/warehouse/stock", {}), ("Salidas", "/warehouse/releases", {}), ("Facturas", "/invoices", {}),
             ("Mapa", "/operations-map/projects", {}), ("Avisos", "/notifications", {}), ("Buscador", "/search", {"q": "QA"})]
    tiempos = {}
    for nombre, ruta, params in rutas:
        ms = []
        for _ in range(3):
            t0 = time.perf_counter()
            r = admin.get(ruta, params=params)
            ms.append((time.perf_counter() - t0) * 1000)
        tiempos[nombre] = (round(max(ms)), r.status_code)
    lentas = {k: v for k, v in tiempos.items() if v[0] >= 500 or v[1] != 200}
    chk("Cada llamada responde en menos de 500 ms (3 veces cada una, en local)", not lentas, json.dumps(tiempos))


esc("_prep")
prep_p03(admin, v)
seguro("TUR-001", tur001)
esc("TUR-002")
e.SECTION[0] = "TUR-002"
try:
    e.flujo_turnos({"adm": adm, "tecnico": tec, "admin": admin, "conta": conta, "gerencia": ger, "vendedor": v})
except Exception as ex:  # noqa: BLE001
    chk(f"El bloque terminó sin error inesperado ({type(ex).__name__})", False, repr(ex)[:300])
for r in e.RESULTS:
    if r["section"] == "TUR-002":
        paso = r["step"].lower()
        if any(p in paso for p in ("corregir", "corrección", "aprueba las horas", "quedan aprobadas", "nómina")):
            r["section"] = "TUR-006"
        elif any(p in paso for p in ("mapa", "orden sugerido")):
            r["section"] = "TUR-007"
        elif any(p in paso for p in ("panel", "tablero", "contabilidad no ve")):
            r["section"] = "TUR-009"
seguro("TUR-003", tur003)
seguro("TUR-004", tur004)
seguro("TUR-005", tur005)
seguro("TUR-007", tur007)
seguro("TUR-008", tur008)
seguro("TUR-009", tur009)
seguro("TUR-010", tur010)
seguro("PER-001", per001)
limpiar()
guardar("/tmp/lote3e.json")
print("ok")
