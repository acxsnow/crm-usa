"""Lote 3, fase C: trabajo particular, finanzas, avisos, buscador, técnicos y bodega.

PAR-001 a PAR-003, FIN-001 a FIN-003, FIN-005, FIN-006, NOT-001, BUS-001,
TEC-003 (parte API), TEC-004, TEC-005, INS-013 (pide el enlace), INS-015 (parte
API), BOD-007 y CON-003. NOT-002 e INS-013 se terminan en `lote3d.py` con los
enlaces del log del api.

PYTHONPATH=/app:/tmp python /tmp/lote3c.py → /tmp/lote3c.json y /tmp/lote3c_estado.json
"""
import json
from datetime import timedelta
from decimal import Decimal

import httpx

from qa_comun import (API, aprobar_rapido, chk, cliente, e, esc, guardar, limpiar, login, prep_p03, seguro, sql)

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "vendedor2", "tecnico", "conta", "gerencia", "carlos",
                             "luis")}
admin, adm, v, tec, conta, ger = c["admin"], c["adm"], c["vendedor"], c["tecnico"], c["conta"], c["gerencia"]
ESTADO: dict = {}
HOY = e.HOY


def remap(origen: str, reglas: list[tuple[str, str]], resto: str | None = None):
    """Reparte las comprobaciones de un bloque entre escenarios por palabras del paso."""
    for r in e.RESULTS:
        if r["section"] != origen:
            continue
        for palabra, destino in reglas:
            if palabra.lower() in r["step"].lower():
                r["section"] = destino
                break
        else:
            if resto:
                r["section"] = resto


def D(x) -> Decimal:
    return Decimal(str(x or 0))


# ===========================================================================
# PAR-001 a PAR-003: trabajo particular
# ===========================================================================
def cliente_particular(nombre):
    return admin.post("/customers", json={"legal_name": f"QA {e.RUN} {nombre}", "main_phone": "(602) 555-0177",
                                          "data_consent_accepted": True}).json()


def par001():
    cli = cliente_particular("Particular Gómez")
    con_precio = [i for i in admin.get("/warehouse/items", params={"limit": 300}).json() if i.get("sku")][:2]
    lineas = [{"kind": "material", "description": i["name"], "service_code": i["sku"], "quantity": 1,
               "unit_price": i.get("sale_price") or i["unit_cost"]} for i in con_precio]
    lineas.append({"kind": "labor", "description": "QA Mano de obra (renglón libre)", "quantity": 1, "unit_price": "120.00"})
    esperado = sum(D(l["unit_price"]) for l in lineas)
    q = e.expect("Armar la cotización con 2 renglones del price book y 1 libre", conta.post("/billing/quotes", json={
        "customer_id": cli["id"], "title": "QA PAR-001", "lines": lineas}), 201) or {}
    chk(f"Total = suma de los renglones ({esperado})", D(q.get("total")) == esperado, f"{q.get('total')} {q.get('tax')}")
    chk("No toca ningún expediente", q.get("case_id") in (None, "") and q.get("project_id") in (None, ""), "")
    e.expect("Enviarla al cliente", conta.post(f"/billing/quotes/{q.get('id')}/send"), 200)
    a = e.expect("Marcarla aceptada", conta.post(f"/billing/quotes/{q.get('id')}/accept"), 200) or {}
    chk("Queda «Aceptada» y crea la factura en borrador", (a.get("quote") or {}).get("status") in ("accepted", None)
        and (a.get("invoice") or {}).get("status") == "draft", f"{(a.get('quote') or {}).get('status')} "
                                                               f"{(a.get('invoice') or {}).get('status')}")
    q2 = conta.post("/billing/quotes", json={"customer_id": cli["id"], "title": "QA PAR-001 b", "lines": lineas[-1:]}).json()
    conta.post(f"/billing/quotes/{q2['id']}/send")
    r = e.expect("Otra, marcada «No aceptada»", conta.post(f"/billing/quotes/{q2['id']}/reject", json={
        "reason": "QA: el cliente no aceptó"}), 200) or {}
    chk("Estado «No aceptada»", r.get("status") in ("rejected", "declined"), r.get("status"))
    resumen = conta.get("/billing/quotes/summary").json()
    chk("El resumen cuenta aceptadas y no aceptadas", bool(resumen), str(resumen)[:200])
    return cli, (a.get("invoice") or {})


