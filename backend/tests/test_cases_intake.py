"""Módulo 2: el vendedor en la puerta (spec `2026-10-04-modulo-2-vendedor-design.md`).

Con el formulario real de TECH Clean (plantilla del módulo 1)."""
import base64
import io

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import func, select

from app.modules.cases import stages
from app.modules.cases.models import CaseStepSubmission
from app.modules.crm.models import Customer
from app.modules.field_ops import case_hooks
from app.modules.programs import service as programs
from app.shared import events as domain_events
from tests.field_helpers import headers_for, jpeg_bytes


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()
    domain_events.clear_subscribers()


PUERTA = {"address_street": "1200 W Sunrise Dr", "address_unit": "Spc 14", "address_city": "San Fernando",
          "address_state": "CA", "address_zip": "91340", "latitude": 34.28, "longitude": -118.44}


def firma_png() -> str:
    img = Image.new("RGB", (300, 100), "white")
    ImageDraw.Draw(img).line([(10, 80), (90, 20), (180, 70), (290, 15)], fill="black", width=4)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


async def _tech(db, org_id):
    await programs.install_defaults(db, organization_id=org_id)
    return next(p for p in await programs.list_programs(db, organization_id=org_id) if p.code == "TECH_CLEAN_CA")


async def _abrir(app_client, headers, program_id=None, **extra):
    r = await app_client.post("/api/v1/visits", json={**PUERTA, "result": "opened",
                                                     **({"program_id": str(program_id)} if program_id else {}),
                                                     **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _subir(app_client, headers, case_id, key, data=None, mime="image/jpeg", name="foto.jpg"):
    r = await app_client.post(f"/api/v1/cases/{case_id}/files", data={"field_key": key, "latitude": "34.28",
                                                                     "longitude": "-118.44"},
                              files={"file": (name, data or jpeg_bytes(), mime)}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _llenar_todo(app_client, headers, case_id):
    """Llena el formulario de TECH completo, como lo haría el vendedor."""
    paso = lambda code, answers: app_client.put(f"/api/v1/cases/{case_id}/steps/{code}",
                                                json={"answers": answers}, headers=headers)
    id_foto = await _subir(app_client, headers, case_id, "customer.id_photo")
    r = await paso("customer", {"customer.full_name": "Marge Simpson", "customer.phone": "(818) 555-0101",
                                "customer.email": "marge@example.com", "customer.address_street": PUERTA["address_street"],
                                "home.unit_number": "Spc 14", "customer.address_city": "San Fernando",
                                "customer.address_state": "CA", "customer.address_zip": "91340",
                                "customer.id_photo": id_foto})
    assert r.status_code == 200, r.text
    assert (await paso("home", {"home.is_homeowner": "yes", "home.residence_type": "mobile_home"})).status_code == 200
    doc = await _subir(app_client, headers, case_id, "eligibility.benefit_document")
    assert (await paso("eligibility", {"eligibility.programs_tech": ["care"],
                                       "eligibility.benefit_document": doc})).status_code == 200
    assert (await paso("technical", {"tech.panel_amperage": "200", "tech.existing_hvac": "none", "home.bedrooms": 2,
                                     "tech.induction_cooktop": "no", "tech.water_heater": "gas",
                                     "tech.electrical_viability": "adequate"})).status_code == 200
    docs = {}
    for key in ("docs.electric_bill", "docs.panel_photo", "docs.hvac_photos", "docs.pedestal_photo",
                "docs.mobile_home_title", "docs.mobile_home_decal"):
        docs[key] = await _subir(app_client, headers, case_id, key)
    assert (await paso("documents", docs)).status_code == 200
    assert (await paso("internal", {"internal.result": "preapproved"})).status_code == 200
    r = await app_client.post(f"/api/v1/cases/{case_id}/terms-acceptance",
                              json={"customer_name": "Marge Simpson", "signature": firma_png()}, headers=headers)
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# Visitas (D2.1)
# ---------------------------------------------------------------------------

async def test_a_door_that_does_not_open_is_still_a_case(app_client, active_salesperson_user):
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    r = await app_client.post("/api/v1/visits", json={**PUERTA, "result": "no_contact"}, headers=headers)
    assert r.status_code == 201
    assert (r.json()["outcome"], r.json()["case"]["stage_code"]) == ("created", "no_contact")


async def test_the_same_door_reuses_its_case_and_reopens_it(app_client, db, active_salesperson_user):
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    primera = (await app_client.post("/api/v1/visits", json={**PUERTA, "result": "no_contact"}, headers=headers)).json()
    # Misma puerta escrita distinto.
    otra = {**PUERTA, "address_street": "1200 w sunrise dr.", "result": "opened"}
    segunda = (await app_client.post("/api/v1/visits", json=otra, headers=headers)).json()
    assert segunda["case"]["id"] == primera["case"]["id"]
    assert (segunda["outcome"], segunda["case"]["stage_code"]) == ("reopened", "new_prospect")
    visitas = (await app_client.get(f"/api/v1/cases/{primera['case']['id']}/visits", headers=headers)).json()
    assert [v["result"] for v in visitas] == ["no_contact", "opened"]


async def test_the_salesperson_picks_the_program_and_its_published_version(app_client, db, seeded_org,
                                                                          active_salesperson_user):
    tech = await _tech(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, headers, tech.id))["case"]
    form = (await app_client.get(f"/api/v1/cases/{caso['id']}/form", headers=headers)).json()
    assert [s["code"] for s in form["definition"]["steps"]][:2] == ["customer", "home"]
    assert form["terms"]["version"] == "2026.1" and form["editable"] is True
    assert form["evaluation"]["can_submit"] is False


# ---------------------------------------------------------------------------
# Formulario (D2.2, D2.3)
# ---------------------------------------------------------------------------

async def test_answers_are_immutable_and_the_latest_wins(app_client, db, seeded_org, active_salesperson_user):
    tech = await _tech(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, headers, tech.id))["case"]
    url = f"/api/v1/cases/{caso['id']}/steps/home"
    await app_client.put(url, json={"answers": {"home.is_homeowner": "no"}}, headers=headers)
    r = await app_client.put(url, json={"answers": {"home.is_homeowner": "yes", "home.residence_type": "condominium"}},
                             headers=headers)
    assert r.json()["answers"]["home.is_homeowner"] == "yes"
    total = (await db.execute(select(func.count()).select_from(CaseStepSubmission)
                              .where(CaseStepSubmission.step_code == "home"))).scalar_one()
    assert total == 2


async def test_bad_values_and_foreign_keys_are_rejected(app_client, db, seeded_org, active_salesperson_user):
    tech = await _tech(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, headers, tech.id))["case"]
    r = await app_client.put(f"/api/v1/cases/{caso['id']}/steps/customer",
                             json={"answers": {"customer.email": "marge@", "customer.address_zip": "913"}}, headers=headers)
    assert r.status_code == 400 and "correo" in r.json()["detail"] and "ZIP" in r.json()["detail"]
    r = await app_client.put(f"/api/v1/cases/{caso['id']}/steps/customer",
                             json={"answers": {"home.gas_type": "natural_gas"}}, headers=headers)
    assert r.status_code == 400


