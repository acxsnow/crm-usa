"""Presupuesto del proyecto (Fase 3 del plan control-bodega, punto 3).

El cliente lo pidió así: «en cada proyecto se pueda hacer un presupuesto o un
estimado» antes de instalar. Lo que se protege aquí es que el estimado sea un
**documento que se aprueba y queda fijo**: se arma a mano o copiando la lista del
tipo de trabajo, se aprueba, y de ahí en adelante es la referencia contra la que
se compara lo que de verdad costó la obra. Por eso un presupuesto aprobado no se
edita —se aprueba otro y el anterior queda como historial— y por eso un proyecto
nunca tiene dos estimados vigentes a la vez.
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


async def _item(app_client, headers, nombre, *, sku, categoria="pipe_copper", unidad="ft", costo="3.25") -> dict:
    r = await app_client.post(f"{API}/warehouse/items", json={
        "name": nombre, "sku": sku, "category": categoria, "unit": unidad, "unit_cost": costo}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _lista(app_client, headers, items, *, nombre="Aire — estándar") -> dict:
    r = await app_client.post(f"{API}/warehouse/kits", json={
        "name": nombre, "project_type": "hvac_install", "items": items}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _presupuesto(app_client, headers, project_id, lineas, *, notas=None) -> dict:
    r = await app_client.post(f"{API}/warehouse/budgets", json={
        "project_id": str(project_id), "notes": notas, "lines": lineas}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _aprobar(app_client, headers, budget_id):
    return await app_client.post(f"{API}/warehouse/budgets/{budget_id}/approve", headers=headers)


async def _vigente(app_client, headers, project_id) -> dict | None:
    r = await app_client.get(f"{API}/warehouse/projects/{project_id}/budget", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _por_descripcion(presupuesto: dict) -> dict:
    return {l["description"]: l for l in presupuesto["lines"]}


# ---------------------------------------------------------------------------
# Armar y aprobar
# ---------------------------------------------------------------------------

async def test_el_presupuesto_se_arma_con_sus_renglones_y_se_aprueba(app_client, login, db, seeded_org,
                                                                    active_admin_user):
    admin = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    tubo = await _item(app_client, admin, "Tubo cobre 3/8", sku="CU-38")

    # Material del catálogo y mano de obra escrita a mano: el presupuesto no es
    # solo material.
    presupuesto = await _presupuesto(app_client, admin, project.id, [
        {"category": "materials", "item_id": tubo["id"], "quantity": "20"},
        {"category": "labor", "description": "Cuadrilla 2 técnicos", "quantity": "8",
         "unit": "hour", "unit_cost": "50"},
    ])
    assert presupuesto["status"] == "borrador"
    lineas = _por_descripcion(presupuesto)
    # El costo del renglón sale del catálogo y el monto se calcula solo.
    assert lineas["Tubo cobre 3/8"]["unit_cost"] == "3.25"
    assert lineas["Tubo cobre 3/8"]["amount"] == "65.00"
    assert lineas["Cuadrilla 2 técnicos"]["amount"] == "400.00"
    assert presupuesto["total"] == "465.00"
    assert presupuesto["by_category"] == {"materials": "65.00", "labor": "400.00"}

    # Todavía es borrador: se puede editar sin dejar rastro.
    editado = await app_client.put(f"{API}/warehouse/budgets/{presupuesto['id']}", json={
        "lines": [{"category": "materials", "item_id": tubo["id"], "quantity": "30"}]}, headers=admin)
    assert editado.status_code == 200, editado.text
    assert editado.json()["total"] == "97.50"

    aprobado = await _aprobar(app_client, admin, presupuesto["id"])
    assert aprobado.status_code == 200, aprobado.text
    cuerpo = aprobado.json()
    assert cuerpo["status"] == "aprobado"
    assert cuerpo["approved_at"] is not None
    assert cuerpo["approved_by_user_id"] == str(active_admin_user.id)


async def test_el_presupuesto_sale_de_una_lista_predefinida(app_client, login, db, seeded_org, active_admin_user):
    admin = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    tubo = await _item(app_client, admin, "Tubo cobre 3/8", sku="CU-38", costo="3.00")
    equipo = await _item(app_client, admin, "Unidad exterior 3 ton", sku="UE-3T", categoria="equipment",
                         unidad="unit", costo="1200.00")
    lista = await _lista(app_client, admin, [
        {"item_id": tubo["id"], "quantity": "20"},
        {"item_id": equipo["id"], "quantity": "1"},
    ])

    # Se arranca el borrador vacío: el caso normal es partirlo de la lista.
    presupuesto = await _presupuesto(app_client, admin, project.id, [])
    assert presupuesto["lines"] == []

    r = await app_client.post(f"{API}/warehouse/budgets/{presupuesto['id']}/apply-kit",
                              json={"kit_id": lista["id"]}, headers=admin)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert (cuerpo["agregadas"], cuerpo["omitidas"]) == (2, 0)
    # El material entra como material y el equipo como equipo, con el costo del
    # catálogo: la lista no trae precios, los pone el catálogo.
    assert cuerpo["by_category"] == {"materials": "60.00", "equipment": "1200.00"}
    assert cuerpo["total"] == "1260.00"

    # Un doble clic no duplica el material.
    otra = (await app_client.post(f"{API}/warehouse/budgets/{presupuesto['id']}/apply-kit",
                                  json={"kit_id": lista["id"]}, headers=admin)).json()
    assert (otra["agregadas"], otra["omitidas"]) == (0, 2)
    assert len(otra["lines"]) == 2


# ---------------------------------------------------------------------------
# Un solo presupuesto vigente
# ---------------------------------------------------------------------------

async def test_aprobar_otro_reemplaza_al_anterior_sin_borrarlo(app_client, login, db, seeded_org,
                                                               active_admin_user):
    admin = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    tubo = await _item(app_client, admin, "Tubo cobre 3/8", sku="CU-38")

    primero = await _presupuesto(app_client, admin, project.id,
                                 [{"category": "materials", "item_id": tubo["id"], "quantity": "10"}])
    await _aprobar(app_client, admin, primero["id"])

    # Se rehizo el estimado más largo y se aprueba: el primero no se borra,
    # queda como historial.
    segundo = await _presupuesto(app_client, admin, project.id,
                                 [{"category": "materials", "item_id": tubo["id"], "quantity": "25"}])
    await _aprobar(app_client, admin, segundo["id"])

    vigente = await _vigente(app_client, admin, project.id)
    assert vigente["id"] == segundo["id"]
    assert vigente["status"] == "aprobado"
    assert (await app_client.get(f"{API}/warehouse/budgets/{primero['id']}", headers=admin)).json()[
        "status"] == "reemplazado"

    # Y solo uno está aprobado: la comparación nunca mira dos versiones.
    aprobados = (await app_client.get(f"{API}/warehouse/budgets?project_id={project.id}&status=aprobado",
                                      headers=admin)).json()
    assert [b["id"] for b in aprobados] == [segundo["id"]]


async def test_un_presupuesto_aprobado_no_se_edita_ni_se_borra(app_client, login, db, seeded_org,
                                                               active_admin_user):
    admin = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    tubo = await _item(app_client, admin, "Tubo cobre 3/8", sku="CU-38")
    presupuesto = await _presupuesto(app_client, admin, project.id,
                                     [{"category": "materials", "item_id": tubo["id"], "quantity": "10"}])
    await _aprobar(app_client, admin, presupuesto["id"])

    tarde = await app_client.put(f"{API}/warehouse/budgets/{presupuesto['id']}", json={
        "lines": [{"category": "materials", "item_id": tubo["id"], "quantity": "99"}]}, headers=admin)
    assert tarde.status_code == 400, tarde.text
    assert tarde.json()["code"] == "budget_not_editable"
    assert (await app_client.delete(f"{API}/warehouse/budgets/{presupuesto['id']}",
                                    headers=admin)).status_code == 400

    # El estimado aprobado sigue intacto.
    assert (await app_client.get(f"{API}/warehouse/budgets/{presupuesto['id']}",
                                 headers=admin)).json()["total"] == "32.50"


# ---------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------

async def test_se_validan_categoria_cantidad_y_presupuesto_vacio(app_client, login, db, seeded_org,
                                                                 active_admin_user):
    admin = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    tubo = await _item(app_client, admin, "Tubo cobre 3/8", sku="CU-38")

    mala_categoria = await app_client.post(f"{API}/warehouse/budgets", json={
        "project_id": str(project.id),
        "lines": [{"category": "no_existe", "item_id": tubo["id"], "quantity": "1"}]}, headers=admin)
    assert mala_categoria.status_code == 400, mala_categoria.text
    assert mala_categoria.json()["code"] == "invalid_budget_category"

    cero = await app_client.post(f"{API}/warehouse/budgets", json={
        "project_id": str(project.id),
        "lines": [{"category": "materials", "item_id": tubo["id"], "quantity": "0"}]}, headers=admin)
    assert cero.status_code == 400, cero.text
    assert cero.json()["code"] == "invalid_budget_quantity"

    # Un presupuesto sin renglones se guarda como borrador, pero no se aprueba:
    # aprobar algo vacío deja la obra «presupuestada» en cero.
    vacio = await _presupuesto(app_client, admin, project.id, [])
    sin_renglones = await _aprobar(app_client, admin, vacio["id"])
    assert sin_renglones.status_code == 400, sin_renglones.text
    assert sin_renglones.json()["code"] == "empty_budget"


async def test_el_tecnico_de_campo_no_arma_presupuesto(app_client, login, db, seeded_org,
                                                       active_technician_user):
    tecnico = await login(active_technician_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)

    r = await app_client.post(f"{API}/warehouse/budgets", json={
        "project_id": str(project.id),
        "lines": [{"category": "labor", "description": "Mano de obra", "quantity": "1",
                   "unit_cost": "100"}]}, headers=tecnico)
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# Aislamiento por organización
# ---------------------------------------------------------------------------

async def test_otra_organizacion_no_ve_ni_toca_el_presupuesto(app_client, login, db, seeded_org,
                                                              active_admin_user, second_org_admin_user):
    propio = await login(active_admin_user.email)
    ajeno = await login(second_org_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    tubo = await _item(app_client, propio, "Tubo cobre 3/8", sku="CU-38")
    presupuesto = await _presupuesto(app_client, propio, project.id,
                                     [{"category": "materials", "item_id": tubo["id"], "quantity": "10"}])

    assert (await app_client.get(f"{API}/warehouse/budgets", headers=ajeno)).json() == []
    assert (await app_client.get(f"{API}/warehouse/budgets/{presupuesto['id']}",
                                 headers=ajeno)).status_code == 404
    # Tampoco puede colgarle un presupuesto a una obra que no es suya.
    assert (await app_client.post(f"{API}/warehouse/budgets", json={
        "project_id": str(project.id),
        "lines": [{"category": "labor", "description": "Mano de obra", "quantity": "1", "unit_cost": "100"}]},
        headers=ajeno)).status_code == 404
    assert (await _aprobar(app_client, ajeno, presupuesto["id"])).status_code == 404
    # Ver el presupuesto vigente de una obra ajena tampoco: la obra no existe
    # para él.
    assert (await app_client.get(f"{API}/warehouse/projects/{project.id}/budget",
                                 headers=ajeno)).status_code == 404
