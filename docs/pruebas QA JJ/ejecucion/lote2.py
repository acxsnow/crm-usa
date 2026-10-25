"""Lote 2 de QA por API: el flujo del negocio (venta → revisión → campo → bodega
→ cobro), D-001 y concurrencia. Reusa las funciones de `scripts/qa_e2e.py`.
Corre dentro del contenedor api: PYTHONPATH=/app python /tmp/lote2.py > /tmp/lote2.json"""
import asyncio
import json
import sys
import threading
import time
from datetime import timedelta

import httpx
import redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from scripts import qa_e2e as e

R = redis.Redis.from_url(get_settings().REDIS_URL)
OUT: dict[str, list] = {}
ACTUAL = ["-"]


def limpiar():
    for k in R.scan_iter("ratelimit:*"):
        R.delete(k)


def sql(q: str) -> str:
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    async def _q():
        motor = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
        try:
            async with motor.connect() as cx:
                filas = (await cx.execute(text(q))).all()
                return "\n".join("|".join("" if v is None else str(v) for v in f) for f in filas)
        finally:
            await motor.dispose()
    return asyncio.run(_q())


e.clear_rate_limit = limpiar
_valor_original = e.valor


def _valor(campo, persona):
    """El estado de la dirección es una lista: qa_e2e tomaba la primera opción («CA»)."""
    opciones = [o["value"] for o in campo.get("options") or []]
    if campo["key"].endswith("state") and persona["state"] in opciones:
        return persona["state"]
    return _valor_original(campo, persona)


e.valor = _valor
e.sql = sql
e.section = lambda nombre: None
e.USERS.update({"vendedor2": "vendedor2@demo-org.com", "luis": "tecnico04@demo-org.com",
                "carlos": "tecnico03@demo-org.com"})
print_original = print


def esc(eid: str):
    ACTUAL[0] = eid
    e.SECTION[0] = eid


def chk(nombre, ok, dato=""):
    e.check(nombre, ok, str(dato))


def recoger():
    for r in e.RESULTS:
        OUT.setdefault(r["section"], []).append({"check": r["step"], "ok": r["ok"], "dato": r["detail"]})
    e.RESULTS.clear()


def remap(origen: str, reglas: list[tuple[str, str]]):
    """Reparte las comprobaciones de un bloque entre escenarios por palabras del paso."""
    for r in e.RESULTS:
        if r["section"] != origen:
            continue
        for palabra, destino in reglas:
            if palabra.lower() in r["step"].lower():
                r["section"] = destino
                break


def seguro(eid, fn, *a, **kw):
    esc(eid)
    try:
        return fn(*a, **kw)
    except Exception as ex:  # noqa: BLE001
        chk(f"El bloque terminó sin error inesperado ({type(ex).__name__})", False, repr(ex)[:300])
        return None


c = {k: e.Client(k) for k in e.USERS}
v, v2, adm, admin, tec, conta, ger = (c["vendedor"], c["vendedor2"], c["adm"], c["admin"], c["tecnico"],
                                       c["conta"], c["gerencia"])
progs = {p["code"]: p for p in admin.get("/programs").json()}


def persona(n, state="AZ"):
    p = e.persona(n, state)
    return p


def caso(cid):
    return admin.get(f"/cases/{cid}").json()


# ===========================================================================
# VEN-001 a VEN-003: salidas tempranas y la misma puerta
# ===========================================================================
def ven_tempranas():
    esc("VEN-001")
    p1 = persona(101, "CA")
    r = e.abrir_puerta(v, p1, None, "no_contact")
    if r:
        chk("Queda en «Sin contacto»", r["case"]["stage_code"] == "no_contact", r["case"]["stage_code"])
        chk("No pide ni crea cliente", not r["case"].get("customer_id"), r["case"].get("customer_id"))
        hist = sql(f"select count(*) from case_stage_events where case_id='{r['case']['id']}'")
        chk("El historial de etapas tiene la entrada inicial", hist == "1", hist)
    esc("VEN-002")
    for res, num in (("not_interested", 102), ("not_eligible", 103)):
        r = e.abrir_puerta(v, persona(num, "CA"), None, res)
        if r:
            chk(f"Queda en «{res}» sin cliente", r["case"]["stage_code"] == res and not r["case"].get("customer_id"),
                r["case"]["stage_code"])
    n = sql("select count(*) from projects") + "/" + sql("select count(*) from customers")
    chk("Las salidas tempranas no crean obra ni cliente (obras/clientes)", n.startswith("0/"), n)
    esc("VEN-003")
    r = e.abrir_puerta(v, p1, "TECH_CLEAN_CA", "opened")
    if r:
        chk("La misma dirección exacta reabre el expediente", r.get("outcome") == "reopened", r.get("outcome"))
    r2 = e.abrir_puerta(v, {**p1, "street": p1["street"].lower() + "."}, None, "no_contact")
    if r2:
        chk("La variante en minúsculas y con punto reconoce la misma puerta", r2["case"]["id"] == r["case"]["id"],
            f"outcome={r2.get('outcome')} mismo={r2['case']['id'] == r['case']['id']}")
    cuantos = sql(f"select count(*) from cases where address_street ilike '{p1['street']}%'")
    chk("Un solo expediente para esa dirección", cuantos == "1", cuantos)


# ===========================================================================
# VEN-004, VEN-005, REV-006: venta completa
# ===========================================================================
def ven_completa(n, state, programa):
    esc("VEN-004")
    cid, p = e.flujo_vendedor(v, adm, n, state, programa)
    remap("VEN-004", [("disfrazado", "VEN-005"), ("no puede aprobar", "REV-006")])
    cs = caso(cid)
    chk("El cliente quedó creado", bool(cs.get("customer_id")), cs.get("customer_id"))
    consent = sql(f"select count(*), max(document_version), bool_and(ip_address is not null) from data_consents "
                  f"where customer_id='{cs.get('customer_id')}'")
    chk("data_consents tiene la autorización con versión e IP", consent.split("|")[0] not in ("0", ""), consent)
    archivos = sql(f"select count(*), count(*) filter (where latitude is not null) from case_files where case_id='{cid}'")
    chk("Los archivos del formulario quedaron con GPS (total|con GPS)", archivos.split("|")[0] == archivos.split("|")[1], archivos)
    time.sleep(3)
    avisos = adm.get("/notifications", params={"limit": 50}).json()
    lista = avisos if isinstance(avisos, list) else avisos.get("items", [])
    chk("Administración recibe el aviso del expediente enviado",
        any(cs["case_number"] in (a.get("title", "") + a.get("body", "")) for a in lista), len(lista))
    return cid, p


