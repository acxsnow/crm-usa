"""Seguridad de bodega: qué ve y qué puede hacer cada quien.

Lo que se protege aquí:

- El técnico usa el catálogo para pedir material y llenar el diario, pero **no
  ve costos, existencias ni movimientos** (revisión del plan).
- El técnico solo ve y cambia **sus** órdenes de salida, y **nadie autoriza lo
  que pidió**: es la separación de funciones del cuestionario.
- El diario descuenta **de la camioneta del técnico** y solo en obras suyas: lo
  de bodega sale por una orden autorizada, nunca por el diario.
- El Excel del catálogo no puede tumbar el servidor (bomba zip) ni dar 500.
"""
import io
import zipfile
from datetime import date

import pytest

from app.core.security import hash_password
from app.modules.users.models import User, UserRole, UserStatus
from tests.field_helpers import approved_case_with_project, headers_for

API = "/api/v1"
HOY = date.today()


@pytest.fixture
def login(app_client):
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


async def _orden(app_client, headers, item_id, **extra):
    return await app_client.post(f"{API}/warehouse/releases", json={
        "lines": [{"item_id": item_id, "quantity": "5"}], **extra}, headers=headers)


async def _ubicacion(app_client, headers, nombre, *, kind="truck", tecnico_id=None) -> dict:
    r = await app_client.post(f"{API}/warehouse/locations", json={
        "name": nombre, "kind": kind, "technician_user_id": str(tecnico_id) if tecnico_id else None},
        headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _cargar(app_client, headers, item_id, cantidad, *, a=None):
    r = await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": item_id, "movement_type": "entrada", "quantity": cantidad}, headers=headers)
    assert r.status_code == 201, r.text
    if a:
        r = await app_client.post(f"{API}/warehouse/movements", json={
            "item_id": item_id, "movement_type": "traslado", "quantity": cantidad, "to_location_id": a},
            headers=headers)
        assert r.status_code == 201, r.text


async def _otro_tecnico(db, seeded_org) -> User:
    org = seeded_org["org"]
    user = User(organization_id=org.id, email="tech2@acme-demo.com", email_display="tech2@acme-demo.com",
                full_name="Terry Technician", password_hash=hash_password("SuperSecret123"),
                status=UserStatus.active)
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=seeded_org["roles"]["field_technician"].id))
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Lo que ve el técnico
# ---------------------------------------------------------------------------

async def test_el_tecnico_ve_el_catalogo_sin_costos_ni_existencias(app_client, login, active_admin_user,
                                                                   active_technician_user):
    admin = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    item = await _item(app_client, admin)

    lista = await app_client.get(f"{API}/warehouse/items", headers=tecnico)
    assert lista.status_code == 200, lista.text
    fila = lista.json()[0]
    assert fila["name"] == "Tubo cobre 3/8"
    assert "unit_cost" not in fila and "value" not in fila

    detalle = (await app_client.get(f"{API}/warehouse/items/{item['id']}", headers=tecnico)).json()
    assert "unit_cost" not in detalle
    # Bodega sí ve el costo.
    assert (await app_client.get(f"{API}/warehouse/items/{item['id']}", headers=admin)).json()["unit_cost"] == "3.25"

    for ruta in ("/warehouse/stock", "/warehouse/movements", "/warehouse/stock/summary"):
        assert (await app_client.get(f"{API}{ruta}", headers=tecnico)).status_code == 403, ruta


async def test_el_tecnico_solo_ve_y_cambia_sus_ordenes(app_client, login, db, seeded_org, active_admin_user,
                                                      active_technician_user):
    admin = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    otro = await _otro_tecnico(db, seeded_org)
    otro_h = await login(otro.email)
    item = await _item(app_client, admin)

    mia = (await _orden(app_client, tecnico, item["id"])).json()
    ajena = (await _orden(app_client, otro_h, item["id"])).json()
    assert "unit_cost" not in mia["lines"][0]

    ids = [o["id"] for o in (await app_client.get(f"{API}/warehouse/releases", headers=tecnico)).json()]
    assert ids == [mia["id"]]
    assert (await app_client.get(f"{API}/warehouse/releases/{ajena['id']}", headers=tecnico)).status_code == 404

    cambio = await app_client.put(f"{API}/warehouse/releases/{ajena['id']}", json={
        "lines": [{"item_id": item["id"], "quantity": "500"}]}, headers=tecnico)
    assert (cambio.status_code, cambio.json()["code"]) == (403, "release_not_owner")
    envio = await app_client.post(f"{API}/warehouse/releases/{ajena['id']}/submit", headers=tecnico)
    assert (envio.status_code, envio.json()["code"]) == (403, "release_not_owner")

    # Bodega ve todas.
    todas = {o["id"] for o in (await app_client.get(f"{API}/warehouse/releases", headers=admin)).json()}
    assert todas == {mia["id"], ajena["id"]}


