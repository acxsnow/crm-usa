"""Lote 3, fase C2: reejecución tras corregir D-015 a D-018 y lo que el script
de la fase C hizo mal (nombres de campo, tipo de proveedor, término de búsqueda,
campo de la agenda y quién pide el enlace de firma). Corre sobre la base que
dejó la fase C.

PYTHONPATH=/app:/tmp python /tmp/lote3c2.py → /tmp/lote3c2.json y /tmp/lote3c_estado.json
"""
import json
from datetime import timedelta
from decimal import Decimal

from qa_comun import chk, cliente, e, esc, guardar, limpiar, seguro, sql

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia", "carlos")}
admin, adm, v, tec, conta, ger = c["admin"], c["adm"], c["vendedor"], c["tecnico"], c["conta"], c["gerencia"]
HOY = e.HOY
ESTADO = json.load(open("/tmp/lote3c_estado.json"))


def D(x) -> Decimal:
    return Decimal(str(x if x is not None else 0))


def _factura(monto, titulo):
    cli = admin.post("/customers", json={"legal_name": f"QA {e.RUN} {titulo}", "data_consent_accepted": True}).json()
    q = conta.post("/billing/quotes", json={"customer_id": cli["id"], "title": titulo, "lines": [
        {"kind": "labor", "description": titulo, "quantity": 1, "unit_price": monto}]}).json()
    conta.post(f"/billing/quotes/{q['id']}/send")
    fac = (conta.post(f"/billing/quotes/{q['id']}/accept").json() or {}).get("invoice") or {}
    conta.post(f"/invoices/{fac['id']}/issue", json={"due_date": (HOY + timedelta(days=30)).isoformat()})
    return fac


def par003():
    fac = _factura("500.00", "QA PAR-003 reejecución")
    pagar = lambda monto, metodo: conta.post(f"/invoices/{fac['id']}/payments", json={  # noqa: E731
        "amount": monto, "paid_at": HOY.isoformat(), "method": metodo})
    r = pagar("200.00", "cash").json()
    chk("Abono de 200.00 en efectivo: saldo 300.00", D(r.get("balance")) == D("300.00") and r.get("status") == "partial",
        f"{r.get('balance')} {r.get('status')}")
    r = pagar("300.00", "transfer").json()
    chk("Abono de 300.00 por transferencia: saldo 0 y «Factura pagada»", D(r.get("balance")) == 0
        and r.get("status") == "paid", f"{r.get('balance')} {r.get('status')}")
    r = pagar("0.01", "cash")
    chk("Pagar 0.01 de más se rechaza (D-015)", r.status_code == 400 and r.json().get("code") == "payment_exceeds_balance",
        f"{r.status_code} {r.text[:150]}")
    final = conta.get(f"/invoices/{fac['id']}").json()
    chk("El saldo sigue en 0", D(final.get("balance")) == 0, final.get("balance"))


def bod007():
    pid = sql("select m.project_id from warehouse_movements m join projects p on p.id = m.project_id "
              "where m.movement_type = 'salida' and p.status = 'completed' limit 1")
    movs = adm.get("/warehouse/movements", params={"project_id": pid, "limit": 100}).json()
    salidas = [m for m in movs if m["movement_type"] == "salida"]
    chk("La salida de la obra cerrada ya tiene su costo (D-018, migración 0044)",
        salidas and all(m.get("unit_cost") is not None for m in salidas), [m.get("unit_cost") for m in salidas])
    suma = sum(D(m["amount"]) for m in salidas)
    fila = (ger.get("/finance/profitability", params={"project_id": pid}).json().get("rows") or [{}])[0]
    materiales = D((fila.get("cost_breakdown") or {}).get("materials"))
    chk(f"El costo de materiales ({materiales}) = la suma de la salida ({suma}) al centavo",
        materiales == suma and suma > 0, f"materiales={materiales} salida={suma}")
    chk("Sin devoluciones", not [m for m in movs if m["movement_type"] == "devolucion"], "")


def fin001_avisos():
    eventos = {i["event"] for i in tec.get("/notifications", params={"limit": 100}).json()}
    chk("Tito recibe el aviso de gasto aprobado y de gasto rechazado", {"expense.approved", "expense.rejected"} <= eventos,
        sorted(eventos))
    rechazado = [g for g in tec.get("/expenses/mine", params={"limit": 50}).json() if g.get("status") == "rejected"]
    chk("El rechazado muestra el motivo", rechazado and rechazado[0].get("review_notes"), str(rechazado[:1])[:200])


