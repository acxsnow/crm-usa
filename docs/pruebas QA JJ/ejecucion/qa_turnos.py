"""Ataque a turnos, asistencia, horas extras, nómina y mapa (10 nov 2026).

Lo que puede pasar: marcas fuera de orden o desde el futuro, coordenadas
absurdas, alguien que aprueba sus propias horas o extras, novedades sobre el
turno de otro, períodos de nómina mal armados y el mapa visto por quien no debe.

PYTHONPATH=/app:/tmp python /tmp/qa_turnos.py → /tmp/qa_turnos.json
"""
from datetime import datetime, timedelta, timezone

from qa_comun import chk, cliente, e, esc, guardar, sql

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "carlos", "conta", "gerencia", "ajeno")}
admin, adm, v, tec, carlos, conta, ger, ajeno = (c[k] for k in ("admin", "adm", "vendedor", "tecnico", "carlos",
                                                                "conta", "gerencia", "ajeno"))
HOY = e.HOY
RUN = e.RUN


def evento(cli, tipo, **kw):
    return cli.post("/attendance/events", json={"event_type": tipo, **kw})


# ===========================================================================
esc("TUR-A1 Marcas")
# ===========================================================================
# Deja a Carlos sin turno abierto para empezar de cero.
evento(carlos, "clock_out", note="QA cierre previo", location_status="no_signal")
r = evento(carlos, "clock_out", note="QA salida sin entrada", location_status="no_signal")
chk("Salir sin haber entrado se rechaza", r.status_code in (400, 409), r.status_code)
r = evento(carlos, "pause_start")
chk("Pausa sin turno abierto se rechaza", r.status_code in (400, 409), r.status_code)
r = evento(carlos, "teletransporte")
chk("Tipo de marca inventado se rechaza", r.status_code in (400, 422), r.status_code)
r = evento(carlos, "clock_in", latitude=999, longitude=-999, location_status="ok")
lat = sql(f"select latitude from attendance_events where user_id = '{carlos.me['id']}' "
          "order by received_at desc limit 1") if r.status_code == 201 else ""
chk(f"Coordenadas imposibles no se guardan como ubicación ({r.status_code}, latitud guardada «{lat}»)",
    r.status_code in (400, 422) or not lat or abs(float(lat)) <= 90, lat)
if r.status_code == 201:
    evento(carlos, "clock_out", location_status="no_signal", note="QA")
futuro = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
r = evento(carlos, "clock_in", device_at=futuro, location_status="no_signal")
if r.status_code == 201:
    hora = sql(f"select occurred_at from attendance_events where user_id = '{carlos.me['id']}' "
               "order by received_at desc limit 1")
    chk(f"Una marca con la hora del celular adelantada 3 días no queda en el futuro ({hora[:19]})",
        hora[:10] <= (HOY + timedelta(days=1)).isoformat(), hora)
    evento(carlos, "clock_out", location_status="no_signal", note="QA")
else:
    chk("Marca desde el futuro se rechaza", r.status_code in (400, 422), r.status_code)
r = carlos.post("/attendance/events/batch", json={"events": [{"event_type": "clock_in"}] * 101})
chk("Una cola de más de 100 marcas se rechaza", r.status_code in (400, 422), r.status_code)
r = evento(carlos, "clock_in", location_status="denied")
chk("Con el permiso de ubicación negado no inicia turno", r.status_code == 409, r.status_code)

# ===========================================================================
esc("TUR-A2 Nadie aprueba lo suyo")
# ===========================================================================
entradas = adm.get("/attendance/entries", params={"date_from": (HOY - timedelta(days=30)).isoformat(),
                                                  "date_to": HOY.isoformat(), "limit": 200}).json()
propia = next((x for x in entradas if x.get("user_id") == adm.me["id"] and x.get("status") == "closed"), None)
ajena = next((x for x in entradas if x.get("user_id") == carlos.me["id"] and x.get("status") == "closed"), None)
if propia:
    r = adm.post("/attendance/entries/approve", json={"entry_ids": [propia["id"]]})
    aprobadas = r.json().get("approved", []) if r.status_code == 200 else []
    chk("Administración no aprueba sus propias horas", r.status_code in (400, 403, 409) or propia["id"] not in aprobadas,
        f"{r.status_code} {r.text[:120]}")
