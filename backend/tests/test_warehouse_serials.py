"""Seriales de bodega (D-007 del plan de QA).

La regla que se protege: **un serial está en un solo lugar**. Entra a bodega,
sale con una orden para una obra, se instala en esa obra o vuelve a bodega.
No se entrega dos veces, no se devuelve a una obra a la que no salió y no se
instala en otra obra. Un equipo que nunca pasó por bodega (D-BOD-3) se instala
con su serial escrito, sin cruce.
"""
import pytest

from tests.field_helpers import approved_case_with_project, headers_for

API = "/api/v1"


@pytest.fixture
def login(app_client):
    cache: dict[str, dict] = {}

    async def _login(email: str) -> dict:
        if email not in cache:
            cache[email] = await headers_for(app_client, email)
        return cache[email]

    return _login


async def _equipo(app_client, headers, *, sku="HP-3T") -> dict:
    r = await app_client.post(f"{API}/warehouse/items", json={
        "name": "Bomba de calor 3 ton", "sku": sku, "category": "other", "unit": "unit", "unit_cost": "2100",
        "brand": "Goodman", "manufacturer_part": "GSZH503610", "has_serial": True}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _mover(app_client, headers, item_id, tipo, cantidad, **extra):
    return await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": item_id, "movement_type": tipo, "quantity": cantidad, **extra}, headers=headers)


async def _orden_autorizada(app_client, pide, autoriza, item_id, cantidad, project_id) -> dict:
    r = await app_client.post(f"{API}/warehouse/releases", json={
        "lines": [{"item_id": item_id, "quantity": cantidad}], "project_id": str(project_id)}, headers=pide)
    assert r.status_code == 201, r.text
    orden = r.json()
    assert (await app_client.post(f"{API}/warehouse/releases/{orden['id']}/submit", headers=pide)).status_code == 200
    r = await app_client.post(f"{API}/warehouse/releases/{orden['id']}/approve", headers=autoriza)
    assert r.status_code == 200, r.text
    return r.json()


async def _entregar(app_client, headers, orden, cantidad, serials=None):
    linea = {"line_id": orden["lines"][0]["id"], "quantity": cantidad}
    if serials is not None:
        linea["serials"] = serials
    return await app_client.post(f"{API}/warehouse/releases/{orden['id']}/deliver",
                                 json={"lines": [linea]}, headers=headers)


async def _seriales(app_client, headers, **params) -> dict:
    r = await app_client.get(f"{API}/warehouse/serials", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return {s["serial"]: s["status"] for s in r.json()}


async def _instalar(app_client, headers, project_id, **extra):
    return await app_client.post(f"{API}/projects/{project_id}/equipment", json={
        "equipment_type": "heat_pump_outdoor", "brand": "Goodman", "model": "GSZH503610", **extra}, headers=headers)


async def test_el_serial_recorre_bodega_obra_e_instalacion(app_client, db, seeded_org, login, active_admin_user,
                                                           active_admin_staff_user, active_technician_user):
    bodega = await login(active_admin_user.email)
    oficina = await login(active_admin_staff_user.email)
    tecnico = await login(active_technician_user.email)
    equipo = await _equipo(app_client, bodega)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)

    # Entra con sus seriales (se guardan sin espacios de más y en mayúsculas).
    r = await _mover(app_client, bodega, equipo["id"], "entrada", "2", serials=["sn-001", " SN-002 "])
    assert r.status_code == 201, r.text
    assert await _seriales(app_client, bodega) == {"SN-001": "in_stock", "SN-002": "in_stock"}

    orden = await _orden_autorizada(app_client, oficina, bodega, equipo["id"], "2", obra.id)
    assert orden["lines"][0]["has_serial"] is True

    # Sin seriales, o con menos de los que salen, no se entrega.
    r = await _entregar(app_client, bodega, orden, "2")
    assert (r.status_code, r.json()["code"]) == (400, "serials_count_mismatch")
    r = await _entregar(app_client, bodega, orden, "2", ["SN-001"])
    assert (r.status_code, r.json()["code"]) == (400, "serials_count_mismatch")
    r = await _entregar(app_client, bodega, orden, "2", ["SN-001", "SN-001"])
    assert (r.status_code, r.json()["code"]) == (400, "serial_repeated")
    # Nada salió con los intentos fallidos.
    assert (await app_client.get(f"{API}/warehouse/items/{equipo['id']}", headers=bodega)).json()[
        "total_quantity"] == "2.00"

    # Uno estaba registrado y otro se anota al salir (lo que había antes del control).
    r = await _entregar(app_client, bodega, orden, "2", ["SN-001", "SN-900"])
    assert r.status_code == 200, r.text
    assert r.json()["lines"][0]["serials"] == ["SN-001", "SN-900"]
    assert await _seriales(app_client, bodega) == {"SN-001": "delivered", "SN-002": "in_stock",
                                                   "SN-900": "delivered"}

    # El técnico ve en su obra los seriales que salieron para ella.
    r = await app_client.get(f"{API}/projects/{obra.id}/serials", headers=tecnico)
    assert r.status_code == 200, r.text
    disponibles = {s["serial"]: s for s in r.json()}
    assert set(disponibles) == {"SN-001", "SN-900"}
    assert disponibles["SN-001"]["release_number"] == orden["number"]

    # Lo elige de la lista: queda instalado y el equipo lleva ese serial.
    r = await _instalar(app_client, tecnico, obra.id, warehouse_serial_id=disponibles["SN-001"]["id"],
                        serial_number="otro escrito")
    assert r.status_code == 201, r.text
    assert (r.json()["serial_number"], r.json()["warehouse_serial_id"]) == ("SN-001", disponibles["SN-001"]["id"])
    # Lo escribe a mano: se cruza solo.
    r = await _instalar(app_client, tecnico, obra.id, serial_number="sn-900")
    assert r.status_code == 201, r.text
    segundo = r.json()
    assert segundo["warehouse_serial_id"] == disponibles["SN-900"]["id"]
    assert await _seriales(app_client, bodega, status="installed") == {"SN-001": "installed", "SN-900": "installed"}
    listado = (await app_client.get(f"{API}/projects/{obra.id}/equipment", headers=tecnico)).json()
    assert {e["serial_number"]: e["warehouse_serial_id"] is not None for e in listado} == {
        "SN-001": True, "SN-900": True}

    # Un instalado no se vuelve a instalar.
    r = await _instalar(app_client, tecnico, obra.id, serial_number="SN-900")
    assert (r.status_code, r.json()["code"]) == (409, "serial_not_available_here")
    # Ni se devuelve a bodega mientras esté instalado.
    r = await _mover(app_client, bodega, equipo["id"], "devolucion", "1", project_id=str(obra.id),
                     serials=["SN-900"])
    assert (r.status_code, r.json()["code"]) == (409, "serial_not_delivered_here")

    # Borrar el equipo lo deja otra vez entregado a la obra, y entonces sí vuelve.
    assert (await app_client.delete(f"{API}/equipment/{segundo['id']}", headers=tecnico)).status_code == 204
    assert (await _seriales(app_client, bodega))["SN-900"] == "delivered"
    r = await _mover(app_client, bodega, equipo["id"], "devolucion", "1", project_id=str(obra.id),
                     serials=["SN-900"])
    assert r.status_code == 201, r.text
    assert (await _seriales(app_client, bodega))["SN-900"] == "in_stock"


async def test_un_serial_no_sale_dos_veces_ni_se_instala_en_otra_obra(
        app_client, db, seeded_org, login, active_admin_user, active_admin_staff_user, active_technician_user):
    bodega = await login(active_admin_user.email)
    oficina = await login(active_admin_staff_user.email)
    tecnico = await login(active_technician_user.email)
    equipo = await _equipo(app_client, bodega)
    assert (await _mover(app_client, bodega, equipo["id"], "entrada", "3")).status_code == 201
    _, obra_a = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    _, obra_b = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)

    orden_a = await _orden_autorizada(app_client, oficina, bodega, equipo["id"], "1", obra_a.id)
    assert (await _entregar(app_client, bodega, orden_a, "1", ["A-1"])).status_code == 200
    orden_b = await _orden_autorizada(app_client, oficina, bodega, equipo["id"], "1", obra_b.id)
    r = await _entregar(app_client, bodega, orden_b, "1", ["A-1"])
    assert (r.status_code, r.json()["code"]) == (409, "serial_not_in_stock")
    assert "entregado a la obra" in r.json()["detail"]
    assert (await _entregar(app_client, bodega, orden_b, "1", ["B-1"])).status_code == 200

    # A-1 salió para la obra A: en la B no se instala ni se devuelve.
    r = await _instalar(app_client, tecnico, obra_b.id, serial_number="A-1")
    assert (r.status_code, r.json()["code"]) == (409, "serial_not_available_here")
    assert "otra obra" in r.json()["detail"]
    r = await _mover(app_client, bodega, equipo["id"], "devolucion", "1", project_id=str(obra_b.id),
                     serials=["A-1"])
    assert (r.status_code, r.json()["code"]) == (409, "serial_not_delivered_here")
    # Elegirlo por id tampoco sirve: salió para otra obra.
    a1 = (await app_client.get(f"{API}/warehouse/serials", params={"q": "a-1"}, headers=bodega)).json()[0]
    r = await _instalar(app_client, tecnico, obra_b.id, warehouse_serial_id=a1["id"])
    assert (r.status_code, r.json()["code"]) == (409, "serial_not_available_here")

    # La devolución de un artículo con serial exige los seriales.
    r = await _mover(app_client, bodega, equipo["id"], "devolucion", "1", project_id=str(obra_b.id))
    assert (r.status_code, r.json()["code"]) == (400, "serials_count_mismatch")