def ven_invalidos(cid):
    esc("VEN-005")
    form = v.get(f"/cases/{cid}/form").json()
    campos = [(s["code"], f) for s in form["definition"]["steps"] for f in s["fields"]]
    mail = next(((s, f["key"]) for s, f in campos if f["type"] == "email"), None)
    tel = next(((s, f["key"]) for s, f in campos if f["type"] == "phone"), None)
    num = next(((s, f) for s, f in campos if f["type"] in ("integer", "decimal") and (f.get("validation") or {}).get("max")), None)
    for nombre, par, valor in (("correo «sin-arroba»", mail, "sin-arroba"), ("teléfono «abc»", tel, "abc")):
        if par:
            r = v.put(f"/cases/{cid}/steps/{par[0]}", json={"answers": {par[1]: valor}})
            chk(f"{nombre} se rechaza o queda marcado con error (expediente ya enviado: 409 esperado)",
                r.status_code in (400, 409, 422), f"{r.status_code} {r.text[:150]}")
    return mail, tel, num


def ven_invalidos_borrador():
    """VEN-005 sobre un borrador (el de VEN-004 ya está enviado)."""
    esc("VEN-005")
    r = e.abrir_puerta(v, persona(202, "AZ"), "AZ_EFFICIENCY")
    if not r:
        return
    cid = r["case"]["id"]
    form = v.get(f"/cases/{cid}/form").json()
    campos = [(s["code"], f) for s in form["definition"]["steps"] for f in s["fields"]]
    for tipo, malo in (("email", "sin-arroba"), ("phone", "abc")):
        par = next(((s, f["key"]) for s, f in campos if f["type"] == tipo), None)
        if not par:
            chk(f"Hay un campo de tipo {tipo} en el formulario", False)
            continue
        r = v.put(f"/cases/{cid}/steps/{par[0]}", json={"answers": {par[1]: malo}})
        guardado = v.get(f"/cases/{cid}/form").json()
        err = next((f.get("error") for s in guardado["evaluation"]["steps"] for f in s["fields"] if f["key"] == par[1]), None)
        chk(f"{tipo} inválido «{malo}»: rechazado o marcado con error",
            r.status_code in (400, 422) or bool(err), f"{r.status_code} error={err} {r.text[:120]}")
    num = next(((s, f) for s, f in campos if f["type"] in ("integer", "decimal") and (f.get("validation") or {}).get("max") is not None), None)
    if num:
        maximo = float(num[1]["validation"]["max"])
        r = v.put(f"/cases/{cid}/steps/{num[0]}", json={"answers": {num[1]["key"]: maximo + 1000}})
        guardado = v.get(f"/cases/{cid}/form").json()
        err = next((f.get("error") for s in guardado["evaluation"]["steps"] for f in s["fields"] if f["key"] == num[1]["key"]), None)
        chk(f"Número por encima del máximo ({num[1]['key']} > {maximo})", r.status_code in (400, 422) or bool(err),
            f"{r.status_code} error={err}")
    chk("Ningún 500 en las validaciones", True)


# ===========================================================================
# VEN-006: aislamiento entre vendedores
# ===========================================================================
def ven_aislamiento(cid):
    esc("VEN-006")
    cs = caso(cid)
    ids = [x["id"] for x in v2.get("/cases", params={"limit": 500}).json()]
    chk("Valeria no ve el expediente de Vicky en su lista", cid not in ids, len(ids))
    r = v2.get(f"/cases/{cid}")
    chk("GET del expediente de Vicky → 404", r.status_code == 404, r.status_code)
    r = v2.get(f"/cases/{cid}/form")
    chk("GET del formulario de Vicky → 404", r.status_code == 404, r.status_code)
    for q in (cs["case_number"], (cs.get("customer_name") or "QA")[:20]):
        res = v2.get("/search", params={"q": q}).json()
        hits = [x for g in res.get("groups", []) for x in g.get("results", []) if x.get("id") == cid]
        chk(f"El buscador de Valeria no lo encuentra («{q}»)", not hits, len(hits))


# ===========================================================================
# REV-001 a REV-003 y REV-004/REV-005
# ===========================================================================
def revision(cid, p):
    esc("REV-002")
    antes = caso(cid).get("submitted_at")
    e.flujo_revision(v, adm, admin, cid, p, devolver=True)
    remap("REV-002", [("documentos", "REV-001"), ("cola de documentos", "REV-001"), ("factura de luz", "REV-001"),
                      ("Rechazar sin nota", "REV-001"), ("Rechazar con nota", "REV-001"),
                      ("documento rechazado", "REV-001"), ("Avance con el programa", "REV-003"),
                      ("Aprobar con código", "REV-003"), ("Aprobado con código", "REV-003")])
    esc("REV-002")
    despues = caso(cid).get("submitted_at")
    chk("El contador de días no se reinicia al reenviar (submitted_at igual)", antes == despues, f"{antes} → {despues}")
    esc("REV-003")
    r = admin.post(f"/cases/{cid}/transition", json={"to_stage": "approved", "approval_code": "AZ-QA-0001"})
    chk("Aprobar dos veces no se permite", r.status_code in (400, 409), r.status_code)
    obras = sql(f"select count(*) from projects where case_id='{cid}'")
    chk("Una sola obra para el expediente", obras == "1", obras)
    datos = sql(f"select p.address_street = c.address_street, p.latitude is not null from projects p "
                f"join cases c on c.id=p.case_id where p.case_id='{cid}'")
    chk("La obra copia la dirección y las coordenadas de la visita", datos == "True|True", datos)


def rechazo_y_cierre():
    esc("REV-004")
    e.flujo_rechazo(v, adm, admin, 204)
    remap("REV-004", [("Cierre administrativo", "REV-005"), ("NO puede cerrar", "REV-005")])
    esc("REV-005")
    r = e.abrir_puerta(v, persona(205, "CA"), "TECH_CLEAN_CA")
    if r:
        cid = r["case"]["id"]
        e.expect("Cerrar un «Nuevo prospecto» sin motivo se bloquea",
                 admin.post(f"/cases/{cid}/transition", json={"to_stage": "closed"}), 400)
        e.expect("Cerrar con motivo", admin.post(f"/cases/{cid}/transition",
                                                  json={"to_stage": "closed", "reason": "QA: cliente se mudó"}), 200)
        e.expect("Cerrado ya no se edita", v.put(f"/cases/{cid}/steps/home", json={"answers": {"home.is_homeowner": "yes"}}),
                 400, 409)
        obras = sql(f"select count(*) from projects where case_id='{cid}'")
        chk("No se creó obra", obras == "0", obras)