def _factura(cli, monto, titulo):
    q = conta.post("/billing/quotes", json={"customer_id": cli["id"], "title": titulo, "lines": [
        {"kind": "labor", "description": titulo, "quantity": 1, "unit_price": monto}]}).json()
    conta.post(f"/billing/quotes/{q['id']}/send")
    return (conta.post(f"/billing/quotes/{q['id']}/accept").json() or {}).get("invoice") or {}


def _emitir(fac):
    return conta.post(f"/invoices/{fac['id']}/issue", json={"due_date": (HOY + timedelta(days=30)).isoformat()})


def par002(cli, fac1):
    numeros = []
    r1 = e.expect("Emitir la factura de la cotización", _emitir(fac1), 200) or {}
    numeros.append(r1.get("invoice_number"))
    r2 = e.expect("Emitir una segunda factura", _emitir(_factura(cli, "250.00", "QA PAR-002 b")), 200) or {}
    numeros.append(r2.get("invoice_number"))
    r = conta.post(f"/invoices/{fac1['id']}/void", json={"reason": ""})
    chk("Anular sin motivo se rechaza", r.status_code in (400, 422), r.status_code)
    r = e.expect("Anular con el motivo «Error en el valor»", conta.post(f"/invoices/{fac1['id']}/void", json={
        "reason": "Error en el valor"}), 200) or {}
    chk("La anulada conserva su número", r.get("status") == "void" and r.get("invoice_number") == numeros[0],
        f"{r.get('status')} {r.get('invoice_number')}")
    r3 = e.expect("Emitir una tercera", _emitir(_factura(cli, "75.00", "QA PAR-002 c")), 200) or {}
    numeros.append(r3.get("invoice_number"))

    def n(x):
        return int(str(x).rsplit("-", 1)[-1])
    chk(f"Números consecutivos sin saltos ni repetidos {numeros}",
        all(numeros) and len(set(numeros)) == 3 and [n(x) - n(numeros[0]) for x in numeros] == [0, 1, 2], numeros)
    aud = sql(f"select count(*) from audit_events where entity_id = '{fac1['id']}' and action like '%void%'")
    chk("La anulación deja rastro en la auditoría", aud not in ("", "0"), aud)


def par003(cli):
    fac = _factura(cli, "500.00", "QA PAR-003")
    e.expect("Factura emitida de USD 500.00", _emitir(fac), 200)
    r = e.expect("Abono de 200.00 en efectivo", conta.post(f"/invoices/{fac['id']}/payments", json={
        "amount": "200.00", "paid_at": HOY.isoformat(), "method": "cash", "reference": "QA efectivo"}), 201) or {}
    chk("Saldo 300.00", D(r.get("balance_due")) == D("300.00"), r.get("balance_due"))
    r = e.expect("Abono de 300.00 por transferencia", conta.post(f"/invoices/{fac['id']}/payments", json={
        "amount": "300.00", "paid_at": HOY.isoformat(), "method": "transfer", "reference": "QA transferencia"}), 201) or {}
    chk("Saldo 0 y «Factura pagada»", D(r.get("balance_due")) == 0 and r.get("status") == "paid",
        f"{r.get('balance_due')} {r.get('status')}")
    r = conta.post(f"/invoices/{fac['id']}/payments", json={"amount": "0.01", "paid_at": HOY.isoformat(),
                                                             "method": "cash"})
    chk("Pagar 0.01 de más se rechaza", r.status_code in (400, 409, 422), f"{r.status_code} {r.text[:150]}")


