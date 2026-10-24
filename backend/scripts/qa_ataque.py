"""Ataque a lo integrado el 24 oct (bodega-cierre y rotación del técnico).

No confirma que funciona: intenta romperlo contra la app real (Postgres) y anota
cada hallazgo. Requiere `docker compose up`, los datos demo y los usuarios de
ataque (tecnico2@demo-org.com y la organización «Atacante SA»).

Uso:  cd backend && PYTHONPATH=. .venv/bin/python -m scripts.qa_ataque
"""
import io
import json
import sys
import threading
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import httpx

from scripts import qa_e2e as qa
from scripts.qa_e2e import API, HOY, RUN, Client, jpeg, png_signature

qa.USERS.update({"t2": "tecnico2@demo-org.com", "atk": "admin@atacante.com", "atk_tec": "tecnico@atacante.com"})

FINDINGS: list[dict] = []
OKS: list[str] = []


def hallazgo(sev: str, titulo: str, pasos: str, esperado: str, paso: str, donde: str = "") -> None:
    FINDINGS.append({"sev": sev, "titulo": titulo, "pasos": pasos, "esperado": esperado, "paso": paso,
                     "donde": donde})
    print(f"  ✗ [{sev}] {titulo} — {paso[:160]}")


def bien(texto: str) -> None:
    OKS.append(texto)
    print(f"  ✓ {texto}")


def esperar(nombre: str, r: httpx.Response, codigos: tuple, *, sev="alta", donde="", pasos="") -> bool:
    if r.status_code in codigos:
        bien(f"{nombre} → {r.status_code}")
        return True
    hallazgo(sev, nombre, pasos or nombre, f"HTTP {codigos}", f"HTTP {r.status_code}: {r.text[:200]}", donde)
    return False


def seccion(nombre: str) -> None:
    print(f"\n=== {nombre}")


# ---------------------------------------------------------------------------
# Escenario
# ---------------------------------------------------------------------------

_CLIENTE: list[str] = []


def obra(admin: Client, titulo: str) -> dict:
    if not _CLIENTE:
        _CLIENTE.append(admin.get("/customers", params={"page_size": 1}).json()[0]["id"])
    r = admin.post("/projects", json={"title": f"ATK {RUN} {titulo}", "customer_id": _CLIENTE[0],
                                      "address_street": "1 Attack Way",
                                      "address_city": "Phoenix", "address_state": "AZ", "address_zip": "85001"})
    assert r.status_code == 201, r.text
    return r.json()


def liberar(adm: Client, pid: str, tecnico_id: str, dia: date | None = None) -> httpx.Response:
    return adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": tecnico_id,
                                                        "scheduled_date": (dia or HOY).isoformat()})


def item(adm: Client, nombre: str, costo="10") -> dict:
    sku = f"ATK-{RUN}-{uuid.uuid4().hex[:6]}"
    r = adm.post("/warehouse/items", json={"name": f"ATK {RUN} {nombre}", "sku": sku, "category": "other",
                                           "unit": "unit", "unit_cost": costo})
    assert r.status_code == 201, r.text
    return r.json()


def entrada(adm: Client, item_id: str, cantidad="100") -> None:
    r = adm.post("/warehouse/movements", json={"item_id": item_id, "movement_type": "entrada", "quantity": cantidad})
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# 1. Rotación: el técnico anterior intenta cada escritura por la API
# ---------------------------------------------------------------------------

def ataque_rotacion(c: dict) -> dict:
    seccion("1. Rotación del técnico y solo lectura")
    admin, adm, t1, t2 = c["admin"], c["adm"], c["tecnico"], c["t2"]
    p = obra(admin, "rotacion")
    pid = p["id"]
    admin.post(f"/projects/{pid}/checklist/apply-template", json={})
    esperar("Administración libera la obra a T1", liberar(adm, pid, t1.me["id"]), (200,))
    # T1 deja cosas suyas mientras es el responsable.
    cosa = item(adm, "tubo rotación")
    entrada(adm, cosa["id"])
    borrador = t1.post("/warehouse/releases", json={"project_id": pid, "lines": [{"item_id": cosa["id"], "quantity": "2"}]})
    esperar("T1 arma un borrador de salida para su obra", borrador, (201,))
    entregada = t1.post("/warehouse/releases", json={"project_id": pid, "lines": [{"item_id": cosa["id"], "quantity": "1"}]}).json()
    t1.post(f"/warehouse/releases/{entregada['id']}/submit")
    admin.post(f"/warehouse/releases/{entregada['id']}/approve")
    adm.post(f"/warehouse/releases/{entregada['id']}/deliver", json={})
    jornada = t1.post(f"/warehouse/projects/{pid}/day-logs", json={"log_date": HOY.isoformat(), "hours": "4",
                                                                  "work_done": "T1 empezó"})
    esperar("T1 registra su jornada", jornada, (201,))
    tarea = t1.post(f"/projects/{pid}/tasks", json={"title": "Tarea de T1"})
    items = admin.get(f"/projects/{pid}/checklist", params={"page_size": 5}).json()

    esperar("Administración rota la obra a T2", liberar(adm, pid, t2.me["id"]), (200,))
    asig = admin.get(f"/projects/{pid}/assignments").json()
    if [a["current"] for a in asig] == [False, True]:
        bien("El historial queda con T1 cerrado y T2 actual")
    else:
        hallazgo("media", "Historial de responsables inesperado tras rotar", "rotar T1→T2",
                 "dos turnos, el último actual", json.dumps(asig)[:200], "field_ops/installation.py:_record_assignment")

    acceso = t1.get(f"/projects/{pid}").json()
    if acceso.get("my_access") == "read_only":
        bien("T1 ve la obra en solo lectura")
    else:
        hallazgo("alta", "El técnico anterior no queda en solo lectura", "GET /projects/{id} como T1",
                 "my_access=read_only", str(acceso.get("my_access")), "field_ops/access.py")

    nombre = "T1 (anterior) "
    intentos = [
        ("sube evidencia", lambda: t1.post(f"/projects/{pid}/evidence", data={"category": "general"},
                                          files={"file": ("f.jpg", jpeg("x"), "image/jpeg")})),
        ("firma como técnico", lambda: t1.post(f"/projects/{pid}/attestation/technician-sign",
                                                json={"signature_base64": png_signature()})),
        ("pide firma del cliente", lambda: t1.post(f"/projects/{pid}/attestation/customer-signature-request")),
        ("firma por el cliente", lambda: t1.post(f"/projects/{pid}/attestation/customer-sign",
                                                  json={"customer_name": "X", "signature_base64": png_signature()})),
        ("cambia condiciones", lambda: t1.patch(f"/projects/{pid}/conditions", json={"conditions": []})),
        ("registra equipo", lambda: t1.post(f"/projects/{pid}/equipment", json={
            "equipment_type": "condenser", "brand": "X", "model": "Y"})),
        ("confirma equipos", lambda: t1.post(f"/projects/{pid}/equipment/confirm")),
        ("cierra la instalación", lambda: t1.post(f"/projects/{pid}/installation/close", json={})),
        ("crea tarea", lambda: t1.post(f"/projects/{pid}/tasks", json={"title": "x"})),
        ("registra jornada", lambda: t1.post(f"/warehouse/projects/{pid}/day-logs", json={
            "log_date": (HOY - timedelta(days=1)).isoformat(), "hours": "1"})),
        ("corrige su jornada de antes", lambda: t1.put(
            f"/warehouse/projects/{pid}/day-logs/{jornada.json().get('id')}",
            json={"log_date": HOY.isoformat(), "hours": "9", "work_done": "T1 corrige después de rotar"})),
        ("anota cobro adicional", lambda: t1.post(f"/warehouse/projects/{pid}/extra-charges",
                                                  json={"description": "x", "amount": "5"})),
        ("pide salida nueva para la obra", lambda: t1.post("/warehouse/releases", json={
            "project_id": pid, "lines": [{"item_id": cosa["id"], "quantity": "1"}]})),
        ("corrige su borrador de la obra", lambda: t1.put(f"/warehouse/releases/{borrador.json().get('id')}", json={
            "project_id": pid, "lines": [{"item_id": cosa["id"], "quantity": "3"}]})),
        ("envía a autorizar su borrador de la obra", lambda: t1.post(
            f"/warehouse/releases/{borrador.json().get('id')}/submit")),
        ("registra gasto cargado a la obra", lambda: t1.post("/expenses", data={"data": json.dumps({
            "expense_date": HOY.isoformat(), "category": "fuel", "amount": "20", "description": "gasolina obra rotada",
            "payment_method": "own_money", "project_id": pid})},
            files={"receipt": ("r.jpg", jpeg("r"), "image/jpeg")})),
    ]
    if items:
        intentos.append(("marca línea del checklist", lambda: t1.patch(f"/checklist-items/{items[0]['id']}",
                                                                        json={"is_complete": True})))
    if tarea.status_code == 201:
        tid = tarea.json()["id"]
        intentos.append(("cambia su tarea", lambda: t1.patch(f"/tasks/{tid}", json={"title": "cambiada"})))
        intentos.append(("comenta su tarea", lambda: t1.post(f"/tasks/{tid}/comments", json={"body": "hola"})))
    linea_entregada = (entregada.get("lines") or [{}])[0].get("id")
    intentos.append(("marca «lo llevo» en la salida entregada de la obra", lambda: t1.post(
        f"/warehouse/releases/{entregada['id']}/lines/{linea_entregada}/load", json={"loaded": True})))

    for texto, accion in intentos:
        r = accion()
        if r.status_code in (403, 404):
            bien(f"{nombre}{texto} → {r.status_code}")
        else:
            sev = "alta" if r.status_code < 300 else "media"
            hallazgo(sev, f"El técnico anterior {texto} en la obra rotada",
                     f"Obra liberada a T1, T1 trabaja, se rota a T2; T1 por la API: {texto}",
                     "403 project_read_only", f"HTTP {r.status_code}: {r.text[:180]}")
    return {"pid": pid, "item": cosa, "jornada_t1": jornada.json(), "entregada": entregada}


