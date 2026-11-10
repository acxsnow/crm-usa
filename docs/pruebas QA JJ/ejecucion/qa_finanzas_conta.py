"""Ataque a gastos, proveedores, conciliación, reportes y contabilidad (10 nov 2026).

PYTHONPATH=/app:/tmp python /tmp/qa_finanzas_conta.py → /tmp/qa_finanzas_conta.json
"""
import json
from datetime import timedelta
from decimal import Decimal

from qa_comun import chk, cliente, e, esc, guardar

c = {k: cliente(k) for k in ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia", "ajeno")}
admin, adm, v, tec, conta, ger, ajeno = (c[k] for k in ("admin", "adm", "vendedor", "tecnico", "conta", "gerencia",
                                                         "ajeno"))
HOY = e.HOY
RUN = e.RUN


def D(x):
    return Decimal(str(x))


def gasto(monto, **kw):
    datos = {"expense_date": HOY.isoformat(), "category": "fuel", "amount": monto, "payment_method": "own_money",
             "description": f"QA {RUN} gasto", **kw}
    return tec.post("/expenses", data={"data": json.dumps(datos)},
                    files={"receipt": ("r.jpg", e.jpeg("r"), "image/jpeg")})


# ===========================================================================
esc("FIN-A1 Gastos de campo")
# ===========================================================================
g = e.expect("Gasto de 25", gasto("25.00"), 201) or {}
r = conta.post(f"/expenses/{g.get('id')}/reimburse", json={"paid_on": HOY.isoformat(), "reference": "QA"})
chk("No se reembolsa un gasto sin aprobar", r.status_code in (400, 409), r.status_code)
e.expect("Se aprueba", conta.post(f"/expenses/{g.get('id')}/review", json={"approve": True}), 200)
e.expect("Se reembolsa", conta.post(f"/expenses/{g.get('id')}/reimburse", json={"paid_on": HOY.isoformat(),
                                                                                "reference": "QA-1"}), 200)
r = conta.post(f"/expenses/{g.get('id')}/reimburse", json={"paid_on": HOY.isoformat(), "reference": "QA-2"})
chk("No se reembolsa dos veces", r.status_code in (400, 409), r.status_code)
r = conta.post(f"/expenses/{g.get('id')}/review", json={"approve": False, "notes": "QA rechazar ya pagado"})
chk("No se rechaza un gasto ya reembolsado", r.status_code in (400, 409), r.status_code)
r = gasto("10.00", category="caviar")
chk("Categoría inventada se rechaza", r.status_code in (400, 422), r.status_code)
r = tec.post("/expenses", data={"data": json.dumps({"expense_date": HOY.isoformat(), "category": "fuel", "amount": "10",
                                                    "description": "QA sin recibo"})})
chk(f"Gasto sin recibo ({r.status_code})", r.status_code in (201, 400, 422), r.status_code)
r = v.get("/expenses", params={"scope": "all", "limit": 50})
ajenos = [x for x in (r.json() if r.status_code == 200 else []) if x.get("user_id") not in (v.me["id"], None)]
chk("El vendedor no ve los gastos de otros", not ajenos, len(ajenos))
r = ajeno.get(f"/expenses/{g.get('id')}/receipt")
chk("Otra organización no baja nuestros recibos", r.status_code in (403, 404), r.status_code)

# ===========================================================================
esc("FIN-A2 Proveedores y pagos")
# ===========================================================================
prov = e.expect("Proveedor", conta.post("/payables/suppliers", json={"name": f"QA Prov fin {RUN}", "kinds": ["equipment"],
                                                                     "payment_terms_days": 15}), 201) or {}
r = conta.post("/payables/suppliers", json={"name": f"QA Prov fin {RUN}", "kinds": ["equipment"]})
chk(f"Proveedor con el mismo nombre ({r.status_code})", r.status_code in (201, 400, 409), r.status_code)


def factura(numero, **kw):
    datos = {"supplier_id": prov.get("id"), "number": numero, "invoice_date": HOY.isoformat(), **kw}
    return conta.post("/payables/invoices", data={"data": json.dumps(datos)},
                      files={"file": ("f.pdf", e.pdf_doc("QA"), "application/pdf")})


r = factura(f"QA-F-{RUN}-0", total="-100")
chk("Factura de proveedor negativa se rechaza", r.status_code in (400, 422), r.status_code)
f = e.expect("Factura de 500", factura(f"QA-F-{RUN}-1", total="500.00", category="materials"), 201) or {}
r = conta.post(f"/payables/invoices/{f.get('id')}/approve", json={})
chk("Quien la registra no la aprueba sola", r.status_code in (403, 409), r.status_code)
ger.post(f"/payables/invoices/{f.get('id')}/approve", json={})


def pagar(monto, repartos):
    return conta.post("/payables/payments", data={"data": json.dumps({
        "supplier_id": prov.get("id"), "paid_on": HOY.isoformat(), "amount": monto, "method": "check",
        "reference": f"QA-P-{RUN}", "allocations": repartos})},
        files={"file": ("c.jpg", e.jpeg("c"), "image/jpeg")})


r = pagar("600.00", [{"invoice_id": f.get("id"), "amount": "600.00"}])
chk("Un pago mayor que la factura se rechaza", r.status_code in (400, 409), f"{r.status_code} {r.text[:120]}")
r = pagar("100.00", [{"invoice_id": f.get("id"), "amount": "-100.00"}])
chk("Un reparto negativo se rechaza", r.status_code in (400, 422), r.status_code)
e.expect("Pago de 500", pagar("500.00", [{"invoice_id": f.get("id"), "amount": "500.00"}]), 201)
r = pagar("1.00", [{"invoice_id": f.get("id"), "amount": "1.00"}])
chk("No se le paga más a una factura ya pagada", r.status_code in (400, 409), r.status_code)
r = conta.post(f"/payables/invoices/{f.get('id')}/void", json={"reason": "QA anular pagada"})
chk("No se anula una factura de proveedor pagada", r.status_code in (400, 409), r.status_code)
r = tec.put(f"/payables/suppliers/{prov.get('id')}", json={"name": prov.get("name") or "x", "bank_details": "Cuenta del ladrón 0000"})
chk("El técnico no cambia los datos bancarios del proveedor", r.status_code == 403, r.status_code)
r = ajeno.get(f"/payables/suppliers/{prov.get('id')}")
chk("Otra organización no ve el proveedor", r.status_code in (403, 404), r.status_code)

# ===========================================================================
esc("FIN-A3 Conciliación y reportes")
# ===========================================================================
r = conta.post("/reconciliation/statements", data={"account_label": "QA"},
               files={"file": ("x.csv", b"\x00\x01\x02 no soy csv", "text/csv")})
chk("Un extracto que no es CSV se rechaza", r.status_code in (400, 422), r.status_code)
r = conta.post("/reconciliation/statements", data={"account_label": "QA"}, files={"file": ("x.csv", b"", "text/csv")})
chk("Un extracto vacío se rechaza", r.status_code in (400, 422), r.status_code)
r = conta.post("/reconciliation/statements", data={"account_label": "QA"},
               files={"file": ("x.csv", b"Date,Description,Amount\nayer,=HYPERLINK(\"http://x\"),abc\n", "text/csv")})
chk("Filas con fecha o monto inválidos no tumban la importación", r.status_code in (201, 400, 422), r.status_code)
r = ger.get("/reports/finance", params={"date_from": HOY.isoformat(), "date_to": (HOY - timedelta(days=30)).isoformat()})
chk("Reporte con fechas al revés se rechaza", r.status_code in (400, 422), r.status_code)
r = tec.get("/finance/profitability")
chk("El técnico no ve la rentabilidad", r.status_code == 403, r.status_code)

# ===========================================================================
esc("FIN-A4 Contabilidad")
# ===========================================================================
cuentas = conta.get("/accounting/accounts").json()
cuentas = cuentas if isinstance(cuentas, list) else cuentas.get("items", [])
caja = next((x for x in cuentas if x.get("account_type") == "asset"), None)
gasto_c = next((x for x in cuentas if x.get("account_type") == "expense"), None)
chk("Hay plan de cuentas", bool(caja and gasto_c), len(cuentas))
if caja and gasto_c:
    linea = lambda cta, d=0, cr=0: {"account_id": cta["id"], "debit": str(d), "credit": str(cr)}
    r = conta.post("/accounting/entries", json={"entry_date": HOY.isoformat(), "memo": "QA descuadrado",
                                               "lines": [linea(gasto_c, 100), linea(caja, 0, 90)]})
    chk("Un asiento descuadrado se rechaza", r.status_code in (400, 422), r.status_code)
    r = conta.post("/accounting/entries", json={"entry_date": HOY.isoformat(), "memo": "QA en cero",
                                               "lines": [linea(gasto_c, 0), linea(caja, 0, 0)]})
    chk("Un asiento en cero se rechaza", r.status_code in (400, 422), r.status_code)
    r = conta.post("/accounting/entries", json={"entry_date": HOY.isoformat(), "memo": "QA doble lado",
                                               "lines": [linea(gasto_c, 50, 50), linea(caja, 0, 0)]})
    chk("Una línea con débito y crédito a la vez se rechaza", r.status_code in (400, 422), r.status_code)
    asiento = e.expect("Asiento manual cuadrado de 100", conta.post("/accounting/entries", json={
        "entry_date": HOY.isoformat(), "memo": f"QA asiento {RUN}", "lines": [linea(gasto_c, 100), linea(caja, 0, 100)]}),
        201) or {}
    r = conta.post(f"/accounting/entries/{asiento.get('id')}/reverse", json={"reason": "QA reversa"})
    chk("Se reversa una vez", r.status_code == 201, r.status_code)
    r = conta.post(f"/accounting/entries/{asiento.get('id')}/reverse", json={"reason": "QA reversa doble"})
    chk("No se reversa dos veces", r.status_code in (400, 409), r.status_code)
    r = v.post("/accounting/entries", json={"entry_date": HOY.isoformat(), "memo": "QA vendedor",
                                            "lines": [linea(gasto_c, 1), linea(caja, 0, 1)]})
    chk("El vendedor no hace asientos", r.status_code == 403, r.status_code)
    r = ajeno.post(f"/accounting/entries/{asiento.get('id')}/reverse", json={"reason": "QA ajeno"})
    chk("Otra organización no reversa nuestros asientos", r.status_code in (403, 404), r.status_code)
    otra = ajeno.get("/accounting/accounts").json()
    otra = otra if isinstance(otra, list) else otra.get("items", [])
    if otra:
        r = conta.post("/accounting/entries", json={"entry_date": HOY.isoformat(), "memo": "QA cuenta ajena",
                                                   "lines": [{"account_id": otra[0]["id"], "debit": "1", "credit": "0"},
                                                             linea(caja, 0, 1)]})
        chk("No se usa una cuenta de otra organización", r.status_code in (400, 404), r.status_code)
    cierre = (HOY - timedelta(days=1)).isoformat()
    e.expect("Cierre contable hasta ayer", conta.put("/accounting/settings/lock", json={"locked_through": cierre}), 200)
    r = conta.post("/accounting/entries", json={"entry_date": (HOY - timedelta(days=3)).isoformat(),
                                               "memo": "QA en período cerrado",
                                               "lines": [linea(gasto_c, 5), linea(caja, 0, 5)]})
    chk("No entra un asiento en un período cerrado", r.status_code in (400, 409), r.status_code)
    conta.put("/accounting/settings/lock", json={"locked_through": None})
    r = conta.patch(f"/accounting/accounts/{caja['id']}", json={"account_type": "carro"})
    chk("Tipo de cuenta inventado se rechaza", r.status_code in (400, 422), r.status_code)
tb = conta.get("/accounting/reports/trial-balance").json()
deb = D(tb.get("total_debit") or 0)
cre = D(tb.get("total_credit") or 0)
chk(f"Después de todo, el balance sigue cuadrado ({deb} = {cre})", deb == cre, str(tb)[:150])
r = tec.get("/accounting/reports/trial-balance")
chk("El técnico no ve la contabilidad", r.status_code == 403, r.status_code)

guardar("/tmp/qa_finanzas_conta.json")
print("FIN")