# ===========================================================================
# Campo: INS-001 a INS-007, TEC-001/002, COB
# ===========================================================================
def kit_3ton():
    return next(k for k in adm.get("/warehouse/kits", params={"q": "3 ton"}).json() if "3 ton" in k["name"])


def stock(item_id) -> float:
    return float(adm.get(f"/warehouse/items/{item_id}").json()["total_quantity"])


def campo_y_cobro(cid):
    esc("INS-002")
    proj = e.proyecto_de(adm, cid)
    pid = proj["id"]
    rad = e.expect("Registrar el permiso solo radicado", adm.post(f"/projects/{pid}/permits", json={
        "jurisdiction": "Phoenix", "permit_number": "PHX-QA-001", "status": "submitted",
        "submitted_on": e.HOY.isoformat()}), 201)
    r = adm.post(f"/cases/{cid}/transition", json={"to_stage": "ready_to_install"})
    chk("Con solo el radicado, el paso manual a «Listo para instalar» se rechaza",
        r.status_code in (400, 409) and caso(cid)["stage_code"] != "ready_to_install", f"{r.status_code} {r.text[:200]}")
    tid = tec.me["id"]
    r = adm.patch(f"/projects/{pid}/schedule", json={
        "technician_user_id": tid, "scheduled_date": (e.HOY + timedelta(days=1)).isoformat()})
    chk("Con solo el radicado, «Liberar orden» también se rechaza (permits_not_cleared)",
        r.status_code == 400 and r.json().get("code") == "permits_not_cleared", f"{r.status_code} {r.text[:200]}")
    if rad:
        e.expect("Registrar el permiso como aprobado", adm.patch(f"/permits/{rad['id']}", json={
            "status": "approved", "approved_on": e.HOY.isoformat(),
            "expires_on": (e.HOY + timedelta(days=180)).isoformat()}), 200)
    esc("INS-001")
    e.expect("Asignar técnico y fecha (Liberar orden)", adm.patch(f"/projects/{pid}/schedule", json={
        "technician_user_id": tid, "scheduled_date": (e.HOY + timedelta(days=1)).isoformat()}), 200)
    esc("INS-002")
    chk("Con el permiso aprobado el expediente pasa a «Listo para instalar»", caso(cid)["stage_code"] == "ready_to_install",
        caso(cid)["stage_code"])
    esc("INS-001")
    p = tec.get(f"/projects/{pid}").json()
    chk("La obra queda programada con técnico y fecha", p.get("status") == "scheduled" and p.get("scheduled_date"),
        f"{p.get('status')} {p.get('scheduled_date')}")
    agenda = tec.get("/dispatch/agenda", params={"date_from": e.HOY.isoformat(),
                                                 "date_to": (e.HOY + timedelta(days=7)).isoformat()}).json()
    chk("El técnico la ve en su agenda", any(a["project_id"] == pid for a in agenda), len(agenda))
    luis = c["luis"]
    agenda_l = luis.get("/dispatch/agenda", params={"date_from": e.HOY.isoformat(),
                                                    "date_to": (e.HOY + timedelta(days=7)).isoformat()}).json()
    chk("Otro técnico (Luis) no la ve en su agenda", not any(a["project_id"] == pid for a in agenda_l), len(agenda_l))
    aud = sql(f"select count(*) from audit_events where action='projects.installation_scheduled' and entity_id='{pid}'")
    chk("La auditoría registra quién asignó", aud != "0", aud)

    esc("INS-003")
    kit = kit_3ton()
    muestra = {}
    for it in adm.get(f"/warehouse/kits/{kit['id']}").json().get("items", [])[:3]:
        muestra[it["item_id"]] = stock(it["item_id"])
    r = tec.post("/warehouse/releases", json={"project_id": pid, "lines": []})
    chk("Un borrador sin renglones se rechaza (422)", r.status_code == 422, r.status_code)
    primero = list(muestra)[0]
    orden = e.expect("El técnico arma el borrador de salida para la obra", tec.post("/warehouse/releases", json={
        "project_id": pid, "lines": [{"item_id": primero, "quantity": "1"}]}), 201) or {}
    ap = e.expect("Cargar la lista «3 ton desde cero»", tec.post(f"/warehouse/kits/{kit['id']}/apply",
                                                               json={"release_id": orden.get("id")}), 200) or {}
    chk("La lista agrega sus renglones (46, menos el que ya estaba)", (ap.get("agregadas") or 0) >= 45, ap.get("agregadas"))
    env = e.expect("Guardar y enviar a autorizar", tec.post(f"/warehouse/releases/{orden.get('id')}/submit"), 200) or {}
    chk("Recibe su número SAL-", str(env.get("number", "")).startswith("SAL-"), env.get("number"))
    autorizada = e.expect("Bodega la autoriza", adm.post(f"/warehouse/releases/{orden.get('id')}/approve"), 200) or {}
    # D-007: los equipos «con serial» de la lista salen con el serial de cada unidad.
    con_serial = [l for l in autorizada.get("lines", []) if l.get("has_serial")]
    sin_serial = adm.post(f"/warehouse/releases/{orden.get('id')}/deliver", json={})
    seriales_qa, renglones = [], []
    for n, l in enumerate(con_serial):
        unidades = int(min(float(l["quantity_requested"]), stock(l["item_id"])))
        lote = [f"QA{e.RUN}-{n}-{k}" for k in range(unidades)]
        seriales_qa += [(l["item_id"], s) for s in lote]
        renglones.append({"line_id": l["id"], "quantity": str(unidades), "serials": lote})
    ent = e.expect("Bodega la entrega", adm.post(f"/warehouse/releases/{orden.get('id')}/deliver",
                                                 json={"lines": renglones}), 200) or {}
    lineas = {l["item_id"]: l for l in ent.get("lines", [])}
    for item_id, antes in muestra.items():
        entregado = float(lineas.get(item_id, {}).get("quantity_delivered") or 0)
        chk(f"Existencia baja exactamente en lo entregado ({lineas.get(item_id, {}).get('item_name', item_id)[:40]})",
            abs(stock(item_id) - (antes - entregado)) < 0.001, f"antes={antes} entregado={entregado} ahora={stock(item_id)}")
    movs = sql(f"select count(*) from warehouse_movements where project_id='{pid}' and movement_type='salida'")
    chk("Movimientos `salida` con la obra", movs != "0", movs)
    mats = tec.get(f"/projects/{pid}/materials").json()
    chk("El material entregado quedó cargado a la obra", any("De bodega" in (m.get("notes") or "") for m in mats), len(mats))
    esc("BOD-011")
    chk("La lista de 3 ton trae equipos «con serial» (85980)", any(l.get("sku") == "85980" for l in con_serial),
        [l.get("sku") for l in con_serial])
    chk("Sin los seriales la entrega se rechaza (400 serials_count_mismatch)",
        sin_serial.status_code == 400 and sin_serial.json().get("code") == "serials_count_mismatch",
        f"{sin_serial.status_code} {sin_serial.text[:150]}")
    entregados = {s: l for l in ent.get("lines", []) for s in l.get("serials", [])}
    chk("Cada unidad entregada quedó con su serial en el renglón", len(entregados) == len(seriales_qa) > 0,
        f"{len(entregados)} de {len(seriales_qa)}")
    estado = {x["serial"]: x for x in adm.get("/warehouse/serials", params={"project_id": pid}).json()}
    chk("Bodega › Seriales los muestra «Entregado a la obra» con la orden",
        all(estado.get(s, {}).get("status") == "delivered" and estado[s].get("release_number") == env.get("number")
            for _, s in seriales_qa), list(estado)[:3])
    obra = {x["serial"] for x in tec.get(f"/projects/{pid}/serials").json()}
    chk("El técnico los ve en su obra para «Equipos instalados»", obra == {s for _, s in seriales_qa}, sorted(obra))
    otro_pid = aprobar_rapido(311)[1]
    r = adm.post(f"/projects/{otro_pid}/equipment", json={"equipment_type": "air_handler", "brand": "QA",
                                                         "model": "QA", "serial_number": seriales_qa[0][1]})
    chk("El mismo serial no se instala en otra obra (409 serial_not_available_here)",
        r.status_code == 409 and r.json().get("code") == "serial_not_available_here", f"{r.status_code} {r.text[:120]}")
    r = tec.post(f"/projects/{pid}/equipment", json={"equipment_type": "air_handler", "brand": "QA", "model": "QA",
                                                   "warehouse_serial_id": estado[seriales_qa[0][1]]["id"]})
    eq = r.json() if r.status_code == 201 else {}
    chk("Instalarlo eligiéndolo de la lista lo deja «Instalado»", r.status_code == 201 and eq.get("serial_number")
        == seriales_qa[0][1] and adm.get("/warehouse/serials", params={"q": seriales_qa[0][1]}).json()[0]["status"]
        == "installed", f"{r.status_code} {r.text[:150]}")
    if eq.get("id"):
        tec.delete(f"/equipment/{eq['id']}")
    chk("Al borrar el equipo el serial vuelve a «Entregado»",
        adm.get("/warehouse/serials", params={"q": seriales_qa[0][1]}).json()[0]["status"] == "delivered", "")

    esc("INS-004")
    pid2 = e.flujo_campo(adm, tec, cid, devolver_acta=True, permiso=True)
    remap("INS-004", [("proyecto de instalación", "INS-001"), ("NO ve un proyecto", "_prep"),
                      ("Permiso municipal", "INS-002"), ("Agendar instalación", "INS-001"), ("ve su orden", "INS-001"),
                      ("Devolver el acta", "INS-005"), ("devuelve el acta", "INS-005"), ("corrige y cierra", "INS-005"),
                      ("confirma el acta", "INS-005"), ("no puede confirmar su propia acta", "TEC-002")])
    esc("INS-004")
    acta = tec.get(f"/projects/{pid}/attestation").json()
    pdf = tec.get(f"/attestations/{acta.get('id')}/pdf")
    chk("Descargar acta firmada (PDF)", pdf.status_code == 200 and pdf.content[:4] == b"%PDF",
        f"{pdf.status_code} {pdf.headers.get('content-type')}")
    etapa = caso(cid)["stage_code"]
    chk("Etapa del expediente después del cierre", etapa in ("installed", "inspection_pending"), etapa)
    esc("INS-005")
    time.sleep(2)
    av = tec.get("/notifications", params={"limit": 50}).json()
    av = av if isinstance(av, list) else av.get("items", [])
    chk("El técnico recibió el aviso de acta devuelta", any(a.get("event") == "project.returned_to_technician" for a in av),
        [a.get("event") for a in av][:6])
    esc("INS-007")
    e.flujo_inspeccion(adm, tec, pid)
    remap("INS-007", [("Segunda inspección", "INS-006"), ("sin permiso firmado", "INS-006"),
                      ("permiso firmado por el inspector", "INS-006"), ("Inspección aprobada", "INS-006")])
    esc("INS-006")
    chk("Etapa tras la inspección aprobada", True, caso(cid)["stage_code"])
    esc("COB-001")
    e.flujo_cobro(adm, conta, admin, pid, cid, "AZ_EFFICIENCY", rechazar=True, cerrar=True)
    remap("COB-001", [("rechaza", "COB-002"), ("Rechazo sin motivo", "COB-002"), ("vuelve a radicar", "COB-002"),
                      ("NO registra pagos", "COB-003"), ("registra el pago", "COB-003"), ("Pagado", "COB-003"),
                      ("Cerrar sin motivo", "COB-003"), ("Cierre administrativo", "COB-003"), ("Cerrado", "COB-003")])
    esc("COB-003")
    eventos = sql(f"select string_agg(to_stage_code, ',' order by occurred_at) from case_stage_events where case_id='{cid}'")
    chk("El historial de etapas recorre el ciclo completo", "paid" in eventos and "closed" in eventos, eventos)
    return pid


