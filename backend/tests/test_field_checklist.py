"""Checklist técnico configurable (módulo 5, spec D5.3 y D5.4).

Lo que protege: que el técnico pueda marcar SU checklist y no el de otro; que
"No aplica" deje constancia; que los ítems condicionales solo se exijan cuando
la condición aplica a la casa; y que cada foto quede en la categoría que el
ítem exige.
"""
import pytest

from app.modules.cases import stages
from app.modules.field_ops import case_hooks
from app.modules.field_ops.checklist import checklist_gaps
from tests.field_helpers import (
    approved_case_with_project,
    checklist_items,
    headers_for,
    item_by_label,
    jpeg_bytes,
)


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()


# ---------------------------------------------------------------------------
# Quién marca
# ---------------------------------------------------------------------------

async def test_the_assigned_technician_completes_an_item(app_client, db, seeded_org, active_technician_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    item = item_by_label(await checklist_items(db, project.id), "Prueba de funcionamiento")

    headers = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.patch(f"/api/v1/checklist-items/{item.id}", json={"is_complete": True}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_complete"] is True


async def test_a_technician_cannot_touch_another_technicians_checklist(app_client, db, seeded_org, active_technician_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id)  # sin asignar
    item = item_by_label(await checklist_items(db, project.id), "Prueba de funcionamiento")

    headers = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.patch(f"/api/v1/checklist-items/{item.id}", json={"is_complete": True}, headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# "No aplica"
# ---------------------------------------------------------------------------

async def test_not_applicable_requires_a_reason(app_client, db, seeded_org, active_admin_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    item = item_by_label(await checklist_items(db, project.id), "panel eléctrico")
    headers = await headers_for(app_client, "admin@acme-demo.com")

    resp = await app_client.patch(
        f"/api/v1/checklist-items/{item.id}", json={"not_applicable": True, "reason": " "}, headers=headers
    )
    assert resp.status_code == 400
    assert "motivo" in resp.json()["detail"]

    resp = await app_client.patch(
        f"/api/v1/checklist-items/{item.id}",
        json={"not_applicable": True, "reason": "La casa no tiene panel propio"},
        headers=headers,
    )
    assert resp.status_code == 200
    cuerpo = resp.json()
    assert cuerpo["not_applicable"] is True
    assert cuerpo["not_applicable_reason"] == "La casa no tiene panel propio"


async def test_not_applicable_is_rejected_where_the_item_does_not_allow_it(app_client, db, seeded_org, active_admin_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    item = item_by_label(await checklist_items(db, project.id), "Prueba de funcionamiento")
    headers = await headers_for(app_client, "admin@acme-demo.com")

    resp = await app_client.patch(
        f"/api/v1/checklist-items/{item.id}", json={"not_applicable": True, "reason": "No se pudo"}, headers=headers
    )
    assert resp.status_code == 400
    assert "no admite" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Condiciones de la instalación
# ---------------------------------------------------------------------------

async def test_a_conditional_item_is_only_required_when_its_condition_applies(app_client, db, seeded_org, active_admin_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    faltan = await checklist_gaps(db, project=project)
    assert not any("gas" in label for label in faltan)

    headers = await headers_for(app_client, "admin@acme-demo.com")
    resp = await app_client.patch(
        f"/api/v1/projects/{project.id}/conditions",
        json={"conditions": ["gas_equipment_removed"]}, headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["installation_conditions"] == ["gas_equipment_removed"]

    await db.refresh(project)
    faltan = await checklist_gaps(db, project=project)
    assert any("gas" in label for label in faltan)


async def test_an_unknown_condition_is_rejected(app_client, db, seeded_org, active_admin_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "admin@acme-demo.com")
    resp = await app_client.patch(
        f"/api/v1/projects/{project.id}/conditions", json={"conditions": ["tiene_piscina"]}, headers=headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Plantilla por programa
# ---------------------------------------------------------------------------

async def test_the_program_template_is_used_when_the_case_has_one(db, seeded_org):
    from app.modules.cases.models import Program
    from app.modules.field_ops.models import ChecklistTemplate, ChecklistTemplateItem

    org_id = seeded_org["org"].id
    programa = Program(organization_id=org_id, code="AZ_EFFICIENCY", name="Eficiencia de Arizona")
    db.add(programa)
    await db.flush()
    plantilla = ChecklistTemplate(organization_id=org_id, name="Arizona", program_id=programa.id)
    db.add(plantilla)
    await db.flush()
    db.add(ChecklistTemplateItem(template_id=plantilla.id, label="Foto del medidor", sort_order=0))
    await db.commit()

    _, project = await approved_case_with_project(db, org_id, program_id=programa.id)
    etiquetas = [i.label for i in await checklist_items(db, project.id)]
    assert etiquetas == ["Foto del medidor"]


# ---------------------------------------------------------------------------
# Evidencia por categoría
# ---------------------------------------------------------------------------

async def test_evidence_for_an_item_takes_the_item_category(app_client, db, seeded_org, active_admin_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    item = item_by_label(await checklist_items(db, project.id), "Etiqueta exterior")
    headers = await headers_for(app_client, "admin@acme-demo.com")

    resp = await app_client.post(
        f"/api/v1/projects/{project.id}/evidence",
        files={"file": ("etiqueta.jpg", jpeg_bytes(), "image/jpeg")},
        data={"checklist_item_id": str(item.id)}, headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["category"] == "outdoor_label"


async def test_evidence_with_a_different_category_than_the_item_is_rejected(app_client, db, seeded_org, active_admin_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    item = item_by_label(await checklist_items(db, project.id), "Etiqueta exterior")
    headers = await headers_for(app_client, "admin@acme-demo.com")

    resp = await app_client.post(
        f"/api/v1/projects/{project.id}/evidence",
        files={"file": ("etiqueta.jpg", jpeg_bytes(), "image/jpeg")},
        data={"checklist_item_id": str(item.id), "category": "facade"}, headers=headers,
    )
    assert resp.status_code == 400
    assert "Etiqueta exterior" in resp.json()["detail"]


async def test_an_unknown_evidence_category_is_rejected(app_client, db, seeded_org, active_admin_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "admin@acme-demo.com")
    resp = await app_client.post(
        f"/api/v1/projects/{project.id}/evidence",
        files={"file": ("x.jpg", jpeg_bytes(), "image/jpeg")},
        data={"category": "before"}, headers=headers,
    )
    assert resp.status_code == 400


async def test_evidence_cannot_be_attached_to_an_item_of_another_project(app_client, db, seeded_org, active_admin_user):
    org_id = seeded_org["org"].id
    _, uno = await approved_case_with_project(db, org_id)
    _, otro = await approved_case_with_project(db, org_id)
    item_ajeno = (await checklist_items(db, otro.id))[0]
    headers = await headers_for(app_client, "admin@acme-demo.com")

    resp = await app_client.post(
        f"/api/v1/projects/{uno.id}/evidence",
        files={"file": ("x.jpg", jpeg_bytes(), "image/jpeg")},
        data={"checklist_item_id": str(item_ajeno.id)}, headers=headers,
    )
    assert resp.status_code == 400


async def test_a_technician_cannot_upload_evidence_to_a_project_not_assigned(app_client, db, seeded_org, active_technician_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.post(
        f"/api/v1/projects/{project.id}/evidence",
        files={"file": ("x.jpg", jpeg_bytes(), "image/jpeg")},
        data={}, headers=headers,
    )
    assert resp.status_code == 404


async def test_an_organization_with_the_pre_module_5_template_gets_the_new_checklist(db, seeded_org):
    """La plantilla por defecto anterior al módulo 5 (sin categorías, con la
    firma de atestación) no debe seguir usándose para proyectos nuevos. Lo
    destapó el recorrido contra la base real: la organización demo la tenía."""
    from app.modules.field_ops.models import ChecklistTemplate, ChecklistTemplateItem

    org_id = seeded_org["org"].id
    vieja = ChecklistTemplate(organization_id=org_id, name="Instalación HVAC — Programa de Aires Gratis",
                              project_type="hvac_install")
    db.add(vieja)
    await db.flush()
    db.add(ChecklistTemplateItem(template_id=vieja.id, label="Firma de atestación (técnico y cliente)", sort_order=0))
    await db.commit()

    _, project = await approved_case_with_project(db, org_id)
    items = await checklist_items(db, project.id)
    assert not any("Firma de atestación" in i.label for i in items)
    assert any(i.evidence_category == "outdoor_label" for i in items)