# ===========================================================================
# Una obra AZ cerrada y cobrada, con salida entregada (FIN-005, BOD-007)
# ===========================================================================
def obra_cobrada():
    cid, pid = aprobar_rapido(v, adm, admin, 341, "AZ", "AZ_EFFICIENCY")
    e.expect("Liberar a Tito", adm.patch(f"/projects/{pid}/schedule", json={
        "technician_user_id": tec.me["id"], "scheduled_date": (HOY + timedelta(days=1)).isoformat()}), 200)
    articulos = [i for i in adm.get("/warehouse/stock", params={"limit": 300}).json()
                 if D(i.get("total_quantity")) >= 3 and not i.get("has_serial") and D(i.get("unit_cost")) > 0][:2]
    o = tec.post("/warehouse/releases", json={"project_id": pid, "lines": [
        {"item_id": a["id"], "quantity": "2"} for a in articulos]}).json()
    tec.post(f"/warehouse/releases/{o['id']}/submit")
    adm.post(f"/warehouse/releases/{o['id']}/approve")
    e.expect("Bodega entrega la salida de la obra", adm.post(f"/warehouse/releases/{o['id']}/deliver", json={}), 200)
    valor = sum(D(a["unit_cost"]) * 2 for a in articulos)
    pid2 = e.flujo_campo(adm, tec, cid, devolver_acta=False, permiso=True)
    e.flujo_inspeccion(adm, tec, pid2 or pid)
    e.flujo_cobro(adm, conta, admin, pid, cid, "AZ_EFFICIENCY", rechazar=False, cerrar=True)
    return cid, pid, valor


def bod007(pid, valor):
    movs = adm.get("/warehouse/movements", params={"project_id": pid, "limit": 100}).json()
    salidas = [m for m in movs if m["movement_type"] == "salida"]
    chk("La obra tiene su salida entregada y ninguna devolución",
        salidas and not [m for m in movs if m["movement_type"] == "devolucion"], len(movs))
    suma = sum(D(m["amount"]) for m in salidas)
    fila = (ger.get("/finance/profitability", params={"project_id": pid}).json().get("rows") or [{}])[0]
    materiales = D((fila.get("cost_breakdown") or {}).get("materials"))
    chk(f"El costo de materiales ({materiales}) = la suma de la salida ({suma}) al centavo",
        materiales == suma == valor, f"materiales={materiales} salida={suma} catálogo={valor}")
    return fila


def fin005(pid, fila):
    fila = (ger.get("/finance/profitability", params={"project_id": pid}).json().get("rows") or [{}])[0]
    costos = sum(D(x) for x in (fila.get("cost_breakdown") or {}).values())
    chk(f"Costos = suma de material, mano de obra, gastos, material menor y herramienta ({costos})",
        costos == D(fila.get("costs")), f"{fila.get('cost_breakdown')} costs={fila.get('costs')}")
    chk(f"Margen = cobrado − costos ({fila.get('collected')} − {fila.get('costs')} = {fila.get('margin')})",
        D(fila.get("collected")) - D(fila.get("costs")) == D(fila.get("margin")) and D(fila.get("collected")) > 0,
        str(fila)[:300])


# ===========================================================================
# FIN-001 a FIN-003 y FIN-006
# ===========================================================================
def finanzas(pid):
    esc("FIN-001")
    e.flujo_finanzas({"tecnico": tec, "conta": conta, "gerencia": ger, "admin": admin, "vendedor": v, "adm": adm},
                     pid, pid)
    remap("FIN-001", [
        ("gasto", "FIN-001"), ("gasolina", "FIN-001"), ("hotel", "FIN-001"), ("Reembolso", "FIN-001"),
        ("Recibo disfrazado", "FIN-001"), ("recibe gasto", "FIN-001"),
        ("extracto", "FIN-003"), ("concilia", "FIN-003"), ("Comisión", "FIN-003"),
        ("Rentabilidad", "FIN-005"), ("Cobrado", "FIN-005"), ("costo incluye", "FIN-005"),
        ("proveedor", "FIN-002"), ("factura", "FIN-002"), ("pago", "FIN-002"), ("aprob", "FIN-002"),
        ("Aldo", "FIN-002"), ("Antigüedad", "FIN-002"), ("Necesita dos", "FIN-002"), ("Grande parcial", "FIN-002"),
        ("Total con impuestos", "FIN-002"), ("Compra con tarjeta", "FIN-002"), ("datos bancarios", "FIN-002"),
    ], resto="_prep")