if ajena:
    r = carlos.post("/attendance/entries/approve", json={"entry_ids": [ajena["id"]]})
    chk("El técnico no aprueba horas", r.status_code == 403, r.status_code)
    r = ajeno.post("/attendance/entries/approve", json={"entry_ids": [ajena["id"]]})
    aprobadas = r.json().get("approved", []) if r.status_code == 200 else []
    chk("Otra organización no aprueba nuestras horas", ajena["id"] not in aprobadas, f"{r.status_code} {r.text[:100]}")
    r = adm.post("/attendance/entries/approve", json={"entry_ids": [ajena["id"]], "approved_minutes": 5000})
    chk("Aprobar más de 24 h en un día se rechaza", r.status_code in (400, 422), r.status_code)
    r = tec.post("/attendance/novelties", json={"kind": "correction", "time_entry_id": ajena["id"],
                                                "description": "QA corregir el turno de otro"})
    chk("Una novedad sobre el turno de otra persona se rechaza", r.status_code in (400, 403, 404), r.status_code)

# ===========================================================================
esc("TUR-A3 Horas extras")
# ===========================================================================
for horas, nombre in (("0", "cero"), ("-2", "negativas"), ("30", "más de 24")):
    r = tec.post("/attendance/overtime", json={"work_date": HOY.isoformat(), "hours": horas})
    chk(f"Horas extras {nombre} se rechazan", r.status_code in (400, 422), r.status_code)
r = tec.post("/attendance/overtime", json={"work_date": (HOY + timedelta(days=5)).isoformat(), "hours": "2"})
chk("Horas extras de un día futuro se rechazan", r.status_code in (400, 422), r.status_code)
dec = e.expect("El técnico declara 2 h extras", tec.post("/attendance/overtime", json={
    "work_date": HOY.isoformat(), "hours": "2", "notes": f"QA {RUN}"}), 201) or {}
r = tec.post(f"/attendance/overtime/{dec.get('id')}/review", json={"approve": True, "value_amount": "999"})
chk("El técnico no aprueba sus extras", r.status_code == 403, r.status_code)
r = adm.post(f"/attendance/overtime/{dec.get('id')}/review", json={"approve": True, "value_amount": "-10"})
chk("Un valor negativo para las extras se rechaza", r.status_code in (400, 422), r.status_code)
r = ajeno.post(f"/attendance/overtime/{dec.get('id')}/review", json={"approve": True, "value_amount": "10"})
chk("Otra organización no revisa nuestras extras", r.status_code in (403, 404), r.status_code)
e.expect("El jefe las aprueba con su valor", adm.post(f"/attendance/overtime/{dec.get('id')}/review", json={
    "approve": True, "value_amount": "50"}), 200)
r = tec.delete(f"/attendance/overtime/{dec.get('id')}")
chk("Unas extras ya aprobadas no las borra el técnico", r.status_code in (400, 403, 409), r.status_code)

# ===========================================================================
esc("TUR-A4 Malla de turnos")
# ===========================================================================
dia = (HOY + timedelta(days=40)).isoformat()
r = adm.post("/attendance/shifts", json={"user_ids": [carlos.me["id"]], "date_from": dia,
                                         "date_to": (HOY + timedelta(days=30)).isoformat(),
                                         "start_time": "08:00", "end_time": "17:00"})
chk("Rango de fechas al revés se rechaza", r.status_code in (400, 422), r.status_code)
r = adm.post("/attendance/shifts", json={"user_ids": [carlos.me["id"]], "date_from": dia, "date_to": dia,
                                         "start_time": "25:00", "end_time": "17:00"})
chk("Hora 25:00 se rechaza", r.status_code in (400, 422), r.status_code)
r = adm.post("/attendance/shifts", json={"user_ids": [carlos.me["id"]], "date_from": dia,
                                         "date_to": (HOY + timedelta(days=2000)).isoformat(),
                                         "start_time": "08:00", "end_time": "17:00"})
