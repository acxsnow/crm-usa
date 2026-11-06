"""Ajustes del cliente al formulario del vendedor (5 nov 2026) sobre una
organización que ya tenía la versión anterior de los programas."""
from sqlalchemy import select

from app.modules.cases.models import Program
from app.modules.programs import client_adjustments, service
from app.modules.programs.models import FieldDefinition, WorkflowStepField


async def _claves(db, org_id, code):
    programa = (await db.execute(select(Program).where(Program.organization_id == org_id,
                                                       Program.code == code))).scalar_one()
    version = await service.published_version(db, organization_id=org_id, program_id=programa.id)
    definicion = await service.version_definition(db, version)
    return version, {c["key"]: c for s in definicion["steps"] for c in s["fields"]}


async def _como_antes(db, org_id):
    """Deja la versión publicada como estaba antes del 5 nov: correo y foto del
    documento obligatorios, viabilidad del vendedor y las fotos de documentos."""
    campos = {f.key: f for f in await service.list_fields(db, organization_id=org_id)}
    campos["tech.panel_amperage"].options = [o for o in campos["tech.panel_amperage"].options
                                             if o["value"] not in ("50", "70")]
    campos["internal.result"].options = [{"value": "preapproved", "label": "Preaprobado"},
                                         {"value": "pending", "label": "Pendiente"},
                                         {"value": "does_not_qualify", "label": "No califica"}]
    for code in ("AZ_EFFICIENCY", "TECH_CLEAN_CA"):
        version, claves = await _claves(db, org_id, code)
        pasos = {s.code: s for f in await service.phases_of(db, version.id) for s in f.steps}
        for c in pasos["customer"].fields:
            if c.field_id in (campos["customer.email"].id, campos["customer.id_photo"].id):
                c.requirement = "required"
        db.add(WorkflowStepField(organization_id=org_id, step_id=pasos["technical"].id,
                                 field_id=campos["tech.electrical_viability"].id, requirement="required", sort_order=90))
        for c in pasos["documents"].fields:
            if c.field_id == campos["docs.mobile_home_title_or_decal"].id:
                await db.delete(c)
        for n, key in enumerate(("docs.furnace_photo", "docs.hvac_photos", "docs.pedestal_photo",
                                 "docs.mobile_home_title", "docs.mobile_home_decal")):
            db.add(WorkflowStepField(organization_id=org_id, step_id=pasos["documents"].id, field_id=campos[key].id,
                                     requirement="required", sort_order=10 + n))
    await db.commit()


async def test_an_existing_org_gets_a_new_published_version_with_the_adjustments(db, seeded_org):
    org_id = seeded_org["org"].id
    await service.install_defaults(db, organization_id=org_id)
    await _como_antes(db, org_id)

    assert await client_adjustments.apply(db, organization_id=org_id) == ["AZ_EFFICIENCY", "TECH_CLEAN_CA"]

    for code in ("AZ_EFFICIENCY", "TECH_CLEAN_CA"):
        version, claves = await _claves(db, org_id, code)
        assert version.version == "2" and client_adjustments.MARCA in version.notes
        assert claves["customer.email"]["requirement"] == "optional"
        assert claves["customer.id_photo"]["requirement"] == ("optional" if code == "TECH_CLEAN_CA" else "required")
        assert not client_adjustments.QUITAR & set(claves)
        assert claves["docs.mobile_home_title_or_decal"]["requirement"] == "conditional"

    campos = {f.key: f for f in (await db.execute(select(FieldDefinition).where(
        FieldDefinition.organization_id == org_id))).scalars().all()}
    assert [o["value"] for o in campos["tech.panel_amperage"].options][:2] == ["50", "70"]
    assert campos["internal.result"].options == [{"value": "preapproved", "label": "Completo"},
                                                 {"value": "pending", "label": "Pendiente de algo"}]

    # Otra vez no hace nada: la versión ya lleva la marca.
    assert await client_adjustments.apply(db, organization_id=org_id) == []


async def test_a_new_org_already_has_them_and_gets_no_empty_version(db, seeded_org):
    org_id = seeded_org["org"].id
    await service.install_defaults(db, organization_id=org_id)
    assert await client_adjustments.apply(db, organization_id=org_id) == []
    version, _ = await _claves(db, org_id, "TECH_CLEAN_CA")
    assert version.version == "1"