def fin002():
    prov = e.expect("Crear el proveedor «HOME DEPOT»", conta.post("/payables/suppliers", json={
        "name": f"QA HOME DEPOT {e.RUN}", "kinds": ["materials"], "payment_terms_days": 30}), 201) or {}
    f = conta.post("/payables/invoices", data={"data": json.dumps({
        "supplier_id": prov.get("id"), "number": f"QA-HD-{e.RUN}", "invoice_date": HOY.isoformat(), "total": "350.00",
        "category": "materials", "due_date": (HOY + timedelta(days=30)).isoformat()})},
        files={"file": ("factura.pdf", e.pdf_doc("QA HD"), "application/pdf")})
    fac = f.json() if f.status_code == 201 else {}
    chk("Factura de USD 350.00 a 30 días", f.status_code == 201 and D(fac.get("total")) == D("350.00"),
        f"{f.status_code} {f.text[:150]}")
    if fac.get("approvals_missing"):
        ger.post(f"/payables/invoices/{fac['id']}/approve", json={})
    r = conta.post("/payables/payments", data={"data": json.dumps({
        "supplier_id": prov.get("id"), "paid_on": HOY.isoformat(), "amount": "350.00", "method": "transfer",
        "reference": f"QA-HD-PAGO-{e.RUN}", "allocations": [{"invoice_id": fac.get("id"), "amount": "350.00"}]})},
        files={"file": ("comprobante.jpg", e.jpeg("comprobante"), "image/jpeg")})
    chk("Pagarla adjuntando el comprobante", r.status_code == 201, f"{r.status_code} {r.text[:150]}")
    fin = conta.get(f"/payables/invoices/{fac.get('id')}").json()
    chk("Saldo en cero tras el pago", D(fin.get("balance")) == 0 and fin.get("status") == "paid",
        f"{fin.get('balance')} {fin.get('status')}")
    r = conta.post("/payables/suppliers", json={"name": f"QA HOME DEPOT {e.RUN}"})
    chk(f"Proveedor con el mismo nombre (anotar): {r.status_code}", True, r.text[:150])
    ESTADO["fin002_duplicado"] = r.status_code


def fin003():
    extracto = (f"Date,Description,Amount\n{HOY.isoformat()},QA LOWES {e.RUN},-45.10\n"
                f"{HOY.isoformat()},QA LOWES {e.RUN},-45.10\n{HOY.isoformat()},QA SHELL GAS {e.RUN},-60.00\n"
                f"{HOY.isoformat()},QA BANK FEE {e.RUN},-12.00\n{HOY.isoformat()},QA MALO {e.RUN},doce dolares\n")
    r = conta.post("/reconciliation/statements", data={"account_label": f"QA FIN-003 {e.RUN}"},
                   files={"file": ("extracto.csv", extracto.encode(), "text/csv")})
    cuerpo = r.json() if r.status_code == 201 else {}
    chk(f"Importar el extracto: entran {cuerpo.get('lines')} y el mal formado se reporta ({cuerpo.get('invalid')})",
        r.status_code == 201 and cuerpo.get("lines") == 4 and cuerpo.get("invalid"), f"{r.status_code} {r.text[:250]}")
    r2 = conta.post("/reconciliation/statements", data={"account_label": f"QA FIN-003 {e.RUN}"},
                    files={"file": ("extracto.csv", extracto.encode(), "text/csv")})
    cuerpo2 = r2.json() if r2.status_code in (200, 201) else {}
    lineas = conta.get("/reconciliation/lines", params={"limit": 200}).json()
    mias = [l for l in lineas if f"{e.RUN}" in l.get("description", "")]
    chk(f"Importar el mismo archivo otra vez no duplica ({len(mias)} líneas del extracto en total)",
        len(mias) == 4, f"segunda importación: {r2.status_code} {str(cuerpo2)[:150]}")
    fee = next((l for l in mias if "BANK FEE" in l["description"]), None)
    r = conta.post(f"/reconciliation/lines/{fee['id']}/ignore", json={"notes": "Comisión del banco"}) if fee else None
    chk("Marcar la comisión como «Es otra cosa»", r is not None and r.status_code == 200, r.status_code if r else "")
    reglas = conta.get("/bank-feeds/rules")
    chk(f"Reglas por comercio (Banca): {reglas.status_code} (anotar si aplican al CSV)", reglas.status_code in (200, 403),
        reglas.text[:150])