async def test_nadie_autoriza_la_salida_que_pidio(app_client, login, active_admin_user, active_admin_staff_user):
    admin = await login(active_admin_user.email)
    ricardo = await login(active_admin_staff_user.email)
    item = await _item(app_client, admin)
    orden = (await _orden(app_client, admin, item["id"])).json()
    assert (await app_client.post(f"{API}/warehouse/releases/{orden['id']}/submit", headers=admin)).status_code == 200

    propia = await app_client.post(f"{API}/warehouse/releases/{orden['id']}/approve", headers=admin)
    assert (propia.status_code, propia.json()["code"]) == (403, "release_self_authorization")
    otra = await app_client.post(f"{API}/warehouse/releases/{orden['id']}/approve", headers=ricardo)
    assert otra.status_code == 200, otra.text


async def test_la_orden_no_acepta_obra_ajena_ni_tecnico_inventado(app_client, login, db, seeded_org,
                                                                  active_admin_user, second_org_admin_user,
                                                                  active_technician_user):
    admin = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    item = await _item(app_client, admin)
    # Obra de otro técnico: el técnico no la ve.
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    r = await _orden(app_client, tecnico, item["id"], project_id=str(obra.id))
    assert (r.status_code, r.json()["code"]) == (404, "project_not_found")

    r = await _orden(app_client, admin, item["id"], technician_user_id=str(second_org_admin_user.id))
    assert (r.status_code, r.json()["code"]) == (400, "invalid_technician")


# ---------------------------------------------------------------------------
# Diario de obra
# ---------------------------------------------------------------------------

async def test_el_diario_de_una_obra_ajena_no_se_ve_ni_se_llena(app_client, login, db, seeded_org,
                                                                active_technician_user):
    tecnico = await login(active_technician_user.email)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)  # sin técnico asignado
    ruta = f"{API}/warehouse/projects/{obra.id}/day-logs"
    assert (await app_client.get(ruta, headers=tecnico)).status_code == 404
    r = await app_client.post(ruta, json={"log_date": HOY.isoformat(), "hours": "8"}, headers=tecnico)
    assert r.status_code == 404


async def test_el_diario_solo_descuenta_de_la_camioneta_del_tecnico(app_client, login, db, seeded_org,
                                                                    active_admin_user, active_technician_user):
    admin = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    otro = await _otro_tecnico(db, seeded_org)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    item = await _item(app_client, admin)
    bodega = await _ubicacion(app_client, admin, "Bodega central", kind="warehouse")
    ajena = await _ubicacion(app_client, admin, "Camioneta Terry", tecnico_id=otro.id)
    propia = await _ubicacion(app_client, admin, "Camioneta Tom", tecnico_id=active_technician_user.id)
    await _cargar(app_client, admin, item["id"], "50", a=propia["id"])
    await _cargar(app_client, admin, item["id"], "7")  # queda en la bodega principal

    # De existencias, el técnico solo ve lo que lleva su camioneta.
    visto = (await app_client.get(f"{API}/warehouse/items/{item['id']}", headers=tecnico)).json()
    assert [(l["name"], l["quantity"]) for l in visto["by_location"]] == [("Camioneta Tom", "50.00")]
    assert visto["total_quantity"] == "50.00"

    ruta = f"{API}/warehouse/projects/{obra.id}/day-logs"
    for lugar in (bodega, ajena):
        r = await app_client.post(ruta, json={"log_date": HOY.isoformat(), "materials": [
            {"item_id": item["id"], "quantity": "3", "location_id": lugar["id"]}]}, headers=tecnico)
        assert (r.status_code, r.json()["code"]) == (400, "day_log_location_not_own_truck"), lugar["name"]

    r = await app_client.post(ruta, json={"log_date": HOY.isoformat(), "materials": [
        {"item_id": item["id"], "quantity": "3", "location_id": propia["id"]}]}, headers=tecnico)
    assert r.status_code == 201, r.text
    assert r.json()["materials"][0]["descontada"] is True


# ---------------------------------------------------------------------------
# Importar el Excel
# ---------------------------------------------------------------------------

async def test_un_archivo_que_no_es_excel_da_400(app_client, login, active_admin_user):
    admin = await login(active_admin_user.email)
    r = await app_client.post(f"{API}/warehouse/import", files={
        "file": ("catalogo.xlsx", b"no soy un zip", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin)
    assert (r.status_code, r.json()["code"]) == (400, "invalid_workbook")


async def test_una_bomba_zip_se_rechaza_sin_descomprimirla(app_client, login, active_admin_user):
    admin = await login(active_admin_user.email)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/worksheets/sheet1.xml", b"0" * (60 * 1024 * 1024))  # 60 MB que comprimen a ~60 KB
    r = await app_client.post(f"{API}/warehouse/import", files={
        "file": ("catalogo.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin)
    assert (r.status_code, r.json()["code"]) == (400, "invalid_workbook")
