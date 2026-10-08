"""Módulo 1: programas, catálogo de campos, flujo versionado, T&C y zonas de
venta (spec `2026-10-04-modulo-1-programas-design.md`)."""
import uuid

import pytest

from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.field_ops import case_hooks
from app.modules.programs import service as svc
from app.shared import events as domain_events
from tests.field_helpers import headers_for


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()
    domain_events.clear_subscribers()


async def _admin(app_client):
    return await headers_for(app_client, "admin@acme-demo.com")


async def _instalar(app_client, headers):
    r = await app_client.post("/api/v1/programs/install-defaults", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _programa(app_client, headers, code):
    return next(p for p in (await app_client.get("/api/v1/programs", headers=headers)).json() if p["code"] == code)


async def _version_publicada(app_client, headers, program_id):
    versiones = (await app_client.get(f"/api/v1/programs/{program_id}/versions", headers=headers)).json()
    return next(v for v in versiones if v["status"] == "published")


# ---------------------------------------------------------------------------
# Plantillas del sistema
# ---------------------------------------------------------------------------

async def test_defaults_install_arizona_and_tech_and_are_idempotent(app_client, active_admin_user):
    headers = await _admin(app_client)
    primero = await _instalar(app_client, headers)
    assert primero["programs_created"] == ["AZ_EFFICIENCY", "TECH_CLEAN_CA"]
    assert primero["fields_created"] > 50
    segundo = await _instalar(app_client, headers)
    assert segundo == {"fields_created": 0, "programs_created": []}

    az = await _programa(app_client, headers, "AZ_EFFICIENCY")
    assert (az["funder_name"], az["published_version"]) == ("Desert Alliance Properties LLC", "1")


async def test_arizona_asks_household_data_and_tech_does_not(app_client, active_admin_user):
    headers = await _admin(app_client)
    await _instalar(app_client, headers)
    claves = {}
    for code in ("AZ_EFFICIENCY", "TECH_CLEAN_CA"):
        p = await _programa(app_client, headers, code)
        v = await _version_publicada(app_client, headers, p["id"])
        d = (await app_client.get(f"/api/v1/program-versions/{v['id']}", headers=headers)).json()["definition"]
        claves[code] = {c["key"] for s in d["steps"] for c in s["fields"]}
    assert {"home.education_level", "home.gas_type"} <= claves["AZ_EFFICIENCY"]
    assert not {"home.education_level", "home.gas_type"} & claves["TECH_CLEAN_CA"]
    # La auditoría técnica del vendedor (PDF §2.4) está en los dos.
    assert {"tech.panel_amperage", "tech.electrical_viability"} <= claves["TECH_CLEAN_CA"]


async def test_the_preview_shows_what_the_salesperson_would_see(app_client, active_admin_user):
    headers = await _admin(app_client)
    await _instalar(app_client, headers)
    p = await _programa(app_client, headers, "AZ_EFFICIENCY")
    v = await _version_publicada(app_client, headers, p["id"])
    url = f"/api/v1/program-versions/{v['id']}/preview"
    vacio = (await app_client.post(url, json={"answers": {}}, headers=headers)).json()
    assert vacio["can_submit"] is False
    assert "customer.full_name" in {m["key"] for m in vacio["missing"]}

    # La foto del pedestal solo aparece en una casa móvil.
    pasos = lambda r: {c["key"] for s in r["steps"] for c in s["fields"]}
    casa = (await app_client.post(url, json={"answers": {"home.residence_type": "single_family_home"}},
                                  headers=headers)).json()
    movil = (await app_client.post(url, json={"answers": {"home.residence_type": "mobile_home"}},
                                   headers=headers)).json()
    assert "docs.pedestal_photo" not in pasos(casa) and "docs.pedestal_photo" in pasos(movil)

    # Lo de uso interno no se muestra al cliente.
    cliente = (await app_client.post(url, json={"answers": {}, "include_internal": False}, headers=headers)).json()
    assert "internal.notes" not in pasos(cliente)


# ---------------------------------------------------------------------------
# Catálogo de campos
# ---------------------------------------------------------------------------

async def test_a_field_key_is_unique_and_a_select_needs_options(app_client, active_admin_user):
    headers = await _admin(app_client)
    base = {"key": "home.pets", "label": "¿Tiene mascotas?", "field_type": "single_select"}
    r = await app_client.post("/api/v1/fields", json=base, headers=headers)
    assert r.status_code == 400
    r = await app_client.post("/api/v1/fields", json={**base, "options": [{"value": "yes", "label": "Sí"},
                                                                          {"value": "no", "label": "No"}]},
                              headers=headers)
    assert r.status_code == 201, r.text
    r = await app_client.post("/api/v1/fields", json={**base, "options": [{"value": "yes", "label": "Sí"}]},
                              headers=headers)
    assert r.status_code == 409
    r = await app_client.post("/api/v1/fields", json={**base, "key": "Mascotas"}, headers=headers)
    assert r.status_code == 400


async def test_options_already_answered_cannot_be_removed(app_client, active_admin_user):
    headers = await _admin(app_client)
    campo = (await app_client.post("/api/v1/fields", json={
        "key": "home.pets", "label": "Mascotas", "field_type": "single_select",
        "options": [{"value": "yes", "label": "Sí"}, {"value": "no", "label": "No"}]}, headers=headers)).json()
    r = await app_client.patch(f"/api/v1/fields/{campo['id']}", json={"options": [{"value": "yes", "label": "Sí"}]},
                               headers=headers)
    assert r.status_code == 409
    r = await app_client.patch(f"/api/v1/fields/{campo['id']}", json={
        "options": [{"value": "yes", "label": "Sí, tiene"}, {"value": "no", "label": "No"}], "active": False},
        headers=headers)
    assert r.status_code == 200 and r.json()["active"] is False


# ---------------------------------------------------------------------------
# Versiones: borrador editable, publicada congelada
# ---------------------------------------------------------------------------

async def _borrador_de_tech(app_client, headers):
    await _instalar(app_client, headers)
    tech = await _programa(app_client, headers, "TECH_CLEAN_CA")
    r = await app_client.post(f"/api/v1/programs/{tech['id']}/versions", headers=headers)
    assert r.status_code == 201, r.text
    return tech, r.json()


async def test_a_published_version_is_frozen_and_a_new_one_copies_it(app_client, active_admin_user):
    headers = await _admin(app_client)
    tech, borrador = await _borrador_de_tech(app_client, headers)
    assert (borrador["version"], borrador["status"]) == ("2", "draft")
    publicada = await _version_publicada(app_client, headers, tech["id"])

    vieja = (await app_client.get(f"/api/v1/program-versions/{publicada['id']}", headers=headers)).json()
    nueva = (await app_client.get(f"/api/v1/program-versions/{borrador['id']}", headers=headers)).json()
    claves = lambda d: [c["key"] for s in d["definition"]["steps"] for c in s["fields"]]
    assert claves(vieja) == claves(nueva)

    paso_viejo = vieja["phases"][0]["steps"][0]["id"]
    r = await app_client.patch(f"/api/v1/workflow-steps/{paso_viejo}", json={"title": "Otro"}, headers=headers)
    assert r.status_code == 409
    # Un solo borrador a la vez.
    assert (await app_client.post(f"/api/v1/programs/{tech['id']}/versions", headers=headers)).status_code == 409


async def test_adding_household_members_to_tech_and_publishing(app_client, active_admin_user):
    headers = await _admin(app_client)
    tech, borrador = await _borrador_de_tech(app_client, headers)
    detalle = (await app_client.get(f"/api/v1/program-versions/{borrador['id']}", headers=headers)).json()
    paso_vivienda = next(s for s in detalle["phases"][0]["steps"] if s["code"] == "home")
    miembros = next(f for f in (await app_client.get("/api/v1/fields", headers=headers)).json()
                    if f["key"] == "home.household_members")
    r = await app_client.post(f"/api/v1/workflow-steps/{paso_vivienda['id']}/fields",
                              json={"field_id": miembros["id"], "requirement": "required"}, headers=headers)
    assert r.status_code == 201, r.text
    # El mismo campo no entra dos veces en la versión.
    r = await app_client.post(f"/api/v1/workflow-steps/{paso_vivienda['id']}/fields",
                              json={"field_id": miembros["id"]}, headers=headers)
    assert r.status_code == 409

    r = await app_client.post(f"/api/v1/program-versions/{borrador['id']}/publish", headers=headers)
    assert r.status_code == 200, r.text
    versiones = (await app_client.get(f"/api/v1/programs/{tech['id']}/versions", headers=headers)).json()
    assert [(v["version"], v["status"]) for v in versiones] == [("1", "archived"), ("2", "published")]


async def test_publishing_checks_conditions_and_terms(app_client, active_admin_user):
    headers = await _admin(app_client)
    tech, borrador = await _borrador_de_tech(app_client, headers)
    detalle = (await app_client.get(f"/api/v1/program-versions/{borrador['id']}", headers=headers)).json()
    paso = detalle["phases"][0]["steps"][0]
    compania = next(f for f in (await app_client.get("/api/v1/fields", headers=headers)).json()
                    if f["key"] == "home.gas_company")
    # Depende de home.gas_type, que TECH no pregunta.
    r = await app_client.post(f"/api/v1/workflow-steps/{paso['id']}/fields", json={
        "field_id": compania["id"], "requirement": "conditional",
        "condition": {"field": "home.gas_type", "eq": "natural_gas"}}, headers=headers)
    assert r.status_code == 201
    r = await app_client.patch(f"/api/v1/program-versions/{borrador['id']}", json={"terms_id": None},
                               headers=headers)
    assert r.status_code == 200
    r = await app_client.post(f"/api/v1/program-versions/{borrador['id']}/publish", headers=headers)
    assert r.status_code == 400
    detalle = r.json()["detail"]
    assert "depende de home.gas_type" in detalle and "términos publicados" in detalle


async def test_a_conditional_field_needs_its_condition(app_client, active_admin_user):
    headers = await _admin(app_client)
    _, borrador = await _borrador_de_tech(app_client, headers)
    detalle = (await app_client.get(f"/api/v1/program-versions/{borrador['id']}", headers=headers)).json()
    paso = detalle["phases"][0]["steps"][0]
    notas = next(f for f in (await app_client.get("/api/v1/fields", headers=headers)).json()
                 if f["key"] == "home.notes")
    r = await app_client.post(f"/api/v1/workflow-steps/{paso['id']}/fields",
                              json={"field_id": notas["id"], "requirement": "conditional"}, headers=headers)
    assert r.status_code == 400


async def test_steps_and_fields_move_up_and_down(app_client, active_admin_user):
    headers = await _admin(app_client)
    _, borrador = await _borrador_de_tech(app_client, headers)
    detalle = (await app_client.get(f"/api/v1/program-versions/{borrador['id']}", headers=headers)).json()
    pasos = [s["code"] for s in detalle["phases"][0]["steps"]]
    segundo = detalle["phases"][0]["steps"][1]["id"]
    r = await app_client.post(f"/api/v1/workflow-steps/{segundo}/move", json={"direction": "up"}, headers=headers)
    assert r.status_code == 204
    despues = (await app_client.get(f"/api/v1/program-versions/{borrador['id']}", headers=headers)).json()
    assert [s["code"] for s in despues["phases"][0]["steps"]] == [pasos[1], pasos[0]] + pasos[2:]


# ---------------------------------------------------------------------------
# T&C
# ---------------------------------------------------------------------------

async def test_terms_by_version_and_language_are_frozen_once_published(app_client, active_admin_user):
    headers = await _admin(app_client)
    p = (await app_client.post("/api/v1/programs", json={"code": "gozero", "name": "GoZero"}, headers=headers)).json()
    assert p["code"] == "GOZERO"
    cuerpo = "I authorize the use of this information to verify my eligibility for GoZero."
    t = (await app_client.post(f"/api/v1/programs/{p['id']}/terms",
                               json={"version": "2026.1", "language": "en", "body": cuerpo}, headers=headers)).json()
    r = await app_client.post(f"/api/v1/programs/{p['id']}/terms",
                              json={"version": "2026.1", "language": "en", "body": cuerpo}, headers=headers)
    assert r.status_code == 409
    r = await app_client.post(f"/api/v1/programs/{p['id']}/terms",
                              json={"version": "2026.1", "language": "es", "body": "Autorizo el uso " * 3},
                              headers=headers)
    assert r.status_code == 201
    await app_client.post(f"/api/v1/program-terms/{t['id']}/publish", headers=headers)
    r = await app_client.patch(f"/api/v1/program-terms/{t['id']}", json={"body": cuerpo + " Edited."}, headers=headers)
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Zonas de venta y el inicio del vendedor
# ---------------------------------------------------------------------------

async def test_salespeople_see_their_programs_and_zones(app_client, active_admin_user, active_salesperson_user,
                                                        active_technician_user):
    headers = await _admin(app_client)
    await _instalar(app_client, headers)
    az = await _programa(app_client, headers, "AZ_EFFICIENCY")
    zona = (await app_client.post(f"/api/v1/programs/{az['id']}/zones",
                                  json={"name": "Sunrise Mobile Park", "state": "AZ", "city": "Phoenix"},
                                  headers=headers)).json()
    assert zona["code"] == "SUNRISE_MOBILE_PARK"
    r = await app_client.put(f"/api/v1/zones/{zona['id']}/salespeople",
                             json={"user_ids": [str(active_technician_user.id)]}, headers=headers)
    assert r.status_code == 400  # un técnico no sale a vender
    r = await app_client.put(f"/api/v1/zones/{zona['id']}/salespeople",
                             json={"user_ids": [str(active_salesperson_user.id)]}, headers=headers)
    assert r.status_code == 200

    vendedor = await headers_for(app_client, "vendedor@acme-demo.com")
    mios = (await app_client.get("/api/v1/me/programs", headers=vendedor)).json()
    assert [(m["program"]["code"], m["version"], [z["name"] for z in m["zones"]]) for m in mios] == [
        ("AZ_EFFICIENCY", "1", ["Sunrise Mobile Park"])]


# ---------------------------------------------------------------------------
# Permisos y aislamiento
# ---------------------------------------------------------------------------

async def test_a_salesperson_reads_programs_but_cannot_change_them(app_client, active_admin_user,
                                                                   active_salesperson_user):
    await _instalar(app_client, await _admin(app_client))
    vendedor = await headers_for(app_client, "vendedor@acme-demo.com")
    assert (await app_client.get("/api/v1/programs", headers=vendedor)).status_code == 200
    assert (await app_client.post("/api/v1/programs", json={"code": "X1", "name": "Nuevo"},
                                  headers=vendedor)).status_code == 403
    assert (await app_client.post("/api/v1/fields", json={"key": "a.b", "label": "x", "field_type": "text"},
                                  headers=vendedor)).status_code == 403


async def test_programs_of_another_organization_are_invisible(app_client, active_admin_user, second_org_admin_user):
    await _instalar(app_client, await _admin(app_client))
    ajeno = await headers_for(app_client, second_org_admin_user.email)
    assert (await app_client.get("/api/v1/programs", headers=ajeno)).json() == []
    assert (await app_client.get("/api/v1/fields", headers=ajeno)).json() == []


# ---------------------------------------------------------------------------
# Pendientes de José con la Cadena B (spec D1.8)
# ---------------------------------------------------------------------------

async def test_approving_stores_the_program_approval_code(app_client, db, seeded_org, active_admin_staff_user):
    case_hooks.register()
    from app.modules.crm.models import Customer

    org = seeded_org["org"].id
    cliente = Customer(organization_id=org, legal_name="Marge Simpson")
    db.add(cliente)
    await db.flush()
    case = await case_service.create_case(db, organization_id=org, actor_id=uuid.uuid4(), stage_code="new_prospect",
                                          customer_id=cliente.id, address_street="1 Main", address_city="Phoenix")
    case = await case_service.transition(db, case=case, to_stage="pending_approval", actor_id=uuid.uuid4(),
                                         actor_permissions=stages.SYSTEM_ACTOR)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    r = await app_client.post(f"/api/v1/cases/{case.id}/transition", json={
        "to_stage": "approved", "approval_code": " AZE-APR-77 ", "application_number": "APP-1001"}, headers=headers)
    assert r.status_code == 200, r.text
    assert (r.json()["approval_code"], r.json()["application_number"]) == ("AZE-APR-77", "APP-1001")


def test_the_two_transitions_requested_by_billing_exist():
    assert stages.is_allowed("approved", "ready_to_install")
    assert stages.is_allowed("installed", "billing_in_progress")


async def test_install_defaults_can_run_from_the_service(db, seeded_org):
    r = await svc.install_defaults(db, organization_id=seeded_org["org"].id)
    assert r["programs_created"] == ["AZ_EFFICIENCY", "TECH_CLEAN_CA"]


async def test_administration_configures_programs_and_assigns_salespeople(
    app_client, active_admin_user, active_admin_staff_user, active_salesperson_user
):
    """Administración maneja la configuración de programas completa: campos,
    formularios, publicar versiones y zonas con sus vendedores. Para asignar
    vendedores le basta `users.read`; no puede administrar usuarios."""
    await _instalar(app_client, await _admin(app_client))
    adm = await headers_for(app_client, "admin-staff@acme-demo.com")
    az = await _programa(app_client, adm, "AZ_EFFICIENCY")

    r = await app_client.post("/api/v1/fields", headers=adm,
                              json={"key": "qa.admin_staff", "label": "Campo de Administración", "field_type": "text"})
    assert r.status_code == 201, r.text

    zona = await app_client.post(f"/api/v1/programs/{az['id']}/zones", headers=adm,
                                 json={"name": "Desert Palms", "state": "AZ", "city": "Phoenix"})
    assert zona.status_code == 201, zona.text
    usuarios = (await app_client.get("/api/v1/users", headers=adm)).json()["items"]
    vendedor = next(u for u in usuarios if "salesperson" in u["roles"])
    r = await app_client.put(f"/api/v1/zones/{zona.json()['id']}/salespeople", headers=adm,
                             json={"user_ids": [vendedor["id"]]})
    assert r.status_code == 200, r.text

    assert (await app_client.post("/api/v1/users", headers=adm, json={
        "email": "x@acme-demo.com", "full_name": "X", "role_codes": ["salesperson"]})).status_code == 403