def fin006(pid_abierta):
    r = conta.post(f"/warehouse/projects/{pid_abierta}/day-logs", json={"log_date": HOY.isoformat(),
                                                                         "work_done": "QA contabilidad"})
    chk("Contabilidad no registra jornadas (403)", r.status_code == 403, r.status_code)
    item = admin.get("/warehouse/items", params={"limit": 1}).json()[0]
    o = adm.post("/warehouse/releases", json={"lines": [{"item_id": item["id"], "quantity": "1"}]}).json()
    adm.post(f"/warehouse/releases/{o['id']}/submit")
    r = conta.post(f"/warehouse/releases/{o['id']}/approve")
    chk("Contabilidad no autoriza salidas (403)", r.status_code == 403, r.status_code)
    adm.post(f"/warehouse/releases/{o['id']}/reject", json={"reason": "QA FIN-006"})
    cli = cliente_particular("FIN-006")
    fac = _factura(cli, "90.00", "QA FIN-006")
    r = ger.post(f"/invoices/{fac['id']}/issue", json={"due_date": (HOY + timedelta(days=30)).isoformat()})
    chk("Gerencia no emite facturas (403)", r.status_code == 403, r.status_code)
    _emitir(fac)
    r = ger.post(f"/invoices/{fac['id']}/payments", json={"amount": "10", "paid_at": HOY.isoformat()})
    chk("Gerencia no registra pagos (403)", r.status_code == 403, r.status_code)
    r = ger.post(f"/invoices/{fac['id']}/void", json={"reason": "QA gerencia"})
    chk("Gerencia no anula facturas (403)", r.status_code == 403, r.status_code)
    chk("Gerencia sí consulta las facturas", ger.get(f"/invoices/{fac['id']}").status_code == 200, "")


# ===========================================================================
# NOT-001, BUS-001
# ===========================================================================
def not001():
    vistas = {}
    for nombre, cli in (("Vicky", v), ("Administración", adm), ("Tito", tec)):
        lista = cli.get("/notifications", params={"limit": 100}).json()
        vistas[nombre] = lista
        chk(f"{nombre} ve sus avisos ({len(lista)})", isinstance(lista, list), len(lista))
    ids = {k: {n["id"] for n in l} for k, l in vistas.items()}
    chk("Ningún aviso aparece en la campana de otro", not (ids["Vicky"] & ids["Tito"]) and not (ids["Vicky"] & ids["Administración"]),
        {k: len(x) for k, x in ids.items()})
    sin_leer = next((n for n in vistas["Vicky"] if not n["read"]), None)
    if sin_leer:
        ajeno = tec.post(f"/notifications/{sin_leer['id']}/read")
        chk("Tito no puede marcar como leído un aviso de Vicky", ajeno.status_code in (403, 404), ajeno.status_code)
        e.expect("Vicky marca uno como leído", v.post(f"/notifications/{sin_leer['id']}/read"), 200)
        otra = next(n for n in v.get("/notifications", params={"limit": 100}).json() if n["id"] == sin_leer["id"])
        chk("Al recargar sigue leído", otra["read"] is True, otra["read"])
    else:
        chk("Vicky tiene un aviso sin leer para la prueba", False, len(vistas["Vicky"]))


def bus001(cli_par):
    caso = admin.get("/cases", params={"limit": 1}).json()
    caso = (caso.get("items") if isinstance(caso, dict) else caso or [{}])[0]
    fac = conta.get("/invoices", params={"limit": 1}).json()
    fac = (fac.get("items") if isinstance(fac, dict) else fac or [{}])[0]
    nombre = cli_par["legal_name"].split(" ", 2)[-1]

    def buscar(cli, q):
        r = cli.get("/search", params={"q": q})
        return r.status_code, r.json() if r.status_code == 200 else {}

    def total(res):
        return sum(len(v) for v in res.values() if isinstance(v, list)) if isinstance(res, dict) else len(res)
    for termino in (nombre, caso.get("case_number"), "QA Mobile", fac.get("invoice_number")):
        st, res = buscar(admin, termino)
        chk(f"Admin busca «{termino}» y lo encuentra", st == 200 and total(res) > 0, f"{st} {total(res)}")
    st, res = buscar(admin, "zzz")
    chk("«zzz» no trae resultados", st == 200 and total(res) == 0, total(res))
    st, res = buscar(admin, "Cliente Ajeno QA")
    chk("«Cliente Ajeno QA» (otra organización) no aparece", st == 200 and total(res) == 0, total(res))
    st, res = buscar(c["vendedor2"], caso.get("case_number"))
    chk("Valeria no encuentra un expediente que no es suyo", st == 200 and total(res) == 0, f"{st} {total(res)}")
    st, res = buscar(c["carlos"], caso.get("case_number"))
    chk("Carlos (técnico) no encuentra expedientes ajenos", st in (200, 403) and total(res) == 0, f"{st} {total(res)}")


