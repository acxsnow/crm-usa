"""Ataque al cobro y a la rentabilidad contra la app real (9 nov 2026).

No solo el camino feliz: con números exactos que se pueden verificar a mano, y
luego lo que puede pasar en la operación (pagos de más, de menos o dobles,
rechazos, roles que no deben poder, otra organización, material devuelto,
gastos sin aprobar, facturas anuladas) y el cuadre contable al final.

Corre en el contenedor api:
    PYTHONPATH=/app:/tmp python /tmp/qa_cobro_rentabilidad.py → /tmp/qa_cobro_rentabilidad.json
"""
import json
import random
from datetime import timedelta
from decimal import Decimal

from qa_comun import aprobar_rapido, chk, cliente, e, esc, guardar, prep_p03, sql

def D(x):
    """Monto exacto, venga como texto o como número de la API."""
    return Decimal(str(x))
c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia", "ajeno")}
admin, adm, v, tec, conta, ger, ajeno = (c[k] for k in ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia",
                                                         "ajeno"))
HOY = e.HOY
prep_p03(admin, v)
progs = {p["code"]: p for p in admin.get("/programs").json()}
TECH, AZ = progs["TECH_CLEAN_CA"]["id"], progs["AZ_EFFICIENCY"]["id"]


def tarifa_vigente(program_id):
    tarifas = conta.get(f"/billing/programs/{program_id}/rates").json()
    vigentes = [t for t in tarifas if t["valid_from"] <= HOY.isoformat() and (not t.get("valid_to") or
                                                                             t["valid_to"] >= HOY.isoformat())]
    return D(vigentes[-1]["amount"]) if vigentes else None


def gasto(proyecto, monto, categoria="fuel"):
    datos = {"expense_date": HOY.isoformat(), "category": categoria, "amount": monto, "payment_method": "own_money",
             "description": f"QA {e.RUN} {categoria}", "project_id": proyecto}
    return tec.post("/expenses", data={"data": json.dumps(datos)},
                    files={"receipt": ("recibo.jpg", e.jpeg("recibo"), "image/jpeg")})


def rentabilidad(pid):
    r = ger.get("/finance/profitability", params={"project_id": pid})
    return (r.json().get("rows") or [{}])[0] if r.status_code == 200 else {}


def agendar(pid):
    return adm.patch(f"/projects/{pid}/schedule", json={"technician_user_id": tec.me["id"],
                                                       "scheduled_date": (HOY + timedelta(days=1)).isoformat()})


def bodega_id():
    locs = adm.get("/warehouse/locations", params={"page_size": 50}).json()
    return next(l["id"] for l in locs if l.get("kind") in ("warehouse", "bodega") or "odega" in l.get("name", ""))


def articulo(costo, cantidad="10"):
    item = adm.post("/warehouse/items", json={"name": f"QA {e.RUN} artículo {costo} {random.randint(1, 99999)}",
                                              "unit_cost": costo, "category": "other"}).json()
    adm.post("/warehouse/movements", json={"item_id": item["id"], "movement_type": "entrada", "quantity": cantidad,
                                           "unit_cost": costo, "location_id": bodega_id(), "reference": "QA entrada"})
    return item


def salida(pid, item_id, cantidad, entregar=True):
    o = tec.post("/warehouse/releases", json={"project_id": pid, "lines": [{"item_id": item_id,
                                                                            "quantity": cantidad}]}).json()
    tec.post(f"/warehouse/releases/{o['id']}/submit")
    adm.post(f"/warehouse/releases/{o['id']}/approve")
    if entregar:
        e.expect("Bodega entrega la salida", adm.post(f"/warehouse/releases/{o['id']}/deliver", json={}), 200)
    return o["id"]