# ---------------------------------------------------------------------------
# 2. Rotación: casos límite
# ---------------------------------------------------------------------------

def ataque_rotacion_limites(c: dict, ctx: dict) -> None:
    seccion("2. Rotación: casos límite")
    admin, adm, t1, t2, atk_tec = c["admin"], c["adm"], c["tecnico"], c["t2"], c["atk_tec"]
    p = obra(admin, "limites")
    pid = p["id"]
    liberar(adm, pid, t1.me["id"])
    # Rotar al mismo técnico no debe abrir otro turno.
    liberar(adm, pid, t1.me["id"], HOY + timedelta(days=1))
    asig = admin.get(f"/projects/{pid}/assignments").json()
    if len(asig) == 1:
        bien("Rotar al mismo técnico no abre otro turno")
    else:
        hallazgo("media", "Rotar al mismo técnico abre turnos duplicados", "liberar dos veces a T1",
                 "un solo turno", json.dumps(asig)[:200], "field_ops/installation.py:_record_assignment")
    # A → B → A
    liberar(adm, pid, t2.me["id"])
    liberar(adm, pid, t1.me["id"])
    asig = admin.get(f"/projects/{pid}/assignments").json()
    actuales = [a for a in asig if a["current"]]
    if len(actuales) == 1 and actuales[0]["technician_user_id"] == t1.me["id"] and len(asig) == 3:
        bien("A→B→A deja tres turnos y A actual")
    else:
        hallazgo("media", "Historial raro al rotar A→B→A", "liberar T1, T2, T1", "3 turnos y T1 actual",
                 json.dumps(asig)[:300], "field_ops/installation.py:_record_assignment")
    if t2.get(f"/projects/{pid}").json().get("my_access") == "read_only":
        bien("Tras A→B→A, B queda en solo lectura")
    # Fecha pasada
    esperar("Rotar con fecha pasada se rechaza", liberar(adm, pid, t2.me["id"], HOY - timedelta(days=3)),
            (400, 422), sev="media")
    # Fecha futura: ¿el actual pierde la obra hoy?
    p2 = obra(admin, "futura")
    liberar(adm, p2["id"], t1.me["id"])
    liberar(adm, p2["id"], t2.me["id"], HOY + timedelta(days=10))
    asig = admin.get(f"/projects/{p2['id']}/assignments").json()
    acceso_t1 = t1.get(f"/projects/{p2['id']}").json().get("my_access")
    t1_cierra = next((a["ended_on"] for a in asig if a["technician_user_id"] == t1.me["id"]), None)
    if acceso_t1 == "read_only" and t1_cierra and t1_cierra > HOY.isoformat():
        hallazgo("media", "Rotar con fecha futura quita la obra hoy, pero el historial dice que T1 sigue",
                 "Obra con T1; liberar a T2 para dentro de 10 días; T1 abre la obra hoy",
                 "T1 sigue llenando hasta el día del cambio, o el historial cierra su turno hoy",
                 f"T1 ve solo lectura desde ya y su turno figura hasta {t1_cierra}",
                 "field_ops/installation.py:schedule_installation y _record_assignment")
    else:
        bien(f"Fecha futura: acceso T1={acceso_t1}, fin de turno={t1_cierra}")
    # Técnico de otra organización
    esperar("Liberar a un técnico de otra organización se rechaza",
            liberar(adm, pid, atk_tec.me["id"]), (400, 404, 422))
    # Usuario que no es técnico
    esperar("Liberar a un vendedor como técnico se rechaza", liberar(adm, pid, c["vendedor"].me["id"]),
            (400, 422), sev="media")
    # Crear la obra ya con técnico (sin «Orden liberada»)
    r = admin.post("/projects", json={"title": f"ATK {RUN} con técnico", "customer_id": _CLIENTE[0],
                                      "primary_technician_user_id": atk_tec.me["id"],
                                      "address_street": "1 Attack Way", "address_city": "Phoenix",
                                      "address_state": "AZ", "address_zip": "85001"})
    if r.status_code == 201:
        hallazgo("media", "Crear una obra acepta como técnico a un usuario de otra organización",
                 "POST /projects con primary_technician_user_id de «Atacante SA»", "400 técnico inválido",
                 f"201; técnico guardado {r.json().get('primary_technician_user_id')}",
                 "field_ops/service.py:create_project (ProjectCreate.primary_technician_user_id)")
    r = admin.post("/projects", json={"title": f"ATK {RUN} directo", "customer_id": _CLIENTE[0],
                                      "primary_technician_user_id": t1.me["id"], "address_street": "1 Attack Way",
                                      "address_city": "Phoenix", "address_state": "AZ", "address_zip": "85001"})
    if r.status_code == 201:
        p3 = r.json()["id"]
        liberar(adm, p3, t2.me["id"])
        historial = admin.get(f"/projects/{p3}/assignments").json()
        ve = t1.get(f"/projects/{p3}")
        if ve.status_code == 404:
            hallazgo("media", "Si la obra nació con técnico, al rotarla el anterior la pierde del todo",
                     "POST /projects con primary_technician_user_id=T1; liberar a T2; T1 abre la obra",
                     "T1 la ve en solo lectura (como en cualquier rotación)",
                     f"404; historial: {[a['technician_name'] for a in historial]}",
                     "field_ops/service.py:create_project no registra el turno inicial")
    # Jornada a nombre de otro / ayudantes
    p4 = obra(admin, "ayudantes")
    liberar(adm, p4["id"], t2.me["id"])
    r = t2.post(f"/warehouse/projects/{p4['id']}/day-logs", json={"log_date": HOY.isoformat(),
                                                                  "technician_user_id": t1.me["id"], "hours": "2"})
    esperar("El técnico no registra la jornada a nombre de otro", r, (403,))
    r = t2.post(f"/warehouse/projects/{p4['id']}/day-logs", json={"log_date": HOY.isoformat(), "hours": "8",
                                                                  "helper_user_ids": [atk_tec.me["id"]]})
    esperar("Un ayudante de otra organización se rechaza", r, (400, 404, 422))
    r = t2.post(f"/warehouse/projects/{p4['id']}/day-logs", json={"log_date": HOY.isoformat(), "hours": "8",
                                                                  "helper_user_ids": [c["vendedor"].me["id"]]})
    if r.status_code == 201:
        hallazgo("baja", "Se puede poner de ayudante a alguien que no es técnico (vendedor, contador)",
                 "jornada con helper_user_ids=[vendedor]", "solo técnicos instaladores como ayudantes",
                 "201", "warehouse/day_logs.py:_check_active_user")
        log = r.json()
        r = t2.put(f"/warehouse/projects/{p4['id']}/day-logs/{log['id']}", json={
            "log_date": HOY.isoformat(), "hours": "8", "helper_user_ids": [t1.me["id"]]})
    else:
        r = t2.post(f"/warehouse/projects/{p4['id']}/day-logs", json={"log_date": HOY.isoformat(), "hours": "8",
                                                                      "helper_user_ids": [t1.me["id"]]})
    log = r.json()
    if t1.get(f"/projects/{p4['id']}").status_code == 200:
        bien("El ayudante ve la obra")
    esperar("El ayudante no llena la obra (evidencia)", t1.post(f"/projects/{p4['id']}/evidence",
            data={"category": "general"}, files={"file": ("f.jpg", jpeg("x"), "image/jpeg")}), (403,))
    t2.put(f"/warehouse/projects/{p4['id']}/day-logs/{log.get('id')}", json={
        "log_date": HOY.isoformat(), "hours": "8", "helper_user_ids": []})
    esperar("Quien deja de ser ayudante deja de ver la obra", t1.get(f"/projects/{p4['id']}"), (404,), sev="baja")
    # El responsable nuevo corrige la jornada del anterior
    jornada_t1 = ctx["rotacion"]["jornada_t1"]
    r = t2.put(f"/warehouse/projects/{ctx['rotacion']['pid']}/day-logs/{jornada_t1['id']}", json={
        "log_date": jornada_t1["log_date"], "hours": "1", "work_done": "T2 pisa a T1"})
    esperar("El responsable nuevo no corrige la jornada del anterior", r, (403,))
    # Obra cerrada: una que el QA de punta a punta dejó terminada con T1 de responsable.
    cerradas = [x for x in admin.get("/projects", params={"page_size": 200}).json()
                if x["status"] == "completed" and x.get("primary_technician_user_id") == t1.me["id"]]
    p5 = cerradas[0] if cerradas else None
    if p5:
        cosa = ctx["rotacion"]["item"]
        for texto, accion in [
            ("pide salida", lambda: t1.post("/warehouse/releases", json={"project_id": p5["id"],
                                                                          "lines": [{"item_id": cosa["id"], "quantity": "1"}]})),
            ("registra jornada", lambda: t1.post(f"/warehouse/projects/{p5['id']}/day-logs",
                                                 json={"log_date": HOY.isoformat(), "hours": "1"})),
            ("anota cobro adicional", lambda: t1.post(f"/warehouse/projects/{p5['id']}/extra-charges",
                                                      json={"description": "x", "amount": "5"})),
            ("sube evidencia", lambda: t1.post(f"/projects/{p5['id']}/evidence", data={"category": "general"},
                                               files={"file": ("f.jpg", jpeg("x"), "image/jpeg")})),
        ]:
            r = accion()
            if r.status_code < 300:
                hallazgo("media", f"En una obra cerrada el técnico {texto}",
                         "cerrar la instalación; el técnico responsable intenta escribir",
                         "409/400: la obra está cerrada", f"HTTP {r.status_code}", "field_ops/access.py:can_work")
            else:
                bien(f"Obra cerrada: el técnico no {texto} → {r.status_code}")
    else:
        print("   (no hay obra cerrada de T1 para probar)")