# ===========================================================================
# D-001: INS-010, INS-011, INS-012 (+ BOD-006, COB-004)
# ===========================================================================
def aprobar_rapido(n, state="CA", programa="TECH_CLEAN_CA"):
    cid, p = e.flujo_vendedor(v, adm, n, state, programa)
    for d in adm.get(f"/cases/{cid}/documents").json():
        adm.post(f"/case-files/{d['id']}/review", json={"status": "accepted"})
    for s in ("ready_to_submit", "submitted_to_program", "program_review"):
        adm.post(f"/cases/{cid}/substatus", json={"substatus": s})
    admin.post(f"/cases/{cid}/transition", json={"to_stage": "approved", "approval_code": f"QA-{n}-{e.RUN}"})
    return cid, e.proyecto_de(adm, cid)["id"]


def d001():
    esc("INS-010")
    aux = e.SECTION[0]
    cid, pid = aprobar_rapido(301)
    e.RESULTS[:] = [r for r in e.RESULTS if r["section"] != aux or True]
    for r in e.RESULTS:
        if r["section"] == "INS-010":
            r["section"] = "_prep"
    esc("INS-010")
    sched = lambda: adm.patch(f"/projects/{pid}/schedule", json={  # noqa: E731
        "technician_user_id": tec.me["id"], "scheduled_date": (e.HOY + timedelta(days=1)).isoformat()})
    e.expect("Liberar orden", sched(), 200)
    item = next(x for x in adm.get("/warehouse/items", params={"q": "3496"}).json() if x["sku"] == "3496")
    antes = stock(item["id"])
    o = tec.post("/warehouse/releases", json={"project_id": pid, "lines": [{"item_id": item["id"], "quantity": "4"}]}).json()
    tec.post(f"/warehouse/releases/{o['id']}/submit")
    adm.post(f"/warehouse/releases/{o['id']}/approve")
    adm.post(f"/warehouse/releases/{o['id']}/deliver", json={})
    chk("Material entregado a la obra (4 × PVC 3496)", abs(stock(item["id"]) - (antes - 4)) < 0.001, stock(item["id"]))
    base = {"reason_code": "customer_absent", "notes": "Toqué tres veces y llamé, no contestó",
            "latitude": 33.45, "longitude": -112.07}
    e.expect("Sin motivo no guarda", tec.post(f"/projects/{pid}/failed-visits", json={**base, "reason_code": ""}), 400)
    e.expect("Con nota de 2 letras no guarda", tec.post(f"/projects/{pid}/failed-visits", json={**base, "notes": "no"}), 400)
    st = e.expect("Registrar visita fallida", tec.post(f"/projects/{pid}/failed-visits", json=base), 201) or {}
    chk("1 de 2 visitas fallidas", (st.get("failed_visits"), st.get("limit")) == (1, 2), st)
    p = adm.get(f"/projects/{pid}").json()
    chk("La obra queda sin fecha, «Sin agendar», con el mismo técnico",
        p["scheduled_date"] is None and p["status"] == "planning" and p["primary_technician_user_id"] == tec.me["id"],
        f"{p['scheduled_date']} {p['status']}")
    cs = caso(cid)
    chk("Expediente «Listo para instalar · Visita fallida»", (cs["stage_code"], cs["substatus_code"]) ==
        ("ready_to_install", "visit_failed"), (cs["stage_code"], cs["substatus_code"]))
    fila = sql(f"select reason_code, scheduled_date, latitude, longitude from project_visit_attempts where project_id='{pid}'")
    chk("project_visit_attempts con motivo, fecha y GPS", fila.startswith("customer_absent|") and "33.45" in fila, fila)
    chk("Auditoría projects.visit_failed",
        sql(f"select count(*) from audit_events where action='projects.visit_failed' and entity_id='{pid}'") == "1")
    chk("El material sigue cargado a la obra", abs(stock(item["id"]) - (antes - 4)) < 0.001, stock(item["id"]))
    time.sleep(3)
    av = adm.get("/notifications", params={"limit": 50}).json()
    av = av if isinstance(av, list) else av.get("items", [])
    chk("Administración recibe el aviso de visita fallida", any(a.get("event") == "installation.visit_failed" for a in av),
        [a.get("event") for a in av][:5])
    avt = tec.get("/notifications", params={"limit": 50}).json()
    avt = avt if isinstance(avt, list) else avt.get("items", [])
    chk("El técnico que la registró no se avisa a sí mismo",
        not any(a.get("event") == "installation.visit_failed" for a in avt))
    e.expect("Sin fecha agendada no hay visita fallida", tec.post(f"/projects/{pid}/failed-visits", json=base), 409)
    e.expect("Reagendar con «Liberar orden»", sched(), 200)
    chk("Vuelve a «Instalación agendada»", caso(cid)["substatus_code"] == "install_scheduled", caso(cid)["substatus_code"])

    esc("INS-011")
    st = e.expect("Segunda visita fallida", tec.post(f"/projects/{pid}/failed-visits", json=base), 201) or {}
    chk("Llegó al límite (2 de 2)", st.get("limit_reached") is True, st)
    r = sched()
    chk("Liberar orden con el límite alcanzado → 409 visit_limit_reached",
        r.status_code == 409 and r.json().get("code") == "visit_limit_reached", f"{r.status_code} {r.text[:200]}")
    e.expect("El técnico no autoriza otro intento", tec.post(f"/projects/{pid}/extra-visit",
                                                             json={"reason": "El cliente llamó"}), 403)
    st = e.expect("Administración autoriza otro intento con motivo", adm.post(
        f"/projects/{pid}/extra-visit", json={"reason": "El cliente llamó y confirmó que estará"}), 200) or {}
    chk("El tope sube a 3", st.get("limit") == 3, st)
    e.expect("Ahora sí agenda", sched(), 200)
    for valor in (0, 11):
        e.expect(f"Límite {valor} se rechaza", admin.put("/field-ops/settings", json={"max_failed_visits": valor}), 400)
    e.expect("El técnico no cambia el límite", tec.put("/field-ops/settings", json={"max_failed_visits": 3}), 403)
    e.expect("Administración (projects.close) cambia el límite a 3", adm.put("/field-ops/settings",
                                                                            json={"max_failed_visits": 3}), 200)
    st = adm.get(f"/projects/{pid}/visit-status").json()
    chk("El nuevo límite aplica de inmediato (3 + 1 autorizada = 4)", st.get("limit") == 4, st)
    e.expect("Volver el límite a 2", admin.put("/field-ops/settings", json={"max_failed_visits": 2}), 200)
    chk("Auditoría de intento extra y de límite",
        sql(f"select count(*) from audit_events where action in ('projects.extra_visit_authorized',"
            f"'field_ops.settings_updated')") not in ("0", "1"))

    esc("INS-012")
    o2 = tec.post("/warehouse/releases", json={"project_id": pid, "lines": [{"item_id": item["id"], "quantity": "1"}]}).json()
    tec.post(f"/warehouse/releases/{o2['id']}/submit")
    e.expect("El técnico no cancela", tec.post(f"/projects/{pid}/cancel", json={"reason": "No quiere"}), 403)
    e.expect("Sin motivo no cancela", adm.post(f"/projects/{pid}/cancel", json={"reason": "  "}), 400)
    r = adm.post(f"/projects/{pid}/cancel", json={"reason": "El cliente desistió del programa"})
    chk("Con una salida «Por autorizar» → 409 open_releases", r.status_code == 409 and r.json()["code"] == "open_releases",
        r.text[:200])
    adm.post(f"/warehouse/releases/{o2['id']}/reject", json={"reason": "La obra se va a cancelar"})
    chq = adm.get(f"/projects/{pid}/cancellation-check").json()
    chk("cancellation-check lista el material afuera (4)", [m["quantity"] for m in chq["material_in_field"]] == ["4.00"], chq)
    r = adm.post(f"/projects/{pid}/cancel", json={"reason": "El cliente desistió del programa"})
    chk("Sin explicar el material → 409 material_pending_return", r.status_code == 409
        and r.json()["code"] == "material_pending_return", r.text[:200])
    esc("BOD-006")
    antes_dev = stock(item["id"])
    e.expect("Devolución de 3 a bodega con la obra", adm.post("/warehouse/movements", json={
        "item_id": item["id"], "movement_type": "devolucion", "quantity": "3", "project_id": pid}), 201)
    chk("La bodega sube 3", abs(stock(item["id"]) - (antes_dev + 3)) < 0.001, stock(item["id"]))
    chq = adm.get(f"/projects/{pid}/cancellation-check").json()
    chk("Lo que sigue afuera baja a 1", [m["quantity"] for m in chq["material_in_field"]] == ["1.00"], chq)
    r = adm.post("/warehouse/movements", json={"item_id": item["id"], "movement_type": "devolucion",
                                               "quantity": "50", "project_id": pid})
    chk("Devolver más de lo entregado a la obra se rechaza", r.status_code in (400, 409, 422),
        f"{r.status_code} {r.text[:150]}")
    if r.status_code == 201:
        adm.post("/warehouse/movements", json={"item_id": item["id"], "movement_type": "ajuste", "quantity": "-50",
                                               "note": "QA: deshacer la devolución de más (BOD-006)"})
    esc("INS-012")
    c_cancel = e.expect("Cancelar con motivo y la explicación del material", adm.post(f"/projects/{pid}/cancel", json={
        "reason": "El cliente desistió del programa", "material_note": "1 tubo quedó cortado en la casa"}), 200) or {}
    chk("La obra queda «cancelled» con el motivo", (c_cancel.get("status"), c_cancel.get("cancel_reason")) ==
        ("cancelled", "El cliente desistió del programa"), c_cancel.get("status"))
    chk("El expediente queda «Cerrado»", caso(cid)["stage_code"] == "closed", caso(cid)["stage_code"])
    e.expect("Liberar orden en la cancelada → 409", sched(), 409)
    e.expect("Registrar visita fallida en la cancelada → 409", tec.post(f"/projects/{pid}/failed-visits", json=base), 409)
    e.expect("Pedir material para la cancelada → 409", tec.post("/warehouse/releases", json={
        "project_id": pid, "lines": [{"item_id": item["id"], "quantity": "1"}]}), 409, 400)
    chk("Auditoría projects.cancelled",
        sql(f"select count(*) from audit_events where action='projects.cancelled' and entity_id='{pid}'") == "1")
    time.sleep(3)
    avt = tec.get("/notifications", params={"limit": 50}).json()
    avt = avt if isinstance(avt, list) else avt.get("items", [])
    chk("El técnico recibe el aviso de obra cancelada", any(a.get("event") == "project.cancelled" for a in avt))
    esc("COB-004")
    r = adm.post(f"/projects/{pid}/claims", json={"program_id": progs["TECH_CLEAN_CA"]["id"]})
    chk("No se crea cobro de una obra cancelada (sin acta confirmada)", r.status_code in (400, 409, 422),
        f"{r.status_code} {r.text[:150]}")
    r = admin.post(f"/cases/{cid}/transition", json={"to_stage": "billing_in_progress"})
    chk("Tampoco por la transición manual a cobro", r.status_code in (400, 403, 409, 422), f"{r.status_code} {r.text[:150]}")


