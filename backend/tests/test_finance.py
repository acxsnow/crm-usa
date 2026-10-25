"""Gastos de campo, proveedores y pagos, conciliación, rentabilidad y reportes."""
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.modules.finance import reconciliation
from tests.field_helpers import approved_case_with_project, headers_for, jpeg_bytes


def _hoy_utc() -> date:
    """El «hoy» del servidor (la organización de prueba está en UTC). Con
    `date.today()` local, después de las 7 p. m. en Bogotá ya es mañana en UTC
    y estas pruebas fallaban por la hora del día."""
    return datetime.now(timezone.utc).date()


HOY = _hoy_utc()
API = "/api/v1"


class _Sesiones:
    """Inicia sesión solo con los usuarios que la prueba usa (el login tiene
    límite de intentos por minuto)."""

    CORREOS = {"admin": "admin@acme-demo.com", "conta": "contabilidad@acme-demo.com",
               "gerencia": "gerencia@acme-demo.com", "vendedor": "vendedor@acme-demo.com",
               "adm": "admin-staff@acme-demo.com"}

    def __init__(self, client, tecnico_email):
        self.client, self.cache = client, {}
        self.CORREOS = {**self.CORREOS, "tecnico": tecnico_email}

    async def __call__(self, quien):
        if quien not in self.cache:
            self.cache[quien] = await headers_for(self.client, self.CORREOS[quien])
        return self.cache[quien]


@pytest.fixture
def sesion(app_client, active_admin_user, active_accounting_user, active_management_user, active_salesperson_user,
           active_technician_user, active_admin_staff_user):
    return _Sesiones(app_client, active_technician_user.email)


async def _gasto(app_client, headers, monto="45.50", **extra):
    datos = {"expense_date": HOY.isoformat(), "category": "fuel", "amount": monto,
             "description": "Gasolina ida al parque", "payment_method": "own_money", **extra}
    return await app_client.post(f"{API}/expenses", data={"data": json.dumps(datos)},
                                 files={"receipt": ("recibo.jpg", jpeg_bytes(), "image/jpeg")}, headers=headers)


# ---------------------------------------------------------------------------
# Gastos de campo
# ---------------------------------------------------------------------------

async def test_expense_flow_with_review_and_reimbursement(app_client, sesion):
    r = await _gasto(app_client, (await sesion("tecnico")))
    assert r.status_code == 201, r.text
    g = r.json()
    assert (g["status"], g["amount"], g["has_receipt"]) == ("submitted", "45.50", True)
    assert (await app_client.get(f"{API}/expenses/{g['id']}/receipt", headers=(await sesion("tecnico")))).status_code == 200
    # El vendedor no ve gastos ajenos; Contabilidad sí.
    assert (await app_client.get(f"{API}/expenses/{g['id']}/receipt", headers=(await sesion("vendedor")))).status_code == 404
    todos = (await app_client.get(f"{API}/expenses", headers=(await sesion("conta")))).json()
    assert [x["id"] for x in todos] == [g["id"]]
    url = f"{API}/expenses/{g['id']}/review"
    assert (await app_client.post(url, json={"approve": False}, headers=(await sesion("conta")))).status_code == 400
    assert (await app_client.post(url, json={"approve": True}, headers=(await sesion("tecnico")))).status_code == 403
    r = await app_client.post(url, json={"approve": True}, headers=(await sesion("conta")))
    assert r.json()["status"] == "approved"
    assert (await app_client.put(f"{API}/expenses/{g['id']}", headers=(await sesion("tecnico")), json={
        "expense_date": HOY.isoformat(), "category": "fuel", "amount": "1", "description": "cambio",
        "payment_method": "own_money"})).status_code == 409
    r = await app_client.post(f"{API}/expenses/{g['id']}/reimburse", json={"paid_on": HOY.isoformat(),
                                                                          "reference": "ZELLE-1"}, headers=(await sesion("conta")))
    assert r.json()["status"] == "reimbursed"


