"""Listas predefinidas por tipo de trabajo (Fase 2 del plan control-bodega, punto 2).

El cliente lo pidió así: «aires y pedestales siempre llevan el mismo material, a
veces cambian algunas cantidades o calibres». Lo que se protege aquí es que la
lista sea una **plantilla** y no un documento compartido: al aplicarla, la orden
de salida se queda con su propia copia, se le ajustan cantidades y calibres, se
le agregan extras a mano, y corregir la plantilla después no cambia lo ya pedido.
"""
import pytest

from tests.field_helpers import headers_for

API = "/api/v1"


@pytest.fixture
def login(app_client):
    """Inicia sesión solo con los usuarios que la prueba usa (el login tiene
    límite de intentos por minuto). El caché es por prueba."""
    cache: dict[str, dict] = {}

    async def _login(email: str) -> dict:
        if email not in cache:
            cache[email] = await headers_for(app_client, email)
        return cache[email]

    return _login


async def _item(app_client, headers, nombre, *, sku, unidad="ft", costo="3.25") -> dict:
    r = await app_client.post(f"{API}/warehouse/items", json={
        "name": nombre, "sku": sku, "category": "pipe_copper", "unit": unidad, "unit_cost": costo}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _lista(app_client, headers, items, *, nombre="Aire — estándar", project_type="hvac_install") -> dict:
    r = await app_client.post(f"{API}/warehouse/kits", json={
        "name": nombre, "project_type": project_type, "description": "Lo que siempre lleva un aire",
        "items": items}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _borrador(app_client, headers, item_id, cantidad="1") -> dict:
    r = await app_client.post(f"{API}/warehouse/releases", json={
        "lines": [{"item_id": item_id, "quantity": cantidad}]}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _aplicar(app_client, headers, kit_id, orden_id):
    return await app_client.post(f"{API}/warehouse/kits/{kit_id}/apply", json={"release_id": orden_id},
                                headers=headers)


async def _orden(app_client, headers, orden_id) -> dict:
    r = await app_client.get(f"{API}/warehouse/releases/{orden_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _lista_por_id(app_client, headers, kit_id) -> dict:
    r = await app_client.get(f"{API}/warehouse/kits/{kit_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _por_articulo(orden: dict) -> dict:
    return {l["item_name"]: l for l in orden["lines"]}


# ---------------------------------------------------------------------------
# La lista
# ---------------------------------------------------------------------------

async def test_crear_lista_y_verla_con_su_material(app_client, login, active_admin_user):
    bodega = await login(active_admin_user.email)
    tubo = await _item(app_client, bodega, "Tubo cobre 3/8", sku="CU-38")
    aislante = await _item(app_client, bodega, "Aislante 3/8", sku="AI-38", unidad="roll")

    lista = await _lista(app_client, bodega, [
        {"item_id": tubo["id"], "quantity": "20", "spec_label": "3/8", "section": "Líneas"},
        {"item_id": aislante["id"], "quantity": "1", "section": "Líneas"},
    ])
    assert lista["name"] == "Aire — estándar"
    assert lista["project_type"] == "hvac_install"
    assert [r["item_name"] for r in lista["items"]] == ["Tubo cobre 3/8", "Aislante 3/8"]
    assert lista["items"][0]["quantity"] == "20.00"
    assert lista["items"][0]["spec_label"] == "3/8"

    todas = (await app_client.get(f"{API}/warehouse/kits", headers=bodega)).json()
    assert [k["id"] for k in todas] == [lista["id"]]


# ---------------------------------------------------------------------------
# Aplicarla: es una copia
# ---------------------------------------------------------------------------

async def test_aplicarla_a_un_borrador_copia_las_lineas(app_client, login, active_admin_user,
                                                       active_technician_user):
    bodega = await login(active_admin_user.email)
    # El técnico es quien arma la orden y usa la lista (respuesta 2).
    tecnico = await login(active_technician_user.email)
    tubo = await _item(app_client, bodega, "Tubo cobre 3/8", sku="CU-38")
    aislante = await _item(app_client, bodega, "Aislante 3/8", sku="AI-38", unidad="roll")
    lista = await _lista(app_client, bodega, [
        {"item_id": tubo["id"], "quantity": "20", "spec_label": "3/8"},
        {"item_id": aislante["id"], "quantity": "1"},
    ])

    # Arranca con un extra a mano y encima aplica la lista: se suman.
    extra = await _item(app_client, bodega, "Cinta de teflón", sku="TE-01", unidad="unit")
    orden = await _borrador(app_client, tecnico, extra["id"], "2")

    respuesta = await _aplicar(app_client, tecnico, lista["id"], orden["id"])
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["agregadas"], cuerpo["omitidas"]) == (2, 0)

    lineas = _por_articulo(cuerpo)
    assert lineas["Tubo cobre 3/8"]["quantity_requested"] == "20.00"
    assert lineas["Tubo cobre 3/8"]["spec_label"] == "3/8"
    # Lo que viene de la lista queda marcado como tal, y el extra como manual.
    assert lineas["Tubo cobre 3/8"]["origin"] == "lista"
    assert lineas["Cinta de teflón"]["origin"] == "manual"
    # Todavía es borrador: nada de esto comprometió saldo.
    assert cuerpo["status"] == "borrador"


async def test_aplicarla_dos_veces_no_repite_el_material(app_client, login, active_admin_user):
    bodega = await login(active_admin_user.email)
    tubo = await _item(app_client, bodega, "Tubo cobre 3/8", sku="CU-38")
    lista = await _lista(app_client, bodega, [{"item_id": tubo["id"], "quantity": "20", "spec_label": "3/8"}])
    orden = await _borrador(app_client, bodega, tubo["id"], "1")

    primera = (await _aplicar(app_client, bodega, lista["id"], orden["id"])).json()
    assert primera["agregadas"] == 1
    # Un doble clic no manda el mismo material dos veces.
    segunda = (await _aplicar(app_client, bodega, lista["id"], orden["id"])).json()
    assert (segunda["agregadas"], segunda["omitidas"]) == (0, 1)
    assert len(segunda["lines"]) == 2


# ---------------------------------------------------------------------------
# La copia es de la orden, no de la plantilla
# ---------------------------------------------------------------------------

async def test_editar_la_lista_no_cambia_la_orden_ya_armada(app_client, login, active_admin_user):
    bodega = await login(active_admin_user.email)
    tubo = await _item(app_client, bodega, "Tubo cobre 3/8", sku="CU-38")
    lista = await _lista(app_client, bodega, [{"item_id": tubo["id"], "quantity": "20", "spec_label": "3/8"}])
    orden = await _borrador(app_client, bodega, tubo["id"], "1")
    await _aplicar(app_client, bodega, lista["id"], orden["id"])

    # Enero: la lista cambia a 30 pies. La orden de diciembre no se entera.
    editada = await app_client.put(f"{API}/warehouse/kits/{lista['id']}", json={
        "name": "Aire — estándar", "project_type": "hvac_install",
        "items": [{"item_id": tubo["id"], "quantity": "30", "spec_label": "1/2"}]}, headers=bodega)
    assert editada.status_code == 200, editada.text
    assert editada.json()["items"][0]["quantity"] == "30.00"

    lineas = _por_articulo(await _orden(app_client, bodega, orden["id"]))
    assert lineas["Tubo cobre 3/8"]["quantity_requested"] == "20.00"
    assert lineas["Tubo cobre 3/8"]["spec_label"] == "3/8"


async def test_en_la_copia_se_ajustan_cantidades_y_calibres(app_client, login, active_admin_user):
    bodega = await login(active_admin_user.email)
    tubo = await _item(app_client, bodega, "Tubo cobre 3/8", sku="CU-38")
    lista = await _lista(app_client, bodega, [{"item_id": tubo["id"], "quantity": "20", "spec_label": "3/8"}])
    orden = await _borrador(app_client, bodega, tubo["id"], "1")
    await _aplicar(app_client, bodega, lista["id"], orden["id"])

    # Este trabajo es más largo y va en 1/2: se ajusta en la orden, no en la lista.
    r = await app_client.put(f"{API}/warehouse/releases/{orden['id']}", json={
        "lines": [{"item_id": tubo["id"], "quantity": "35", "spec_label": "1/2", "origin": "lista"}]},
        headers=bodega)
    assert r.status_code == 200, r.text
    lineas = _por_articulo(r.json())
    assert lineas["Tubo cobre 3/8"]["quantity_requested"] == "35.00"
    assert lineas["Tubo cobre 3/8"]["spec_label"] == "1/2"

    # La plantilla sigue como estaba.
    assert (await _lista_por_id(app_client, bodega, lista["id"]))["items"][0]["quantity"] == "20.00"


async def test_se_agregan_extras_libres_a_la_copia(app_client, login, active_admin_user):
    bodega = await login(active_admin_user.email)
    tubo = await _item(app_client, bodega, "Tubo cobre 3/8", sku="CU-38")
    filtro = await _item(app_client, bodega, "Filtro 16x25", sku="FI-1625", unidad="unit")
    lista = await _lista(app_client, bodega, [{"item_id": tubo["id"], "quantity": "20", "spec_label": "3/8"}])
    orden = await _borrador(app_client, bodega, tubo["id"], "1")
    await _aplicar(app_client, bodega, lista["id"], orden["id"])

    r = await app_client.put(f"{API}/warehouse/releases/{orden['id']}", json={
        "lines": [{"item_id": tubo["id"], "quantity": "20", "spec_label": "3/8", "origin": "lista",
                   "notes": "El cliente pidió 20 pies"},
                  # El extra que pide este trabajo y que ninguna lista trae.
                  {"item_id": filtro["id"], "quantity": "2", "origin": "manual"}]}, headers=bodega)
    assert r.status_code == 200, r.text
    lineas = _por_articulo(r.json())
    assert set(lineas) == {"Tubo cobre 3/8", "Filtro 16x25"}
    assert lineas["Filtro 16x25"]["origin"] == "manual"
    assert lineas["Tubo cobre 3/8"]["notes"] == "El cliente pidió 20 pies"


async def test_una_lista_sin_material_no_se_aplica(app_client, login, active_admin_user):
    bodega = await login(active_admin_user.email)
    tubo = await _item(app_client, bodega, "Tubo cobre 3/8", sku="CU-38")
    lista = await _lista(app_client, bodega, [{"item_id": tubo["id"], "quantity": "20"}])
    orden = await _borrador(app_client, bodega, tubo["id"], "1")

    # Cantidad cero no es un renglón: la lista se guarda a medias y se corrige.
    vacia = await app_client.put(f"{API}/warehouse/kits/{lista['id']}", json={
        "name": "Aire — estándar", "items": [{"item_id": tubo["id"], "quantity": "0"}]}, headers=bodega)
    assert vacia.status_code == 400, vacia.text
    assert vacia.json()["code"] == "invalid_kit_quantity"

    # Y una orden ya enviada no acepta que le apliquen una lista por debajo.
    await app_client.post(f"{API}/warehouse/releases/{orden['id']}/submit", headers=bodega)
    tarde = await _aplicar(app_client, bodega, lista["id"], orden["id"])
    assert tarde.status_code == 400, tarde.text


# ---------------------------------------------------------------------------
# Aislamiento por organización
# ---------------------------------------------------------------------------

async def test_otra_organizacion_no_ve_ni_usa_la_lista(app_client, login, active_admin_user,
                                                       second_org_admin_user):
    propio = await login(active_admin_user.email)
    ajeno = await login(second_org_admin_user.email)
    tubo = await _item(app_client, propio, "Tubo cobre 3/8", sku="CU-38")
    lista = await _lista(app_client, propio, [{"item_id": tubo["id"], "quantity": "20"}])
    orden = await _borrador(app_client, propio, tubo["id"], "1")

    assert (await app_client.get(f"{API}/warehouse/kits", headers=ajeno)).json() == []
    assert (await app_client.get(f"{API}/warehouse/kits/{lista['id']}", headers=ajeno)).status_code == 404
    assert (await app_client.put(f"{API}/warehouse/kits/{lista['id']}", json={
        "name": "Ajena", "items": [{"item_id": tubo["id"], "quantity": "1"}]}, headers=ajeno)).status_code == 404
    assert (await app_client.delete(f"{API}/warehouse/kits/{lista['id']}", headers=ajeno)).status_code == 404
    assert (await _aplicar(app_client, ajeno, lista["id"], orden["id"])).status_code == 404