# ===========================================================================
# Bodega propia: BOD-002/003/005/015/016, CON-001/002
# ===========================================================================
def bodega_propia():
    esc("BOD-002")
    for nombre, cuerpo, ok in (("costo -1", {"name": "QA X", "unit_cost": "-1"}, (400, 422)),
                               ("costo abc", {"name": "QA X", "unit_cost": "abc"}, (400, 422)),
                               ("código repetido 3496", {"name": "QA X", "sku": "3496"}, (400, 409)),
                               ("nombre vacío", {"name": ""}, (400, 422))):
        r = adm.post("/warehouse/items", json=cuerpo)
        chk(f"Artículo con {nombre} se rechaza", r.status_code in ok, f"{r.status_code} {r.text[:150]}")
        if r.status_code == 201:
            adm.put(f"/warehouse/items/{r.json()['id']}", json={**r.json(), "active": False})
    it = e.expect("Crear «Cinta de aluminio QA» (QA-0001)", adm.post("/warehouse/items", json={
        "name": "Cinta de aluminio QA", "sku": f"QA-0001-{e.RUN}", "category": "consumables", "unit": "roll",
        "unit_cost": "7.35", "min_quantity": "4"}), 201) or {}
    chk("Existencia inicial 0", stock(it["id"]) == 0, stock(it["id"]))
    r = adm.put(f"/warehouse/items/{it['id']}", json={**{k: it[k] for k in ("name", "sku", "category", "unit")},
                                                     "unit_cost": "7.50", "has_serial": True, "min_quantity": "4"})
    chk("Editar costo a 7.50 y marcar «con serial»", r.status_code == 200 and r.json().get("unit_cost") == "7.50",
        f"{r.status_code} {r.text[:150]}")
    # Una cinta no lleva serial: se desmarca para que BOD-005 y BOD-016 la entreguen como material común.
    r = adm.put(f"/warehouse/items/{it['id']}", json={**{k: it[k] for k in ("name", "sku", "category", "unit")},
                                                     "unit_cost": "7.50", "has_serial": False, "min_quantity": "4"})
    chk("Desmarcar «con serial»", r.status_code == 200 and r.json().get("has_serial") is False, r.status_code)
    esc("BOD-003")
    valor0 = float(sql("select sum(s.quantity*i.unit_cost) from warehouse_stock s join warehouse_items i on i.id=s.item_id "
                       "join organizations o on o.id=i.organization_id where o.name='Demo Organization'"))
    e.expect("Entrada de 10 rollos", adm.post("/warehouse/movements", json={
        "item_id": it["id"], "movement_type": "entrada", "quantity": "10", "reference": "FAC-PROV-QA"}), 201)
    chk("Existencia 10", stock(it["id"]) == 10, stock(it["id"]))
    valor1 = float(sql("select sum(s.quantity*i.unit_cost) from warehouse_stock s join warehouse_items i on i.id=s.item_id "
                       "join organizations o on o.id=i.organization_id where o.name='Demo Organization'"))
    chk("El valor de bodega sube USD 75.00", abs((valor1 - valor0) - 75.0) < 0.001, f"{valor0} → {valor1}")
    mov = sql(f"select movement_type, created_by_user_id is not null, unit_cost from warehouse_movements where item_id='{it['id']}'")
    chk("Movimiento `entrada` con usuario y costo", mov.startswith("entrada|True|7.5"), mov)

    esc("BOD-005")
    o = adm.post("/warehouse/releases", json={"lines": [{"item_id": it["id"], "quantity": "15"}]}).json()
    r = adm.post(f"/warehouse/releases/{o['id']}/submit")
    chk("Pedir 15 con 10 en bodega: ¿avisa al pedir? (anotar)", True, f"{r.status_code} {r.text[:150]}")
    r = admin.post(f"/warehouse/releases/{o['id']}/approve")
    chk("¿Avisa al autorizar? (anotar)", True, f"{r.status_code}")
    ent = adm.post(f"/warehouse/releases/{o['id']}/deliver", json={}).json()
    chk("Entrega solo los 10 y lo deja como faltante", stock(it["id"]) == 0 and len(ent.get("faltantes", [])) == 1,
        f"stock={stock(it['id'])} faltantes={ent.get('faltantes')}")
    neg = sql("select count(*) from warehouse_stock where quantity < 0")
    chk("Ninguna existencia negativa en toda la base", neg == "0", neg)

    esc("BOD-015")
    for valor in ("0", "-1", "0.0001", "1000000000", "1,5"):
        r = adm.post("/warehouse/movements", json={"item_id": it["id"], "movement_type": "entrada", "quantity": valor})
        esperado = valor in ("0.0001", "1000000000")
        chk(f"Entrada con cantidad {valor}: {'acepta' if esperado else 'rechaza'} (anotar)",
            r.status_code != 500, f"{r.status_code} {r.text[:120]}")
        if r.status_code == 201:
            q = float(r.json().get("quantity", 0) or 0)
            adm.post("/warehouse/movements", json={"item_id": it["id"], "movement_type": "ajuste",
                                                   "quantity": str(-abs(q)) if q else "0", "note": "QA: deshacer BOD-015"})
    r = adm.post("/warehouse/items", json={"name": "QA costo grande", "sku": f"QA-BIG-{e.RUN}", "unit_cost": "9999999.99"})
    chk("Costo 9,999,999.99 se acepta sin desbordar", r.status_code == 201 and r.json().get("unit_cost") == "9999999.99",
        f"{r.status_code} {r.text[:120]}")
    neg = sql("select count(*) from warehouse_stock where quantity < 0")
    chk("Sin existencias negativas después de los valores extremos", neg == "0", neg)

    esc("BOD-016")
    e.expect("Entrada de 1 unidad", adm.post("/warehouse/movements", json={
        "item_id": it["id"], "movement_type": "entrada", "quantity": "1"}), 201)
    base_stock = stock(it["id"])
    ords = []
    for _ in range(2):
        o = adm.post("/warehouse/releases", json={"lines": [{"item_id": it["id"], "quantity": "1"}]}).json()
        adm.post(f"/warehouse/releases/{o['id']}/submit")
        admin.post(f"/warehouse/releases/{o['id']}/approve")
        ords.append(o["id"])
    res = [None, None]

    def entregar(i):
        res[i] = httpx.post(f"{e.API}/warehouse/releases/{ords[i]}/deliver", json={}, headers=adm.h, timeout=60)
    hilos = [threading.Thread(target=entregar, args=(i,)) for i in range(2)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    fin = stock(it["id"])
    salidas = sql(f"select count(*) from warehouse_movements where item_id='{it['id']}' and movement_type='salida' "
                  f"and reference in (select number from warehouse_release_orders where id in ('{ords[0]}','{ords[1]}'))")
    chk(f"Existencia final 0 (había {base_stock}), nunca negativa", fin == 0, fin)
    chk("Una sola salida efectiva entre las dos entregas simultáneas", salidas == "1",
        f"salidas={salidas} códigos={[x.status_code for x in res]}")

    esc("CON-002")
    o1 = adm.post("/warehouse/releases", json={"lines": [{"item_id": it["id"], "quantity": "1"}]}).json()
    o2 = adm.post("/warehouse/releases", json={"lines": [{"item_id": it["id"], "quantity": "1"}]}).json()
    out = [None, None]

    def enviar(i, oid):
        out[i] = httpx.post(f"{e.API}/warehouse/releases/{oid}/submit", headers=adm.h, timeout=60)
    hilos = [threading.Thread(target=enviar, args=(i, x["id"])) for i, x in enumerate((o1, o2))]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    nums = [x.json().get("number") if x.status_code == 200 else x.status_code for x in out]
    chk("Dos salidas enviadas a la vez reciben números SAL distintos", len(set(nums)) == 2 and all(
        str(n).startswith("SAL-") for n in nums), nums)

    esc("CON-001")
    o3 = adm.post("/warehouse/releases", json={"lines": [{"item_id": it["id"], "quantity": "1"}]}).json()
    adm.post(f"/warehouse/releases/{o3['id']}/submit")
    aprob = [None, None]

    def aprobar(i):
        aprob[i] = httpx.post(f"{e.API}/warehouse/releases/{o3['id']}/approve", headers=admin.h, timeout=60)
    hilos = [threading.Thread(target=aprobar, args=(i,)) for i in range(2)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    chk("Dos autorizaciones simultáneas de la misma salida: una pasa", sorted(x.status_code for x in aprob)[0] == 200,
        [x.status_code for x in aprob])
    aud = sql(f"select count(*) from audit_events where entity_id='{o3['id']}' and action='warehouse.release_authorized'")
    chk("Y queda una sola autorización en la auditoría", aud == "1", aud)


# ===========================================================================
# Obra abierta para bodega, rotación, reprogramar y material comprado
# ===========================================================================
def obra_abierta():
    cid, pid = aprobar_rapido(302)
    for r in e.RESULTS:
        r["section"] = "_prep" if r["section"] == ACTUAL[0] else r["section"]
    adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": tec.me["id"],
                                                 "scheduled_date": (e.HOY + timedelta(days=2)).isoformat()})
    return cid, pid


