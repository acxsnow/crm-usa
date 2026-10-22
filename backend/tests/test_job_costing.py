"""Costo del trabajo: estimado contra real (spec 2026-10-22, fases 1 y 2).

Lo que se protege aquí es lo que Aldo hoy mira en Housecall Pro al cerrar un
trabajo: **cuánto esperaba ganar, cuánto ganó y en qué se fue la diferencia**,
sin volver a capturar lo que el sistema ya sabe. Las cifras son las reales que
dio el cliente para el pedestal de rebate (4.200 USD).
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


# ---------------------------------------------------------------------------
# Conceptos del tablero
# ---------------------------------------------------------------------------

async def test_las_categorias_nuevas_y_los_conceptos_cubren_todo():
    from app.modules.warehouse.catalogs import BUDGET_CATEGORIES, CONCEPT_OF_CATEGORY, JOB_CONCEPTS
    from app.modules.warehouse.costing import ACTUAL_LABELS

    assert BUDGET_CATEGORIES["sales_rep"] == "Representante"
    assert BUDGET_CATEGORIES["consumables"] == "Consumibles"
    assert list(JOB_CONCEPTS) == ["sales_rep", "permits", "materials", "labor", "other"]
    # Toda categoría que puede tener costo real cae en un concepto del tablero.
    assert set(ACTUAL_LABELS) <= set(CONCEPT_OF_CATEGORY)
    assert set(CONCEPT_OF_CATEGORY.values()) <= set(JOB_CONCEPTS)


# ---------------------------------------------------------------------------
# Ayudas
# ---------------------------------------------------------------------------

async def _plantillas(app_client, headers) -> dict:
    r = await app_client.get(f"{API}/warehouse/cost-templates", headers=headers)
    assert r.status_code == 200, r.text
    return {t["name"]: t for t in r.json()}


async def _presupuesto(app_client, headers, project_id, lineas=None) -> dict:
    r = await app_client.post(f"{API}/warehouse/budgets", json={
        "project_id": str(project_id), "lines": lineas or []}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _aplicar(app_client, headers, budget_id, template_id, precio=None):
    cuerpo = {"template_id": template_id}
    if precio is not None:
        cuerpo["expected_revenue"] = precio
    return await app_client.post(f"{API}/warehouse/budgets/{budget_id}/apply-template", json=cuerpo,
                                 headers=headers)


async def _programa_con_tarifa(db, org_id, monto="4200"):
    """Un programa de rebate con tarifa vigente hoy (lo que paga por el pedestal)."""
    from datetime import date
    from decimal import Decimal

    from app.modules.billing.models import ProgramRebateRate
    from app.modules.cases.models import Program

    programa = Program(organization_id=org_id, code="PED", name="Pedestales AZ")
    db.add(programa)
    await db.flush()
    db.add(ProgramRebateRate(organization_id=org_id, program_id=programa.id, amount=Decimal(monto),
                             valid_from=date(2026, 1, 1)))
    await db.commit()
    return programa


# ---------------------------------------------------------------------------
# Plantillas y estimado (Task 2)
# ---------------------------------------------------------------------------

async def test_la_organizacion_arranca_con_las_tres_plantillas(app_client, login, active_admin_user):
    h = await login(active_admin_user.email)
    assert set(await _plantillas(app_client, h)) == {
        "Trabajo particular ideal", "Pedestal (rebate) con personal propio", "Pedestal (rebate) con subcontratista"}
    # Pedirlas otra vez no las duplica.
    assert len(await _plantillas(app_client, h)) == 3


async def test_plantilla_por_porcentaje_reparte_el_precio(app_client, login, db, seeded_org, active_admin_user):
    h = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    ideal = (await _plantillas(app_client, h))["Trabajo particular ideal"]
    budget = await _presupuesto(app_client, h, project.id)

    r = await _aplicar(app_client, h, budget["id"], ideal["id"], "10000")
    assert r.status_code == 200, r.text
    b = r.json()
    assert (b["by_category"]["permit"], b["by_category"]["materials"], b["by_category"]["labor"]) == (
        "1000.00", "3000.00", "2000.00")
    assert (b["expected_revenue"], b["expected_profit"], b["expected_margin_pct"]) == ("10000.00", "4000.00", 40.0)
    assert (b["target_profit_pct"], b["below_target"]) == (40.0, False)


async def test_pedestal_con_personal_propio_deja_1500(app_client, login, db, seeded_org, active_admin_user):
    h = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    propio = (await _plantillas(app_client, h))["Pedestal (rebate) con personal propio"]
    budget = await _presupuesto(app_client, h, project.id)

    b = (await _aplicar(app_client, h, budget["id"], propio["id"], "4200")).json()
    assert (b["by_category"]["sales_rep"], b["by_category"]["permit"], b["by_category"]["materials"],
            b["by_category"]["labor"]) == ("800.00", "238.00", "1062.00", "600.00")
    assert (b["expected_profit"], b["expected_margin_pct"]) == ("1500.00", 35.7)


async def test_rebate_toma_el_precio_de_la_tarifa_del_programa(app_client, login, db, seeded_org,
                                                               active_admin_user):
    h = await login(active_admin_user.email)
    org_id = seeded_org["org"].id
    programa = await _programa_con_tarifa(db, org_id, "4200")
    _, project = await approved_case_with_project(db, org_id, program_id=programa.id)
    sub = (await _plantillas(app_client, h))["Pedestal (rebate) con subcontratista"]
    budget = await _presupuesto(app_client, h, project.id)

    b = (await _aplicar(app_client, h, budget["id"], sub["id"])).json()
    assert (b["expected_revenue"], b["by_category"]["contractor"], b["expected_profit"]) == (
        "4200.00", "1050.00", "1050.00")


async def test_plantilla_por_porcentaje_sin_precio_da_400(app_client, login, db, seeded_org, active_admin_user):
    h = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    ideal = (await _plantillas(app_client, h))["Trabajo particular ideal"]
    budget = await _presupuesto(app_client, h, project.id)

    r = await _aplicar(app_client, h, budget["id"], ideal["id"])
    assert (r.status_code, r.json()["code"]) == (400, "expected_revenue_required")


async def test_no_se_aplica_plantilla_a_un_presupuesto_aprobado(app_client, login, db, seeded_org,
                                                                active_admin_user):
    h = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    propio = (await _plantillas(app_client, h))["Pedestal (rebate) con personal propio"]
    budget = await _presupuesto(app_client, h, project.id, [
        {"category": "labor", "description": "Instalación", "quantity": "1", "unit_cost": "600"}])
    assert (await app_client.post(f"{API}/warehouse/budgets/{budget['id']}/approve", headers=h)).status_code == 200

    r = await _aplicar(app_client, h, budget["id"], propio["id"], "4200")
    assert (r.status_code, r.json()["code"]) == (400, "budget_not_editable")


async def test_aplicar_plantilla_conserva_el_material_de_la_lista(app_client, login, db, seeded_org,
                                                                  active_admin_user):
    h = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    r = await app_client.post(f"{API}/warehouse/items", json={
        "name": "Condensador 3 ton", "sku": "COND-3", "category": "equipment", "unit": "unit",
        "unit_cost": "1412.16"}, headers=h)
    equipo = r.json()
    budget = await _presupuesto(app_client, h, project.id, [
        {"category": "equipment", "item_id": equipo["id"], "quantity": "1"},
        {"category": "labor", "description": "Mano de obra vieja", "quantity": "1", "unit_cost": "999"}])
    propio = (await _plantillas(app_client, h))["Pedestal (rebate) con personal propio"]

    b = (await _aplicar(app_client, h, budget["id"], propio["id"], "4200")).json()
    descripciones = [l["description"] for l in b["lines"]]
    assert "Condensador 3 ton" in descripciones  # el renglón del catálogo sigue
    assert "Mano de obra vieja" not in descripciones  # lo escrito a mano lo reemplaza la plantilla
    assert b["by_category"]["equipment"] == "1412.16"


async def test_el_tecnico_no_ve_plantillas(app_client, login, active_technician_user):
    tecnico = await login(active_technician_user.email)
    assert (await app_client.get(f"{API}/warehouse/cost-templates", headers=tecnico)).status_code == 403


# ---------------------------------------------------------------------------
# Costos reales anotados a mano (Task 3)
# ---------------------------------------------------------------------------

async def _anotar(app_client, headers, project_id, categoria, monto, **extra):
    return await app_client.post(f"{API}/warehouse/projects/{project_id}/cost-entries", json={
        "entry_date": "2026-10-22", "category": categoria, "description": extra.pop("description", "Instalación"),
        "amount": monto, **extra}, headers=headers)


async def _real(app_client, headers, project_id) -> dict:
    r = await app_client.get(f"{API}/warehouse/projects/{project_id}/budget-vs-actual", headers=headers)
    assert r.status_code == 200, r.text
    return {f["category"]: f["actual"] for f in r.json()["rows"]}


async def test_la_mano_de_obra_anotada_suma_al_costo_real(app_client, login, db, seeded_org, active_admin_user,
                                                          active_technician_user):
    h = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    r = await _anotar(app_client, h, project.id, "labor", "600", person_user_id=str(active_technician_user.id))
    assert r.status_code == 201, r.text
    assert r.json()["person_name"] == "Tom Technician"
    assert (await _real(app_client, h, project.id))["labor"] == "600.00"
    lista = (await app_client.get(f"{API}/warehouse/projects/{project.id}/cost-entries", headers=h)).json()
    assert [e["amount"] for e in lista] == ["600.00"]


async def test_el_pago_de_luis_puede_ir_como_representante_o_como_mano_de_obra(app_client, login, db, seeded_org,
                                                                              active_admin_user):
    h = await login(active_admin_user.email)
    _, una = await approved_case_with_project(db, seeded_org["org"].id)
    _, otra = await approved_case_with_project(db, seeded_org["org"].id)
    await _anotar(app_client, h, una.id, "sales_rep", "800", person_name="Luis", description="Representante")
    await _anotar(app_client, h, otra.id, "labor", "800", person_name="Luis", description="Representante")
    assert (await _real(app_client, h, una.id))["sales_rep"] == "800.00"
    assert (await _real(app_client, h, otra.id))["labor"] == "800.00"


async def test_monto_cero_o_categoria_inventada_da_400(app_client, login, db, seeded_org, active_admin_user):
    h = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    r = await _anotar(app_client, h, project.id, "labor", "0")
    assert (r.status_code, r.json()["code"]) == (400, "invalid_cost_amount")
    r = await _anotar(app_client, h, project.id, "propina", "10")
    assert (r.status_code, r.json()["code"]) == (400, "invalid_cost_category")


async def test_corregir_y_borrar_una_entrada(app_client, login, db, seeded_org, active_admin_user):
    h = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    entrada = (await _anotar(app_client, h, project.id, "contractor", "1000", person_name="HVAC Pros LLC")).json()
    url = f"{API}/warehouse/projects/{project.id}/cost-entries/{entrada['id']}"
    r = await app_client.put(url, json={"entry_date": "2026-10-22", "category": "contractor",
                                        "description": "Subcontrato", "amount": "1050",
                                        "person_name": "HVAC Pros LLC"}, headers=h)
    assert r.json()["amount"] == "1050.00"
    assert (await app_client.delete(url, headers=h)).status_code == 204
    assert (await _real(app_client, h, project.id))["contractor"] == "0.00"


async def test_el_tecnico_no_puede_anotar_ni_ver_costos(app_client, login, db, seeded_org, active_technician_user):
    tecnico = await login(active_technician_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    assert (await app_client.get(f"{API}/warehouse/projects/{project.id}/cost-entries",
                                 headers=tecnico)).status_code == 403
    assert (await _anotar(app_client, tecnico, project.id, "labor", "600")).status_code == 403


async def test_otra_organizacion_no_ve_las_entradas(app_client, login, db, seeded_org, active_admin_user,
                                                    second_org_admin_user):
    h = await login(active_admin_user.email)
    ajeno = await login(second_org_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    await _anotar(app_client, h, project.id, "labor", "600")
    assert (await app_client.get(f"{API}/warehouse/projects/{project.id}/cost-entries",
                                 headers=ajeno)).status_code == 404
    assert (await _anotar(app_client, ajeno, project.id, "labor", "600")).status_code == 404


# ---------------------------------------------------------------------------
# Cobros adicionales en efectivo (Task 4)
# ---------------------------------------------------------------------------

async def _extra(app_client, headers, project_id, monto="150", **extra):
    return await app_client.post(f"{API}/warehouse/projects/{project_id}/extra-charges", json={
        "description": extra.pop("description", "Breaker 30A y 10 ft de cable"), "amount": monto, **extra},
        headers=headers)


async def test_el_tecnico_anota_el_extra_y_queda_por_entregar(app_client, login, db, seeded_org,
                                                              active_technician_user):
    tecnico = await login(active_technician_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    r = await _extra(app_client, tecnico, project.id)
    assert r.status_code == 201, r.text
    c = r.json()
    assert (c["status"], c["payment_method"], c["amount"], c["received_by_user_id"]) == (
        "por_entregar", "cash", "150.00", str(active_technician_user.id))


async def test_aldo_marca_recibido_y_deja_de_estar_pendiente(app_client, login, db, seeded_org, active_admin_user,
                                                             active_technician_user):
    h = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    c = (await _extra(app_client, tecnico, project.id)).json()
    pendientes = (await app_client.get(f"{API}/warehouse/extra-charges/pending", headers=h)).json()
    assert [p["id"] for p in pendientes] == [c["id"]]

    r = await app_client.post(f"{API}/warehouse/extra-charges/{c['id']}/deliver", headers=h)
    assert r.status_code == 200, r.text
    recibido = r.json()
    assert recibido["status"] == "recibido"
    assert (await app_client.get(f"{API}/warehouse/extra-charges/pending", headers=h)).json() == []
    otra_vez = (await app_client.post(f"{API}/warehouse/extra-charges/{c['id']}/deliver", headers=h)).json()
    assert otra_vez["delivered_at"] == recibido["delivered_at"]


async def test_el_tecnico_no_anota_extras_en_obra_ajena(app_client, login, db, seeded_org, active_technician_user):
    tecnico = await login(active_technician_user.email)
    _, ajena = await approved_case_with_project(db, seeded_org["org"].id)
    r = await _extra(app_client, tecnico, ajena.id)
    assert (r.status_code, r.json()["code"]) == (404, "project_not_found")


async def test_el_tecnico_solo_ve_sus_extras(app_client, login, db, seeded_org, active_admin_user,
                                             active_technician_user):
    h = await login(active_admin_user.email)
    tecnico = await login(active_technician_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    mio = (await _extra(app_client, tecnico, project.id)).json()
    await _extra(app_client, h, project.id, "40", description="Mover el termostato")
    url = f"{API}/warehouse/projects/{project.id}/extra-charges"
    assert [c["id"] for c in (await app_client.get(url, headers=tecnico)).json()] == [mio["id"]]
    assert len((await app_client.get(url, headers=h)).json()) == 2


async def test_el_tecnico_no_puede_marcar_recibido(app_client, login, db, seeded_org, active_technician_user):
    tecnico = await login(active_technician_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    c = (await _extra(app_client, tecnico, project.id)).json()
    assert (await app_client.post(f"{API}/warehouse/extra-charges/{c['id']}/deliver",
                                  headers=tecnico)).status_code == 403


async def test_un_extra_sin_monto_da_400(app_client, login, db, seeded_org, active_admin_user):
    h = await login(active_admin_user.email)
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    r = await _extra(app_client, h, project.id, "0")
    assert (r.status_code, r.json()["code"]) == (400, "invalid_extra_amount")
