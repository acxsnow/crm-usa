"""Lote 3, fase E2: reejecución de TUR-007, TUR-008 y TUR-010 con lo que el
script de la fase E hizo mal (la obra «inventada» tenía el GPS de la visita, la
geocodificación pide cuerpo, la limpieza se corre con el worker de verdad, y el
mapa del técnico se revisa por lo que devuelve y no solo por el código).

PYTHONPATH=/app:/tmp python /tmp/lote3e2.py → /tmp/lote3e2.json
"""
import subprocess

from qa_comun import aprobar_rapido, chk, cliente, e, guardar, limpiar, seguro, sql

e.USERS["t06"] = "tecnico06@demo-org.com"
c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "carlos")}
admin, adm, v = c["admin"], c["adm"], c["vendedor"]


def tur007():
    _, pid = aprobar_rapido(v, adm, admin, 372, "AZ", "AZ_EFFICIENCY")
    sql(f"update projects set latitude = null, longitude = null where id = '{pid}'")
    mapa = adm.get("/operations-map/projects").json()
    sin = {p.get("id") or p.get("project_id") for p in mapa.get("unlocated", [])}
    chk("La obra sin coordenadas aparece «sin ubicar»", pid in sin, len(sin))
    r = adm.post("/operations-map/projects/geocode", json={"project_ids": [pid]})
    chk(f"«Ubicar por dirección» responde ({r.status_code})", r.status_code == 200, r.text[:250])
    mapa = adm.get("/operations-map/projects").json()
    chk("La dirección inventada sigue sin coordenadas y avisando", pid in {p.get("id") or p.get("project_id")
                                                                          for p in mapa.get("unlocated", [])}, r.text[:150])
    r = adm.post("/operations-map/projects/geocode", json={"project_ids": [pid] * 26})
    chk("Más de 25 obras por intento se rechaza (422)", r.status_code == 422, r.status_code)
    r = adm.put(f"/operations-map/projects/{pid}/location", json={"latitude": 33.4484, "longitude": -112.074})
    chk("Se ubica a mano", r.status_code == 200, f"{r.status_code} {r.text[:120]}")


def tur008():
    t = cliente("t06")
    for evento in ("clock_in", "clock_out"):
        t.post("/attendance/events", json={"event_type": evento, "latitude": 33.45, "longitude": -112.07,
                                           "accuracy_m": 10, "location_status": "ok"})
    ids = sql(f"select id from attendance_events where user_id = '{t.me['id']}' and latitude is not null "
              f"order by occurred_at desc limit 2").split("\n")
    chk("Hay dos puntos con ubicación", len(ids) == 2 and all(ids), ids)
    sql(f"update attendance_events set occurred_at = now() - interval '91 days' where id = '{ids[0]}'")
    sql(f"update attendance_events set occurred_at = now() - interval '89 days' where id = '{ids[1]}'")
    salida = subprocess.run(["python", "-c", "from app.workers.tasks import purge_old_locations_task as t; print(t())"],
                            capture_output=True, text=True, cwd="/app").stdout.strip()
    chk(f"La tarea de limpieza del worker corre ({salida})", salida.isdigit() and int(salida) >= 1, salida)
    chk("El punto de 91 días pierde la ubicación",
        sql(f"select latitude is null from attendance_events where id = '{ids[0]}'") == "True", "")
    chk("El de 89 días la conserva",
        sql(f"select latitude is null from attendance_events where id = '{ids[1]}'") == "False", "")


def tur010():
    carlos = c["carlos"]
    gente = carlos.get("/operations-map/people").json()
    chk("En el mapa de personas Carlos solo se ve a sí mismo", {g["user_id"] for g in gente} <= {carlos.me["id"]},
        [g.get("full_name") or g.get("user_id") for g in gente])
    obras = carlos.get("/operations-map/projects").json()
    todas = obras.get("projects", []) + obras.get("unlocated", [])
    ajenas = [p for p in todas if p.get("technician_user_id") not in (None, carlos.me["id"])
              and p.get("primary_technician_user_id") not in (None, carlos.me["id"])]
    chk(f"En el mapa de obras Carlos solo ve las suyas ({len(todas)})", not ajenas, len(ajenas))
    chk("El menú no le muestra «Mapa operativo» (exige locations.view o projects.read_all)",
        not ({"locations.view", "projects.read_all"} & set(carlos.me.get("permissions") or [])), "")


seguro("TUR-007", tur007)
seguro("TUR-008", tur008)
seguro("TUR-010", tur010)
limpiar()
guardar("/tmp/lote3e2.json")
print("ok")