async def test_customer_data_goes_to_a_real_customer_reusing_the_phone(app_client, db, seeded_org,
                                                                       active_salesperson_user):
    org = seeded_org["org"].id
    tech = await _tech(db, org)
    db.add(Customer(organization_id=org, legal_name="Marjorie Simpson", main_phone="+1 818-555-0101"))
    await db.commit()
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, headers, tech.id))["case"]
    r = await app_client.put(f"/api/v1/cases/{caso['id']}/steps/customer", json={"answers": {
        "customer.full_name": "Marge Simpson", "customer.phone": "(818) 555-0101",
        "customer.address_street": "1200 W Sunrise Dr", "customer.address_city": "San Fernando"}}, headers=headers)
    assert r.status_code == 200, r.text
    clientes = (await db.execute(select(Customer).where(Customer.organization_id == org))).scalars().all()
    assert len(clientes) == 1 and r.json()["case"]["customer_id"] == str(clientes[0].id)


# ---------------------------------------------------------------------------
# Archivos (D2.5)
# ---------------------------------------------------------------------------

async def test_files_are_checked_and_watermarked(app_client, db, seeded_org, active_salesperson_user):
    tech = await _tech(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, headers, tech.id))["case"]
    r = await app_client.post(f"/api/v1/cases/{caso['id']}/files", data={"field_key": "docs.panel_photo"},
                              files={"file": ("virus.exe", b"MZ...", "application/octet-stream")}, headers=headers)
    assert r.status_code == 400
    r = await app_client.post(f"/api/v1/cases/{caso['id']}/files", data={"field_key": "home.notes"},
                              files={"file": ("f.jpg", jpeg_bytes(), "image/jpeg")}, headers=headers)
    assert r.status_code == 400
    r = await app_client.post(f"/api/v1/cases/{caso['id']}/files", data={"field_key": "docs.panel_photo"},
                              files={"file": ("panel.jpg", jpeg_bytes(), "image/jpeg")}, headers=headers)
    assert r.status_code == 201 and r.json()["watermarked"] is True
    # Un archivo de otro campo no se puede usar como respuesta.
    r = await app_client.put(f"/api/v1/cases/{caso['id']}/steps/documents",
                             json={"answers": {"docs.electric_bill": r.json()["id"]}}, headers=headers)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Términos, firma y envío (D2.6, D2.7)
