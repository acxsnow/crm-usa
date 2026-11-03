"""Contabilidad: asientos automáticos idempotentes, doble partida, cierre,
estados financieros e impuestos. Spec 2026-11-01-contabilidad."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.modules.accounting import ledger, posting
from app.modules.accounting.models import Account, JournalEntry, JournalLine
from app.modules.billing.models import Invoice, InvoicePayment
from app.modules.crm.models import Customer
from app.modules.finance.models import Expense, Supplier, SupplierInvoice, SupplierInvoiceLine, SupplierPayment
from app.modules.warehouse.models import WarehouseItem, WarehouseLocation, WarehouseMovement
from tests.field_helpers import approved_case_with_project, headers_for

API = "/api/v1/accounting"
HOY = datetime.now(timezone.utc).date()
Y = HOY.year


@pytest.fixture
async def admin(app_client, active_admin_user):
    return await headers_for(app_client, active_admin_user.email)


async def _factura(db, org, monto="1000", *, status="issued", dia=None, kind="particular"):
    c = Customer(organization_id=org, legal_name="Marge Simpson")
    db.add(c)
    await db.flush()
    f = Invoice(organization_id=org, kind=kind, customer_id=c.id, invoice_number=f"FAC-{monto}", amount=Decimal(monto),
                document_status=status, issue_date=dia or HOY)
    db.add(f)
    await db.commit()
    return f


async def _saldos(db, org, hasta=None) -> dict:
    totales = await ledger._totals(db, org, date_to=hasta or HOY)
    cuentas = {a.id: a for a in (await db.execute(select(Account).where(Account.organization_id == org))).scalars()}
    return {cuentas[k].system_key or cuentas[k].code: ledger._balance(cuentas[k].account_type, *v) for k, v in totales.items()}


async def test_factura_y_pago_con_comision_quedan_cuadrados(app_client, db, seeded_org, admin):
    org = seeded_org["org"].id
    f = await _factura(db, org)
    db.add(InvoicePayment(invoice_id=f.id, amount=Decimal("400"), paid_at=HOY, method="Efectivo"))
    db.add(InvoicePayment(invoice_id=f.id, amount=Decimal("100"), paid_at=HOY, provider="stripe", fee_amount=Decimal("3.20")))
    await db.commit()
    await posting.sync(db, org)
    s = await _saldos(db, org)
    assert s["ar"] == Decimal("500.00") and s["income_particular"] == Decimal("1000.00")
    assert s["bank"] == Decimal("400.00") and s["stripe_clearing"] == Decimal("96.80")
    assert s["exp_merchant_fees"] == Decimal("3.20")
    r = (await app_client.get(f"{API}/reports/balance-sheet", headers=admin)).json()
    assert r["balanced"] is True and r["total_assets"] == "996.80" and r["retained_earnings"] == "996.80"
    tb = (await app_client.get(f"{API}/reports/trial-balance", headers=admin)).json()
    assert tb["balanced"] is True


async def test_correr_dos_veces_no_duplica_y_el_borrador_no_entra(db, seeded_org):
    org = seeded_org["org"].id
    await _factura(db, org)
    await _factura(db, org, "500", status="draft")
    assert (await posting.sync(db, org)) == {"posted": 1, "reversed": 0}
    assert (await posting.sync(db, org)) == {"posted": 0, "reversed": 0}
    assert (await db.execute(select(func.count()).select_from(JournalEntry))).scalar_one() == 1


async def test_anular_reversa_y_cambiar_reversa_y_registra(db, seeded_org):
    org = seeded_org["org"].id
    f = await _factura(db, org)
    await posting.sync(db, org)
    f.amount = Decimal("1200")
    await db.commit()
    assert (await posting.sync(db, org)) == {"posted": 1, "reversed": 1}
    assert (await _saldos(db, org))["income_particular"] == Decimal("1200.00")
    f.document_status = "void"
    await db.commit()
    assert (await posting.sync(db, org)) == {"posted": 0, "reversed": 1}
    assert (await _saldos(db, org))["income_particular"] == Decimal("0.00")
    # El historial queda: nada se borró.
    assert (await db.execute(select(func.count()).select_from(JournalEntry))).scalar_one() == 4


async def test_periodo_cerrado_corre_la_fecha_y_no_mueve_el_pasado(app_client, db, seeded_org, admin):
    org = seeded_org["org"].id
    viejo = date(Y - 1, 3, 10)
    f = await _factura(db, org, dia=viejo)
    await posting.sync(db, org)
    fin = date(Y - 1, 12, 31)
    assert (await app_client.put(f"{API}/settings/lock", json={"locked_through": fin.isoformat()}, headers=admin)).status_code == 200
    f.document_status = "void"
    await db.commit()
    await posting.sync(db, org)
    assert (await _saldos(db, org, fin))["income_particular"] == Decimal("1000.00")  # el año cerrado no cambió
    assert (await _saldos(db, org))["income_particular"] == Decimal("0.00")
    # Una factura nueva con fecha cerrada entra el primer día abierto, una sola vez.
    await _factura(db, org, "50", dia=viejo)
    await posting.sync(db, org)
    assert (await posting.sync(db, org)) == {"posted": 0, "reversed": 0}
    ultima = (await db.execute(select(JournalEntry).where(JournalEntry.source_date == viejo, JournalEntry.reversal_of_id.is_(None))
                               .order_by(JournalEntry.number.desc()))).scalars().first()
    assert ultima.entry_date == date(Y, 1, 1)
    # Y un asiento manual en lo cerrado se rechaza.
    cuentas = {a["system_key"]: a["id"] for a in (await app_client.get(f"{API}/accounts", params={"limit": 200}, headers=admin)).json()}
    r = await app_client.post(f"{API}/entries", headers=admin, json={"entry_date": viejo.isoformat(), "memo": "x", "lines": [
        {"account_id": cuentas["bank"], "debit": 10}, {"account_id": cuentas["opening_equity"], "credit": 10}]})
    assert (r.status_code, r.json()["code"]) == (409, "accounting_period_closed")


async def test_proveedor_inventario_y_salida_a_costo(db, seeded_org):
    org = seeded_org["org"].id
    _, obra = await approved_case_with_project(db, org)
    p = Supplier(organization_id=org, name="Ferguson", kinds=["equipment"])
    db.add(p)
    await db.flush()
    f = SupplierInvoice(organization_id=org, supplier_id=p.id, number="F-1", invoice_date=HOY, due_date=HOY, subtotal=Decimal("300"),
                        tax=Decimal("10"), shipping=Decimal("5"), total=Decimal("315"), status="approved")
    db.add(f)
    await db.flush()
    bodega = SupplierInvoiceLine(invoice_id=f.id, description="Tubo", category="materials", quantity=1, unit_cost=Decimal("200"), amount=Decimal("200"))
    directo = SupplierInvoiceLine(invoice_id=f.id, description="Permiso", category="permit", quantity=1, unit_cost=Decimal("100"), amount=Decimal("100"), project_id=obra.id)
    db.add_all([bodega, directo])
    await db.flush()
    item = WarehouseItem(organization_id=org, name="Tubo", unit="u", unit_cost=Decimal("20"))
    sitio = WarehouseLocation(organization_id=org, name="Principal", kind="warehouse")
    db.add_all([item, sitio])
    await db.flush()
    from app.modules.warehouse.costing import warehouse_entry_key
    db.add(WarehouseMovement(organization_id=org, item_id=item.id, location_id=sitio.id, movement_type="entrada", quantity=Decimal("10"),
                             unit_cost=Decimal("20"), movement_date=HOY, source_key=warehouse_entry_key(bodega.id)))
    db.add(WarehouseMovement(organization_id=org, item_id=item.id, location_id=sitio.id, movement_type="salida", quantity=Decimal("-3"),
                             unit_cost=Decimal("20"), movement_date=HOY, project_id=obra.id))
    db.add(SupplierPayment(organization_id=org, supplier_id=p.id, paid_on=HOY, amount=Decimal("315"), method="ach"))
    await db.commit()
    await posting.sync(db, org)
    s = await _saldos(db, org)
    # 200 entraron, 60 salieron a costo; la entrada del movimiento no se cuenta dos veces.
    assert s["inventory"] == Decimal("140.00") and s["cogs_materials"] == Decimal("60.00")
    assert s["cogs_permit"] == Decimal("100.00") and s["exp_purchase_tax"] == Decimal("10.00") and s["exp_freight"] == Decimal("5.00")
    assert s["ap"] == Decimal("0.00") and s["bank"] == Decimal("-315.00")
    r = await ledger.income_statement(db, org, HOY, HOY, project_id=obra.id)
    assert r["total_cogs"] == "160.00"


async def test_gastos_segun_de_donde_salio_la_plata(db, seeded_org, active_admin_user):
    org = seeded_org["org"].id
    base = dict(organization_id=org, user_id=active_admin_user.id, expense_date=HOY, description="x")
    db.add_all([Expense(**base, category="fuel", amount=Decimal("40"), payment_method="company_card", status="approved"),
                Expense(**base, category="meals", amount=Decimal("15"), payment_method="own_money", status="approved"),
                Expense(**base, category="tools", amount=Decimal("25"), payment_method="own_money", status="reimbursed", reimbursed_at=HOY),
                Expense(**base, category="other", amount=Decimal("999"), payment_method="own_money", status="submitted")])
    await db.commit()
    await posting.sync(db, org)
    s = await _saldos(db, org)
    assert s["credit_card"] == Decimal("40.00") and s["reimbursements"] == Decimal("15.00") and s["bank"] == Decimal("-25.00")
    assert "exp_other" not in s


async def test_asiento_manual_cuadra_y_se_reversa(app_client, db, seeded_org, admin):
    cuentas = {a["system_key"]: a["id"] for a in (await app_client.get(f"{API}/accounts", params={"limit": 200}, headers=admin)).json()}
    hoy = HOY.isoformat()
    malo = await app_client.post(f"{API}/entries", headers=admin, json={"entry_date": hoy, "memo": "Nómina", "lines": [
        {"account_id": cuentas["exp_payroll"], "debit": 100}, {"account_id": cuentas["bank"], "credit": 90}]})
    assert (malo.status_code, malo.json()["code"]) == (400, "journal_unbalanced")
    doble = await app_client.post(f"{API}/entries", headers=admin, json={"entry_date": hoy, "memo": "x", "lines": [
        {"account_id": cuentas["bank"], "debit": 10, "credit": 10}, {"account_id": cuentas["ar"], "credit": 0}]})
    assert doble.json()["code"] == "journal_line_invalid"
    r = await app_client.post(f"{API}/entries", headers=admin, json={"entry_date": hoy, "memo": "Nómina de octubre", "lines": [
        {"account_id": cuentas["exp_payroll"], "debit": "100.50"}, {"account_id": cuentas["bank"], "credit": "100.50"}]})
    assert r.status_code == 201, r.text
    e = r.json()
    corto = await app_client.post(f"{API}/entries/{e['id']}/reverse", headers=admin, json={"reason": "No"})
    assert (corto.status_code, corto.json()["code"]) == (400, "journal_reason_required")
    r = await app_client.post(f"{API}/entries/{e['id']}/reverse", headers=admin, json={"reason": "Mal registrado"})
    assert r.status_code == 201, r.text
    assert (await _saldos(db, seeded_org["org"].id)).get("bank", Decimal("0")) == Decimal("0.00")
    otra = await app_client.post(f"{API}/entries/{e['id']}/reverse", headers=admin, json={"reason": "Otra vez"})
    assert (otra.status_code, otra.json()["code"]) == (409, "journal_already_reversed")


async def test_un_automatico_no_se_reversa_a_mano_y_plan_de_cuentas(app_client, db, seeded_org, admin):
    org = seeded_org["org"].id
    await _factura(db, org)
    await posting.sync(db, org)
    auto = (await app_client.get(f"{API}/entries", params={"source": "automatic"}, headers=admin)).json()[0]
    r = await app_client.post(f"{API}/entries/{auto['id']}/reverse", headers=admin, json={"reason": "Quiero"})
    assert (r.status_code, r.json()["code"]) == (409, "journal_automatic")
    cuentas = (await app_client.get(f"{API}/accounts", params={"limit": 200}, headers=admin)).json()
    banco = next(a for a in cuentas if a["system_key"] == "bank")
    r = await app_client.patch(f"{API}/accounts/{banco['id']}", headers=admin, json={"active": False})
    assert (r.status_code, r.json()["code"]) == (409, "account_system")
    assert (await app_client.patch(f"{API}/accounts/{banco['id']}", headers=admin, json={"name": "Chase Business"})).json()["name"] == "Chase Business"
    malo = await app_client.patch(f"{API}/accounts/{banco['id']}", headers=admin, json={"account_type": "inventado"})
    assert malo.status_code == 422
    r = await app_client.post(f"{API}/accounts", headers=admin, json={"code": "1000", "name": "Otra", "account_type": "asset"})
    assert (r.status_code, r.json()["code"]) == (409, "account_code_taken")
    r = await app_client.post(f"{API}/accounts", headers=admin, json={"code": "1001", "name": "Wells Fargo", "account_type": "asset"})
    assert r.status_code == 201


async def test_impuestos_y_1099_por_anio(app_client, db, seeded_org, admin):
    org = seeded_org["org"].id
    await _factura(db, org, "5000", dia=date(2026, 2, 1))
    grande = Supplier(organization_id=org, name="Instalador", legal_name="=cmd Instalador LLC", kinds=["contractor"], tax_id="12-345")
    chico = Supplier(organization_id=org, name="Pequeño", kinds=["contractor"])
    tarjeta = Supplier(organization_id=org, name="Por tarjeta", kinds=["contractor"])
    materiales = Supplier(organization_id=org, name="Ferguson", kinds=["equipment"])
    db.add_all([grande, chico, tarjeta, materiales])
    await db.flush()
    db.add_all([SupplierPayment(organization_id=org, supplier_id=grande.id, paid_on=date(2026, 3, 1), amount=Decimal("2500"), method="check"),
                SupplierPayment(organization_id=org, supplier_id=chico.id, paid_on=date(2026, 3, 1), amount=Decimal("1999.99"), method="ach"),
                SupplierPayment(organization_id=org, supplier_id=tarjeta.id, paid_on=date(2026, 3, 1), amount=Decimal("9000"), method="card"),
                SupplierPayment(organization_id=org, supplier_id=materiales.id, paid_on=date(2026, 3, 1), amount=Decimal("8000"), method="check")])
    await db.commit()
    r = (await app_client.get(f"{API}/reports/tax-summary", params={"year": 2026}, headers=admin)).json()
    assert r["threshold_1099"] == "2000"
    assert [c["total_paid"] for c in r["contractors_1099"]] == ["2500.00"]
    assert r["contractors_1099"][0]["missing"] == ["W-9", "dirección"]
    assert next(l for l in r["lines"] if l["tax_category"] == "Ingresos brutos")["amount"] == "5000.00"
    assert ledger.threshold_for(2025) == Decimal("600")
    # Quien exporta ve el TIN; Gerencia, que solo lee, lo ve enmascarado y sin dirección.
    assert r["contractors_1099"][0]["tax_id"] == "12-345"
    from app.modules.accounting.ledger import tax_summary

    enmascarado = await tax_summary(db, org, 2026)
    assert enmascarado["contractors_1099"][0]["tax_id"] == "···-345" and enmascarado["contractors_1099"][0]["address"] is None
    # El CSV no deja una fórmula viva en Excel.
    csv = (await app_client.get(f"{API}/export/tax-summary.csv", params={"year": 2026}, headers=admin)).text
    assert "'=cmd Instalador LLC" in csv


async def test_permisos_y_aislamiento(app_client, db, seeded_org, admin, active_technician_user, active_management_user,
                                      active_accounting_user, second_org_admin_user):
    tec = await headers_for(app_client, active_technician_user.email)
    gerencia = await headers_for(app_client, active_management_user.email)
    conta = await headers_for(app_client, active_accounting_user.email)
    otro = await headers_for(app_client, second_org_admin_user.email)
    assert (await app_client.get(f"{API}/accounts", headers=tec)).status_code == 403
    assert (await app_client.get(f"{API}/reports/balance-sheet", headers=tec)).status_code == 403
    assert (await app_client.get(f"{API}/reports/balance-sheet", headers=gerencia)).status_code == 200
    assert (await app_client.post(f"{API}/sync", headers=gerencia)).status_code == 403
    assert (await app_client.post(f"{API}/sync", headers=conta)).status_code == 200
    await _factura(db, seeded_org["org"].id)
    await posting.sync(db, seeded_org["org"].id)
    # La otra organización no ve el asiento ni la cuenta.
    assert (await app_client.get(f"{API}/entries", headers=otro)).json() == []
    assert (await app_client.get(f"{API}/reports/balance-sheet", headers=otro)).json()["total_assets"] == "0.00"
    mia = (await app_client.get(f"{API}/accounts", params={"limit": 1}, headers=admin)).json()[0]
    assert (await app_client.get(f"{API}/accounts/{mia['id']}/ledger", headers=otro)).status_code == 404
    assert (await app_client.patch(f"{API}/accounts/{mia['id']}", json={"name": "x"}, headers=otro)).status_code == 404
    e = (await app_client.get(f"{API}/entries", headers=admin)).json()[0]
    assert (await app_client.post(f"{API}/entries/{e['id']}/reverse", json={"reason": "abc"}, headers=otro)).status_code == 404
    # El mayor de una cuenta lleva su saldo corrido.
    ar = next(a for a in (await app_client.get(f"{API}/accounts", params={"limit": 200}, headers=admin)).json() if a["system_key"] == "ar")
    m = (await app_client.get(f"{API}/accounts/{ar['id']}/ledger", headers=admin)).json()
    assert m["closing_balance"] == "1000.00" and m["rows"][0]["balance"] == "1000.00"
    assert (await db.execute(select(func.count()).select_from(JournalLine))).scalar_one() == 2