chk("Programar años de una vez se rechaza", r.status_code in (400, 422), r.status_code)
r = adm.post("/attendance/shifts", json={"user_ids": [ajeno.me["id"]], "date_from": dia, "date_to": dia,
                                         "start_time": "08:00", "end_time": "17:00"})
chk("No se programa a alguien de otra organización", r.status_code in (400, 404), r.status_code)
r = adm.post("/attendance/shifts", json={"user_ids": [carlos.me["id"]], "date_from": dia, "date_to": dia,
                                         "start_time": "08:00", "end_time": "17:00", "break_minutes": 600})
chk("Una pausa de 10 h se rechaza", r.status_code in (400, 422), r.status_code)

# ===========================================================================
esc("TUR-A5 Nómina")
# ===========================================================================
r = conta.post("/attendance/payroll/periods", json={"start_date": HOY.isoformat(),
                                                    "end_date": (HOY - timedelta(days=10)).isoformat()})
chk("Período de nómina al revés se rechaza", r.status_code in (400, 422), r.status_code)
ini = (HOY - timedelta(days=400 + int(RUN[-3:]) % 200)).isoformat()
fin = (HOY - timedelta(days=386 + int(RUN[-3:]) % 200)).isoformat()
per = e.expect("Período de nómina de dos semanas", conta.post("/attendance/payroll/periods", json={
    "start_date": ini, "end_date": fin}), 201) or {}
r = conta.post("/attendance/payroll/periods", json={"start_date": ini, "end_date": fin})
chk("Un período que se cruza con otro se rechaza", r.status_code in (400, 409), r.status_code)
if per.get("id"):
    e.expect("Se cierra el período", conta.post(f"/attendance/payroll/periods/{per['id']}/close", json={}), 200)
    r = conta.post(f"/attendance/payroll/periods/{per['id']}/close", json={})
    chk("Cerrar dos veces se bloquea", r.status_code in (400, 409), r.status_code)
    r = conta.post(f"/attendance/payroll/periods/{per['id']}/reopen", json={})
    chk("Reabrir sin motivo se bloquea", r.status_code in (400, 422), r.status_code)
r = tec.get("/attendance/payroll/report", params={"date_from": ini, "date_to": fin})
chk("El técnico no ve la nómina", r.status_code == 403, r.status_code)
r = tec.put(f"/attendance/pay-settings/{tec.me['id']}", json={"pay_type": "hour"})
chk("El técnico no cambia su forma de pago", r.status_code == 403, r.status_code)
r = adm.put(f"/attendance/pay-settings/{adm.me['id']}", json={"pay_type": "day"})
chk("Nadie cambia su propia forma de pago", r.status_code in (400, 403, 409), r.status_code)
r = adm.put(f"/attendance/pay-settings/{carlos.me['id']}", json={"pay_type": "semanal"})
chk("Forma de pago inventada se rechaza", r.status_code in (400, 422), r.status_code)

# ===========================================================================
esc("TUR-A6 Mapa y ubicaciones")
# ===========================================================================
for quien, cli in (("vendedor", v), ("Gerencia", ger), ("Contabilidad", conta)):
    r = cli.get("/operations-map/people")
    chk(f"{quien} no ve dónde está el personal", r.status_code == 403, r.status_code)
gente_t = tec.get("/operations-map/people").json()
chk("El técnico solo se ve a sí mismo en el mapa", all(tec.me["id"] in str(x) for x in gente_t) and len(gente_t) <= 1,
    len(gente_t))
r = ajeno.get("/operations-map/people")
gente = r.json() if r.status_code == 200 else []
chk("Otra organización no ve a nuestra gente en su mapa",
    not any(tec.me["id"] in str(x) for x in (gente if isinstance(gente, list) else gente.get("people", []))), r.status_code)
r = ajeno.delete(f"/attendance/users/{tec.me['id']}/locations")
chk("Otra organización no borra nuestras ubicaciones", r.status_code in (403, 404), r.status_code)
r = adm.put("/attendance/settings", json={"location_retention_days": 0})
chk("Retención de ubicaciones en 0 días se rechaza", r.status_code in (400, 422), r.status_code)

guardar("/tmp/qa_turnos.json")
print("FIN")
