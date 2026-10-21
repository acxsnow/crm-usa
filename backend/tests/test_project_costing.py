"""Estimado contra real del proyecto y compras por adelantado (Fase 3, punto 3).

Lo que se protege aquí es la decisión D-BOD-2: **lo que entra a bodega es
inventario, no costo de la obra**. La obra se cuesta cuando el material sale, así
que el mismo material nunca se cuenta dos veces —ni en la factura de compra ni en
la entrega de bodega— y el número que ve el supervisor es el que puede explicar.
"""
import json
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.modules.field_ops.models import ProjectStatus
from app.modules.finance.models import SupplierInvoiceLine
from app.modules.warehouse import costing as costing_svc
from app.modules.warehouse import service as wh
from tests.field_helpers import approved_case_with_project, headers_for, jpeg_bytes

HOY = date.today()
API = "/api/v1"


@pytest.fixture
def login(app_client):
    cache: dict[str, dict] = {}

    async def _login(email: str) -> dict:
        if email not in cache:
            cache[email] = await headers_for(app_client, email)
        return cache[email]

    return _login


# ---------------------------------------------------------------------------
# Ayudas: catálogo, bodega y el camino de la orden de salida
# ---------------------------------------------------------------------------

async def _item(app_client, headers, nombre="Tubo cobre 3/8", *, sku="CU-38", categoria="pipe_copper",
                unidad="ft", costo="5.00") -> dict:
    r = await app_client.post(f"{API}/warehouse/items", json={
        "name": nombre, "sku": sku, "category": categoria, "unit": unidad, "unit_cost": costo}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _entrada(app_client, headers, item_id, cantidad) -> dict:
    r = await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": item_id, "movement_type": "entrada", "quantity": cantidad}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _entregar(app_client, headers, item_id, project_id, cantidad) -> dict:
    """Arma, manda a autorizar, autoriza y entrega: el camino del punto 1."""
    r = await app_client.post(f"{API}/warehouse/releases", json={
        "project_id": str(project_id), "lines": [{"item_id": item_id, "quantity": cantidad}]}, headers=headers)
    assert r.status_code == 201, r.text
    orden_id = r.json()["id"]
    for paso in ("submit", "approve", "deliver"):
        r = await app_client.post(f"{API}/warehouse/releases/{orden_id}/{paso}", headers=headers)
        assert r.status_code == 200, r.text
    return r.json()


async def _presupuesto_aprobado(app_client, headers, project_id, lineas) -> dict:
    r = await app_client.post(f"{API}/warehouse/budgets", json={
        "project_id": str(project_id), "lines": lineas}, headers=headers)
    assert r.status_code == 201, r.text
    presupuesto = r.json()
    aprobado = await app_client.post(f"{API}/warehouse/budgets/{presupuesto['id']}/approve", headers=headers)
    assert aprobado.status_code == 200, aprobado.text
    return aprobado.json()


async def _proveedor(app_client, headers) -> dict:
    r = await app_client.post(f"{API}/payables/suppliers", json={
        "name": "Ferguson HVAC Supply", "kinds": ["equipment"], "payment_terms_days": 30,
        "states": ["AZ"], "bank_details": "Chase 1234"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _factura(app_client, headers, supplier_id, numero, lineas) -> dict:
    r = await app_client.post(f"{API}/payables/invoices", data={"data": json.dumps({
        "supplier_id": supplier_id, "number": numero, "invoice_date": HOY.isoformat(), "lines": lineas})},
        headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _gasto_aprobado(app_client, tecnico, aprobador, project_id, monto="60.00") -> dict:
    """El técnico lo sube y el admin lo aprueba: nadie aprueba su propio gasto."""
    r = await app_client.post(f"{API}/expenses", data={"data": json.dumps({
        "expense_date": HOY.isoformat(), "category": "fuel", "amount": monto, "description": "Gasolina",
        "payment_method": "own_money", "project_id": str(project_id)})},
        files={"receipt": ("recibo.jpg", jpeg_bytes(), "image/jpeg")}, headers=tecnico)
    assert r.status_code == 201, r.text
    gasto = r.json()
    r = await app_client.post(f"{API}/expenses/{gasto['id']}/review", json={"approve": True}, headers=aprobador)
    assert r.status_code == 200, r.text
    return r.json()


async def _comparacion(app_client, headers, project_id) -> dict:
    r = await app_client.get(f"{API}/warehouse/projects/{project_id}/budget-vs-actual", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _fila(comparacion: dict, categoria: str) -> dict:
    return next(r for r in comparacion["rows"] if r["category"] == categoria)


# ---------------------------------------------------------------------------
# D-BOD-2: el mismo material no se cuenta dos veces
# ---------------------------------------------------------------------------

async def test_el_material_que_entra_por_factura_y_luego_sale_no_se_cuenta_dos_veces(
        app_client, login, db, seeded_org, active_admin_user):
    admin = await login(active_admin_user.email)
    org = seeded_org["org"]
    org_id = org.id
    _, project = await approved_case_with_project(db, org.id)
    project_id = project.id
    tubo = await _item(app_client, admin, "Tubo cobre 3/8", costo="5.00")

    # La compra del tubo: 20 pies por 100.00, cargada al proyecto.
    proveedor = await _proveedor(app_client, admin)
    await _factura(app_client, admin, proveedor["id"], "F-100", [
        {"description": "Tubo cobre 3/8", "category": "materials", "quantity": "20", "unit_cost": "5.00",
         "project_id": str(project.id)},
    ])
    # El equipo que se compró y se fue directo a la obra: eso sí es costo desde
    # el primer día.
    await _factura(app_client, admin, proveedor["id"], "F-101", [
        {"description": "Bomba de calor", "category": "equipment", "quantity": "1", "unit_cost": "800.00",
         "project_id": str(project.id)},
    ])

    # Pero el tubo **entró a bodega**: es inventario, no costo todavía. El
    # movimiento de entrada por compra deja la clave de la línea de factura.
    db.expire_all()
    linea = (await db.execute(select(SupplierInvoiceLine).where(
        SupplierInvoiceLine.description == "Tubo cobre 3/8"))).scalars().one()
    ubicacion = await wh.default_location(db, org_id)
    await wh.record_movement(db, organization_id=org_id, user=None, item_id=uuid.UUID(tubo["id"]),
                             location_id=ubicacion.id, movement_type="entrada", quantity="20",
                             source_key=costing_svc.warehouse_entry_key(linea.id))

    # Ahora sí sale a la obra: 8 pies. Ese es el costo del proyecto.
    await _entregar(app_client, admin, tubo["id"], project_id, "8")

    comparacion = await _comparacion(app_client, admin, project_id)
    # El tubo cuenta una sola vez: los 40 de lo entregado, no los 100 de la
    # factura. El equipo comprado directo sí cuenta completo.
    assert _fila(comparacion, "materials")["actual"] == "40.00"
    assert _fila(comparacion, "equipment")["actual"] == "800.00"
    assert comparacion["totals"]["actual"] == "840.00"


async def test_sin_pasar_por_bodega_la_compra_ya_es_costo_de_la_obra(
        app_client, login, db, seeded_org, active_admin_user):
    admin = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    proveedor = await _proveedor(app_client, admin)
    await _factura(app_client, admin, proveedor["id"], "F-200", [
        {"description": "Tubo cobre 3/8", "category": "materials", "quantity": "20", "unit_cost": "5.00",
         "project_id": str(project.id)},
    ])

    comparacion = await _comparacion(app_client, admin, project.id)
    assert _fila(comparacion, "materials")["actual"] == "100.00"


# ---------------------------------------------------------------------------
# Gastos de campo y estimado contra real
# ---------------------------------------------------------------------------

async def test_los_gastos_aprobados_del_proyecto_suman_al_costo_real(
        app_client, login, db, seeded_org, active_admin_user, active_technician_user):
    admin = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    # El gasto se carga a la obra del técnico: nadie gasta en una obra que no es suya.
    _, project = await approved_case_with_project(db, seeded_org["org"].id,
                                                  technician_id=active_technician_user.id)
    await _gasto_aprobado(app_client, tecnico, admin, project.id, "60.00")

    comparacion = await _comparacion(app_client, admin, project.id)
    assert _fila(comparacion, "field_expenses")["actual"] == "60.00"
    assert comparacion["totals"]["actual"] == "60.00"


async def test_la_desviacion_por_categoria_sale_del_presupuesto_aprobado(
        app_client, login, db, seeded_org, active_admin_user):
    admin = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    tubo = await _item(app_client, admin, "Tubo cobre 3/8", costo="5.00")
    await _entrada(app_client, admin, tubo["id"], "100")

    # Se presupuestó 50 de material y 100 de mano de obra.
    await _presupuesto_aprobado(app_client, admin, project.id, [
        {"category": "materials", "item_id": tubo["id"], "quantity": "10"},
        {"category": "labor", "description": "Cuadrilla", "quantity": "1", "unit": "day", "unit_cost": "100"},
    ])

    # Y se usaron 8 pies: 40 de material, contra los 50 estimados.
    await _entregar(app_client, admin, tubo["id"], project.id, "8")

    comparacion = await _comparacion(app_client, admin, project.id)
    assert _fila(comparacion, "materials") == {
        "category": "materials", "label": "Material", "estimated": "50.00", "actual": "40.00",
        "deviation": "-10.00", "deviation_pct": -20.0}
    # La mano de obra está presupuestada y todavía no se registró ningún costo
    # de esa categoría: la fila lo muestra tal cual.
    assert (_fila(comparacion, "labor")["estimated"], _fila(comparacion, "labor")["actual"]) == ("100.00", "0.00")
    assert comparacion["totals"] == {"estimated": "150.00", "actual": "40.00", "deviation": "-110.00",
                                     "deviation_pct": -73.3}
    assert comparacion["budget_status"] == "aprobado"


# ---------------------------------------------------------------------------
# Compras por adelantado
# ---------------------------------------------------------------------------

async def test_compras_sugeridas_son_lo_presupuestado_por_venir_menos_la_existencia(
        app_client, login, db, seeded_org, active_admin_user):
    admin = await login(active_admin_user.email)
    org = seeded_org["org"]
    _, en_curso = await approved_case_with_project(db, org.id)
    _, otra_en_curso = await approved_case_with_project(db, org.id)
    _, terminada = await approved_case_with_project(db, org.id)
    tubo = await _item(app_client, admin, "Tubo cobre 3/8", costo="5.00")
    await _entrada(app_client, admin, tubo["id"], "10")

    await _presupuesto_aprobado(app_client, admin, en_curso.id,
                                [{"category": "materials", "item_id": tubo["id"], "quantity": "20"}])
    await _presupuesto_aprobado(app_client, admin, otra_en_curso.id,
                                [{"category": "materials", "item_id": tubo["id"], "quantity": "5"}])
    # Lo de una obra ya terminada no se vuelve a comprar.
    await _presupuesto_aprobado(app_client, admin, terminada.id,
                                [{"category": "materials", "item_id": tubo["id"], "quantity": "100"}])
    terminada.status = ProjectStatus.completed
    await db.commit()
    # Y un presupuesto sin aprobar tampoco cuenta.
    r = await app_client.post(f"{API}/warehouse/budgets", json={
        "project_id": str(otra_en_curso.id),
        "lines": [{"category": "materials", "item_id": tubo["id"], "quantity": "50"}]}, headers=admin)
    assert r.status_code == 201, r.text

    # Lo que cuenta es 20 + 5 = 25: la obra terminada y el borrador sin aprobar
    # quedan fuera. Con 10 en bodega, faltan 15 por comprar (75.00 a 5.00).
    reporte = (await app_client.get(f"{API}/warehouse/purchasing", headers=admin)).json()
    fila = reporte["rows"][0]
    assert (fila["budgeted"], fila["in_stock"], fila["to_buy"]) == ("25.00", "10.00", "15.00")
    assert fila["estimated_cost"] == "75.00"
    assert reporte["totals"]["to_buy"] == "15.00"


async def test_la_obra_con_presupuesto_no_ve_el_presupuesto_de_otra_organizacion(
        app_client, login, db, seeded_org, active_admin_user, second_org_admin_user):
    propio = await login(active_admin_user.email)
    ajeno = await login(second_org_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    tubo = await _item(app_client, propio, "Tubo cobre 3/8", costo="5.00")
    await _presupuesto_aprobado(app_client, propio, project.id,
                                [{"category": "materials", "item_id": tubo["id"], "quantity": "10"}])

    assert (await app_client.get(f"{API}/warehouse/projects/{project.id}/budget-vs-actual",
                                 headers=ajeno)).status_code == 404
    assert (await app_client.get(f"{API}/warehouse/purchasing", headers=ajeno)).json() == {
        "rows": [], "totals": {"budgeted": "0.00", "to_buy": "0.00", "items": 0}}