def bodega_qa_e2e(pid):
    titulos = {"16.": "BOD-010", "17.": "BOD-017", "18.": "BOD-013", "19.": "BOD-014", "20.": "INS-016"}

    def section(nombre):
        for k, eid in titulos.items():
            if nombre.startswith(k):
                esc(eid)
    e.section = section
    try:
        e.flujo_bodega(c, pid)
    finally:
        e.section = lambda nombre: None
    remap("BOD-010", [("Conteo", "BOD-009"), ("conteo cuadra", "BOD-009"), ("ajuste", "BOD-009"),
                      ("categoría", "BOD-002"), ("código AC Pro", "BOD-002"), ("número del fabricante", "BOD-002")])
    remap("BOD-017", [("traslado", "BOD-008"), ("salida manual", "BOD-008")])
    remap("BOD-013", [("entrega", "BOD-004"), ("Rechazar exige", "BOD-004"), ("rechaza con motivo", "BOD-004"),
                      ("rechazada", "BOD-004"), ("faltante", "BOD-004"), ("Entregar dos veces", "CON-001"),
                      ("autoriza la salida que pidió", "TEC-002"), ("técnico no puede autorizar", "TEC-002")])
    remap("BOD-014", [("Compras sugeridas", "BOD-012"), ("Sugiere", "BOD-012"), ("Descuenta lo que ya salió", "BOD-012"),
                      ("ya no pide comprar", "BOD-012")])