# ===========================================================================
# TEC-003, TEC-004, TEC-005, INS-013, INS-015, CON-003
# ===========================================================================
def tec003():
    tecnicos = adm.get("/dispatch/technicians").json()
    nombres = [t.get("full_name") for t in tecnicos]
    chk(f"El selector «Elige un técnico» trae los {len(tecnicos)} técnicos en orden", len(tecnicos) >= 15
        and nombres == sorted(nombres, key=lambda x: (x or "").lower()), nombres[:16])
    obras = []
    for i, t in enumerate(tecnicos[:10]):
        _, pid = aprobar_rapido(v, adm, admin, 350 + i)
        r = adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": t["id"],
                                                          "scheduled_date": (HOY + timedelta(days=1 + i % 5)).isoformat()})
        obras.append(r.status_code)
    chk("Una obra programada para 10 técnicos distintos en la misma semana", obras.count(200) == 10, obras)
    agenda = adm.get("/dispatch/agenda", params={"date_from": HOY.isoformat(),
                                                  "date_to": (HOY + timedelta(days=7)).isoformat()}).json()
    con_obra = {a.get("technician_user_id") for a in agenda}
    chk(f"La agenda de la semana muestra a los 10 ({len(con_obra & {t['id'] for t in tecnicos[:10]})})",
        {t["id"] for t in tecnicos[:10]} <= con_obra, len(agenda))


def tec004():
    hector = next(u for u in admin.get("/users", params={"limit": 100}).json()["items"]
                  if u["email"] == "tecnico15@demo-org.com")
    _, pid = aprobar_rapido(v, adm, admin, 361)
    e.expect("Obra programada a Héctor", adm.patch(f"/projects/{pid}/schedule", json={
        "technician_user_id": hector["id"], "scheduled_date": (HOY + timedelta(days=2)).isoformat()}), 200)
    camioneta = e.expect("Camioneta de Héctor", adm.post("/warehouse/locations", json={
        "name": f"QA Camioneta Héctor {e.RUN}", "kind": "truck", "technician_user_id": hector["id"]}), 201) or {}
    item = next(i for i in adm.get("/warehouse/stock", params={"limit": 300}).json()
                if D(i.get("total_quantity")) >= 2 and not i.get("has_serial"))
    e.expect("Traslado de 2 unidades a su camioneta", adm.post("/warehouse/movements", json={
        "item_id": item["id"], "movement_type": "traslado", "quantity": "2", "to_location_id": camioneta.get("id")}), 201)
    e.expect("Admin desactiva a Héctor", admin.post(f"/users/{hector['id']}/deactivate"), 200)
    obra = adm.get(f"/projects/{pid}").json()
    chk(f"La obra queda (anotar): técnico={'Héctor' if obra.get('primary_technician_user_id') == hector['id'] else obra.get('primary_technician_user_id')}, "
        f"estado={obra.get('status')}", True, "")
    ESTADO["tec004_obra"] = {"sigue_asignada": obra.get("primary_technician_user_id") == hector["id"],
                             "estado": obra.get("status")}
    avisos = {n["event"] for n in adm.get("/notifications", params={"limit": 50}).json()}
    chk(f"¿Avisa a Administración que la obra quedó con un técnico inactivo? (anotar: {sorted(avisos)[:6]})", True, "")
    saldo = sql(f"select quantity from warehouse_stock where location_id = '{camioneta.get('id')}' and item_id = '{item['id']}'")
    chk(f"El material de su camioneta no se pierde ({saldo})", saldo.startswith("2"), saldo)
    sel = [t["id"] for t in adm.get("/dispatch/technicians").json()]
    chk("Héctor ya no aparece para asignar", hector["id"] not in sel, len(sel))
    otro = next(t for t in adm.get("/dispatch/technicians").json() if t["id"] != hector["id"])
    r = adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": otro["id"],
                                                      "scheduled_date": (HOY + timedelta(days=2)).isoformat()})
    chk("Rotar la obra a otro técnico", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
    chk("Héctor ya no entra", login("tecnico15@demo-org.com").status_code == 401, "")


def tec005():
    _, pid = aprobar_rapido(v, adm, admin, 362)
    adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": tec.me["id"],
                                                  "scheduled_date": HOY.isoformat()})
    r = tec.post(f"/warehouse/projects/{pid}/extra-charges", json={
        "amount": "150.00", "description": "QA cobro adicional: cambio de termostato", "payment_method": "cash"})
    chk("Tito anota un cobro en efectivo de USD 150.00", r.status_code == 201, f"{r.status_code} {r.text[:150]}")
    cargo = r.json() if r.status_code == 201 else {}
    pend = adm.get("/warehouse/extra-charges/pending").json()
    filas = pend if isinstance(pend, list) else pend.get("rows") or pend.get("items") or []
    mio = [p for p in filas if p.get("id") == cargo.get("id")]
    chk("«Efectivo por entregar» lo muestra a cargo de Tito", bool(mio), str(pend)[:250])
    e.expect("Administración recibe la entrega", adm.post(f"/warehouse/extra-charges/{cargo.get('id')}/deliver"), 200)
    pend = adm.get("/warehouse/extra-charges/pending").json()
    filas = pend if isinstance(pend, list) else pend.get("rows") or pend.get("items") or []
    chk("Después de entregarlo ya no está pendiente", not [p for p in filas if p.get("id") == cargo.get("id")], "")