# ---------------------------------------------------------------------------

async def test_an_incomplete_case_cannot_be_submitted_and_says_what_is_missing(app_client, db, seeded_org,
                                                                                active_salesperson_user):
    tech = await _tech(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, headers, tech.id))["case"]
    r = await app_client.post(f"/api/v1/cases/{caso['id']}/submit", headers=headers)
    assert r.status_code == 400
    assert "Nombre completo" in r.json()["detail"] and "Firma del cliente" in r.json()["detail"]


async def test_an_empty_signature_is_rejected(app_client, db, seeded_org, active_salesperson_user):
    tech = await _tech(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, headers, tech.id))["case"]
    r = await app_client.post(f"/api/v1/cases/{caso['id']}/terms-acceptance",
                              json={"customer_name": "Marge", "signature": "data:image/png;base64,AAAA"}, headers=headers)
    assert r.status_code == 400


async def test_the_full_door_to_review_flow(app_client, db, seeded_org, active_salesperson_user,
                                            active_admin_staff_user):
    eventos = []
    domain_events.subscribe("case.submitted", lambda n, p: eventos.append(p["resubmitted"]))
    tech = await _tech(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, headers, tech.id))["case"]
    await _llenar_todo(app_client, headers, caso["id"])

    form = (await app_client.get(f"/api/v1/cases/{caso['id']}/form", headers=headers)).json()
    assert form["evaluation"]["can_submit"] is True, form["evaluation"]["missing"]
    assert form["acceptance"]["terms_version"] == "2026.1"
    r = await app_client.post(f"/api/v1/cases/{caso['id']}/submit", headers=headers)
    assert r.status_code == 200, r.text
    assert (r.json()["stage_code"], r.json()["substatus_code"]) == ("pending_approval", "pending_review")
    assert eventos == [False]
    # Enviado ya no se edita.
    r = await app_client.put(f"/api/v1/cases/{caso['id']}/steps/home",
                             json={"answers": {"home.is_homeowner": "no"}}, headers=headers)
    assert r.status_code == 409

    # Administración lo devuelve; el vendedor corrige y reenvía.
    admin = await headers_for(app_client, active_admin_staff_user.email)
    r = await app_client.post(f"/api/v1/cases/{caso['id']}/substatus",
                              json={"substatus": "returned", "reason": "Falta el número de habitaciones correcto"},
                              headers=admin)
    assert r.status_code == 200, r.text
    r = await app_client.put(f"/api/v1/cases/{caso['id']}/steps/technical",
                             json={"answers": {"home.bedrooms": 3}}, headers=headers)
    assert r.status_code == 200
    r = await app_client.post(f"/api/v1/cases/{caso['id']}/submit", headers=headers)
    assert (r.json()["stage_code"], r.json()["substatus_code"]) == ("pending_approval", "pending_review")
    assert eventos == [False, True]


# ---------------------------------------------------------------------------
# Dueño, aislamiento y tablero
# ---------------------------------------------------------------------------

