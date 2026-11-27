"""Bodega: recepción de compras, conteos, traslados y ajustes con motivo
(cuestionario de bodega, 26 nov 2026).

Lo que se protege:
- Una compra puede llegar por partes: lo pendiente se ve y no se recibe de más.
- El costo de lo que entra es el de la factura más su parte del impuesto y del
  envío, y mueve el costo promedio del artículo.
- En contabilidad lo recibido queda debiendo («Compras recibidas por
  facturar») hasta que se asocia la factura, y la factura no duplica la deuda.
- El conteo inicial arranca el inventario; el mensual deja ajustes.
- Un ajuste a mano dice por qué.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.modules.accounting import ledger, posting
from app.modules.accounting.models import Account
from app.modules.finance.models import Supplier, SupplierInvoice
from tests.field_helpers import headers_for

API = "/api/v1"
HOY = datetime.now(timezone.utc).date()


@pytest.fixture
async def admin(app_client, active_admin_user):
    return await headers_for(app_client, active_admin_user.email)


async def _item(app_client, h, nombre="Capacitor 45/5", sku="CAP-455", costo="10.00", **extra) -> dict:
    r = await app_client.post(f"{API}/warehouse/items", json={
        "name": nombre, "sku": sku, "category": "parts", "unit": "unit", "unit_cost": costo, **extra}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


async def _proveedor(db, org, nombre="Ferguson") -> Supplier:
    p = Supplier(organization_id=org, name=nombre, kinds=["materials"])
    db.add(p)
    await db.commit()
    return p


async def _saldos(db, org) -> dict:
    totales = await ledger._totals(db, org, date_to=HOY)
    cuentas = {a.id: a for a in (await db.execute(select(Account).where(Account.organization_id == org))).scalars()}
    return {cuentas[k].system_key or cuentas[k].code: ledger._balance(cuentas[k].account_type, *v)
            for k, v in totales.items()}


async def _existencia(app_client, h, item_id) -> tuple[str, str]:
    i = (await app_client.get(f"{API}/warehouse/items/{item_id}", headers=h)).json()
    return i["total_quantity"], i["unit_cost"]


async def test_recepcion_parcial_costo_con_impuesto_y_promedio(app_client, db, seeded_org, admin):
    org = seeded_org["org"].id
    prov = await _proveedor(db, org)
    cap = await _item(app_client, admin)
    # Ya había 10 a 10,00 (conteo inicial).
    r = await app_client.post(f"{API}/warehouse/counts", headers=admin, json={
        "initial": True, "lines": [{"item_id": cap["id"], "counted_quantity": "10"}]})
    assert r.status_code == 200, r.text
    assert r.json()["ajustes"][0]["movement_type"] == "entrada"

    # Pidió 10 a 12,00 con 6 de impuesto y 6 de envío: cada unidad cuesta 13,20.
    r = await app_client.post(f"{API}/warehouse/receipts", headers=admin, json={
        "supplier_id": str(prov.id), "document_number": "F-778", "tax": "6", "shipping": "6",
        "lines": [{"item_id": cap["id"], "ordered_quantity": "10", "unit_cost": "12.00", "received": "8"}]})
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["number"].startswith("REC-")
    assert (rec["status"], rec["pending_lines"]) == ("abierta", 1)
    linea = rec["lines"][0]
    assert (linea["received_quantity"], linea["pending_quantity"], linea["landed_unit_cost"]) == ("8.00", "2.00", "13.20")
    # Promedio: (10 × 10,00 + 8 × 13,20) / 18 = 11,42
    assert await _existencia(app_client, admin, cap["id"]) == ("18.00", "11.42")

    # No se reciben más de los que faltan.
    r = await app_client.post(f"{API}/warehouse/receipts/{rec['id']}/receive", headers=admin, json={
        "lines": [{"line_id": linea["id"], "quantity": "3"}]})
    assert (r.status_code, r.json()["code"]) == (400, "receipt_exceeds_pending")

    # Llegan los 2 que faltaban: queda recibida completa.
    r = await app_client.post(f"{API}/warehouse/receipts/{rec['id']}/receive", headers=admin, json={
        "lines": [{"line_id": linea["id"], "quantity": "2"}]})
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["pending_lines"]) == ("recibida", 0)
    assert (await _existencia(app_client, admin, cap["id"]))[0] == "20.00"

    # Ya completa, no se recibe más ni se cierra.
    r = await app_client.post(f"{API}/warehouse/receipts/{rec['id']}/receive", headers=admin, json={
        "lines": [{"line_id": linea["id"], "quantity": "1"}]})
    assert (r.status_code, r.json()["code"]) == (409, "receipt_not_open")

    # En el libro hay dos entradas con la referencia de la recepción.
    movs = (await app_client.get(f"{API}/warehouse/movements", headers=admin,
                                 params={"item_id": cap["id"], "movement_type": "entrada"})).json()
    assert sorted(m["quantity"] for m in movs) == ["10.00", "2.00", "8.00"]
    assert any((m["reference"] or "").startswith(rec["number"]) for m in movs)


async def test_cerrar_con_faltante_y_anular_si_no_llego_nada(app_client, db, seeded_org, admin):
    org = seeded_org["org"].id
    cap = await _item(app_client, admin)
    filtro = await _item(app_client, admin, "Filtro 16x25", "FIL-1625", "4.00")
    r = await app_client.post(f"{API}/warehouse/receipts", headers=admin, json={
        "supplier_name": "Home Depot", "lines": [
            {"item_id": cap["id"], "ordered_quantity": "5", "unit_cost": "10", "received": "5"},
            {"item_id": filtro["id"], "ordered_quantity": "12", "unit_cost": "4", "received": "6"}]})
    rec = r.json()
    assert rec["status"] == "abierta" and rec["supplier_name"] == "Home Depot"
    r = await app_client.post(f"{API}/warehouse/receipts/{rec['id']}/close", headers=admin, json={"reason": " "})
    assert r.status_code in (400, 422)
    r = await app_client.post(f"{API}/warehouse/receipts/{rec['id']}/close", headers=admin,
                              json={"reason": "El proveedor no tiene más filtros"})
    assert (r.status_code, r.json()["status"]) == (200, "cerrada")
    assert r.json()["close_reason"] == "El proveedor no tiene más filtros"

    vacia = (await app_client.post(f"{API}/warehouse/receipts", headers=admin, json={
        "supplier_name": "Home Depot", "lines": [{"item_id": cap["id"], "ordered_quantity": "5", "unit_cost": "10"}]})).json()
    assert vacia["status"] == "abierta" and vacia["lines"][0]["received_quantity"] == "0.00"
    r = await app_client.post(f"{API}/warehouse/receipts/{vacia['id']}/close", headers=admin, json={"reason": "Se canceló el pedido"})
    assert r.json()["status"] == "anulada"

    # Datos malos.
    malas = [
        {"lines": [{"item_id": cap["id"], "ordered_quantity": "1"}]},  # sin proveedor
        {"supplier_name": "X", "lines": [{"item_id": cap["id"], "ordered_quantity": "0"}]},
        {"supplier_name": "X", "lines": [{"item_id": cap["id"], "ordered_quantity": "1", "unit_cost": "-1"}]},
        {"supplier_name": "X", "lines": [{"item_id": cap["id"], "ordered_quantity": "2"},
                                         {"item_id": cap["id"], "ordered_quantity": "1"}]},
        {"supplier_name": "X", "lines": [{"item_id": cap["id"], "ordered_quantity": "2", "received": "3"}]},
    ]
    for datos in malas:
        r = await app_client.post(f"{API}/warehouse/receipts", headers=admin, json=datos)
        assert r.status_code in (400, 422), (datos, r.text)
    assert (await _existencia(app_client, admin, cap["id"]))[0] == "5.00"


async def test_contabilidad_queda_por_facturar_y_la_factura_lo_salda(app_client, db, seeded_org, admin):
    org = seeded_org["org"].id
    prov = await _proveedor(db, org)
    otro = await _proveedor(db, org, "Johnstone")
    cap = await _item(app_client, admin)
    rec = (await app_client.post(f"{API}/warehouse/receipts", headers=admin, json={
        "supplier_id": str(prov.id), "document_number": "F-90", "tax": "10",
        "lines": [{"item_id": cap["id"], "ordered_quantity": "10", "unit_cost": "10", "received": "10"}]})).json()
    assert rec["received_value"] == "110.00"
    await posting.sync(db, org)
    s = await _saldos(db, org)
    assert (s["inventory"], s["grni"]) == (Decimal("110.00"), Decimal("110.00"))

    # La factura del proveedor (la registra Contabilidad) por 112: dos de diferencia.
    f = SupplierInvoice(organization_id=org, supplier_id=prov.id, number="F-90", invoice_date=HOY, due_date=HOY,
                        subtotal=Decimal("102"), tax=Decimal("10"), shipping=Decimal("0"), total=Decimal("112"),
                        status="approved")
    ajena = SupplierInvoice(organization_id=org, supplier_id=otro.id, number="J-1", invoice_date=HOY, due_date=HOY,
                            subtotal=Decimal("5"), tax=Decimal("0"), shipping=Decimal("0"), total=Decimal("5"),
                            status="approved")
    db.add_all([f, ajena])
    await db.commit()

    cands = (await app_client.get(f"{API}/warehouse/receipts/{rec['id']}/invoice-candidates", headers=admin)).json()
    assert [c["number"] for c in cands] == ["F-90"]
    r = await app_client.put(f"{API}/warehouse/receipts/{rec['id']}/invoice", headers=admin,
                             json={"supplier_invoice_id": str(ajena.id)})
    assert (r.status_code, r.json()["code"]) == (400, "supplier_mismatch")
    r = await app_client.put(f"{API}/warehouse/receipts/{rec['id']}/invoice", headers=admin,
                             json={"supplier_invoice_id": str(f.id)})
    assert (r.status_code, r.json()["supplier_invoice_number"]) == (200, "F-90")

    await posting.sync(db, org)
    s = await _saldos(db, org)
    # La cuenta puente queda en cero, la deuda es la de la factura (no el doble)
    # y la diferencia de 2 sube el inventario.
    assert s["grni"] == Decimal("0.00")
    assert s["ap"] == Decimal("117.00")  # 112 de esta + 5 de la otra
    assert s["inventory"] == Decimal("112.00")
    assert s.get("exp_purchase_tax", Decimal("0")) == Decimal("0")

    # Quitar la factura devuelve la deuda a «por facturar».
    await app_client.put(f"{API}/warehouse/receipts/{rec['id']}/invoice", headers=admin, json={"supplier_invoice_id": None})
    await posting.sync(db, org)
    s = await _saldos(db, org)
    assert s["grni"] == Decimal("110.00")


async def test_conteo_mensual_deja_ajustes_y_el_inicial_entra_con_costo(app_client, db, seeded_org, admin):
    cap = await _item(app_client, admin, costo="0")
    planilla = (await app_client.get(f"{API}/warehouse/counts/sheet", headers=admin)).json()
    assert any(f["item_id"] == cap["id"] and f["system_quantity"] == "0.00" for f in planilla)

    r = await app_client.post(f"{API}/warehouse/counts", headers=admin, json={
        "initial": True, "lines": [{"item_id": cap["id"], "counted_quantity": "7", "unit_cost": "9.50"}]})
    assert r.status_code == 200, r.text
    assert await _existencia(app_client, admin, cap["id"]) == ("7.00", "9.50")

    r = await app_client.post(f"{API}/warehouse/counts", headers=admin, json={
        "lines": [{"item_id": cap["id"], "counted_quantity": "5"}]})
    aj = r.json()["ajustes"][0]
    assert (aj["movement_type"], aj["diferencia"]) == ("ajuste", "-2.00")
    movs = (await app_client.get(f"{API}/warehouse/movements", headers=admin,
                                 params={"item_id": cap["id"], "movement_type": "ajuste"})).json()
    assert movs[0]["reason"] == "count" and movs[0]["reason_label"] == "Conteo físico"

    for malo in ({"lines": [{"item_id": cap["id"], "counted_quantity": "-1"}]},
                 {"lines": [{"item_id": cap["id"], "counted_quantity": "1"}, {"item_id": cap["id"], "counted_quantity": "2"}]}):
        r = await app_client.post(f"{API}/warehouse/counts", headers=admin, json=malo)
        assert r.status_code == 400, r.text
    assert (await _existencia(app_client, admin, cap["id"]))[0] == "5.00"


async def test_ajuste_a_mano_pide_motivo_y_traslado_a_la_camioneta(app_client, db, seeded_org, admin,
                                                                   active_technician_user):
    cap = await _item(app_client, admin)
    await app_client.post(f"{API}/warehouse/counts", headers=admin, json={
        "initial": True, "lines": [{"item_id": cap["id"], "counted_quantity": "10"}]})
    base = {"item_id": cap["id"], "movement_type": "ajuste", "quantity": "-1"}
    r = await app_client.post(f"{API}/warehouse/movements", headers=admin, json=base)
    assert (r.status_code, r.json()["code"]) == (400, "adjustment_reason_required")
    r = await app_client.post(f"{API}/warehouse/movements", headers=admin, json={**base, "reason": "inventado"})
    assert r.status_code == 400
    r = await app_client.post(f"{API}/warehouse/movements", headers=admin, json={**base, "reason": "other"})
    assert (r.status_code, r.json()["code"]) == (400, "adjustment_note_required")
    r = await app_client.post(f"{API}/warehouse/movements", headers=admin, json={**base, "reason": "damaged",
                                                                                 "note": "Se quemó en la prueba"})
    assert r.status_code == 201, r.text
    assert r.json()["reason_label"] == "Dañado o vencido"

    camioneta = (await app_client.post(f"{API}/warehouse/locations", headers=admin, json={
        "name": "Camioneta de Tito", "kind": "truck", "technician_user_id": str(active_technician_user.id)})).json()
    r = await app_client.post(f"{API}/warehouse/movements", headers=admin, json={
        "item_id": cap["id"], "movement_type": "traslado", "quantity": "4", "to_location_id": camioneta["id"]})
    assert r.status_code == 201, r.text
    i = (await app_client.get(f"{API}/warehouse/items/{cap['id']}", headers=admin)).json()
    donde = {l["name"]: l["quantity"] for l in i["by_location"]}
    assert donde["Camioneta de Tito"] == "4.00" and i["total_quantity"] == "9.00"

    cats = (await app_client.get(f"{API}/warehouse/catalogs", headers=admin)).json()
    assert "count" not in cats["adjustment_reasons"] and "damaged" in cats["adjustment_reasons"]


async def test_permisos_y_aislamiento(app_client, db, seeded_org, admin, active_technician_user,
                                      second_org_admin_user):
    cap = await _item(app_client, admin)
    rec = (await app_client.post(f"{API}/warehouse/receipts", headers=admin, json={
        "supplier_name": "Home Depot", "lines": [{"item_id": cap["id"], "ordered_quantity": "5", "unit_cost": "10"}]})).json()
    tec = await headers_for(app_client, active_technician_user.email)
    r = await app_client.post(f"{API}/warehouse/receipts", headers=tec, json={
        "supplier_name": "X", "lines": [{"item_id": cap["id"], "ordered_quantity": "1"}]})
    assert r.status_code == 403
    assert (await app_client.get(f"{API}/warehouse/receipts", headers=tec)).status_code == 403
    ajeno = await headers_for(app_client, second_org_admin_user.email)
    assert (await app_client.get(f"{API}/warehouse/receipts/{rec['id']}", headers=ajeno)).status_code == 404
    r = await app_client.post(f"{API}/warehouse/receipts/{rec['id']}/receive", headers=ajeno, json={
        "lines": [{"line_id": rec["lines"][0]["id"], "quantity": "1"}]})
    assert r.status_code == 404
    lista = (await app_client.get(f"{API}/warehouse/receipts", headers=ajeno)).json()
    assert rec["id"] not in str(lista)