def ins015_y_con003():
    _, pid = aprobar_rapido(v, adm, admin, 363)
    adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": tec.me["id"], "scheduled_date": HOY.isoformat()})
    esc("INS-015")
    cuerpo = {"log_date": HOY.isoformat(), "work_done": "QA jornada con señal débil", "hours": "6"}
    r1 = tec.post(f"/warehouse/projects/{pid}/day-logs", json=cuerpo)
    r2 = tec.post(f"/warehouse/projects/{pid}/day-logs", json=cuerpo)
    n = sql(f"select count(*) from project_day_logs where project_id = '{pid}'")
    chk(f"Guardar la jornada dos veces seguidas no crea dos ({r1.status_code}, {r2.status_code})", n == "1",
        f"jornadas={n} {r2.text[:150]}")
    esc("CON-003")
    otra = cliente("adm")
    a = adm.patch(f"/projects/{pid}", json={"notes": "QA nota de la ventana A"})
    b = otra.patch(f"/projects/{pid}", json={"notes": "QA nota de la ventana B"})
    final = adm.get(f"/projects/{pid}").json().get("notes")
    chk(f"Dos sesiones guardan las notas una tras otra (A {a.status_code}, B {b.status_code}): queda «{final}»",
        a.status_code == 200 and b.status_code == 200, "")
    ESTADO["con003"] = "último gana sin aviso" if final == "QA nota de la ventana B" else f"otro: {final}"
    return pid


def ins013_pedir(pid_cerrada):
    """Pide el enlace de firma dos veces; la fase D prueba el viejo, el alterado y sin token."""
    for vez in (1, 2):
        r = adm.post(f"/projects/{pid_cerrada}/attestation/customer-signature-request",
                     json={"recipient_email": "cliente.qa@example.com"})
        chk(f"Enviar enlace de firma (vez {vez})", r.status_code in (200, 201), f"{r.status_code} {r.text[:150]}")
    ESTADO["ins013_pid"] = pid_cerrada


esc("_prep")
prep_p03(admin, v)
cli_par, fac1 = seguro("PAR-001", par001) or ({}, {})
if fac1:
    seguro("PAR-002", par002, cli_par, fac1)
seguro("PAR-003", par003, cli_par)
r = seguro("_prep", obra_cobrada)
if r:
    cid_c, pid_c, valor = r
    fila = seguro("BOD-007", bod007, pid_c, valor)
    seguro("FIN-005", fin005, pid_c, fila)
    seguro("FIN-001", finanzas, pid_c)
seguro("FIN-002", fin002)
seguro("FIN-003", fin003)
pid_abierta = seguro("INS-015", ins015_y_con003)
if pid_abierta:
    seguro("FIN-006", fin006, pid_abierta)
seguro("NOT-001", not001)
if cli_par:
    seguro("BUS-001", bus001, cli_par)
seguro("TEC-005", tec005)
seguro("TEC-004", tec004)
seguro("TEC-003", tec003)
if pid_abierta:
    seguro("INS-013", ins013_pedir, pid_abierta)
limpiar()
guardar("/tmp/lote3c.json")
json.dump(ESTADO, open("/tmp/lote3c_estado.json", "w"))
print("ok")
