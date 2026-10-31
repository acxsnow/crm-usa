"""Las salidas de bodega de una obra siguen a su técnico y se pueden anular
(QA de José, 31 oct 2026).

Administración pidió material para una obra que aún no tenía técnico: la orden
quedó a nombre de ella misma y, al asignar después a Carlos, no se movió.
Tampoco había forma de deshacer una salida pedida por error si nadie la había
tocado. Las tres reglas que se protegen:

1. No se pide material para una obra sin técnico: primero «Orden liberada».
2. Al asignar o cambiar el técnico, las salidas que no se han entregado pasan
   a él; las entregadas no se tocan.
3. Quien pidió la salida (o bodega) la anula con motivo mientras no se entregue.
"""
from datetime import date, timedelta

import pytest

from app.core.security import hash_password
from app.modules.users.models import User, UserRole, UserStatus
from tests.field_helpers import approved_case_with_project, headers_for

API = "/api/v1"
MANANA = date.today() + timedelta(days=1)


@pytest.fixture
def login(app_client):
    cache: dict[str, dict] = {}

    async def _login(email: str) -> dict:
        if email not in cache:
            cache[email] = await headers_for(app_client, email)
        return cache[email]

    return _login


async def _tecnico(db, seeded_org, nombre: str) -> User:
    correo = f"{nombre.lower().replace(' ', '.')}@acme-demo.com"
    user = User(organization_id=seeded_org["org"].id, email=correo, email_display=correo, full_name=nombre,
                password_hash=hash_password("SuperSecret123"), status=UserStatus.active)
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=seeded_org["roles"]["field_technician"].id))
    await db.commit()
    await db.refresh(user)
    return user


async def _item(app_client, headers) -> dict:
    r = await app_client.post(f"{API}/warehouse/items", json={
        "name": "Tubo cobre 3/8", "sku": "CU-38", "category": "pipe_copper", "unit": "ft", "unit_cost": "3.25"},
        headers=headers)
    assert r.status_code == 201, r.text
    item = r.json()
    r = await app_client.post(f"{API}/warehouse/movements", json={
        "item_id": item["id"], "movement_type": "entrada", "quantity": "100"}, headers=headers)
    assert r.status_code == 201, r.text
    return item


async def _pedir(app_client, headers, item_id, project_id):
    return await app_client.post(f"{API}/warehouse/releases", json={
        "lines": [{"item_id": item_id, "quantity": "5"}], "project_id": str(project_id)}, headers=headers)


async def _liberar(app_client, headers, project_id, tecnico_id):
    r = await app_client.patch(f"{API}/projects/{project_id}/schedule", json={
        "technician_user_id": str(tecnico_id), "scheduled_date": MANANA.isoformat()}, headers=headers)
    assert r.status_code == 200, r.text