# ---------------------------------------------------------------------------
# 3. Salidas: cantidades, entregas, «lo llevo», omisiones, separación de funciones
# ---------------------------------------------------------------------------

def _orden(cli: Client, lineas, **extra) -> httpx.Response:
    return cli.post("/warehouse/releases", json={"lines": lineas, **extra})


def ataque_salidas(c: dict, ctx: dict) -> None:
    seccion("3. Salidas de bodega")
    admin, adm, t1, t2, atk = c["admin"], c["adm"], c["tecnico"], c["t2"], c["atk"]
    a = item(adm, "salida A")
    b = item(adm, "salida B")
    entrada(adm, a["id"], "50")
    entrada(adm, b["id"], "50")
    for cantidad in ["-1", "0", "0.001", "1e309", "NaN", "Infinity", "abc", "", "99999999999999999", "1,5", " 2 "]:
        r = _orden(t1, [{"item_id": a["id"], "quantity": cantidad}])
        if r.status_code >= 500:
            hallazgo("alta", f"Cantidad «{cantidad}» en la orden revienta el servidor",
                     f"POST /warehouse/releases con quantity={cantidad!r}", "400 con mensaje", f"HTTP {r.status_code}",
                     "warehouse/releases.py:_normalizar_lineas")
        elif r.status_code == 201 and cantidad in ("-1", "0", "NaN", "Infinity", "abc", ""):
            hallazgo("alta", f"Se acepta una orden con cantidad «{cantidad}»", f"quantity={cantidad!r}", "400",
                     f"201 cantidad {r.json()['lines'][0].get('quantity_requested')}", "warehouse/releases.py")
        else:
            bien(f"Cantidad {cantidad!r} → {r.status_code}")
    # Artículo de otra organización en la orden y en las omisiones
    ajeno = atk.post("/warehouse/items", json={"name": "ajeno", "sku": f"AJ-{RUN}", "category": "other",
                                                "unit": "unit", "unit_cost": "1"})
    if ajeno.status_code == 201:
        aj = ajeno.json()["id"]
        esperar("Orden con artículo de otra organización", _orden(t1, [{"item_id": aj, "quantity": "1"}]), (404, 400))
        esperar("Omisión con artículo de otra organización", _orden(t1, [{"item_id": a["id"], "quantity": "1"}],
                omissions=[{"item_id": aj, "reason": "x"}]), (404, 400))
    esperar("Omisión sin motivo", _orden(t1, [{"item_id": a["id"], "quantity": "1"}],
                                         omissions=[{"item_id": b["id"], "reason": " "}]), (400, 422))
    # Entrega con cantidades ajenas, de más, negativas, raras
    o = _orden(t1, [{"item_id": a["id"], "quantity": "5"}, {"item_id": b["id"], "quantity": "3"}]).json()
    t1.post(f"/warehouse/releases/{o['id']}/submit")
    admin.post(f"/warehouse/releases/{o['id']}/approve")
    otra = _orden(t2, [{"item_id": a["id"], "quantity": "1"}]).json()
    la, lb = o["lines"][0]["id"], o["lines"][1]["id"]
    for texto, lineas, codigos in [
        ("renglón de otra orden", [{"line_id": otra["lines"][0]["id"], "quantity": "1"}], (400, 404)),
        ("más de lo pedido", [{"line_id": la, "quantity": "6"}], (400,)),
        ("negativa", [{"line_id": la, "quantity": "-1"}], (400,)),
        ("NaN", [{"line_id": la, "quantity": "NaN"}], (400,)),
        ("texto", [{"line_id": la, "quantity": "abc"}], (400,)),
        ("id inventado", [{"line_id": str(uuid.uuid4()), "quantity": "1"}], (400, 404)),
    ]:
        r = adm.post(f"/warehouse/releases/{o['id']}/deliver", json={"lines": lineas})
        if r.status_code >= 500:
            hallazgo("alta", f"Entregar con cantidad {texto} revienta el servidor", f"deliver lines={lineas}",
                     "400", f"HTTP {r.status_code}", "warehouse/releases.py:deliver_order")
        else:
            esperar(f"Entrega con {texto}", r, codigos)
    saldo_antes = adm.get(f"/warehouse/items/{a['id']}").json()["total_quantity"]
    # Dos personas entregan a la vez
    resultados = []
    def entregar(cli):
        resultados.append(cli.post(f"/warehouse/releases/{o['id']}/deliver",
                                   json={"lines": [{"line_id": la, "quantity": "5"}, {"line_id": lb, "quantity": "0"}]}))
    hilos = [threading.Thread(target=entregar, args=(cli,)) for cli in (adm, admin, adm)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    codigos = sorted(r.status_code for r in resultados)
    saldo = adm.get(f"/warehouse/items/{a['id']}").json()["total_quantity"]
    if any(cod >= 500 for cod in codigos):
        hallazgo("media", "Dos entregas simultáneas de la misma orden dan 500", "tres POST /deliver a la vez",
                 "una 200 y las demás 400/409 «ya entregada»", f"códigos {codigos}", "warehouse/releases.py:deliver_order")
    else:
        bien(f"Entregas simultáneas → {codigos}")
    if float(saldo_antes) - float(saldo) != 5.0:
        hallazgo("crítica", "Entregas simultáneas descuentan de más", "tres entregas a la vez",
                 f"bajar 5 (de {saldo_antes})", f"quedó en {saldo}", "warehouse/releases.py:deliver_order")
    else:
        bien("Entregas simultáneas descuentan una sola vez")
    # «Lo llevo»
    orden = adm.get(f"/warehouse/releases/{o['id']}").json()
    esperar("«Lo llevo» de otro técnico", t2.post(f"/warehouse/releases/{o['id']}/lines/{la}/load",
                                                    json={"loaded": True}), (403, 404))
    esperar("«Lo llevo» de un renglón no entregado", t1.post(f"/warehouse/releases/{o['id']}/lines/{lb}/load",
                                                               json={"loaded": True}), (400,))
    esperar("«Lo llevo» en orden sin entregar", t2.post(f"/warehouse/releases/{otra['id']}/lines/{otra['lines'][0]['id']}/load",
                                                          json={"loaded": True}), (400,))
    esperar("«Lo llevo» con renglón de otra orden", t1.post(f"/warehouse/releases/{o['id']}/lines/{otra['lines'][0]['id']}/load",
                                                              json={"loaded": True}), (404,))
    esperar("«Lo llevo» desde otra organización", atk.post(f"/warehouse/releases/{o['id']}/lines/{la}/load",
                                                             json={"loaded": True}), (404,))
    marcas = []
    hilos = [threading.Thread(target=lambda v=v: marcas.append(t1.post(
        f"/warehouse/releases/{o['id']}/lines/{la}/load", json={"loaded": v}))) for v in (True, False, True, True)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    if any(m.status_code >= 500 for m in marcas):
        hallazgo("media", "Marcar «lo llevo» varias veces a la vez da 500", "cuatro POST /load a la vez", "200",
                 str([m.status_code for m in marcas]), "warehouse/releases.py:mark_loaded")
    else:
        bien("«Lo llevo» simultáneo sin errores")
    # Separación de funciones: salida pedida desde la obra a nombre del técnico
    p = obra(admin, "sod")
    liberar(adm, p["id"], t1.me["id"])
    desde_obra = _orden(adm, [{"item_id": a["id"], "quantity": "1"}], project_id=p["id"]).json()
    if desde_obra.get("technician_user_id") == t1.me["id"]:
        bien("La salida pedida desde la obra queda a nombre del técnico responsable")
    adm.post(f"/warehouse/releases/{desde_obra['id']}/submit")
    esperar("Quien la pidió (Administración) no la autoriza", adm.post(f"/warehouse/releases/{desde_obra['id']}/approve"),
            (403,))
    esperar("El técnico a cuyo nombre está no la autoriza", t1.post(f"/warehouse/releases/{desde_obra['id']}/approve"),
            (403,))
    # El que la pide pone de técnico a quien la va a autorizar
    truco = _orden(adm, [{"item_id": a["id"], "quantity": "1"}], technician_user_id=admin.me["id"]).json()
    adm.post(f"/warehouse/releases/{truco.get('id')}/submit")
    esperar("Autoriza alguien que figura como técnico de la orden", admin.post(f"/warehouse/releases/{truco.get('id')}/approve"),
            (403,), sev="media")
    # Rechazar lo propio
    propia = _orden(adm, [{"item_id": a["id"], "quantity": "1"}]).json()
    adm.post(f"/warehouse/releases/{propia['id']}/submit")
    r = adm.post(f"/warehouse/releases/{propia['id']}/reject", json={"reason": "me arrepentí"})
    if r.status_code == 200:
        hallazgo("baja", "Quien pidió la salida puede rechazarla él mismo", "pedir, enviar y rechazar con el mismo usuario",
                 "a discutir: retirarla sí, «rechazarla» como autorizador no", "200", "warehouse/releases.py:reject_order")


# ---------------------------------------------------------------------------
# 4. Materiales de la orden
# ---------------------------------------------------------------------------

def ataque_materiales(c: dict, ctx: dict) -> None:
    seccion("4. Materiales de la orden")
    admin, adm, t1, atk = c["admin"], c["adm"], c["tecnico"], c["atk"]
    pid = ctx["rotacion"]["pid"]
    mats = admin.get(f"/projects/{pid}/materials", params={"page_size": 50}).json()
    de_bodega = [m for m in mats if m.get("warehouse_release_line_id") or m.get("from_warehouse")]
    if not de_bodega:
        hallazgo("media", "Lo entregado por bodega no aparece en «Materiales de la orden»",
                 "entregar una salida de la obra y abrir sus materiales", "un renglón por lo entregado",
                 json.dumps(mats)[:200], "field_ops/installation.py")
    else:
        m = de_bodega[0]
        esperar("Borrar por la API un material que vino de bodega", admin.delete(f"/materials/{m['id']}"), (409,))
    esperar("Pedir material para una obra de otra organización",
            atk.post("/warehouse/releases", json={"project_id": pid, "lines": [{"item_id": str(uuid.uuid4()), "quantity": "1"}]}),
            (404,))
    esperar("Pedir material para una obra inventada",
            t1.post("/warehouse/releases", json={"project_id": str(uuid.uuid4()),
                                                 "lines": [{"item_id": ctx["rotacion"]["item"]["id"], "quantity": "1"}]}),
            (404,))
    esperar("Pedir material con project_id que no es UUID",
            t1.post("/warehouse/releases", json={"project_id": "1 OR 1=1",
                                                 "lines": [{"item_id": ctx["rotacion"]["item"]["id"], "quantity": "1"}]}),
            (422,))
    esperar("Ver materiales de una obra de otra organización", atk.get(f"/projects/{pid}/materials"), (404,))


# ---------------------------------------------------------------------------
# 5. Catálogo, categorías e importación
# ---------------------------------------------------------------------------

def ataque_catalogo(c: dict, ctx: dict) -> None:
    seccion("5. Catálogo, categorías e importación")
    admin, adm, t1, atk = c["admin"], c["adm"], c["tecnico"], c["atk"]
    base = f"Filtros {RUN}"
    esperar("Crear categoría", adm.post("/warehouse/categories", json={"label": base}), (201,))
    for variante in [base.upper(), f"  {base}  ", base.lower()]:
        esperar(f"Categoría repetida «{variante.strip()}»", adm.post("/warehouse/categories", json={"label": variante}),
                (409,), sev="media")
    r = adm.post("/warehouse/categories", json={"label": base.replace("Filtros", "Fíltros")})
    if r.status_code == 201:
        hallazgo("baja", "Se crean categorías que solo difieren en una tilde", f"crear «{base}» y «Fíltros {RUN}»",
                 "409 categoría repetida", "201: quedan dos categorías", "warehouse/categories.py:create_category")
    # Dos personas crean la misma a la vez
    resultados = []
    hilos = [threading.Thread(target=lambda: resultados.append(adm.post("/warehouse/categories",
             json={"label": f"Concurrente {RUN}"}))) for _ in range(3)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    cods = sorted(r.status_code for r in resultados)
    if any(x >= 500 for x in cods):
        hallazgo("media", "Crear la misma categoría a la vez da 500", "tres POST /warehouse/categories iguales a la vez",
                 "una 201 y las demás 409", str(cods), "warehouse/categories.py:create_category")
    else:
        bien(f"Categoría concurrente → {cods}")
    cats = adm.get("/warehouse/categories", params={"page_size": 200}).json()
    otro = next(x for x in cats if x["code"] == "other")
    esperar("Desactivar «Otro»", adm.put(f"/warehouse/categories/{otro['id']}", json={"active": False}), (400,))
    nueva = next(x for x in cats if x["label"] == base)
    r = adm.put(f"/warehouse/categories/{nueva['id']}", json={"label": "%"})
    if r.status_code == 409:
        hallazgo("baja", "Renombrar una categoría a «%» o con «_» choca con otras por comodín",
                 "PUT /warehouse/categories/{id} label=%", "200 (ninguna se llama «%»)", "409 category_exists",
                 "warehouse/categories.py:update_category usa ilike sin escapar")
    else:
        bien(f"Renombrar a «%» → {r.status_code}")
    esperar("El técnico no crea categorías", t1.post("/warehouse/categories", json={"label": "x"}), (403,))
    esperar("Otra organización no edita categorías ajenas",
            atk.put(f"/warehouse/categories/{nueva['id']}", json={"label": "hackeada"}), (404,))
    # Importación por filas
    filas = [
        {"name": f"Foam Insulation Tape Black 1/8 x 2 x 30' {RUN}", "sku": 36140, "brand": "Armacell",
         "manufacturer_part": "TAP18230", "category": "Cintas y sellantes", "unit": "unidades", "unit_cost": "19.57"},
        {"name": f"Foam Insulation Tape Black 1/8 x 2 x 30' {RUN}", "sku": 3088, "brand": "Diversitech",
         "manufacturer_part": "6-9718", "category": "Cintas y sellantes", "unit": "unidades", "unit_cost": "14.05"},
    ]
    r = adm.post("/warehouse/import/rows", json={"rows": filas, "filename": "acpro.xlsx"})
    items = adm.get("/warehouse/items", params={"q": f"Foam Insulation Tape Black 1/8 x 2 x 30' {RUN}"}).json()
    if len(items) < 2:
        hallazgo("alta", "Dos productos de AC Pro con el mismo nombre y distinto código se funden en uno",
                 "importar las dos «Foam Insulation Tape Black 1/8\" x 2\" x 30'» del PDF del cliente (AC Pro 36140 "
                 "Armacell y 3088 Diversitech)", "dos artículos, uno por código",
                 f"{len(items)} artículo; código final {[i.get('sku') for i in items]}; respuesta {json.dumps(r.json())[:150]}",
                 "warehouse/service.py:_find_item (busca por nombre si el código no existe)")
    else:
        bien("Mismo nombre, distinto código → dos artículos")
    cat_rota = f"Rota {RUN}"
    r = adm.post("/warehouse/import/rows", json={"rows": [
        {"name": f"fila mala {RUN}", "sku": f"M-{RUN}", "category": cat_rota, "unit_cost": "abc"},
        {"name": f"fila buena {RUN}", "sku": f"B-{RUN}", "category": cat_rota, "unit_cost": "5"}]})
    buena = adm.get("/warehouse/items", params={"q": f"fila buena {RUN}"}).json()
    labels = {x["code"]: x["label"] for x in adm.get("/warehouse/categories", params={"page_size": 300}).json()}
    if buena and buena[0].get("category") not in labels:
        hallazgo("media", "Una fila que falla deja a las siguientes con una categoría que no existe",
                 "importar dos filas con la misma categoría nueva; la primera con costo «abc»",
                 "la segunda crea la categoría", f"artículo con categoría «{buena[0].get('category')}» inexistente",
                 "warehouse/service.py:import_catalog (cache `categorias` tras el rollback del savepoint)")
    else:
        bien("Una fila mala no deja categorías fantasma")
    r = adm.post("/warehouse/import/rows", json={"rows": [
        {"name": f"num prov {RUN}", "sku": f"N-{RUN}", "supplier_name": 12345, "notes": 678, "unit_cost": 1}]})
    errs = r.json().get("errores") if r.status_code == 200 else None
    if r.status_code >= 500 or errs:
        hallazgo("baja", "Proveedor o notas numéricos en el Excel hacen fallar la fila",
                 "importar una fila con proveedor 12345 y notas 678 (Excel los guarda como número)",
                 "se guardan como texto", f"HTTP {r.status_code} {json.dumps(errs)[:150]}",
                 "warehouse/service.py:import_catalog (.strip() sobre número)")
    else:
        bien("Proveedor y notas numéricos se importan")
    r = adm.post("/warehouse/import/rows", json={"rows": [{"name": "", "category": ""}, {"name": None}]})
    esperar("Filas vacías se omiten sin error", r, (200,), sev="baja")
    r = adm.post("/warehouse/import", files={"file": ("x.xlsx", b"PK\x03\x04basura", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    esperar("Excel corrupto", r, (400,))
    r = adm.post("/warehouse/import", files={"file": ("x.xlsx", b"0" * (11 * 1024 * 1024), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    esperar("Excel gigante", r, (400, 413))


# ---------------------------------------------------------------------------
# 6. Compras sugeridas
# ---------------------------------------------------------------------------

def ataque_compras(c: dict, ctx: dict) -> None:
    seccion("6. Compras sugeridas")
    admin, adm, t1, t2 = c["admin"], c["adm"], c["tecnico"], c["t2"]
    x = item(adm, "compras X")
    entrada(adm, x["id"], "20")
    p1, p2 = obra(admin, "compras 1"), obra(admin, "compras 2")
    liberar(adm, p1["id"], t1.me["id"])
    liberar(adm, p2["id"], t2.me["id"])
    for p in (p1, p2):
        b = adm.post("/warehouse/budgets", json={"project_id": p["id"], "lines": [{"category": "materials",
                                                                                   "item_id": x["id"], "quantity": "10"}]}).json()
        admin.post(f"/warehouse/budgets/{b['id']}/approve")
    # A la obra 1 se le entregan 15 (5 de más) y devuelve 3.
    o = t1.post("/warehouse/releases", json={"project_id": p1["id"], "lines": [{"item_id": x["id"], "quantity": "15"}]}).json()
    t1.post(f"/warehouse/releases/{o['id']}/submit")
    admin.post(f"/warehouse/releases/{o['id']}/approve")
    adm.post(f"/warehouse/releases/{o['id']}/deliver", json={})
    dev = adm.post("/warehouse/movements", json={"item_id": x["id"], "movement_type": "devolucion", "quantity": "3",
                                                  "project_id": p1["id"]})
    fila = next((r for r in admin.get("/warehouse/purchasing").json()["rows"] if r["item_id"] == x["id"]), None)
    # Obra 1: 10 − (15 − 3) → 0 pendiente; obra 2: 10. Existencia: 20 − 15 + 3 = 8 → comprar 2.
    esperado = {"budgeted": "20.00", "delivered": "10.00", "pending": "10.00", "in_stock": "8.00", "to_buy": "2.00"}
    if fila and all(fila.get(k) == v for k, v in esperado.items()):
        bien("Compras sugeridas con entrega de más y devolución cuadran")
    else:
        hallazgo("media", "Compras sugeridas no cuadran con entrega de más y devolución",
                 "dos obras con 10 presupuestados; a la 1 se le entregan 15 y devuelve 3 (devolución "
                 f"{dev.status_code})", json.dumps(esperado), json.dumps(fila)[:250], "warehouse/costing.py:purchasing_report")
    # Presupuesto reemplazado: el nuevo de la obra 2 pide 4.
    b2 = adm.post("/warehouse/budgets", json={"project_id": p2["id"], "lines": [{"category": "materials",
                                                                                 "item_id": x["id"], "quantity": "4"}]}).json()
    admin.post(f"/warehouse/budgets/{b2['id']}/approve")
    fila = next((r for r in admin.get("/warehouse/purchasing").json()["rows"] if r["item_id"] == x["id"]), None)
    if fila and fila["pending"] == "4.00":
        bien("Solo cuenta el presupuesto vigente (el reemplazado no)")
    else:
        hallazgo("media", "El presupuesto reemplazado sigue contando en compras sugeridas",
                 "aprobar un segundo presupuesto de la obra 2 con 4", "pendiente 4", json.dumps(fila)[:200],
                 "warehouse/costing.py:purchasing_report")


# ---------------------------------------------------------------------------
# 7. Buscador
# ---------------------------------------------------------------------------

def ataque_buscador(c: dict, ctx: dict) -> None:
    seccion("7. Buscador")
    adm, t1, atk = c["adm"], c["tecnico"], c["atk"]
    item(adm, "Codo 90° 3/4\" CXC 100%_raro")
    for q in ["%", "_", "100%", "\"", "'", "\\", "codo", "CODO", "códo", "90°", "' OR 1=1 --", "%' --", "a" * 500, "\x00"]:
        r = adm.get("/warehouse/items", params={"q": q, "page_size": 20})
        if r.status_code >= 500:
            hallazgo("alta", f"El buscador revienta con «{q[:20]}»", f"GET /warehouse/items?q={q[:20]}", "200 o 400",
                     f"HTTP {r.status_code}", "warehouse/service.py:items_stmt")
            continue
        total = int(r.headers.get("x-total-count", len(r.json())))
        if q in ("%", "_") and total > 5:
            hallazgo("baja", f"Buscar «{q}» trae todo el catálogo (comodín sin escapar)", f"q={q}",
                     "solo lo que contiene ese carácter", f"{total} resultados", "warehouse/service.py:items_stmt")
        elif q == "códo" and total == 0:
            hallazgo("baja", "Buscar con tilde no encuentra lo que no la tiene", "q=códo con un artículo «Codo»",
                     "encuentra «Codo»", "0 resultados", "warehouse/service.py:items_stmt")
        else:
            bien(f"Buscar {q[:15]!r} → {r.status_code} ({total})")
    r = atk.get("/warehouse/items", params={"q": "Codo 90"})
    if r.status_code == 200 and any("raro" in (i.get("name") or "") for i in r.json()):
        hallazgo("crítica", "El buscador muestra artículos de otra organización", "buscar desde «Atacante SA»",
                 "nada de Demo", "aparecen artículos de Demo", "warehouse/service.py:items_stmt")
    else:
        bien("Otra organización no encuentra artículos ajenos")
    r = t1.get("/projects", params={"q": "%", "page_size": 100})
    if r.status_code >= 500:
        hallazgo("media", "Buscar obra con «%» revienta", "GET /projects?q=%", "200", f"HTTP {r.status_code}",
                 "field_ops/router.py:list_projects")


# ---------------------------------------------------------------------------
# 8. Calendario
# ---------------------------------------------------------------------------

def ataque_calendario(c: dict, ctx: dict) -> None:
    seccion("8. Calendario de obras")
    admin, t1, t2, v, atk = c["admin"], c["tecnico"], c["t2"], c["vendedor"], c["atk"]
    cal = lambda cli, a, b, **kw: cli.get("/warehouse/calendar", params={"date_from": a.isoformat(), "date_to": b.isoformat(), **kw})
    esperar("Rango de 63 días", cal(admin, HOY, HOY + timedelta(days=63)), (400,))
    esperar("Rango de 62 días", cal(admin, HOY, HOY + timedelta(days=62)), (200,))
    esperar("Fechas invertidas", cal(admin, HOY, HOY - timedelta(days=1)), (400,))
    esperar("Fecha inválida", admin.get("/warehouse/calendar", params={"date_from": "2026-13-40", "date_to": "x"}), (422,))
    r = cal(t1, HOY - timedelta(days=30), HOY + timedelta(days=30), technician_user_id=t2.me["id"])
    if r.status_code == 200:
        datos = r.json()
        ajenos = [a for a in datos["assignments"] if a["technician_user_id"] != t1.me["id"]] + \
                 [d for d in datos["day_logs"] if d["technician_user_id"] not in (t1.me["id"], None)
                  and t1.me["id"] not in [h["user_id"] for h in d["helpers"]]]
        if ajenos:
            hallazgo("alta", "El técnico ve en el calendario lo de otro técnico", "GET /warehouse/calendar con technician_user_id=T2 como T1",
                     "solo lo de T1", f"{len(ajenos)} registros de otros", "warehouse/day_logs.py:calendar")
        else:
            bien("El técnico solo ve lo suyo aunque pida a otro")
    esperar("El vendedor no ve el calendario", cal(v, HOY, HOY), (403,), sev="media")
    r = cal(atk, HOY - timedelta(days=30), HOY + timedelta(days=30))
    if r.status_code == 200 and (r.json()["assignments"] or r.json()["day_logs"]):
        titulos = {a["project_title"] for a in r.json()["assignments"]}
        if any(t.startswith("ATK") for t in titulos):
            hallazgo("crítica", "Otra organización ve el calendario de Demo", "GET /warehouse/calendar como Atacante",
                     "vacío", str(list(titulos))[:150], "warehouse/day_logs.py:calendar")
    bien("Calendario de otra organización revisado")


# ---------------------------------------------------------------------------
# 9. Entradas numéricas en otras rutas de bodega
# ---------------------------------------------------------------------------

def ataque_numeros(c: dict, ctx: dict) -> None:
    seccion("9. Entradas numéricas raras en otras rutas")
    admin, adm, t1 = c["admin"], c["adm"], c["tecnico"]
    x = ctx["rotacion"]["item"]
    pid = obra(admin, "numeros")["id"]
    liberar(adm, pid, t1.me["id"])
    pruebas = {
        "movimiento": lambda q: adm.post("/warehouse/movements", json={"item_id": x["id"], "movement_type": "entrada", "quantity": q}),
        "artículo (costo)": lambda q: adm.post("/warehouse/items", json={"name": f"num {uuid.uuid4().hex[:5]}", "unit_cost": q}),
        "conteo": lambda q: adm.post("/warehouse/counts", json={"lines": [{"item_id": x["id"], "counted_quantity": q}]}),
        "lista": lambda q: adm.post("/warehouse/kits", json={"name": f"kit {uuid.uuid4().hex[:5]}", "items": [{"item_id": x["id"], "quantity": q}]}),
        "presupuesto": lambda q: adm.post("/warehouse/budgets", json={"project_id": pid, "lines": [{"category": "materials", "item_id": x["id"], "quantity": q}]}),
        "diario (material)": lambda q: t1.post(f"/warehouse/projects/{pid}/day-logs", json={"log_date": (HOY - timedelta(days=int(time.time()) % 20 + 1)).isoformat(), "materials": [{"description": "x", "quantity": q}]}),
        "diario (horas)": lambda q: t1.post(f"/warehouse/projects/{pid}/day-logs", json={"log_date": (HOY - timedelta(days=int(time.time() * 7) % 20 + 21)).isoformat(), "hours": q}),
        "cobro adicional": lambda q: t1.post(f"/warehouse/projects/{pid}/extra-charges", json={"description": "x", "amount": q}),
        "costo anotado": lambda q: adm.post(f"/warehouse/projects/{pid}/cost-entries", json={"category": "labor", "amount": q}),
    }
    for nombre, fn in pruebas.items():
        malos = []
        for q in ["NaN", "abc", "1e309", "99999999999999999"]:
            r = fn(q)
            if r.status_code >= 500:
                malos.append(q)
        if malos:
            hallazgo("alta", f"Valores no numéricos o enormes dan 500 en {nombre}", f"enviar {malos}",
                     "400 con mensaje", "HTTP 500", "warehouse/*.py: _q / to_money sin validar")
        else:
            bien(f"{nombre}: valores raros → sin 500")


# ---------------------------------------------------------------------------
# 10. Permisos de las rutas nuevas, rol por rol y desde otra organización
# ---------------------------------------------------------------------------

def ataque_permisos(c: dict, ctx: dict) -> None:
    seccion("10. Permisos por rol y aislamiento")
    pid = ctx["rotacion"]["pid"]
    entregada = ctx["rotacion"]["entregada"]
    linea = entregada["lines"][0]["id"]
    cats = c["admin"].get("/warehouse/categories", params={"page_size": 5}).json()
    cat_id = cats[-1]["id"]
    hoy, fin = HOY.isoformat(), (HOY + timedelta(days=7)).isoformat()
    rutas = [
        ("GET categorías", lambda u: u.get("/warehouse/categories"),
         {"admin": 200, "adm": 200, "tecnico": 200, "conta": 200, "gerencia": 200, "vendedor": 403}),
        ("POST categoría", lambda u: u.post("/warehouse/categories", json={"label": f"perm {u.role} {RUN}"}),
         {"admin": 201, "adm": 201, "tecnico": 403, "conta": 403, "gerencia": 403, "vendedor": 403}),
        ("PUT categoría", lambda u: u.put(f"/warehouse/categories/{cat_id}", json={"active": True}),
         {"admin": 200, "adm": 200, "tecnico": 403, "conta": 403, "gerencia": 403, "vendedor": 403}),
        ("GET calendario", lambda u: u.get("/warehouse/calendar", params={"date_from": hoy, "date_to": fin}),
         {"admin": 200, "adm": 200, "tecnico": 200, "conta": 200, "gerencia": 200, "vendedor": 403}),
        ("GET ayudantes", lambda u: u.get("/warehouse/day-log-helpers"),
         {"admin": 200, "adm": 200, "tecnico": 200, "conta": 403, "gerencia": 403, "vendedor": 403}),
        ("GET historial de responsables", lambda u: u.get(f"/projects/{pid}/assignments"),
         {"admin": 200, "adm": 200, "tecnico": 200, "conta": 200, "gerencia": 200, "vendedor": 403}),
        ("POST «lo llevo»", lambda u: u.post(f"/warehouse/releases/{entregada['id']}/lines/{linea}/load", json={"loaded": False}),
         {"admin": 200, "adm": 200, "conta": 403, "gerencia": 403, "vendedor": 403}),
        ("GET compras sugeridas", lambda u: u.get("/warehouse/purchasing"),
         {"admin": 200, "adm": 200, "tecnico": 403, "conta": 200, "gerencia": 200, "vendedor": 403}),
    ]
    for nombre, fn, esperados in rutas:
        for rol, codigo in esperados.items():
            r = fn(c[rol])
            ok = r.status_code == codigo or (codigo == 201 and r.status_code == 409)
            if ok:
                bien(f"{nombre} · {rol} → {r.status_code}")
            else:
                sev = "alta" if r.status_code < 300 and codigo >= 400 else "media"
                hallazgo(sev, f"{nombre} responde {r.status_code} a {rol} (se esperaba {codigo})", f"{nombre} como {rol}",
                         str(codigo), f"HTTP {r.status_code}: {r.text[:120]}")
    atk = c["atk"]
    for nombre, r in [
        ("historial de una obra de Demo", atk.get(f"/projects/{pid}/assignments")),
        ("«lo llevo» en una salida de Demo", atk.post(f"/warehouse/releases/{entregada['id']}/lines/{linea}/load", json={"loaded": True})),
        ("ver una salida de Demo", atk.get(f"/warehouse/releases/{entregada['id']}")),
        ("entregar una salida de Demo", atk.post(f"/warehouse/releases/{entregada['id']}/deliver", json={})),
        ("jornadas de una obra de Demo", atk.get(f"/warehouse/projects/{pid}/day-logs")),
        ("editar categoría de Demo", atk.put(f"/warehouse/categories/{cat_id}", json={"label": "x"})),
    ]:
        esperar(f"Otra organización: {nombre}", r, (404,), sev="crítica")
    ayudantes = c["tecnico"].get("/warehouse/day-log-helpers", params={"page_size": 200}).json()
    nombres = {a.get("name") or a.get("full_name") for a in ayudantes}
    if any(n and ("Atacante" in n) for n in nombres):
        hallazgo("crítica", "La lista de ayudantes trae usuarios de otra organización", "GET /warehouse/day-log-helpers",
                 "solo técnicos de Demo", str(nombres)[:150], "warehouse/router.py:day_log_helpers")
    elif any(n in ("Vicky Vendedora", "Clara Contable", "Demo Admin") for n in nombres):
        hallazgo("baja", "La lista de ayudantes trae personas que no son técnicos", "GET /warehouse/day-log-helpers",
                 "solo técnicos", str(nombres)[:150], "warehouse/router.py:day_log_helpers")
    else:
        bien(f"Ayudantes: solo técnicos de Demo ({len(nombres)})")


def main() -> int:
    c = {k: Client(k) for k in ("admin", "adm", "tecnico", "t2", "vendedor", "conta", "gerencia", "atk", "atk_tec")}
    contexto = {}
    for nombre, fn in [("rotacion", ataque_rotacion), ("limites", ataque_rotacion_limites), ("salidas", ataque_salidas), ("materiales", ataque_materiales), ("catalogo", ataque_catalogo), ("compras", ataque_compras), ("buscador", ataque_buscador), ("calendario", ataque_calendario), ("numeros", ataque_numeros), ("permisos", ataque_permisos)]:
        try:
            contexto[nombre] = fn(c) if nombre == "rotacion" else fn(c, contexto)
        except Exception as exc:  # noqa: BLE001
            hallazgo("media", f"La sección {nombre} reventó", "correr el ataque", "sin excepción", f"{type(exc).__name__}: {exc}")
    import os

    salida = Path(os.getenv("QA_ATAQUE_OUT", f"ataque-crudo-{RUN}.json"))
    salida.write_text(json.dumps({"findings": FINDINGS, "oks": OKS}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(FINDINGS)} hallazgos · {len(OKS)} controles OK · {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