async def test_another_salesperson_cannot_see_or_fill_my_case(app_client, db, seeded_org, active_salesperson_user):
    from tests.conftest import _make_role_user

    tech = await _tech(db, seeded_org["org"].id)
    await _make_role_user(db, seeded_org, role_code="salesperson", email="vendedor2@acme-demo.com", full_name="Otro")
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, headers, tech.id))["case"]
    otro = await headers_for(app_client, "vendedor2@acme-demo.com")
    assert (await app_client.get(f"/api/v1/cases/{caso['id']}/form", headers=otro)).status_code == 404
    r = await app_client.put(f"/api/v1/cases/{caso['id']}/steps/home",
                             json={"answers": {"home.is_homeowner": "yes"}}, headers=otro)
    assert r.status_code == 404
    # Tocar la misma puerta no le roba el expediente.
    r = await app_client.post("/api/v1/visits", json={**PUERTA, "result": "opened"}, headers=otro)
    assert r.status_code == 409


async def test_the_board_groups_by_stage_and_hides_early_closes(app_client, db, seeded_org, active_salesperson_user):
    tech = await _tech(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    await _abrir(app_client, headers, tech.id)
    await app_client.post("/api/v1/visits", json={**PUERTA, "address_unit": "Spc 15", "result": "not_interested"},
                          headers=headers)
    columnas = {c["code"]: c for c in (await app_client.get("/api/v1/case-board", headers=headers)).json()}
    assert "not_interested" not in columnas
    assert columnas["new_prospect"]["count"] == 1
    assert columnas["new_prospect"]["cases"][0]["program_name"] == "TECH Clean California"
    todas = {c["code"]: c for c in (await app_client.get("/api/v1/case-board?include_early_closes=true",
                                                         headers=headers)).json()}
    assert todas["not_interested"]["count"] == 1


async def test_returning_is_for_administration_not_the_salesperson(app_client, db, seeded_org, active_salesperson_user):
    tech = await _tech(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, headers, tech.id))["case"]
    await _llenar_todo(app_client, headers, caso["id"])
    await app_client.post(f"/api/v1/cases/{caso['id']}/submit", headers=headers)
    r = await app_client.post(f"/api/v1/cases/{caso['id']}/substatus", json={"substatus": "returned"}, headers=headers)
    assert r.status_code == 403


async def test_the_signature_image_can_be_seen_after_signing(app_client, db, seeded_org, active_salesperson_user):
    tech = await _tech(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, headers, tech.id))["case"]
    url = f"/api/v1/cases/{caso['id']}/terms-acceptance/signature"
    assert (await app_client.get(url, headers=headers)).status_code == 404
    await app_client.post(f"/api/v1/cases/{caso['id']}/terms-acceptance",
                          json={"customer_name": "Marge Simpson", "signature": firma_png()}, headers=headers)
    r = await app_client.get(url, headers=headers)
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"


async def test_my_day_shows_only_my_cases_even_for_an_admin(app_client, db, seeded_org, active_salesperson_user,
                                                            active_admin_user):
    tech = await _tech(db, seeded_org["org"].id)
    await _abrir(app_client, await headers_for(app_client, "vendedor@acme-demo.com"), tech.id)
    admin = await headers_for(app_client, "admin@acme-demo.com")
    todos = {c["code"]: c["count"] for c in (await app_client.get("/api/v1/case-board", headers=admin)).json()}
    mios = {c["code"]: c["count"] for c in (await app_client.get("/api/v1/case-board?mine=true", headers=admin)).json()}
    assert (todos["new_prospect"], mios["new_prospect"]) == (1, 0)


async def test_a_phone_alone_does_not_overwrite_another_customer(app_client, db, seeded_org, active_salesperson_user):
    org_id = seeded_org["org"].id
    ajeno = Customer(organization_id=org_id, legal_name="Ned Flanders", main_phone="(818) 555-0101")
    db.add(ajeno)
    await db.commit()
    tech = await _tech(db, org_id)
    headers = await headers_for(app_client, "vendedor@acme-demo.com")
    caso = (await _abrir(app_client, headers, tech.id))["case"]
    r = await app_client.put(f"/api/v1/cases/{caso['id']}/steps/customer", headers=headers, json={"answers": {
        "customer.full_name": "Marge Simpson", "customer.phone": "(818) 555-0101"}})
    assert r.status_code == 200, r.text
    # Se enlaza por teléfono (no duplica), pero no le cambia el nombre.
    assert r.json()["case"]["customer_id"] == str(ajeno.id)
    await db.refresh(ajeno)
    assert ajeno.legal_name == "Ned Flanders"