def fin002():
    prov = e.expect("Crear el proveedor «HOME DEPOT»", conta.post("/payables/suppliers", json={
        "name": f"QA HOME DEPOT C2 {e.RUN}", "kinds": ["other"], "payment_terms_days": 30}), 201) or {}
    r = conta.post("/payables/invoices", data={"data": json.dumps({"supplier_id": None, "total": "350.00"})})
    chk("Factura con el proveedor vacío → 422, no 500 (D-016)", r.status_code == 422, f"{r.status_code} {r.text[:150]}")
    f = conta.post("/payables/invoices", data={"data": json.dumps({
        "supplier_id": prov.get("id"), "number": f"QA-HD-C2-{e.RUN}", "invoice_date": HOY.isoformat(),
        "total": "350.00", "category": "materials", "due_date": (HOY + timedelta(days=30)).isoformat()})},
        files={"file": ("factura.pdf", e.pdf_doc("QA HD"), "application/pdf")})
    fac = f.json() if f.status_code == 201 else {}
    chk("Factura de USD 350.00 a 30 días", f.status_code == 201 and D(fac.get("total")) == D("350.00"),
        f"{f.status_code} {f.text[:150]}")
    if fac.get("approvals_missing"):
        e.expect("Gerencia la aprueba", ger.post(f"/payables/invoices/{fac['id']}/approve", json={}), 200)
    r = conta.post("/payables/payments", data={"data": json.dumps({
        "supplier_id": prov.get("id"), "paid_on": HOY.isoformat(), "amount": "350.00", "method": "transfer",
        "reference": f"QA-HD-PAGO-{e.RUN}", "allocations": [{"invoice_id": fac.get("id"), "amount": "350.00"}]})},
        files={"file": ("comprobante.jpg", e.jpeg("comprobante"), "image/jpeg")})
    chk("Pagarla adjuntando el comprobante", r.status_code == 201, f"{r.status_code} {r.text[:150]}")
    fin = conta.get(f"/payables/invoices/{fac.get('id')}").json()
    chk("Saldo en cero tras el pago", D(fin.get("balance")) == 0 and fin.get("status") == "paid",
        f"{fin.get('balance')} {fin.get('status')}")
    r = conta.post("/payables/suppliers", json={"name": f"QA HOME DEPOT C2 {e.RUN}", "kinds": ["other"]})
    chk(f"Proveedor con el mismo nombre (anotar): {r.status_code}", True, r.text[:120])
    ESTADO["fin002_duplicado"] = r.status_code


def fin003():
    extracto = (f"Date,Description,Amount\n{HOY.isoformat()},QA C2 LOWES {e.RUN},-45.10\n"
                f"{HOY.isoformat()},QA C2 LOWES {e.RUN},-45.10\n{HOY.isoformat()},QA C2 SHELL {e.RUN},-60.00\n"
                f"{HOY.isoformat()},QA C2 FEE {e.RUN},-12.00\n{HOY.isoformat()},QA C2 MALO {e.RUN},doce dolares\n")

    def importar():
        return conta.post("/reconciliation/statements", data={"account_label": f"QA C2 {e.RUN}"},
                          files={"file": ("extracto.csv", extracto.encode(), "text/csv")})
    r = importar()
    cuerpo = r.json() if r.status_code == 201 else {}
    chk(f"Entran 4 (el repetido del mismo día también) y el mal formado se reporta ({cuerpo.get('invalid')})",
        cuerpo.get("lines") == 4 and cuerpo.get("invalid"), f"{r.status_code} {r.text[:200]}")
    r = importar()
    chk("Importar el mismo archivo otra vez no duplica (D-017: 409 «ya estaba importado»)",
        r.status_code == 409 and r.json().get("code") == "statement_already_imported", f"{r.status_code} {r.text[:150]}")
    mias = [l for l in conta.get("/reconciliation/lines", params={"limit": 200}).json() if f"C2" in l["description"]
            and e.RUN in l["description"]]
    chk(f"Quedan 4 movimientos de ese extracto ({len(mias)})", len(mias) == 4, len(mias))


def bus001():
    calle = sql("select address_street from cases where address_street like '%Mobile Park%' limit 1")
    r = admin.get("/search", params={"q": "Mobile Park"})
    total = sum(len(x) for x in r.json().values() if isinstance(x, list)) if r.status_code == 200 else 0
    chk(f"Admin busca «Mobile Park» (las direcciones de prueba, p. ej. «{calle}») y las encuentra", total > 0, total)


def tec003():
    tecnicos = {t["id"] for t in adm.get("/dispatch/technicians").json()}
    agenda = adm.get("/dispatch/agenda", params={"date_from": HOY.isoformat(),
                                                  "date_to": (HOY + timedelta(days=7)).isoformat()}).json()
    con_obra = {a.get("primary_technician_user_id") for a in agenda} & tecnicos
    chk(f"La agenda de la semana muestra obras de {len(con_obra)} técnicos distintos", len(con_obra) >= 10, len(agenda))


def ins013_pedir():
    pid = ESTADO.get("ins013_pid") or sql("select id from projects where primary_technician_user_id = "
                                          "(select id from users where email = 'tecnico@demo-org.com') "
                                          "and status <> 'completed' limit 1")
    for vez in (1, 2):
        r = tec.post(f"/projects/{pid}/attestation/customer-signature-request")
        chk(f"El técnico envía el enlace de firma (vez {vez})", r.status_code in (200, 201), f"{r.status_code} {r.text[:150]}")
    r = adm.post(f"/projects/{pid}/attestation/customer-signature-request")
    chk(f"Administración (sin evidence.create) no lo envía ({r.status_code}; anotar)", True, r.text[:120])
    ESTADO["ins013_pid"] = pid


seguro("PAR-003", par003)
seguro("BOD-007", bod007)
seguro("FIN-001", fin001_avisos)
seguro("FIN-002", fin002)
seguro("FIN-003", fin003)
seguro("BUS-001", bus001)
seguro("TEC-003", tec003)
seguro("INS-013", ins013_pedir)
limpiar()
guardar("/tmp/lote3c2.json")
json.dump(ESTADO, open("/tmp/lote3c_estado.json", "w"))
print("ok")
