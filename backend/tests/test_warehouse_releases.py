"""Órdenes de salida de bodega (Fase 1 del plan control-bodega, punto 1).

Lo que se protege aquí es la regla del cuestionario: **el material sale solo por
una orden autorizada y entregada**. Si eso se rompe, el saldo deja de cuadrar y
nadie puede decir quién autorizó qué. Por eso las pruebas insisten en el camino
completo (borrador → por autorizar → autorizada → entregada), en que el técnico
no pueda autorizar lo suyo, y en que entregar dos veces no descuente dos veces.
"""
import pytest

from tests.field_helpers import approved_case_with_project, headers_for

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


async def _item(app_client, headers, nombre="Tubo cobre 3/8", *, sku="CU-38") -> dict:
    r = await app_client.post(f"{API}/warehouse/items", json={
        "name": nombre, "sku": sku, "category": "pipe_copper", "unit": "ft", "unit_cost": "3.25"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _entrada(app_client, headers, item_id, cantidad="100") -> dict:
    r = await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": item_id, "movement_type": "entrada", "quantity": cantidad}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _existencia(app_client, headers, item_id) -> str:
    r = await app_client.get(f"{API}/warehouse/items/{item_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["total_quantity"]


async def _orden(app_client, headers, item_id, cantidad="10", **extra) -> dict:
    """Arma el borrador, como lo hace el técnico desde su orden."""
    r = await app_client.post(f"{API}/warehouse/releases", json={
        "lines": [{"item_id": item_id, "quantity": cantidad}], **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _enviar(app_client, headers, orden_id) -> dict:
    r = await app_client.post(f"{API}/warehouse/releases/{orden_id}/submit", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _autorizar(app_client, headers, orden_id) -> dict:
    r = await app_client.post(f"{API}/warehouse/releases/{orden_id}/approve", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _entregar(app_client, headers, orden_id):
    return await app_client.post(f"{API}/warehouse/releases/{orden_id}/deliver", headers=headers)


# ---------------------------------------------------------------------------
# El camino completo
# ---------------------------------------------------------------------------

async def test_la_salida_pasa_por_autorizacion_y_baja_el_saldo(app_client, login, active_admin_user,
                                                              active_technician_user):
    bodega = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    item = await _item(app_client, bodega)
    await _entrada(app_client, bodega, item["id"], "100")

    # El técnico arma su borrador: todavía no tiene número ni compromete saldo.
    orden = await _orden(app_client, tecnico, item["id"], "30")
    assert (orden["status"], orden["number"]) == ("borrador", None)
    assert await _existencia(app_client, bodega, item["id"]) == "100.00"

    enviada = await _enviar(app_client, tecnico, orden["id"])
    assert enviada["status"] == "por_autorizar"
    assert enviada["number"].startswith("SAL-")

    # La bandeja del autorizador la ve; mientras tanto no salió nada.
    pendientes = (await app_client.get(f"{API}/warehouse/releases/pending", headers=bodega)).json()
    assert [o["id"] for o in pendientes] == [orden["id"]]
    assert await _existencia(app_client, bodega, item["id"]) == "100.00"

    autorizada = await _autorizar(app_client, bodega, orden["id"])
    assert autorizada["status"] == "autorizada"
    assert autorizada["authorized_at"] is not None

    entrega = await _entregar(app_client, bodega, orden["id"])
    assert entrega.status_code == 200, entrega.text
    cuerpo = entrega.json()
    assert (cuerpo["status"], cuerpo["faltantes"]) == ("entregada", [])
    assert cuerpo["lines"][0]["quantity_delivered"] == "30.00"
    assert await _existencia(app_client, bodega, item["id"]) == "70.00"

    # Ya entregada no vuelve a la bandeja de pendientes.
    assert (await app_client.get(f"{API}/warehouse/releases/pending", headers=bodega)).json() == []


async def test_el_tecnico_no_puede_autorizar_su_propia_salida(app_client, login, active_admin_user,
                                                             active_technician_user):
    bodega = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    item = await _item(app_client, bodega)
    orden = await _enviar(app_client, tecnico, (await _orden(app_client, tecnico, item["id"]))["id"])

    # Pedir sí, autorizar no: es la separación que pide el cuestionario (punto 1).
    intento = await app_client.post(f"{API}/warehouse/releases/{orden['id']}/approve", headers=tecnico)
    assert intento.status_code == 403, intento.text
    assert (await app_client.get(f"{API}/warehouse/releases/{orden['id']}", headers=bodega)).json()["status"] == \
        "por_autorizar"


async def test_rechazar_exige_el_motivo_y_no_deja_entregar(app_client, login, active_admin_user):
    bodega = await login(active_admin_user.email)
    item = await _item(app_client, bodega)
    await _entrada(app_client, bodega, item["id"], "100")
    orden = await _enviar(app_client, bodega, (await _orden(app_client, bodega, item["id"], "5"))["id"])

    sin_motivo = await app_client.post(f"{API}/warehouse/releases/{orden['id']}/reject",
                                       json={"reason": "   "}, headers=bodega)
    assert sin_motivo.status_code == 400, sin_motivo.text

    rechazada = await app_client.post(f"{API}/warehouse/releases/{orden['id']}/reject",
                                      json={"reason": "El trabajo quedó para el viernes"}, headers=bodega)
    assert rechazada.status_code == 200, rechazada.text
    assert rechazada.json()["status"] == "rechazada"
    assert rechazada.json()["reject_reason"] == "El trabajo quedó para el viernes"

    # Rechazada es un final: ni se entrega ni el saldo se mueve.
    assert (await _entregar(app_client, bodega, orden["id"])).status_code == 400
    assert await _existencia(app_client, bodega, item["id"]) == "100.00"


# ---------------------------------------------------------------------------
# Sin existencia: avisa, no bloquea (D-BOD-4)
# ---------------------------------------------------------------------------

async def test_sin_existencia_avisa_y_deja_el_motivo(app_client, login, active_admin_user, active_admin_staff_user):
    bodega = await login(active_admin_user.email)
    autoriza = await login(active_admin_staff_user.email)
    item = await _item(app_client, bodega)  # sin entrada: la bodega está en cero
    orden = await _enviar(app_client, bodega, (await _orden(app_client, bodega, item["id"], "5"))["id"])
    await _autorizar(app_client, autoriza, orden["id"])

    entrega = await _entregar(app_client, bodega, orden["id"])
    assert entrega.status_code == 200, entrega.text
    cuerpo = entrega.json()
    assert cuerpo["status"] == "entregada"
    assert cuerpo["faltantes"][0]["motivo"] == "No había existencia en bodega."
    assert cuerpo["shortage_note"] == "No había existencia en bodega."
    assert cuerpo["lines"][0]["quantity_delivered"] == "0.00"
    assert await _existencia(app_client, bodega, item["id"]) == "0.00"


async def test_alcanza_solo_para_parte_y_dice_cuanto_faltó(app_client, login, active_admin_user, active_admin_staff_user):
    bodega = await login(active_admin_user.email)
    autoriza = await login(active_admin_staff_user.email)
    item = await _item(app_client, bodega)
    await _entrada(app_client, bodega, item["id"], "3")
    orden = await _enviar(app_client, bodega, (await _orden(app_client, bodega, item["id"], "10"))["id"])
    await _autorizar(app_client, autoriza, orden["id"])

    cuerpo = (await _entregar(app_client, bodega, orden["id"])).json()
    assert cuerpo["lines"][0]["quantity_delivered"] == "3.00"
    assert cuerpo["lines"][0]["pending_quantity"] == "7.00"
    assert cuerpo["faltantes"][0]["motivo"] == "Solo había 3.00 de 10.00."
    # Se entregó todo lo que había: la bodega queda en cero y baja una sola vez.
    assert await _existencia(app_client, bodega, item["id"]) == "0.00"


# ---------------------------------------------------------------------------
# La entrega es única
# ---------------------------------------------------------------------------

async def test_entregar_dos_veces_no_descuenta_dos_veces(app_client, login, active_admin_user, active_admin_staff_user):
    bodega = await login(active_admin_user.email)
    autoriza = await login(active_admin_staff_user.email)
    item = await _item(app_client, bodega)
    await _entrada(app_client, bodega, item["id"], "100")
    orden = await _enviar(app_client, bodega, (await _orden(app_client, bodega, item["id"], "30"))["id"])
    await _autorizar(app_client, autoriza, orden["id"])

    primera = await _entregar(app_client, bodega, orden["id"])
    assert primera.status_code == 200, primera.text
    assert await _existencia(app_client, bodega, item["id"]) == "70.00"

    # Un reintento (doble clic, red que se repite) no vuelve a descontar: la
    # orden ya no está `autorizada`, así que la puerta se cierra.
    segunda = await _entregar(app_client, bodega, orden["id"])
    assert segunda.status_code == 400, segunda.text
    assert await _existencia(app_client, bodega, item["id"]) == "70.00"


# ---------------------------------------------------------------------------
# Lo entregado queda en la obra
# ---------------------------------------------------------------------------

async def test_lo_entregado_aparece_en_el_material_de_la_obra(app_client, db, login, active_admin_user, active_admin_staff_user, seeded_org):
    bodega = await login(active_admin_user.email)
    autoriza = await login(active_admin_staff_user.email)
    item = await _item(app_client, bodega, "Tubo cobre 3/8", sku="CU-38")
    await _entrada(app_client, bodega, item["id"], "50")

    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    orden = await _enviar(app_client, bodega,
                          (await _orden(app_client, bodega, item["id"], "12", project_id=str(project.id)))["id"])
    await _autorizar(app_client, autoriza, orden["id"])
    await _entregar(app_client, bodega, orden["id"])

    materiales = (await app_client.get(f"{API}/projects/{project.id}/materials", headers=bodega)).json()
    assert len(materiales) == 1
    assert materiales[0]["description"] == "Tubo cobre 3/8"
    assert materiales[0]["quantity"] == 12
    assert "De bodega" in materiales[0]["notes"]


# ---------------------------------------------------------------------------
# Aislamiento por organización
# ---------------------------------------------------------------------------

async def test_otra_organizacion_no_ve_la_orden(app_client, login, active_admin_user, second_org_admin_user):
    propio = await login(active_admin_user.email)
    ajeno = await login(second_org_admin_user.email)
    item = await _item(app_client, propio)
    orden = await _enviar(app_client, propio, (await _orden(app_client, propio, item["id"]))["id"])

    assert (await app_client.get(f"{API}/warehouse/releases", headers=ajeno)).json() == []
    assert (await app_client.get(f"{API}/warehouse/releases/pending", headers=ajeno)).json() == []
    assert (await app_client.get(f"{API}/warehouse/releases/{orden['id']}", headers=ajeno)).status_code == 404
    # Y no puede autorizarle ni entregarle material a la otra organización.
    assert (await app_client.post(f"{API}/warehouse/releases/{orden['id']}/approve",
                                  headers=ajeno)).status_code == 404
    assert (await app_client.post(f"{API}/warehouse/releases/{orden['id']}/deliver",
                                  headers=ajeno)).status_code == 404


# ---------------------------------------------------------------------------
# La lista como checklist (plan bodega-cierre, fase 2)
# ---------------------------------------------------------------------------

async def test_quitar_un_obligatorio_pide_el_motivo_y_lo_ve_quien_autoriza(app_client, login, active_admin_user,
                                                                         active_technician_user):
    bodega = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    tubo = await _item(app_client, bodega, "Tubo cobre 3/8", sku="CU-38")
    disconnect = await _item(app_client, bodega, "Disconnect 30 A", sku="257")

    linea = {"item_id": tubo["id"], "quantity": "20", "section": "Líneas", "is_required": True, "origin": "lista"}
    sin_motivo = await app_client.post(f"{API}/warehouse/releases", json={
        "lines": [linea], "omissions": [{"item_id": disconnect["id"], "reason": "   "}]}, headers=tecnico)
    assert (sin_motivo.status_code, sin_motivo.json()["code"]) == (400, "omission_reason_required")

    r = await app_client.post(f"{API}/warehouse/releases", json={
        "lines": [linea], "omissions": [{"item_id": disconnect["id"], "reason": "La casa ya tiene disconnect"}]},
        headers=tecnico)
    assert r.status_code == 201, r.text
    orden = r.json()
    assert orden["omissions"] == [{"item_id": disconnect["id"], "item_name": "Disconnect 30 A", "spec_label": None,
                                   "reason": "La casa ya tiene disconnect"}]
    assert (orden["lines"][0]["section"], orden["lines"][0]["is_required"]) == ("Líneas", True)
    # Quien autoriza ve lo mismo en su bandeja.
    await _enviar(app_client, tecnico, orden["id"])
    bandeja = (await app_client.get(f"{API}/warehouse/releases/pending", headers=bodega)).json()
    assert next(o for o in bandeja if o["id"] == orden["id"])["omissions"][0]["reason"] == "La casa ya tiene disconnect"


async def test_bodega_confirma_lo_que_sale_de_cada_renglon(app_client, login, active_admin_user,
                                                          active_admin_staff_user):
    bodega = await login(active_admin_user.email)
    supervisor = await login(active_admin_staff_user.email)
    tubo = await _item(app_client, bodega, "Tubo cobre 3/8", sku="CU-38")
    cinta = await _item(app_client, bodega, "Cinta de aluminio", sku="CI-01")
    await _entrada(app_client, bodega, tubo["id"], "100")
    await _entrada(app_client, bodega, cinta["id"], "100")
    r = await app_client.post(f"{API}/warehouse/releases", json={"lines": [
        {"item_id": tubo["id"], "quantity": "20"}, {"item_id": cinta["id"], "quantity": "3"}]}, headers=bodega)
    orden = r.json()
    await _enviar(app_client, bodega, orden["id"])
    await _autorizar(app_client, supervisor, orden["id"])
    l_tubo, l_cinta = orden["lines"][0]["id"], orden["lines"][1]["id"]
    url = f"{API}/warehouse/releases/{orden['id']}/deliver"

    # Nunca más de lo pedido, ni renglones de otra orden.
    de_mas = await app_client.post(url, json={"lines": [{"line_id": l_tubo, "quantity": "25"}]}, headers=bodega)
    assert (de_mas.status_code, de_mas.json()["code"]) == (400, "invalid_delivered_quantity")
    ajena = await app_client.post(url, json={"lines": [{"line_id": orden["id"], "quantity": "1"}]}, headers=bodega)
    assert (ajena.status_code, ajena.json()["code"]) == (400, "release_line_not_found")

    r = await app_client.post(url, json={"lines": [{"line_id": l_tubo, "quantity": "15"},
                                                   {"line_id": l_cinta, "quantity": "0"}]}, headers=bodega)
    assert r.status_code == 200, r.text
    entregada = r.json()
    cantidades = {l["item_name"]: l["quantity_delivered"] for l in entregada["lines"]}
    assert cantidades == {"Tubo cobre 3/8": "15.00", "Cinta de aluminio": "0.00"}
    assert sorted(f["motivo"] for f in entregada["faltantes"]) == ["Bodega entregó 15.00 de 20.00.",
                                                                   "Bodega no lo entregó."]
    assert await _existencia(app_client, bodega, tubo["id"]) == "85.00"
    assert await _existencia(app_client, bodega, cinta["id"]) == "100.00"


async def test_el_tecnico_marca_lo_que_carga_en_la_camioneta(app_client, db, seeded_org, login, active_admin_user,
                                                             active_admin_staff_user, active_technician_user):
    from tests.test_warehouse_security import _otro_tecnico

    bodega = await login(active_admin_user.email)
    supervisor = await login(active_admin_staff_user.email)
    tecnico = await login(active_technician_user.email)
    tubo = await _item(app_client, bodega, "Tubo cobre 3/8", sku="CU-38")
    cinta = await _item(app_client, bodega, "Cinta de aluminio", sku="CI-01")
    await _entrada(app_client, bodega, tubo["id"], "100")  # de la cinta no hay
    r = await app_client.post(f"{API}/warehouse/releases", json={"lines": [
        {"item_id": tubo["id"], "quantity": "20", "is_required": True, "origin": "lista"},
        {"item_id": cinta["id"], "quantity": "2", "is_required": True, "origin": "lista"}]}, headers=tecnico)
    orden = r.json()
    l_tubo, l_cinta = orden["lines"][0]["id"], orden["lines"][1]["id"]
    marcar = f"{API}/warehouse/releases/{orden['id']}/lines/{l_tubo}/load"

    # Antes de entregarla no hay qué cargar.
    antes = await app_client.post(marcar, json={"loaded": True}, headers=tecnico)
    assert (antes.status_code, antes.json()["code"]) == (400, "release_not_delivered")

    await _enviar(app_client, tecnico, orden["id"])
    await _autorizar(app_client, supervisor, orden["id"])
    entregada = (await _entregar(app_client, bodega, orden["id"])).json()
    # Lo que se entregó se puede cargar; lo que no había, no.
    assert entregada["loading"] == {"loadable": 1, "loaded": 0, "required_pending": 1}

    r = await app_client.post(marcar, json={"loaded": True}, headers=tecnico)
    assert r.status_code == 200, r.text
    assert r.json()["loading"] == {"loadable": 1, "loaded": 1, "required_pending": 0}
    assert next(l for l in r.json()["lines"] if l["id"] == l_tubo)["loaded"] is True
    sin_entregar = await app_client.post(f"{API}/warehouse/releases/{orden['id']}/lines/{l_cinta}/load",
                                         json={"loaded": True}, headers=tecnico)
    assert (sin_entregar.status_code, sin_entregar.json()["code"]) == (400, "release_line_not_delivered")

    # Otro técnico no marca la orden ajena.
    otro = await _otro_tecnico(db, seeded_org)
    ajeno = await app_client.post(marcar, json={"loaded": False}, headers=await login(otro.email))
    assert ajeno.status_code in (403, 404)

    # Se puede desmarcar si se equivocó.
    r = await app_client.post(marcar, json={"loaded": False}, headers=tecnico)
    assert r.json()["loading"] == {"loadable": 1, "loaded": 0, "required_pending": 1}