def turno_aprobado(pid, minutos):
    """Un turno aprobado del técnico con `minutos` en la obra (marcas «llegué» y «salí»)."""
    org = sql(f"select organization_id from projects where id = '{pid}'")
    dia = HOY - timedelta(days=random.randint(120, 900))
    salida_ = e.worker(f"""from datetime import datetime, timezone, timedelta, time
import uuid
from app.db import all_models  # noqa: F401
from app.modules.attendance.models import TimeEntry, AttendanceEvent
inicio = datetime.combine(__import__('datetime').date.fromisoformat('{dia.isoformat()}'), time(14, 0), tzinfo=timezone.utc)
fin = inicio + timedelta(minutes={minutos})
t = TimeEntry(organization_id=uuid.UUID('{org}'), user_id=uuid.UUID('{tec.me["id"]}'), work_date=inicio.date(),
              clock_in_at=inicio, clock_in_received_at=inicio, clock_out_at=fin, clock_out_received_at=fin,
              status='approved', approved_minutes={minutos})
db.add(t)
await db.flush()
for tipo, m in (('arrived', 0), ('left_site', {minutos})):
    momento = inicio + timedelta(minutes=m)
    db.add(AttendanceEvent(organization_id=t.organization_id, user_id=t.user_id, time_entry_id=t.id,
                           project_id=uuid.UUID('{pid}'), event_type=tipo, received_at=momento, occurred_at=momento))
await db.commit()
print('turno ok')""")
    return "turno ok" in salida_, salida_[-300:]


def cobrar(pid, program_id=TECH):
    claim = e.expect("Crear el cobro al programa", adm.post(f"/projects/{pid}/claims", json={"program_id": program_id}),
                     201) or {}
    for req in claim.get("requirements", []):
        if req["kind"] == "manual" and not req["met"]:
            adm.post(f"/claims/{claim['id']}/checks/{req['code']}", json={})
    return claim


# ===========================================================================
esc("COB-01 Camino completo con números exactos")
# ===========================================================================
TARIFA = tarifa_vigente(TECH)
chk(f"TECH tiene tarifa vigente ({TARIFA})", TARIFA is not None, TARIFA)
cid, pid = aprobar_rapido(v, adm, admin, 701)
e.expect("Administración agenda la obra con Tito", agendar(pid), 200)
item = articulo("600.00")
salida(pid, item["id"], "2")
ok, det = turno_aprobado(pid, 480)
chk("Turno aprobado de 8 h en la obra", ok, det)
e.expect("Tarifa de Tito: 45 USD la hora", admin.put(f"/jobcost/labor-rates/{tec.me['id']}", json={"hourly_rate": "45"}),
         200)
g = e.expect("Técnico registra 40 USD de gasolina", gasto(pid, "40.00"), 201) or {}
e.expect("Contabilidad aprueba la gasolina", conta.post(f"/expenses/{g.get('id')}/review", json={"approve": True}), 200)
e.flujo_campo(adm, tec, cid, devolver_acta=False, permiso=False)

fila = rentabilidad(pid)
cb = fila.get("cost_breakdown") or {}
chk(f"Antes de cobrar: material 1.200 ({cb.get('materials')})", D(cb.get("materials") or 0) == D("1200.00"), cb)
chk(f"Antes de cobrar: mano de obra 360 = 8 h × 45 ({cb.get('labor')})", D(cb.get("labor") or 0) == D("360.00"), cb)
chk(f"Antes de cobrar: gastos de campo 40 ({cb.get('field_expenses')})", D(cb.get("field_expenses") or 0) == D("40.00"),
    cb)
chk(f"Costos = 1.600 ({fila.get('costs')})", D(fila.get("costs") or 0) == D("1600.00"), fila)
chk(f"Sin cobro todavía, cobrado 0 ({fila.get('collected')})", D(fila.get("collected") or 0) == 0, fila)

claim = cobrar(pid)
chk(f"El cobro toma la tarifa vigente el día de la instalación ({claim.get('amount')})",
    D(claim.get("amount") or 0) == TARIFA, claim.get("amount"))