async def test_expense_rules(app_client, sesion):
    assert (await _gasto(app_client, (await sesion("tecnico")), monto="0")).status_code == 400
    assert (await _gasto(app_client, (await sesion("tecnico")), monto="5000.01")).status_code == 400
    r = await _gasto(app_client, (await sesion("tecnico")), expense_date=(HOY + timedelta(days=3)).isoformat())
    assert r.status_code == 400
    sin_recibo = await app_client.post(f"{API}/expenses", data={"data": json.dumps({
        "expense_date": HOY.isoformat(), "category": "fuel", "amount": "10", "description": "sin recibo"})},
        headers=(await sesion("tecnico")))
    assert sin_recibo.status_code == 422
    disfrazado = await app_client.post(f"{API}/expenses", data={"data": json.dumps({
        "expense_date": HOY.isoformat(), "category": "fuel", "amount": "10", "description": "exe"})},
        files={"receipt": ("r.jpg", b"MZ\x90\x00 exe", "image/jpeg")}, headers=(await sesion("tecnico")))
    assert disfrazado.status_code == 400
    # Nadie aprueba lo propio, ni siquiera Contabilidad.
    propio = (await _gasto(app_client, (await sesion("admin")))).json()
    assert (await app_client.post(f"{API}/expenses/{propio['id']}/review", json={"approve": True},
                                  headers=(await sesion("admin")))).status_code == 403


# ---------------------------------------------------------------------------
# Proveedores y cuentas por pagar
# ---------------------------------------------------------------------------

