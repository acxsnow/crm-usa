"""Bodega: catálogo, existencias y movimientos (Fase 0 del plan control-bodega).

Lo que se protege aquí es la regla que sostiene todo el módulo: el saldo
(`warehouse_stock`) solo lo mueve `warehouse/service.py`, y el mismo documento
no se aplica dos veces. Si eso se rompe, la bodega deja de cuadrar y el resto
del módulo (salidas, presupuesto, costo real) hereda el error.
"""
import uuid

import pytest
from sqlalchemy import select

from app.modules.warehouse import service as wh
from app.modules.warehouse.catalogs import MovementType
from app.modules.warehouse.models import WarehouseMovement
from tests.field_helpers import headers_for

API = "/api/v1"


@pytest.fixture
def login(app_client):
    """Inicia sesión solo con los usuarios que la prueba usa (el login tiene
    límite de intentos por minuto). El caché es por prueba: cada prueba crea
    usuarios nuevos, así que un token de otra prueba no sirve."""

    cache: dict[str, dict] = {}

    async def _login(email: str) -> dict:
        if email not in cache:
            cache[email] = await headers_for(app_client, email)
        return cache[email]

    return _login


async def _item(app_client, headers, nombre="Tubo cobre 3/8", *, sku="CU-38", **extra) -> dict:
    r = await app_client.post(f"{API}/warehouse/items", json={
        "name": nombre, "sku": sku, "category": "pipe_copper", "unit": "ft",
        "unit_cost": "3.25", "supplier_name": "Ferguson HVAC Supply", **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _entrada(app_client, headers, item_id, cantidad="100", **extra) -> dict:
    r = await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": item_id, "movement_type": "entrada", "quantity": cantidad, **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _existencia(app_client, headers, item_id) -> str:
    """La existencia total del artículo, como la ve la pantalla."""
    r = await app_client.get(f"{API}/warehouse/items/{item_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["total_quantity"]


async def _articulos(app_client, headers) -> list[dict]:
    return (await app_client.get(f"{API}/warehouse/items", headers=headers)).json()


# ---------------------------------------------------------------------------
# Artículos
# ---------------------------------------------------------------------------

async def test_crear_articulo(app_client, login, active_admin_user):
    h = await login(active_admin_user.email)
    item = await _item(app_client, h, min_quantity="50", sale_price="8.50")
    assert (item["name"], item["sku"], item["unit_cost"], item["sale_price"]) == (
        "Tubo cobre 3/8", "CU-38", "3.25", "8.50"
    )
    assert item["margin_pct"] == 61.8
    # Las etiquetas en español viajan con el artículo: el frontend no repite el catálogo.
    assert (item["category_label"], item["unit_label"]) == ("Tubería y cobre", "pies (ft)")
    assert (item["total_quantity"], item["below_minimum"]) == ("0.00", True)  # 0 ≤ 50

    # Una categoría o unidad que no está en el catálogo se rechaza en la puerta:
    # lo que entra a la base son códigos, no el texto libre del Excel.
    mala = await app_client.post(f"{API}/warehouse/items",
                                 json={"name": "X", "category": "categoría inventada"}, headers=h)
    assert mala.status_code == 400, mala.text
    sin_unidad = await app_client.post(f"{API}/warehouse/items",
                                       json={"name": "X", "unit": "cajas_de_madera"}, headers=h)
    assert sin_unidad.status_code == 400, sin_unidad.text


# ---------------------------------------------------------------------------
# Movimientos y saldo
# ---------------------------------------------------------------------------

async def test_la_entrada_sube_y_la_salida_baja_el_saldo(app_client, db, login, active_admin_user):
    h = await login(active_admin_user.email)
    item = await _item(app_client, h)

    entrada = await _entrada(app_client, h, item["id"], "100", reference="FAC-1001")
    assert (entrada["movement_type_label"], entrada["quantity"], entrada["amount"]) == ("Entrada", "100.00", "325.00")
    assert await _existencia(app_client, h, item["id"]) == "100.00"

    # Una salida no se hace a mano por el endpoint (punto 1: va por una orden
    # autorizada); el servicio es quien la aplica, y aquí se comprueba el signo.
    assert (await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": item["id"], "movement_type": "salida", "quantity": "30"}, headers=h)).status_code == 400

    org_id = active_admin_user.organization_id
    bodega = await wh.default_location(db, org_id)
    await wh.record_movement(db, organization_id=org_id, user=active_admin_user, item_id=uuid.UUID(item["id"]),
                             location_id=bodega.id, movement_type=MovementType.SALIDA, quantity="30")
    assert await _existencia(app_client, h, item["id"]) == "70.00"

    # El libro guarda el signo, así el saldo es la suma de los movimientos.
    movs = (await app_client.get(f"{API}/warehouse/movements", params={"item_id": item["id"]}, headers=h)).json()
    assert [m["quantity"] for m in movs] == ["-30.00", "100.00"]


async def test_el_mismo_movimiento_no_descuenta_dos_veces(app_client, db, login, active_admin_user):
    h = await login(active_admin_user.email)
    item = await _item(app_client, h)
    await _entrada(app_client, h, item["id"], "10")

    org_id = active_admin_user.organization_id
    bodega = await wh.default_location(db, org_id)
    clave = "release:0001:linea-1"
    datos = dict(organization_id=org_id, user=active_admin_user, item_id=uuid.UUID(item["id"]),
                 location_id=bodega.id, movement_type=MovementType.SALIDA, quantity="4", source_key=clave)

    primero = await wh.record_movement(db, **datos)
    segundo = await wh.record_movement(db, **datos)  # reintento de la misma entrega
    assert segundo.id == primero.id
    assert await _existencia(app_client, h, item["id"]) == "6.00"

    # Y el libro tiene un solo renglón con esa clave, no dos.
    filas = (await db.execute(select(WarehouseMovement).where(WarehouseMovement.source_key == clave))).scalars().all()
    assert len(filas) == 1


# ---------------------------------------------------------------------------
# Aislamiento por organización
# ---------------------------------------------------------------------------

async def test_aislamiento_por_organizacion(app_client, login, active_admin_user, second_org_admin_user):
    propio = await login(active_admin_user.email)
    ajeno = await login(second_org_admin_user.email)
    item = await _item(app_client, propio)

    assert (await app_client.get(f"{API}/warehouse/items", headers=ajeno)).json() == []
    assert (await app_client.get(f"{API}/warehouse/stock", headers=ajeno)).json() == []
    # De otra organización el artículo no existe: 404, igual que si no existiera.
    assert (await app_client.get(f"{API}/warehouse/items/{item['id']}", headers=ajeno)).status_code == 404
    # Y la otra organización no puede moverle el saldo.
    mov = await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": item["id"], "movement_type": "entrada", "quantity": "5"}, headers=ajeno)
    assert mov.status_code == 404, mov.text


# ---------------------------------------------------------------------------
# Carga del Excel (el conteo del fin de semana)
# ---------------------------------------------------------------------------

async def test_importar_dos_veces_no_duplica_articulos(app_client, login, active_admin_user):
    h = await login(active_admin_user.email)
    filas = [
        {"name": "Tubo cobre 3/8", "sku": "CU-38", "category": "Tubería y cobre", "unit": "ft",
         "unit_cost": "3.25", "quantity": "100", "min_quantity": "50"},
        {"name": "Capacitor 35/5", "sku": "CAP-355", "category": "Eléctrico", "unit": "unidades",
         "quantity": "12"},
    ]
    url = f"{API}/warehouse/import/rows"
    primera = (await app_client.post(url, json={"rows": filas, "filename": "catalogo.xlsx"}, headers=h)).json()
    assert (primera["creados"], primera["actualizados"], primera["conteo_inicial"]) == (2, 0, 2)

    segunda = (await app_client.post(url, json={"rows": filas, "filename": "catalogo.xlsx"}, headers=h)).json()
    assert (segunda["creados"], segunda["actualizados"], segunda["conteo_inicial"]) == (0, 2, 0)

    items = await _articulos(app_client, h)
    assert len(items) == 2
    tubo = next(i for i in items if i["sku"] == "CU-38")
    # El saldo es el del conteo inicial, no el doble por haber subido el archivo dos veces.
    assert (tubo["total_quantity"], tubo["category_label"], tubo["unit_label"]) == ("100.00", "Tubería y cobre", "pies (ft)")
    assert tubo["below_minimum"] is False  # 100 > 50


async def test_una_fila_mala_no_aborta_la_carga(app_client, login, active_admin_user):
    h = await login(active_admin_user.email)
    filas = [
        {"name": "Tubo cobre 3/8", "sku": "CU-38", "quantity": "10"},
        {"name": "Artículo roto", "sku": "ROTO-1", "quantity": "no es un número"},
        {"name": "Capacitor 35/5", "sku": "CAP-355", "quantity": "5"},
        {"name": "Cinta americana", "sku": "CIN-01", "category": "Categoría inventada", "quantity": "3"},
    ]
    r = (await app_client.post(f"{API}/warehouse/import/rows",
                               json={"rows": filas, "filename": "catalogo.xlsx"}, headers=h)).json()

    assert r["creados"] == 3  # los tres buenos entraron
    assert {e["fila"] for e in r["errores"]} == {2}

    items = await _articulos(app_client, h)
    # La fila rota no dejó un artículo a medias: la carga siguió con la siguiente.
    assert {i["sku"] for i in items} == {"CU-38", "CAP-355", "CIN-01"}
    cinta = next(i for i in items if i["sku"] == "CIN-01")
    # Desde la fase 3 del plan de cierre la categoría que el Excel trae y no
    # existe se crea (la hoja «Listas» dejaba agregar las propias) y se avisa.
    assert cinta["category_label"] == "Categoría inventada"
    assert r["categorias_nuevas"] == ["Categoría inventada"]
    assert cinta["total_quantity"] == "3.00"


# ---------------------------------------------------------------------------
# Conteo físico
# ---------------------------------------------------------------------------

async def test_el_conteo_cuadra_el_saldo_con_un_ajuste(app_client, login, active_admin_user):
    h = await login(active_admin_user.email)
    item = await _item(app_client, h)
    await _entrada(app_client, h, item["id"], "10")

    conteo = await app_client.post(f"{API}/warehouse/counts", json={
        "note": "Conteo mensual de bodega",
        "lines": [{"item_id": item["id"], "counted_quantity": "7"}]}, headers=h)
    assert conteo.status_code == 200, conteo.text
    assert conteo.json()["ajustes"][0]["diferencia"] == "-3.00"
    assert await _existencia(app_client, h, item["id"]) == "7.00"

    # La diferencia quedó en el libro como ajuste con su motivo, no como un
    # saldo escrito a mano.
    ajustes = (await app_client.get(f"{API}/warehouse/movements",
                                    params={"movement_type": "ajuste"}, headers=h)).json()
    assert [a["quantity"] for a in ajustes] == ["-3.00"]
    assert ajustes[0]["reference"] == "Conteo físico"

    # Volver a contar lo mismo no inventa movimientos.
    repetido = await app_client.post(f"{API}/warehouse/counts", json={
        "lines": [{"item_id": item["id"], "counted_quantity": "7"}]}, headers=h)
    assert (repetido.json()["ajustes"], repetido.json()["sin_cambio"]) == ([], 1)
    assert await _existencia(app_client, h, item["id"]) == "7.00"


def _xlsx(filas: list[list]) -> bytes:
    """Un .xlsx mínimo con la hoja «Catálogo»: números como celdas numéricas,
    igual que los guarda Excel."""
    import io
    import zipfile

    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

    def celda(col, fila, valor):
        ref = f"{chr(65 + col)}{fila}"
        if valor is None:  # celda vacía, como la deja Excel
            return ""
        if isinstance(valor, (int, float)):
            return f'<c r="{ref}"><v>{valor}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t>{valor}</t></is></c>'

    hoja = "".join(f'<row r="{i}">' + "".join(celda(j, i, v) for j, v in enumerate(f)) + "</row>"
                   for i, f in enumerate(filas, start=1))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>'
                                      f'<sheet name="Catálogo" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData>{hoja}</sheetData></worksheet>')
    return buf.getvalue()


async def test_el_excel_con_costos_con_centavos_se_carga_completo(app_client, login, active_admin_user):
    """Falla real del QA del 21 oct: Excel guarda 3.25 como número, el lector lo
    devolvía como float y el dinero (que no acepta floats) rechazaba la fila."""
    h = await login(active_admin_user.email)
    libro = _xlsx([
        ["Nombre del material", "Referencia / SKU", "Categoría", "Unidad", "Costo unitario", "Cantidad en bodega hoy"],
        ["Tubo cobre 3/8", "CU-38", "Tubería y cobre", "pies (ft)", 3.25, 120.5],
        ["Capacitor 35/5", "CAP-355", "Eléctrico", "unidades", 18, 4],
    ])
    r = await app_client.post(f"{API}/warehouse/import", files={
        "file": ("catalogo.xlsx", libro, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=h)
    assert r.status_code == 200, r.text
    assert (r.json()["creados"], r.json()["errores"]) == (2, [])
    items = {i["sku"]: i for i in (await app_client.get(f"{API}/warehouse/items", headers=h)).json()}
    assert (items["CU-38"]["unit_cost"], items["CU-38"]["total_quantity"]) == ("3.25", "120.50")


# ---------------------------------------------------------------------------
# Catálogo listo para AC Pro (plan bodega-cierre, fase 3)
# ---------------------------------------------------------------------------

async def test_el_excel_de_ac_pro_trae_codigo_fabricante_y_marca(app_client, login, active_admin_user):
    """AC Pro identifica cada producto con su código (número: Excel lo guarda
    como número y antes la fila fallaba al limpiarlo), el del fabricante y la
    marca. Los tres quedan en el artículo y el buscador encuentra por cualquiera."""
    h = await login(active_admin_user.email)
    libro = _xlsx([
        ["Nombre del material", "Código AC Pro", "Número del fabricante", "Marca", "Categoría", "Unidad",
         "Costo unitario", "Cantidad en bodega hoy"],
        ["T4 Pro Programmable Thermostat", 61664, "TH4110U2005", "Honeywell", "Termostatos", "unidades", 74.40, 3],
        ["Wire Connector Orange 100 Pack", 36141, None, None, "Eléctrico", "paquetes", 12.64, 2],
    ])
    r = await app_client.post(f"{API}/warehouse/import", files={
        "file": ("acpro.xlsx", libro, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=h)
    assert r.status_code == 200, r.text
    assert (r.json()["creados"], r.json()["errores"], r.json()["categorias_nuevas"]) == (2, [], [])

    items = {i["sku"]: i for i in (await _articulos(app_client, h))}
    termostato = items["61664"]  # sin «.0»
    assert (termostato["brand"], termostato["manufacturer_part"]) == ("Honeywell", "TH4110U2005")
    assert (termostato["category_label"], items["36141"]["unit_label"]) == ("Termostatos", "paquetes")

    for buscado in ("th4110", "honeywell", "61664"):
        hallados = (await app_client.get(f"{API}/warehouse/items", params={"q": buscado}, headers=h)).json()
        assert [a["sku"] for a in hallados] == ["61664"], buscado


async def test_las_categorias_las_administra_la_organizacion(app_client, login, active_admin_user,
                                                             active_technician_user, second_org_admin_user):
    admin = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)

    # Arrancan con las del cuestionario más las de AC Pro.
    iniciales = (await app_client.get(f"{API}/warehouse/catalogs", headers=admin)).json()["categories"]
    assert {"Tubería y cobre", "Termostatos", "Filtros", "Hierro negro y gas", "Otro"} <= set(iniciales.values())

    # Crear: el código sale del nombre y no se repite el nombre.
    r = await app_client.post(f"{API}/warehouse/categories", json={"label": "Bombas de condensado"}, headers=admin)
    assert r.status_code == 201, r.text
    bombas = r.json()
    assert (bombas["code"], bombas["active"]) == ("bombas_de_condensado", True)
    otra = await app_client.post(f"{API}/warehouse/categories", json={"label": "bombas de condensado"}, headers=admin)
    assert (otra.status_code, otra.json()["code"]) == (409, "category_exists")
    # El técnico ve el catálogo pero no lo administra.
    nope = await app_client.post(f"{API}/warehouse/categories", json={"label": "X"}, headers=tecnico)
    assert nope.status_code == 403
    assert (await app_client.get(f"{API}/warehouse/categories", headers=tecnico)).status_code == 200

    item = await _item(app_client, admin, "Bomba CP-22T", sku="1936", category=bombas["code"])
    assert item["category_label"] == "Bombas de condensado"

    # Renombrar cambia cómo se ve en los artículos, sin tocarlos.
    r = await app_client.put(f"{API}/warehouse/categories/{bombas['id']}", json={"label": "Bombas"}, headers=admin)
    assert r.status_code == 200, r.text
    visto = (await app_client.get(f"{API}/warehouse/items/{item['id']}", headers=admin)).json()
    assert (visto["category"], visto["category_label"]) == ("bombas_de_condensado", "Bombas")

    # Desactivar: deja de ofrecerse, el artículo que la tiene se sigue editando
    # sin moverlo y un artículo nuevo ya no la puede usar.
    await app_client.put(f"{API}/warehouse/categories/{bombas['id']}", json={"active": False}, headers=admin)
    catalogo = (await app_client.get(f"{API}/warehouse/catalogs", headers=admin)).json()
    assert "bombas_de_condensado" not in catalogo["categories"]
    assert catalogo["category_labels"]["bombas_de_condensado"] == "Bombas"
    editar = await app_client.put(f"{API}/warehouse/items/{item['id']}", json={
        "name": "Bomba CP-22T 115V", "sku": "1936", "category": "bombas_de_condensado", "unit": "ft"}, headers=admin)
    assert editar.status_code == 200, editar.text
    nuevo = await app_client.post(f"{API}/warehouse/items", json={
        "name": "Otra bomba", "category": "bombas_de_condensado"}, headers=admin)
    assert (nuevo.status_code, nuevo.json()["code"]) == (400, "inactive_item_category")

    # «Otro» es el comodín: no se desactiva.
    lista = (await app_client.get(f"{API}/warehouse/categories", headers=admin)).json()
    otro = next(c for c in lista if c["code"] == "other")
    r = await app_client.put(f"{API}/warehouse/categories/{otro['id']}", json={"active": False}, headers=admin)
    assert (r.status_code, r.json()["code"]) == (400, "default_category_required")
    assert next(c for c in lista if c["code"] == "bombas_de_condensado")["item_count"] == 1

    # Cada organización tiene las suyas.
    ajena = await login(second_org_admin_user.email)
    suyas = (await app_client.get(f"{API}/warehouse/categories", headers=ajena)).json()
    assert "bombas_de_condensado" not in {c["code"] for c in suyas}
    r = await app_client.put(f"{API}/warehouse/categories/{bombas['id']}", json={"label": "Mía"}, headers=ajena)
    assert r.status_code == 404