r = e.expect("Radicar", adm.post(f"/claims/{claim['id']}/submit", json={"portal_reference": f"QA-{e.RUN}"}), 200) or {}
chk("El expediente pasa a «En cobro»", admin.get(f"/cases/{cid}").json()["stage_code"] == "billing_in_progress")
fila = rentabilidad(pid)
chk(f"Radicado: esperado = tarifa ({fila.get('expected')})", D(fila.get("expected") or 0) == TARIFA, fila)
e.expect("Contabilidad registra el pago completo", conta.post(f"/claims/{claim['id']}/payment", json={
    "amount": str(TARIFA), "paid_on": HOY.isoformat(), "reference": f"QA-CHK-{e.RUN}"}), 200)
chk("El expediente queda «Pagado»", admin.get(f"/cases/{cid}").json()["stage_code"] == "paid")
fila = rentabilidad(pid)
chk(f"Cobrado = tarifa ({fila.get('collected')})", D(fila.get("collected") or 0) == TARIFA, fila)
chk(f"Margen = tarifa − 1.600 = {TARIFA - D('1600')} ({fila.get('margin')})",
    D(fila.get("margin") or 0) == TARIFA - D("1600.00"), fila)
detalle = ger.get(f"/projects/{pid}/labor-hours").json() if ger.get(f"/projects/{pid}/labor-hours").status_code == 200 \
    else adm.get(f"/projects/{pid}/labor-hours").json()
chk(f"Detalle de horas: 480 min y 360 USD ({detalle.get('total')})", D(detalle.get("total") or 0) == D("360.00"),
    str(detalle)[:200])
OBRA_FELIZ = (cid, pid, claim["id"])

# ===========================================================================
esc("COB-02 Cobro: lo que no se debe poder")
# ===========================================================================
cid2, pid2 = aprobar_rapido(v, adm, admin, 702)
r = adm.post(f"/projects/{pid2}/claims", json={"program_id": TECH})
chk("Sin acta confirmada no se crea el cobro", r.status_code in (400, 409), f"{r.status_code} {r.text[:150]}")
e.flujo_campo(adm, tec, cid2, devolver_acta=False, permiso=False)
r = adm.post(f"/projects/{pid2}/claims", json={"program_id": AZ})
chk("No se cobra a otro programa distinto al del expediente", r.status_code in (400, 409), f"{r.status_code} {r.text[:150]}")
r = v.post(f"/projects/{pid2}/claims", json={"program_id": TECH})
chk("El vendedor no crea cobros", r.status_code == 403, r.status_code)
r = tec.post(f"/projects/{pid2}/claims", json={"program_id": TECH})
chk("El técnico no crea cobros", r.status_code == 403, r.status_code)
claim2 = e.expect("Crear cobro (sin marcar los requisitos manuales)",
                  adm.post(f"/projects/{pid2}/claims", json={"program_id": TECH}), 201) or {}
e.expect("Cobro duplicado del mismo programa", adm.post(f"/projects/{pid2}/claims", json={"program_id": TECH}), 409)
r = adm.post(f"/claims/{claim2['id']}/submit", json={})
chk("Radicar con requisitos manuales sin marcar se bloquea", r.status_code in (400, 409), f"{r.status_code} {r.text[:150]}")
r = conta.post(f"/claims/{claim2['id']}/payment", json={"amount": "100", "paid_on": HOY.isoformat()})
chk("No se paga un cobro sin radicar", r.status_code == 409, r.status_code)
for req in claim2.get("requirements", []):
    if req["kind"] == "manual" and not req["met"]:
        adm.post(f"/claims/{claim2['id']}/checks/{req['code']}", json={})