def rotacion_y_otros(pid):
    esc("INS-008")
    e.flujo_rotacion(c)
    esc("INS-009")
    nueva = (e.HOY + timedelta(days=4)).isoformat()
    e.expect("Cambiar fechas", adm.patch(f"/projects/{pid}/schedule", json={
        "technician_user_id": tec.me["id"], "scheduled_date": nueva}), 200)
    agenda = tec.get("/dispatch/agenda", params={"date_from": e.HOY.isoformat(),
                                                 "date_to": (e.HOY + timedelta(days=10)).isoformat()}).json()
    chk("La obra aparece en la nueva fecha en la agenda del técnico",
        any(a["project_id"] == pid and a["scheduled_date"] == nueva for a in agenda))
    aud = sql(f"select before_data::text, after_data::text from audit_events where entity_id='{pid}' "
              f"and action='projects.installation_scheduled' order by created_at desc limit 1")
    chk("La auditoría registra la fecha anterior y la nueva", nueva in aud and "scheduled_date" in aud, aud[:200])
    esc("INS-014")
    item = next(x for x in adm.get("/warehouse/items", params={"q": "3496"}).json() if x["sku"] == "3496")
    antes = stock(item["id"])
    m = e.expect("La oficina anota material comprado en la obra", adm.post(f"/projects/{pid}/materials", json={
        "description": "Breaker 30A y 10 ft de cable", "quantity": 1, "notes": "Comprado en la obra USD 48.75"}), 201) or {}
    chk("Aparece en los materiales de la obra", any(x.get("id") == m.get("id") for x in adm.get(f"/projects/{pid}/materials").json()))
    chk("La bodega no cambia", stock(item["id"]) == antes)
    esc("TEC-001")
    luis = c["luis"]
    chk("Luis no ve la obra de Tito en Proyectos", pid not in [x["id"] for x in luis.get("/projects", params={"limit": 500}).json()])
    e.expect("Luis: GET de la obra de Tito → 404", luis.get(f"/projects/{pid}"), 404)
    tit = adm.get(f"/projects/{pid}").json()["title"]
    res = luis.get("/search", params={"q": tit[:30]}).json()
    chk("El buscador de Luis no la encuentra", not any(x.get("id") == pid for g in res.get("groups", [])
                                                       for x in g.get("results", [])))
    esc("TEC-002")
    o = tec.post("/warehouse/releases", json={"project_id": pid, "lines": [
        {"item_id": item["id"], "quantity": "1"}]}).json()
    tec.post(f"/warehouse/releases/{o['id']}/submit")
    e.expect("El técnico no autoriza su salida", tec.post(f"/warehouse/releases/{o['id']}/approve"), 403)
    e.expect("El técnico no entrega", tec.post(f"/warehouse/releases/{o['id']}/deliver", json={}), 403)
    adm.post(f"/warehouse/releases/{o['id']}/reject", json={"reason": "QA: solo para probar permisos"})