async def test_el_equipo_que_no_paso_por_bodega_se_instala_sin_cruce(
        app_client, db, seeded_org, login, active_admin_user, active_technician_user):
    """D-BOD-3: los equipos grandes van directo a la obra; su serial queda escrito."""
    bodega = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    equipo = await _equipo(app_client, bodega)
    assert (await _mover(app_client, bodega, equipo["id"], "entrada", "1", serials=["EN-BODEGA"])).status_code == 201
    _, obra = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)

    r = await _instalar(app_client, tecnico, obra.id, serial_number="DIRECTO-123")
    assert r.status_code == 201, r.text
    assert (r.json()["serial_number"], r.json()["warehouse_serial_id"]) == ("DIRECTO-123", None)
    # Pero uno que sigue en bodega no se puede instalar sin que salga primero.
    r = await _instalar(app_client, tecnico, obra.id, serial_number="en-bodega")
    assert (r.status_code, r.json()["code"]) == (409, "serial_not_available_here")
    assert "sigue en bodega" in r.json()["detail"]


async def test_reglas_de_captura(app_client, login, active_admin_user):
    bodega = await login(active_admin_user.email)
    equipo = await _equipo(app_client, bodega)
    tubo = (await app_client.post(f"{API}/warehouse/items", json={
        "name": "Tubo", "sku": "T-1", "category": "pipe_copper", "unit": "ft"}, headers=bodega)).json()

    # Un artículo sin serial no recibe seriales.
    r = await _mover(app_client, bodega, tubo["id"], "entrada", "1", serials=["X"])
    assert (r.status_code, r.json()["code"]) == (400, "serials_not_expected")
    # Con serial se mueve por unidades enteras.
    r = await _mover(app_client, bodega, equipo["id"], "entrada", "1.5", serials=["X", "Y"])
    assert (r.status_code, r.json()["code"]) == (400, "serial_whole_units")
    # La entrada puede ir sin seriales (se anotan al entregar), pero si van, uno por unidad.
    assert (await _mover(app_client, bodega, equipo["id"], "entrada", "2")).status_code == 201
    r = await _mover(app_client, bodega, equipo["id"], "entrada", "2", serials=["X"])
    assert (r.status_code, r.json()["code"]) == (400, "serials_count_mismatch")
    # Un serial ya registrado no entra otra vez.
    assert (await _mover(app_client, bodega, equipo["id"], "entrada", "1", serials=["X"])).status_code == 201
    r = await _mover(app_client, bodega, equipo["id"], "entrada", "1", serials=[" x "])
    assert (r.status_code, r.json()["code"]) == (409, "serial_already_registered")
    # Un ajuste no lleva seriales.
    r = await _mover(app_client, bodega, equipo["id"], "ajuste", "-1", serials=["X"])
    assert (r.status_code, r.json()["code"]) == (400, "serials_not_expected")
    # El estado que se filtra tiene que existir, y el catálogo lo nombra.
    r = await app_client.get(f"{API}/warehouse/serials", params={"status": "perdido"}, headers=bodega)
    assert (r.status_code, r.json()["code"]) == (400, "invalid_serial_status")
    catalogos = (await app_client.get(f"{API}/warehouse/catalogs", headers=bodega)).json()
    assert catalogos["serial_statuses"]["delivered"] == "Entregado a la obra"


async def test_seriales_aislados_por_organizacion_y_por_obra(
        app_client, db, seeded_org, login, active_admin_user, second_org_admin_user, active_technician_user):
    propio = await login(active_admin_user.email)
    ajeno = await login(second_org_admin_user.email)
    tecnico = await login(active_technician_user.email)
    equipo = await _equipo(app_client, propio)
    assert (await _mover(app_client, propio, equipo["id"], "entrada", "1", serials=["MIO-1"])).status_code == 201

    assert (await app_client.get(f"{API}/warehouse/serials", headers=ajeno)).json() == []
    # La otra organización puede usar el mismo serial en su propio artículo.
    suyo = await _equipo(app_client, ajeno)
    assert (await _mover(app_client, ajeno, suyo["id"], "entrada", "1", serials=["MIO-1"])).status_code == 201

    # El técnico no ve los seriales de una obra que no es suya, ni la bodega completa.
    _, ajena = await approved_case_with_project(db, seeded_org["org"].id)
    assert (await app_client.get(f"{API}/projects/{ajena.id}/serials", headers=tecnico)).status_code == 404
    assert (await app_client.get(f"{API}/warehouse/serials", headers=tecnico)).status_code == 403