e.expect("Radicar", adm.post(f"/claims/{claim2['id']}/submit", json={"portal_reference": "QA-2"}), 200)
for monto, nombre in (("0", "cero"), ("-50", "negativo"), ("abc", "texto"), ("1e9999", "gigante")):
    r = conta.post(f"/claims/{claim2['id']}/payment", json={"amount": monto, "paid_on": HOY.isoformat()})
    chk(f"Pago {nombre} se rechaza", r.status_code in (400, 422), f"{r.status_code} {r.text[:120]}")
r = conta.post(f"/claims/{claim2['id']}/payment", json={"amount": "100",
                                                       "paid_on": (HOY + timedelta(days=3)).isoformat()})
chk("Pago con fecha futura se rechaza", r.status_code in (400, 422), r.status_code)
for quien, cli in (("vendedor", v), ("técnico", tec), ("Gerencia", ger)):
    r = cli.post(f"/claims/{claim2['id']}/payment", json={"amount": "100", "paid_on": HOY.isoformat()})
    chk(f"{quien} no registra pagos", r.status_code == 403, r.status_code)
r = adm.post(f"/claims/{claim2['id']}/reject", json={"reason": "x", "category": "documentary"})
chk("Rechazo con motivo de una letra se bloquea", r.status_code in (400, 422), r.status_code)
e.expect("El programa rechaza con motivo", adm.post(f"/claims/{claim2['id']}/reject", json={
    "reason": "QA: falta la firma en el formulario", "category": "documentary"}), 200)
chk("Rechazado, el expediente sigue «En cobro»", admin.get(f"/cases/{cid2}").json()["stage_code"] == "billing_in_progress")
e.expect("Se corrige y se vuelve a radicar", adm.post(f"/claims/{claim2['id']}/submit", json={"portal_reference": "QA-2b"}),
         200)
PARCIAL = TARIFA - D("500.00")
r = e.expect(f"El programa paga de menos ({PARCIAL})", conta.post(f"/claims/{claim2['id']}/payment", json={
    "amount": str(PARCIAL), "paid_on": HOY.isoformat(), "reference": "QA-PARCIAL"}), 200) or {}
chk(f"La diferencia queda a la vista (−500: {r.get('difference')})", D(r.get("difference") or 0) == D("-500.00"),
    r.get("difference"))
r = conta.post(f"/claims/{claim2['id']}/payment", json={"amount": "500", "paid_on": HOY.isoformat()})
chk("Un segundo pago sobre un cobro pagado se bloquea (doble clic)", r.status_code == 409, r.status_code)
r = adm.post(f"/claims/{claim2['id']}/reject", json={"reason": "QA rechazo tardío", "category": "documentary"})
chk("No se rechaza un cobro ya pagado", r.status_code == 409, r.status_code)
r = adm.post(f"/claims/{claim2['id']}/withdraw", json={"reason": "QA retirar pagado"})
chk("No se retira un cobro pagado", r.status_code == 409, r.status_code)
fila = rentabilidad(pid2)
chk(f"Rentabilidad con pago de menos: cobrado {PARCIAL} ({fila.get('collected')})",
    D(fila.get("collected") or 0) == PARCIAL, fila)

r = ajeno.get(f"/claims/{claim2['id']}")
chk("Otra organización no ve el cobro", r.status_code == 404, r.status_code)
r = ajeno.post(f"/claims/{claim2['id']}/payment", json={"amount": "1", "paid_on": HOY.isoformat()})
chk("Otra organización no le registra pagos", r.status_code in (403, 404), r.status_code)
r = ajeno.get("/finance/profitability", params={"project_id": pid2})
filas_ajenas = r.json().get("rows", []) if r.status_code == 200 else []
chk("Otra organización no ve la rentabilidad de la obra", r.status_code in (403, 404) or not filas_ajenas,
    f"{r.status_code} {str(filas_ajenas)[:100]}")
for quien, cli in (("vendedor", v), ("técnico", tec)):
    r = cli.get("/finance/profitability", params={"project_id": pid2})
    chk(f"El {quien} no ve rentabilidad", r.status_code == 403, r.status_code)