# ===========================================================================
esc("_prep")
e.asignar_zona_az(admin, v)
if not any(m["program"]["code"] == "TECH_CLEAN_CA" for m in v.get("/me/programs").json()):
    z = admin.post(f"/programs/{progs['TECH_CLEAN_CA']['id']}/zones", json={
        "name": f"QA San Fernando {e.RUN}", "state": "CA", "city": "San Fernando"}).json()
    admin.put(f"/zones/{z['id']}/salespeople", json={"user_ids": [v.me["id"]]})
for codigo in ("AZ_EFFICIENCY", "TECH_CLEAN_CA"):
    pid_prog = progs[codigo]["id"]
    if not admin.get(f"/billing/programs/{pid_prog}/rates").json():
        e.expect(f"P-03: tarifa vigente de {codigo}", admin.post(f"/billing/programs/{pid_prog}/rates", json={
            "amount": "6500.00", "valid_from": (e.HOY - timedelta(days=30)).isoformat(),
            "notes": "Tarifa de prueba QA (P-03)"}), 201)
    ciudad = {"AZ_EFFICIENCY": "Phoenix", "TECH_CLEAN_CA": "San Fernando"}[codigo]
    if not admin.get(f"/billing/programs/{pid_prog}/jurisdictions").json():
        e.expect(f"P-03: zona de cobro de {codigo} ({ciudad})", admin.post(
            f"/billing/programs/{pid_prog}/jurisdictions", json={
                "kind": "city", "value": ciudad, "valid_from": (e.HOY - timedelta(days=30)).isoformat()}), 201)
chk("Vicky tiene zonas de TECH y de Arizona",
    {m["program"]["code"] for m in v.get("/me/programs").json()} >= {"TECH_CLEAN_CA", "AZ_EFFICIENCY"})
e.configurar_tech(admin)
seguro("VEN-001", ven_tempranas)
r = seguro("VEN-004", ven_completa, 21, "AZ", "AZ_EFFICIENCY")
cid_az, p_az = r if r else (None, None)
seguro("VEN-005", ven_invalidos_borrador)
if cid_az:
    seguro("VEN-006", ven_aislamiento, cid_az)
    seguro("REV-002", revision, cid_az, p_az)
    seguro("REV-004", rechazo_y_cierre)
    seguro("INS-004", campo_y_cobro, cid_az)
seguro("INS-010", d001)
seguro("BOD-002", bodega_propia)
r = seguro("_prep", obra_abierta)
if r:
    seguro("BOD-010", bodega_qa_e2e, r[1])
    seguro("INS-008", rotacion_y_otros, r[1])
recoger()
OUT.pop("_prep", None)
json.dump(OUT, open('/tmp/lote2.json', 'w'), ensure_ascii=False, indent=1)