async def _proveedor(app_client, headers, nombre="Ferguson HVAC Supply", **extra):
    r = await app_client.post(f"{API}/payables/suppliers", json={"name": nombre, "kinds": ["equipment"],
                                                                  "payment_terms_days": 30, "states": ["AZ"],
                                                                  "bank_details": "Chase 1234", **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _factura(app_client, headers, supplier_id, numero, total=None, lines=None, **extra):
    datos = {"supplier_id": supplier_id, "number": numero, "invoice_date": HOY.isoformat(), **extra}
    if lines:
        datos["lines"] = lines
    else:
        datos["total"] = total
    return await app_client.post(f"{API}/payables/invoices", data={"data": json.dumps(datos)}, headers=headers)


async def test_suppliers_and_bank_details_visibility(app_client, sesion):
    s = await _proveedor(app_client, (await sesion("conta")))
    vista = (await app_client.get(f"{API}/payables/suppliers/{s['id']}", headers=(await sesion("gerencia")))).json()
    assert vista["bank_details"] == "•••"  # Gerencia (Aldo) no ve datos bancarios; Contabilidad sí
    lista = (await app_client.get(f"{API}/payables/suppliers", headers=(await sesion("conta")))).json()
    assert lista[0]["bank_details"] == "Chase 1234"
    assert (await app_client.post(f"{API}/payables/suppliers", json={"name": "Ferguson HVAC Supply"},
                                  headers=(await sesion("conta")))).status_code == 409
    assert (await app_client.post(f"{API}/payables/suppliers", json={"name": "X", "states": ["TX"]},
                                  headers=(await sesion("conta")))).status_code == 400
    assert (await app_client.get(f"{API}/payables/suppliers", headers=(await sesion("tecnico")))).status_code == 403
    r = await app_client.post(f"{API}/payables/suppliers/import", headers=(await sesion("conta")), json={
        "text": "Nombre,EIN,Teléfono,Condiciones\nCED Electrical,12-345,(602) 555-0100,15\nFerguson HVAC Supply,,,\n,,,\n"})
    assert r.json()["created"] == 1 and r.json()["skipped"] == 1 and len(r.json()["invalid"]) == 1


async def test_invoice_below_threshold_needs_one_approval_from_the_approver(app_client, sesion):
    s = await _proveedor(app_client, (await sesion("conta")))
    r = await _factura(app_client, (await sesion("conta")), s["id"], "F-100", lines=[
        {"description": "Mini-split 12k", "category": "equipment", "quantity": "2", "unit_cost": "1200.00"}],
        tax="192.00", shipping="25")
    assert r.status_code == 201, r.text
    inv = r.json()
    assert (inv["subtotal"], inv["total"], inv["status"]) == ("2400.00", "2617.00", "pending_approval")
    assert inv["due_date"] == (HOY + timedelta(days=30)).isoformat()
    assert inv["approvals_missing"] == ["approve"]
    assert (await _factura(app_client, (await sesion("conta")), s["id"], "F-100", total="10")).status_code == 409
    url = f"{API}/payables/invoices/{inv['id']}/approve"
    # Contabilidad sola no aprueba bajo el umbral: es de Aldo (payables.approve).
    assert (await app_client.post(url, json={}, headers=(await sesion("conta")))).status_code == 403
    r = await app_client.post(url, json={"notes": "OK"}, headers=(await sesion("gerencia")))
    assert r.json()["status"] == "approved"
    r = await app_client.post(f"{API}/payables/invoices/{inv['id']}/schedule",
                              json={"scheduled_payment_date": (HOY + timedelta(days=7)).isoformat()}, headers=(await sesion("gerencia")))
    assert r.status_code == 200 and r.json()["scheduled_payment_date"]


async def test_invoice_over_threshold_needs_accounting_and_approver(app_client, sesion):
    s = await _proveedor(app_client, (await sesion("conta")))
    inv = (await _factura(app_client, (await sesion("conta")), s["id"], "F-BIG", total="12000.00")).json()
    assert inv["approvals_missing"] == ["approve", "accounting"]
    url = f"{API}/payables/invoices/{inv['id']}/approve"
    r = await app_client.post(url, json={}, headers=(await sesion("gerencia")))
    assert r.json()["status"] == "pending_approval" and r.json()["approvals_missing"] == ["accounting"]
    assert (await app_client.post(url, json={}, headers=(await sesion("gerencia")))).status_code == 409  # misma persona
    r = await app_client.post(url, json={}, headers=(await sesion("conta")))
    assert r.json()["status"] == "approved"
    assert [a["capacity"] for a in r.json()["approvals"]] == ["approve", "accounting"]
    # «Pagada al momento» no sirve desde el umbral.
    r = await _factura(app_client, (await sesion("conta")), s["id"], "F-BIG2", total="15000", paid_now=True)
    assert r.status_code == 400 and r.json()["code"] == "paid_now_over_threshold"


async def test_paid_now_purchase_with_card(app_client, sesion):
    s = await _proveedor(app_client, (await sesion("conta")))
    r = await _factura(app_client, (await sesion("conta")), s["id"], "T-55", total="89.99", paid_now=True, paid_method="card")
    assert r.status_code == 201, r.text
    assert (r.json()["status"], r.json()["balance"]) == ("paid", "0.00")


async def test_partial_and_multi_invoice_payments(app_client, sesion):
    s = await _proveedor(app_client, (await sesion("conta")))
    otro = await _proveedor(app_client, (await sesion("conta")), nombre="Otro proveedor")
    a = (await _factura(app_client, (await sesion("conta")), s["id"], "A1", total="1000.00")).json()
    b = (await _factura(app_client, (await sesion("conta")), s["id"], "B1", total="500.00")).json()
    ajena = (await _factura(app_client, (await sesion("conta")), otro["id"], "Z1", total="10.00")).json()

    conta = await sesion("conta")

    def pago(monto, repartos):
        return app_client.post(f"{API}/payables/payments", headers=conta, data={"data": json.dumps({
            "supplier_id": s["id"], "paid_on": HOY.isoformat(), "amount": monto, "method": "ach",
            "reference": "ACH-1", "allocations": repartos})})

    r = await pago("100", [{"invoice_id": a["id"], "amount": "100"}])
    assert r.status_code == 409  # sin aprobar no se paga
    for inv in (a, b, ajena):
        await app_client.post(f"{API}/payables/invoices/{inv['id']}/approve", json={}, headers=(await sesion("gerencia")))
    assert (await pago("100", [{"invoice_id": a["id"], "amount": "90"}])).status_code == 400  # no cuadra
    assert (await pago("1001", [{"invoice_id": a["id"], "amount": "1001"}])).status_code == 400  # pasa el saldo
    assert (await pago("10", [{"invoice_id": ajena["id"], "amount": "10"}])).status_code == 400  # otro proveedor
    r = await pago("1200", [{"invoice_id": a["id"], "amount": "1000"}, {"invoice_id": b["id"], "amount": "200"}])
    assert r.status_code == 201, r.text
    a2 = (await app_client.get(f"{API}/payables/invoices/{a['id']}", headers=(await sesion("conta")))).json()
    b2 = (await app_client.get(f"{API}/payables/invoices/{b['id']}", headers=(await sesion("conta")))).json()
    assert (a2["status"], b2["status"], b2["balance"]) == ("paid", "partially_paid", "300.00")
    assert (await app_client.post(f"{API}/payables/invoices/{a['id']}/void", json={"reason": "x"},
                                  headers=(await sesion("conta")))).status_code == 409  # con pagos no se anula
    aging = (await app_client.get(f"{API}/payables/aging", headers=(await sesion("gerencia")))).json()
    assert aging["totals"]["total"] == "310.00"
    csv_ = await app_client.get(f"{API}/payables/export.csv?kind=payments", headers=(await sesion("conta")))
    assert csv_.status_code == 200 and "ACH-1" in csv_.text and "A1:1000.00" in csv_.text
    assert (await app_client.get(f"{API}/payables/export.csv", headers=(await sesion("gerencia")))).status_code == 403


async def test_aging_buckets_by_due_date(app_client, sesion):
    s = await _proveedor(app_client, (await sesion("conta")))
    for n, dias in (("V1", 0), ("V2", 15), ("V3", 45), ("V4", 120)):
        fecha = HOY - timedelta(days=dias + 30)
        await _factura(app_client, (await sesion("conta")), s["id"], n, total="100", invoice_date=fecha.isoformat())
    filas = (await app_client.get(f"{API}/payables/aging", headers=(await sesion("conta")))).json()["totals"]
    assert (filas["current"], filas["d1_30"], filas["d31_60"], filas["d90_plus"]) == ("100.00", "100.00", "100.00", "100.00")


# ---------------------------------------------------------------------------
# Rentabilidad
# ---------------------------------------------------------------------------

async def test_project_profitability(app_client, db, seeded_org, sesion, active_technician_user):
    case, project = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    from app.modules.billing.models import Invoice, InvoicePayment

    db.add(Invoice(organization_id=seeded_org["org"].id, kind="rebate", project_id=project.id,
                   customer_id=project.customer_id, invoice_number="REB-T-1", amount=Decimal("4000.00"),
                   payments=[InvoicePayment(amount=Decimal("3800.00"), paid_at=HOY)]))
    await db.commit()
    s = await _proveedor(app_client, (await sesion("conta")))
    r = await _factura(app_client, (await sesion("conta")), s["id"], "P-1", lines=[
        {"description": "Bomba de calor", "category": "equipment", "quantity": "1", "unit_cost": "1500",
         "project_id": str(project.id)},
        {"description": "Bodega", "category": "materials", "quantity": "1", "unit_cost": "500"}],
        tax="100.00")
    assert r.status_code == 201, r.text
    g = (await _gasto(app_client, (await sesion("tecnico")), monto="60.00", project_id=str(project.id))).json()
    await app_client.post(f"{API}/expenses/{g['id']}/review", json={"approve": True}, headers=(await sesion("conta")))
    rep = (await app_client.get(f"{API}/finance/profitability?project_id={project.id}", headers=(await sesion("gerencia")))).json()
    fila = rep["rows"][0]
    # 1500 + 75 de impuesto proporcional (1500/2000 × 100) + 60 de gasolina.
    assert (fila["expected"], fila["collected"], fila["costs"]) == ("4000.00", "3800.00", "1635.00")
    assert fila["cost_breakdown"]["equipment"] == "1575.00" and fila["cost_breakdown"]["field_expenses"] == "60.00"
    assert (fila["margin"], fila["margin_pct"]) == ("2165.00", 57.0)
    assert (await app_client.get(f"{API}/finance/profitability", headers=(await sesion("tecnico")))).status_code == 403


# ---------------------------------------------------------------------------
# Conciliación bancaria
# ---------------------------------------------------------------------------

def test_statement_parser_accepts_common_bank_formats():
    filas, malas = reconciliation.parse_statement(
        "Posting Date,Description,Debit,Credit\n10/01/2026,ACH CREDIT PROGRAM,,4000.00\n"
        "10/02/2026,CHECK 1001,(1200.00),\n10/03/2026,FEE,15.00,\nbad,row,,\n")
    assert [str(f["amount"]) for f in filas] == ["4000.00", "-1200.00", "-15.00"] and malas == ["fila 5"]


async def test_reconciliation_auto_and_manual(app_client, db, seeded_org, sesion):
    s = await _proveedor(app_client, (await sesion("conta")))
    inv = (await _factura(app_client, (await sesion("conta")), s["id"], "R-1", total="1200.00")).json()
    await app_client.post(f"{API}/payables/invoices/{inv['id']}/approve", json={}, headers=(await sesion("gerencia")))
    await app_client.post(f"{API}/payables/payments", headers=(await sesion("conta")), data={"data": json.dumps({
        "supplier_id": s["id"], "paid_on": HOY.isoformat(), "amount": "1200.00", "method": "check",
        "allocations": [{"invoice_id": inv["id"], "amount": "1200.00"}]})})
    extracto = (f"Date,Description,Amount\n{HOY.isoformat()},CHECK 1001,-1200.00\n"
                f"{HOY.isoformat()},MONTHLY FEE,-15.00\n")
    r = await app_client.post(f"{API}/reconciliation/statements", data={"account_label": "Chase operativa"},
                              files={"file": ("extracto.csv", extracto.encode(), "text/csv")}, headers=(await sesion("conta")))
    assert r.status_code == 201, r.text
    assert (r.json()["lines"], r.json()["auto_matched"]) == (2, 1)
    pendientes = (await app_client.get(f"{API}/reconciliation/lines?status=unmatched", headers=(await sesion("conta")))).json()
    assert [l["description"] for l in pendientes] == ["MONTHLY FEE"]
    fee = pendientes[0]["id"]
    assert (await app_client.get(f"{API}/reconciliation/lines/{fee}/candidates", headers=(await sesion("conta")))).json()["items"] == []
    assert (await app_client.post(f"{API}/reconciliation/lines/{fee}/ignore", json={"notes": "Comisión bancaria"},
                                  headers=(await sesion("conta")))).json()["status"] == "ignored"
    resumen = (await app_client.get(f"{API}/reconciliation/summary", headers=(await sesion("conta")))).json()
    assert (resumen["matched"], resumen["ignored"], resumen["unmatched"]) == (1, 1, 0)
    # Un pago ya conciliado no se ofrece otra vez.
    cheque = (await app_client.get(f"{API}/reconciliation/lines?status=matched", headers=(await sesion("conta")))).json()[0]
    await app_client.post(f"{API}/reconciliation/lines/{cheque['id']}/unmatch", headers=(await sesion("conta")))
    cands = (await app_client.get(f"{API}/reconciliation/lines/{cheque['id']}/candidates", headers=(await sesion("conta")))).json()
    assert len(cands["items"]) == 1
    r = await app_client.post(f"{API}/reconciliation/lines/{cheque['id']}/match", headers=(await sesion("conta")),
                              json={"matched_type": cands["items"][0]["type"], "matched_id": cands["items"][0]["id"]})
    assert r.json()["status"] == "matched" and r.json()["auto_matched"] is False
    assert (await app_client.get(f"{API}/reconciliation/summary", headers=(await sesion("gerencia")))).status_code == 403


# ---------------------------------------------------------------------------
# Reportes y permisos e inspecciones
# ---------------------------------------------------------------------------

async def test_reports_and_csv(app_client, sesion):
    for kind in ("commercial", "operations", "finance"):
        r = await app_client.get(f"{API}/reports/{kind}", headers=(await sesion("gerencia")))
        assert r.status_code == 200, r.text
        assert r.json()["kpis"] and r.json()["sections"]
        csv_ = await app_client.get(f"{API}/reports/{kind}/csv", headers=(await sesion("gerencia")))
        assert csv_.status_code == 200 and csv_.text.startswith("Reporte")
    assert (await app_client.get(f"{API}/reports/inventado", headers=(await sesion("gerencia")))).status_code == 404
    assert (await app_client.get(f"{API}/reports/commercial", headers=(await sesion("tecnico")))).status_code == 403


async def test_permits_and_inspections_overview(app_client, db, seeded_org, sesion):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    r = await app_client.post(f"{API}/projects/{project.id}/permits", headers=(await sesion("adm")), json={
        "jurisdiction": "Phoenix", "status": "approved", "approved_on": HOY.isoformat(),
        "expires_on": (HOY + timedelta(days=10)).isoformat()})
    assert r.status_code == 201, r.text
    lista = (await app_client.get(f"{API}/permits?expiring_within_days=30", headers=(await sesion("adm")))).json()
    assert len(lista) == 1 and lista[0]["days_to_expiry"] == 10
    assert (await app_client.get(f"{API}/permits?expiring_within_days=5", headers=(await sesion("adm")))).json() == []
    assert (await app_client.get(f"{API}/inspections", headers=(await sesion("adm")))).status_code == 200
    assert (await app_client.get(f"{API}/permits", headers=(await sesion("vendedor")))).status_code == 403


# ---------------------------------------------------------------------------
# Separación de funciones (revisión de seguridad del 21 de octubre)
# ---------------------------------------------------------------------------

async def test_nadie_se_reembolsa_su_propio_gasto(app_client, sesion):
    propio = (await _gasto(app_client, (await sesion("admin")))).json()
    assert (await app_client.post(f"{API}/expenses/{propio['id']}/review", json={"approve": True},
                                  headers=(await sesion("conta")))).status_code == 200
    url = f"{API}/expenses/{propio['id']}/reimburse"
    r = await app_client.post(url, json={"paid_on": HOY.isoformat()}, headers=(await sesion("admin")))
    assert (r.status_code, r.json()["code"]) == (403, "expense_self_reimbursement")
    r = await app_client.post(url, json={"paid_on": HOY.isoformat()}, headers=(await sesion("conta")))
    assert r.json()["status"] == "reimbursed"


async def test_solo_contabilidad_cambia_los_datos_bancarios(app_client, sesion):
    gerencia, conta = await sesion("gerencia"), await sesion("conta")
    # Gerencia puede dar de alta y editar el proveedor, pero no su cuenta.
    r = await app_client.post(f"{API}/payables/suppliers", json={
        "name": "Proveedor Nuevo", "kinds": ["equipment"], "states": ["AZ"], "bank_details": "Cuenta X"}, headers=gerencia)
    assert (r.status_code, r.json()["code"]) == (403, "bank_details_forbidden")
    s = await _proveedor(app_client, conta)
    base = {"name": s["name"], "kinds": ["equipment"], "states": ["AZ"], "payment_terms_days": 30}
    # Lo que Gerencia ve enmascarado no se toca al guardar.
    r = await app_client.put(f"{API}/payables/suppliers/{s['id']}", json={**base, "phone": "602-555-0101",
                                                                         "bank_details": "•••"}, headers=gerencia)
    assert r.status_code == 200, r.text
    r = await app_client.put(f"{API}/payables/suppliers/{s['id']}", json={**base, "bank_details": "Otra cuenta"},
                             headers=gerencia)
    assert (r.status_code, r.json()["code"]) == (403, "bank_details_forbidden")
    r = await app_client.put(f"{API}/payables/suppliers/{s['id']}", json={**base, "bank_details": "Wells 9876"},
                             headers=conta)
    assert r.json()["bank_details"] == "Wells 9876"


async def test_cambio_de_banco_y_pago_al_momento_avisan_a_quien_aprueba(db, seeded_org, app_client, sesion,
                                                                       active_accounting_user,
                                                                       active_management_user):
    from sqlalchemy import select

    from app.modules.notifications import service as avisos
    from app.modules.notifications.models import Notification

    org = seeded_org["org"].id
    s = await _proveedor(app_client, (await sesion("conta")))
    f = (await _factura(app_client, (await sesion("conta")), s["id"], "T-77", total="50", paid_now=True)).json()
    base = {"organization_id": str(org), "user_id": str(active_accounting_user.id)}
    await avisos.process_event(db, "supplier.bank_changed", {**base, "supplier_id": s["id"]})
    await avisos.process_event(db, "payable.paid_now", {**base, "invoice_id": f["id"]})

    async def titulos(user_id):
        return sorted(n.title for n in (await db.execute(select(Notification).where(
            Notification.user_id == user_id))).scalars().all())

    assert await titulos(active_management_user.id) == [
        "Datos bancarios cambiados: Ferguson HVAC Supply", "Pagada al momento: Ferguson HVAC Supply T-77"]
    assert await titulos(active_accounting_user.id) == []  # quien hizo el cambio no se avisa a sí mismo