# Retirar y volver a cobrar
cid3, pid3 = aprobar_rapido(v, adm, admin, 703)
e.flujo_campo(adm, tec, cid3, devolver_acta=False, permiso=False)
claim3 = cobrar(pid3)
r = adm.post(f"/claims/{claim3['id']}/withdraw", json={"reason": "x"})
chk("Retirar sin motivo se bloquea", r.status_code in (400, 422), r.status_code)
e.expect("Retirar con motivo (se equivocó la tarifa)", adm.post(f"/claims/{claim3['id']}/withdraw", json={
    "reason": "QA: se cargó con la tarifa equivocada"}), 200)
fila = rentabilidad(pid3)
chk(f"El cobro retirado no cuenta como esperado ({fila.get('expected')})", D(fila.get("expected") or 0) == 0, fila)
claim3b = e.expect("Después de retirar se puede volver a cobrar",
                   adm.post(f"/projects/{pid3}/claims", json={"program_id": TECH}), 201) or {}
fila = rentabilidad(pid3)
chk(f"Solo cuenta el cobro vivo ({fila.get('expected')})", D(fila.get("expected") or 0) in (0, TARIFA), fila)

# ===========================================================================
esc("COB-03 Rentabilidad: lo que no debe contar")
# ===========================================================================
cid4, pid4 = aprobar_rapido(v, adm, admin, 704)
agendar(pid4)
item4 = articulo("250.00")
salida(pid4, item4["id"], "4")                    # 1.000 entregados
salida(pid4, item4["id"], "2", entregar=False)    # autorizada, sin entregar: no cuenta
fila = rentabilidad(pid4)
chk(f"Solo cuenta lo entregado: material 1.000 ({(fila.get('cost_breakdown') or {}).get('materials')})",
    D((fila.get("cost_breakdown") or {}).get("materials") or 0) == D("1000.00"), fila.get("cost_breakdown"))
e.expect("Vuelve 1 unidad a bodega (devolución)", adm.post("/warehouse/movements", json={
    "item_id": item4["id"], "movement_type": "devolucion", "quantity": "1", "project_id": pid4,
    "location_id": bodega_id(), "note": "QA sobró una"}), 201)
fila = rentabilidad(pid4)
chk(f"La devolución descuenta: material 750 ({(fila.get('cost_breakdown') or {}).get('materials')})",
    D((fila.get("cost_breakdown") or {}).get("materials") or 0) == D("750.00"), fila.get("cost_breakdown"))
r = adm.post("/warehouse/movements", json={"item_id": item4["id"], "movement_type": "devolucion", "quantity": "10",
                                           "project_id": pid4, "location_id": bodega_id()})
chk("No se devuelve más de lo que se entregó a la obra", r.status_code in (400, 409), r.status_code)

g_pend = e.expect("Gasto de 75 sin aprobar", gasto(pid4, "75.00"), 201) or {}
g_rech = e.expect("Gasto de 90 que se rechaza", gasto(pid4, "90.00", "meals"), 201) or {}
conta.post(f"/expenses/{g_rech.get('id')}/review", json={"approve": False, "notes": "QA sin factura válida"})
g_ok = e.expect("Gasto de 12,35 aprobado (centavos)", gasto(pid4, "12.35"), 201) or {}
conta.post(f"/expenses/{g_ok.get('id')}/review", json={"approve": True})
g_otro = e.expect("Gasto de 500 aprobado de OTRA obra", gasto(pid, "500.00"), 201) or {}
conta.post(f"/expenses/{g_otro.get('id')}/review", json={"approve": True})
fila = rentabilidad(pid4)
chk(f"Gastos de campo: solo el aprobado de esta obra, 12,35 ({(fila.get('cost_breakdown') or {}).get('field_expenses')})",
    D((fila.get("cost_breakdown") or {}).get("field_expenses") or 0) == D("12.35"), fila.get("cost_breakdown"))