async def _salida(app_client, headers, orden_id) -> dict:
    r = await app_client.get(f"{API}/warehouse/releases/{orden_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def test_no_material_for_a_project_without_technician(app_client, db, login, seeded_org, active_admin_staff_user):
    oficina = await login(active_admin_staff_user.email)
    item = await _item(app_client, oficina)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    r = await _pedir(app_client, oficina, item["id"], obra.id)
    assert r.status_code == 409
    assert r.json()["code"] == "project_without_technician"
    assert "Orden liberada" in r.json()["detail"]


async def test_open_releases_follow_the_new_technician_and_delivered_ones_stay(
        app_client, db, login, seeded_org, active_admin_user, active_admin_staff_user):
    oficina = await login(active_admin_staff_user.email)
    admin = await login(active_admin_user.email)
    carlos = await _tecnico(db, seeded_org, "Carlos Ramirez")
    luis = await _tecnico(db, seeded_org, "Luis Gomez")
    item = await _item(app_client, oficina)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    await _liberar(app_client, oficina, obra.id, carlos.id)

    # Una entregada, una autorizada, una por autorizar y un borrador, todas a nombre de Carlos.
    ids = []
    for _ in range(4):
        r = await _pedir(app_client, oficina, item["id"], obra.id)
        assert r.status_code == 201, r.text
        assert r.json()["technician_user_id"] == str(carlos.id)
        ids.append(r.json()["id"])
    entregada, autorizada, por_autorizar, borrador = ids
    for oid in (entregada, autorizada, por_autorizar):
        assert (await app_client.post(f"{API}/warehouse/releases/{oid}/submit", headers=oficina)).status_code == 200
    for oid in (entregada, autorizada):
        assert (await app_client.post(f"{API}/warehouse/releases/{oid}/approve", headers=admin)).status_code == 200
    assert (await app_client.post(f"{API}/warehouse/releases/{entregada}/deliver", headers=admin)).status_code == 200

    await _liberar(app_client, oficina, obra.id, luis.id)

    assert (await _salida(app_client, oficina, entregada))["technician_user_id"] == str(carlos.id)
    for oid in (autorizada, por_autorizar, borrador):
        assert (await _salida(app_client, oficina, oid))["technician_user_id"] == str(luis.id)
    assert (await _salida(app_client, oficina, autorizada))["status"] == "autorizada"


async def test_saving_the_schedule_again_fixes_a_release_left_with_someone_else(
        app_client, db, login, seeded_org, active_admin_staff_user):
    """Como SAL-2026-0004: la salida quedó a nombre de otra persona. Volver a
    guardar la orden con el mismo técnico la corrige."""
    from app.modules.warehouse.models import WarehouseReleaseOrder

    oficina = await login(active_admin_staff_user.email)
    carlos = await _tecnico(db, seeded_org, "Carlos Ramirez")
    item = await _item(app_client, oficina)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    await _liberar(app_client, oficina, obra.id, carlos.id)
    oid = (await _pedir(app_client, oficina, item["id"], obra.id)).json()["id"]
    orden = await db.get(WarehouseReleaseOrder, __import__("uuid").UUID(oid))
    orden.technician_user_id = active_admin_staff_user.id
    await db.commit()

    await _liberar(app_client, oficina, obra.id, carlos.id)
    assert (await _salida(app_client, oficina, oid))["technician_user_id"] == str(carlos.id)


async def test_the_requester_cancels_a_release_not_yet_delivered(
        app_client, db, login, seeded_org, active_admin_user, active_admin_staff_user):
    oficina = await login(active_admin_staff_user.email)
    admin = await login(active_admin_user.email)
    carlos = await _tecnico(db, seeded_org, "Carlos Ramirez")
    item = await _item(app_client, oficina)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    await _liberar(app_client, oficina, obra.id, carlos.id)
    oid = (await _pedir(app_client, oficina, item["id"], obra.id)).json()["id"]
    assert (await app_client.post(f"{API}/warehouse/releases/{oid}/submit", headers=oficina)).status_code == 200

    sin_motivo = await app_client.post(f"{API}/warehouse/releases/{oid}/cancel", json={"reason": " "}, headers=oficina)
    assert sin_motivo.status_code in (400, 422)

    r = await app_client.post(f"{API}/warehouse/releases/{oid}/cancel",
                              json={"reason": "La pedí antes de asignar el técnico"}, headers=oficina)
    assert r.status_code == 200, r.text
    anulada = r.json()
    assert anulada["status"] == "anulada"
    assert anulada["cancel_reason"] == "La pedí antes de asignar el técnico"
    assert anulada["cancelled_by_user_id"] == str(active_admin_staff_user.id)
    # Ya no se autoriza ni se entrega, y no movió existencias.
    assert (await app_client.post(f"{API}/warehouse/releases/{oid}/approve", headers=admin)).status_code == 400
    assert (await app_client.post(f"{API}/warehouse/releases/{oid}/deliver", headers=admin)).status_code == 400
    r = await app_client.get(f"{API}/warehouse/items/{item['id']}", headers=oficina)
    assert r.json()["total_quantity"] in ("100", "100.00", "100.000")


async def test_a_delivered_release_cannot_be_cancelled_and_others_cannot_cancel(
        app_client, db, login, seeded_org, active_admin_user, active_admin_staff_user):
    oficina = await login(active_admin_staff_user.email)
    admin = await login(active_admin_user.email)
    carlos = await _tecnico(db, seeded_org, "Carlos Ramirez")
    item = await _item(app_client, oficina)
    _, obra = await approved_case_with_project(db, seeded_org["org"].id)
    await _liberar(app_client, oficina, obra.id, carlos.id)
    entregada = (await _pedir(app_client, oficina, item["id"], obra.id)).json()["id"]
    abierta = (await _pedir(app_client, oficina, item["id"], obra.id)).json()["id"]
    assert (await app_client.post(f"{API}/warehouse/releases/{entregada}/submit", headers=oficina)).status_code == 200
    assert (await app_client.post(f"{API}/warehouse/releases/{entregada}/approve", headers=admin)).status_code == 200
    assert (await app_client.post(f"{API}/warehouse/releases/{entregada}/deliver", headers=admin)).status_code == 200

    r = await app_client.post(f"{API}/warehouse/releases/{entregada}/cancel", json={"reason": "error"}, headers=oficina)
    assert r.status_code == 400
    assert r.json()["code"] == "release_not_cancellable"

    # El técnico no la pidió ni administra la bodega: no la anula.
    tecnico = await login(carlos.email)
    r = await app_client.post(f"{API}/warehouse/releases/{abierta}/cancel", json={"reason": "no la quiero"},
                              headers=tecnico)
    assert r.status_code == 403
