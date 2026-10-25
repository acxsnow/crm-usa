"""Regresiones del ataque del 24 oct a bodega y rotación del técnico
(`docs/qa/ataque-bodega-rotacion-2026-10-24.md`).

Cada prueba reproduce un hallazgo crítico o alto encontrado contra la app real:
si vuelve a fallar, el hallazgo volvió.
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.modules.field_ops.models import Project, ProjectStatus
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


async def _segundo_tecnico(db, seeded_org) -> User:
    user = User(organization_id=seeded_org["org"].id, email="tech2@acme-demo.com", email_display="tech2@acme-demo.com",
                full_name="Terry Technician", password_hash=hash_password("SuperSecret123"), status=UserStatus.active)
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=seeded_org["roles"]["field_technician"].id))
    await db.commit()
    await db.refresh(user)
    return user


async def _item(app_client, headers, nombre="Tubo cobre 3/8", sku="CU-38") -> dict:
    r = await app_client.post(f"{API}/warehouse/items", json={"name": nombre, "sku": sku, "category": "pipe_copper",
                                                              "unit": "ft", "unit_cost": "3.25"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _liberar(app_client, headers, project_id, tecnico_id):
    r = await app_client.patch(f"{API}/projects/{project_id}/schedule", json={
        "technician_user_id": str(tecnico_id), "scheduled_date": HOY.isoformat()}, headers=headers)
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# A1 · Números raros: 400 con mensaje, nunca 500
# ---------------------------------------------------------------------------

RAROS = ["NaN", "abc", "Infinity", "1e309", "99999999999999999", "1,5"]


@pytest.mark.parametrize("valor", RAROS)
async def test_cantidad_rara_en_la_salida_da_400(app_client, login, active_admin_user, valor):
    h = await login(active_admin_user.email)
    item = await _item(app_client, h)
    r = await app_client.post(f"{API}/warehouse/releases", json={"lines": [{"item_id": item["id"], "quantity": valor}]},
                              headers=h)
    assert (r.status_code, r.json()["code"]) == (400, "invalid_number"), r.text


@pytest.mark.parametrize("valor", RAROS)
async def test_numero_raro_en_movimiento_costo_y_cobro_da_400(app_client, login, db, seeded_org, active_admin_user,
                                                             valor):
    h = await login(active_admin_user.email)
    item = await _item(app_client, h)
    r = await app_client.post(f"{API}/warehouse/movements", json={"item_id": item["id"], "movement_type": "entrada",
                                                                  "quantity": valor}, headers=h)
    assert r.status_code == 400, r.text
    r = await app_client.post(f"{API}/warehouse/items", json={"name": "otro", "unit_cost": valor}, headers=h)
    assert r.status_code == 400, r.text
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    r = await app_client.post(f"{API}/warehouse/projects/{project.id}/extra-charges",
                              json={"description": "x", "amount": valor}, headers=h)
    assert r.status_code == 400, r.text


async def test_entregar_con_cantidad_rara_da_400(app_client, login, active_admin_user, active_admin_staff_user):
    h = await login(active_admin_user.email)
    oficina = await login(active_admin_staff_user.email)
    item = await _item(app_client, h)
    orden = (await app_client.post(f"{API}/warehouse/releases", json={
        "lines": [{"item_id": item["id"], "quantity": "5"}]}, headers=h)).json()
    await app_client.post(f"{API}/warehouse/releases/{orden['id']}/submit", headers=h)
    assert (await app_client.post(f"{API}/warehouse/releases/{orden['id']}/approve", headers=oficina)).status_code == 200
    for valor in ("NaN", "abc"):
        r = await app_client.post(f"{API}/warehouse/releases/{orden['id']}/deliver", json={
            "lines": [{"line_id": orden["lines"][0]["id"], "quantity": valor}]}, headers=h)
        assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# A2 · Mismo nombre, distinto código AC Pro: dos artículos
# ---------------------------------------------------------------------------

async def test_mismo_nombre_y_distinto_codigo_ac_pro_son_dos_articulos(app_client, login, active_admin_user):
    """Caso real del PDF del cliente: «Foam Insulation Tape Black 1/8" x 2" x 30'»
    viene de Armacell (AC Pro 36140) y de Diversitech (AC Pro 3088)."""
    h = await login(active_admin_user.email)
    nombre = "Foam Insulation Tape Black 1/8 x 2 x 30'"
    filas = [{"name": nombre, "sku": "36140", "brand": "Armacell", "unit_cost": "19.57"},
             {"name": nombre, "sku": "3088", "brand": "Diversitech", "unit_cost": "14.05"}]
    r = await app_client.post(f"{API}/warehouse/import/rows", json={"rows": filas}, headers=h)
    assert (r.json()["creados"], r.json()["errores"]) == (2, [])
    items = (await app_client.get(f"{API}/warehouse/items", params={"q": "Foam Insulation"}, headers=h)).json()
    assert sorted((i["sku"], i["brand"]) for i in items) == [("3088", "Diversitech"), ("36140", "Armacell")]
    # Volver a subir el mismo Excel no duplica: cada código encuentra su artículo.
    r = await app_client.post(f"{API}/warehouse/import/rows", json={"rows": filas}, headers=h)
    assert (r.json()["creados"], r.json()["actualizados"]) == (0, 2)


async def test_el_codigo_nuevo_se_le_pone_al_articulo_que_no_tenia(app_client, login, active_admin_user):
    """El catálogo cargado antes sin códigos sigue encontrándose por nombre y gana su código."""
    h = await login(active_admin_user.email)
    await app_client.post(f"{API}/warehouse/import/rows", json={"rows": [{"name": "Codo 3/4", "unit_cost": "1"}]},
                          headers=h)
    r = await app_client.post(f"{API}/warehouse/import/rows", json={"rows": [
        {"name": "Codo 3/4", "sku": "1886", "unit_cost": "3.28"}]}, headers=h)
    assert (r.json()["creados"], r.json()["actualizados"]) == (0, 1)
    items = (await app_client.get(f"{API}/warehouse/items", params={"q": "Codo 3/4"}, headers=h)).json()
    assert [(i["sku"], i["unit_cost"]) for i in items] == [("1886", "3.28")]


# ---------------------------------------------------------------------------
# A3 · El técnico anterior no envía a autorizar material para la obra rotada
# ---------------------------------------------------------------------------

async def test_el_tecnico_anterior_no_envia_a_autorizar_su_borrador_de_la_obra(
        app_client, login, db, seeded_org, active_admin_user, active_technician_user):
    h = await login(active_admin_user.email)
    t1 = await login(active_technician_user.email)
    otro = await _segundo_tecnico(db, seeded_org)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    await _liberar(app_client, h, project.id, active_technician_user.id)
    item = await _item(app_client, h)
    borrador = (await app_client.post(f"{API}/warehouse/releases", json={
        "project_id": str(project.id), "lines": [{"item_id": item["id"], "quantity": "2"}]}, headers=t1)).json()
    await _liberar(app_client, h, project.id, otro.id)

    r = await app_client.post(f"{API}/warehouse/releases/{borrador['id']}/submit", headers=t1)
    assert (r.status_code, r.json()["code"]) == (403, "project_read_only")


# ---------------------------------------------------------------------------
# A4 · No se pide material para una obra cerrada
# ---------------------------------------------------------------------------

async def test_no_se_pide_material_para_una_obra_cerrada(app_client, login, db, seeded_org, active_admin_user,
                                                       active_technician_user):
    h = await login(active_admin_user.email)
    t1 = await login(active_technician_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    item = await _item(app_client, h)
    borrador = (await app_client.post(f"{API}/warehouse/releases", json={
        "project_id": str(project.id), "lines": [{"item_id": item["id"], "quantity": "2"}]}, headers=t1)).json()
    fila = (await db.execute(select(Project).where(Project.id == project.id))).scalar_one()
    fila.status = ProjectStatus.completed
    await db.commit()

    for quien in (t1, h):
        r = await app_client.post(f"{API}/warehouse/releases", json={
            "project_id": str(project.id), "lines": [{"item_id": item["id"], "quantity": "1"}]}, headers=quien)
        assert (r.status_code, r.json()["code"]) == (409, "project_closed"), r.text
    r = await app_client.post(f"{API}/warehouse/releases/{borrador['id']}/submit", headers=t1)
    assert (r.status_code, r.json()["code"]) == (409, "project_closed")