r = tec.post(f"/expenses/{g_pend.get('id')}/review", json={"approve": True})
chk("El técnico no se aprueba su propio gasto", r.status_code == 403, r.status_code)
r = gasto(pid4, "-20.00")
chk("Gasto negativo se rechaza", r.status_code in (400, 422), r.status_code)

ok, det = turno_aprobado(pid4, 90)
fila = rentabilidad(pid4)
chk(f"90 min aprobados × 45 = 67,50 de mano de obra ({(fila.get('cost_breakdown') or {}).get('labor')})",
    D((fila.get("cost_breakdown") or {}).get("labor") or 0) == D("67.50"), fila.get("cost_breakdown"))

prov = conta.post("/payables/suppliers", json={"name": f"QA Proveedor rentabilidad {e.RUN}", "kinds": ["equipment"],
                                               "payment_terms_days": 30}).json()


def factura_prov(numero, lineas, **kw):
    datos = {"supplier_id": prov["id"], "number": numero, "invoice_date": HOY.isoformat(), "lines": lineas, **kw}
    return conta.post("/payables/invoices", data={"data": json.dumps(datos)},
                      files={"file": ("f.pdf", e.pdf_doc("QA"), "application/pdf")})


f1 = e.expect("Factura de proveedor: equipo 1.000 a esta obra + 100 de impuesto", factura_prov(
    f"QA-R-{e.RUN}-1", [{"description": "Condensadora", "category": "equipment", "quantity": "1", "unit_cost": "1000.00",
                         "project_id": pid4}], tax="100.00"), 201) or {}
f2 = e.expect("Otra factura de 300 a esta obra, que luego se anula", factura_prov(
    f"QA-R-{e.RUN}-2", [{"description": "Error", "category": "equipment", "quantity": "1", "unit_cost": "300.00",
                         "project_id": pid4}]), 201) or {}
anular = conta.post(f"/payables/invoices/{f2.get('id')}/void", json={"reason": "QA factura duplicada del proveedor"})
chk("Se anula la factura equivocada", anular.status_code == 200, f"{anular.status_code} {anular.text[:150]}")
fila = rentabilidad(pid4)
chk(f"Equipo 1.100 (con su impuesto) y la anulada no cuenta ({(fila.get('cost_breakdown') or {}).get('equipment')})",
    D((fila.get("cost_breakdown") or {}).get("equipment") or 0) == D("1100.00"), fila.get("cost_breakdown"))
esperado_costos = D("750.00") + D("12.35") + D("67.50") + D("1100.00")
chk(f"Costos totales = {esperado_costos} ({fila.get('costs')})", D(fila.get("costs") or 0) == esperado_costos, fila)
suma = sum(D(x) for x in (fila.get("cost_breakdown") or {}).values())
chk(f"La suma del desglose da el total ({suma})", suma == D(fila.get("costs") or 0), fila.get("cost_breakdown"))

# ===========================================================================
esc("COB-04 Trabajo particular: cotización, factura y pagos")
# ===========================================================================
cli = adm.post("/customers", json={"legal_name": f"QA Particular {e.RUN}", "main_phone": "6025550199",
                                   "data_consent_accepted": True}).json()
q = e.expect("Cotización con dos opciones", adm.post("/billing/quotes", json={
    "customer_id": cli["id"], "title": "QA reparación", "options": [{"key": "A", "label": "Básica"},
                                                                    {"key": "B", "label": "Premium"}],
    "lines": [{"kind": "labor", "description": "Mano de obra", "quantity": 1, "unit_price": 300},
              {"kind": "material", "description": "Filtro", "quantity": 2, "unit_price": 25.5, "option_key": "A"},
              {"kind": "equipment", "description": "Termostato wifi", "quantity": 1, "unit_price": 199.99,
               "option_key": "B"}]}), 201) or {}
r = adm.post(f"/billing/quotes/{q.get('id')}/accept", json={"option": "B"})
chk("No se acepta una cotización en borrador (sin enviar)", r.status_code == 409, r.status_code)
e.expect("Enviar", adm.post(f"/billing/quotes/{q.get('id')}/send"), 200)
r = adm.post(f"/billing/quotes/{q.get('id')}/accept", json={"option": "Z"})
chk("Opción que no existe se rechaza", r.status_code in (400, 422), r.status_code)
acep = e.expect("El cliente acepta la Premium", adm.post(f"/billing/quotes/{q.get('id')}/accept",
                                                         json={"option": "B"}), 200) or {}
inv = acep.get("invoice") or {}
chk(f"Factura de la opción elegida: 300 + 199,99 = 499,99 ({inv.get('amount')})", D(inv.get("amount") or 0) == D("499.99"),
    inv.get("amount"))
r = adm.post(f"/billing/quotes/{q.get('id')}/accept", json={"option": "A"})
chk("Aceptar dos veces se bloquea", r.status_code == 409, r.status_code)
obra_q = adm.get(f"/billing/quotes/{q.get('id')}").json().get("project_id")
chk("Nació la obra", bool(obra_q))
r = conta.post(f"/invoices/{inv.get('id')}/payments", json={"amount": "100", "paid_at": HOY.isoformat()})
chk("No se paga una factura en borrador", r.status_code in (400, 409), r.status_code)
e.expect("Emitir la factura", conta.post(f"/invoices/{inv.get('id')}/issue", json={}), 200)
r = e.expect("Anticipo de 200", conta.post(f"/invoices/{inv.get('id')}/payments", json={
    "amount": "200", "paid_at": HOY.isoformat(), "method": "zelle"}), 201) or {}
chk(f"Saldo 299,99 ({r.get('balance')})", D(r.get("balance") or 0) == D("299.99"), r.get("balance"))
r = conta.post(f"/invoices/{inv.get('id')}/payments", json={"amount": "300.00", "paid_at": HOY.isoformat()})
chk("Un pago que supera el saldo se rechaza", r.status_code in (400, 409), f"{r.status_code} {r.text[:120]}")
r = e.expect("Paga el saldo exacto", conta.post(f"/invoices/{inv.get('id')}/payments", json={
    "amount": "299.99", "paid_at": HOY.isoformat()}), 201) or {}
chk(f"Queda pagada con saldo 0 ({r.get('balance')}, {r.get('payment_status') or r.get('status')})",
    r.get("balance") is not None and D(r.get("balance")) == 0, str(r.get("balance")))
r = conta.post(f"/invoices/{inv.get('id')}/void", json={"reason": "QA anular pagada"})
chk("No se anula una factura con pagos", r.status_code in (400, 409), f"{r.status_code} {r.text[:120]}")
if obra_q:
    fila = rentabilidad(obra_q)
    chk(f"Rentabilidad del particular: esperado y cobrado 499,99 ({fila.get('expected')} / {fila.get('collected')})",
        D(fila.get("expected") or 0) == D("499.99") and D(fila.get("collected") or 0) == D("499.99"), fila)

# ===========================================================================
esc("COB-05 Contabilidad cuadra")
# ===========================================================================
tb = conta.get("/accounting/reports/trial-balance")
if tb.status_code == 200:
    cuerpo = tb.json()
    deb = D(str(cuerpo.get("total_debit") or cuerpo.get("debit") or 0))
    cre = D(str(cuerpo.get("total_credit") or cuerpo.get("credit") or 0))
    chk(f"Balance de comprobación cuadrado ({deb} = {cre})", deb == cre and deb > 0, str(cuerpo)[:200])
else:
    chk("Balance de comprobación", False, f"{tb.status_code} {tb.text[:200]}")

guardar("/tmp/qa_cobro_rentabilidad.json")
print("FIN", json.dumps({"feliz": OBRA_FELIZ}))
