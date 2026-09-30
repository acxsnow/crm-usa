"""Ajuste del módulo 5 para el cobro (módulo 6, spec D6.4 y D6.6).

- El permiso es flexible en el orden (se puede instalar antes), pero la
  inspección exige permiso radicado y aprobarla exige el permiso firmado por
  el inspector.
- Administración confirma la información del técnico o se la devuelve con
  motivo; devolver reabre el acta y el técnico puede volver a cerrarla aunque
  el expediente ya esté más adelante.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.field_ops import case_hooks
from app.modules.field_ops.models import Evidence, Permit
from app.shared import events as domain_events
from app.shared.errors import InvalidInputError
from tests.field_helpers import (
    headers_for,
    installed_case,
    jpeg_bytes,
    refreshed_case,
)


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()
    domain_events.clear_subscribers()


def _cuando():
    return (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()


async def _subir_permiso_firmado(app_client, headers, inspection_id):
    resp = await app_client.post(
        f"/api/v1/inspections/{inspection_id}/signed-permit",
        files={"file": ("permiso.jpg", jpeg_bytes(), "image/jpeg")}, headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["category"] == "permit_signed"


# ---------------------------------------------------------------------------
# Permiso e inspección
# ---------------------------------------------------------------------------

async def test_the_inspection_needs_a_filed_permit(app_client, db, seeded_org, active_admin_staff_user):
    _, project = await installed_case(db, seeded_org["org"].id)
    project_id = project.id
    # Sin ningún permiso registrado (se instaló antes de sacarlo).
    await db.execute(delete(Permit).where(Permit.project_id == project_id))
    await db.commit()
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.post(f"/api/v1/projects/{project_id}/inspections",
                                 json={"scheduled_for": _cuando()}, headers=headers)
    assert resp.status_code == 409
    assert "permiso" in resp.json()["detail"]


async def test_passing_the_inspection_needs_the_permit_signed_by_the_inspector(app_client, db, seeded_org, active_admin_staff_user):
    _, project = await installed_case(db, seeded_org["org"].id)
    project_id = project.id
    headers = await headers_for(app_client, active_admin_staff_user.email)
    inspeccion = (await app_client.post(f"/api/v1/projects/{project_id}/inspections",
                                        json={"scheduled_for": _cuando()}, headers=headers)).json()
    url = f"/api/v1/inspections/{inspeccion['id']}/result"

    resp = await app_client.post(url, json={"result": "passed"}, headers=headers)
    assert resp.status_code == 400
    assert "permiso firmado" in resp.json()["detail"]

    await _subir_permiso_firmado(app_client, headers, inspeccion["id"])
    assert (await app_client.post(url, json={"result": "passed"}, headers=headers)).status_code == 200


async def test_a_failed_inspection_does_not_need_the_signed_permit(app_client, db, seeded_org, active_admin_staff_user):
    _, project = await installed_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    inspeccion = (await app_client.post(f"/api/v1/projects/{project.id}/inspections",
                                        json={"scheduled_for": _cuando()}, headers=headers)).json()
    resp = await app_client.post(f"/api/v1/inspections/{inspeccion['id']}/result",
                                 json={"result": "failed", "observations": "Falta sellado"}, headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Confirmación del acta y devolución al técnico
# ---------------------------------------------------------------------------

async def test_administration_confirms_the_technician_info(app_client, db, seeded_org, active_admin_staff_user):
    _, project = await installed_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.post(f"/api/v1/projects/{project.id}/review/confirm", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["technician_info_confirmed"] is True

    historial = (await app_client.get(f"/api/v1/projects/{project.id}/reviews", headers=headers)).json()
    assert [r["action"] for r in historial] == ["confirmed"]


async def test_an_open_acta_cannot_be_confirmed(app_client, db, seeded_org, active_admin_staff_user):
    from tests.field_helpers import ready_to_install_case

    _, project = await ready_to_install_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.post(f"/api/v1/projects/{project.id}/review/confirm", json={}, headers=headers)
    assert resp.status_code == 409


async def test_returning_needs_a_reason_and_reopens_the_acta(app_client, db, seeded_org, active_admin_staff_user):
    _, project = await installed_case(db, seeded_org["org"].id)
    project_id = project.id
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.post(f"/api/v1/projects/{project_id}/review/return", json={"reason": ""}, headers=headers)
    assert resp.status_code == 422

    resp = await app_client.post(f"/api/v1/projects/{project_id}/review/return",
                                 json={"reason": "La foto de la etiqueta exterior no se lee"}, headers=headers)
    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert (cuerpo["status"], cuerpo["technician_info_confirmed"]) == ("scheduled", False)
    assert cuerpo["returned_reason"] == "La foto de la etiqueta exterior no se lee"


async def test_the_technician_recloses_a_returned_acta_while_the_case_stays(app_client, db, seeded_org, active_admin_staff_user):
    """El expediente ya está en «Instalado» (o más adelante): la devolución
    reabre el acta, no el expediente, y el técnico la vuelve a cerrar."""
    case, project = await installed_case(db, seeded_org["org"].id)
    project_id = project.id
    headers = await headers_for(app_client, active_admin_staff_user.email)
    await app_client.post(f"/api/v1/projects/{project_id}/review/return",
                          json={"reason": "Falta el serial del equipo"}, headers=headers)

    resp = await app_client.post(f"/api/v1/projects/{project_id}/installation/close",
                                 json={"observations": "Serial corregido"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"
    assert (await refreshed_case(db, case)).stage_code == "installed"

    # Queda pendiente de confirmar otra vez.
    proyecto = (await app_client.get(f"/api/v1/projects/{project_id}", headers=headers)).json()
    assert proyecto["technician_info_confirmed"] is False


async def test_a_technician_cannot_confirm_their_own_acta(app_client, db, seeded_org, active_technician_user):
    _, project = await installed_case(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    headers = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.post(f"/api/v1/projects/{project.id}/review/confirm", json={}, headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Entrada a cobro: acta confirmada (la inspección pasa a requisito del programa)
# ---------------------------------------------------------------------------

async def test_billing_entry_needs_the_confirmed_acta(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await installed_case(db, seeded_org["org"].id)
    project_id = project.id
    headers = await headers_for(app_client, active_admin_staff_user.email)
    inspeccion = (await app_client.post(f"/api/v1/projects/{project_id}/inspections",
                                        json={"scheduled_for": _cuando()}, headers=headers)).json()
    await _subir_permiso_firmado(app_client, headers, inspeccion["id"])
    await app_client.post(f"/api/v1/inspections/{inspeccion['id']}/result", json={"result": "passed"}, headers=headers)
    case = await refreshed_case(db, case)

    org_id, case_id = case.organization_id, case.id
    with pytest.raises(InvalidInputError, match="confirme la información"):
        await case_service.transition(db, case=case, to_stage="billing_in_progress", actor_id=uuid.uuid4(),
                                      actor_permissions=stages.SYSTEM_ACTOR)
    await db.rollback()

    await app_client.post(f"/api/v1/projects/{project_id}/review/confirm", json={}, headers=headers)
    db.expire_all()
    case = await case_service.get_case_or_404(db, organization_id=org_id, case_id=case_id)
    case = await case_service.transition(db, case=case, to_stage="billing_in_progress", actor_id=uuid.uuid4(),
                                         actor_permissions=stages.SYSTEM_ACTOR)
    assert case.stage_code == "billing_in_progress"


# ---------------------------------------------------------------------------
# Instalar antes del permiso (pedido a José, contrato §9.1)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not stages.is_allowed("approved", "ready_to_install"),
                    reason="Falta la transición approved → ready_to_install en cases/stages.py (pedido a José)")
async def test_releasing_the_order_without_a_permit_moves_the_case_to_ready_to_install(
        app_client, db, seeded_org, active_admin_staff_user, active_technician_user):
    from datetime import date as _date

    from tests.field_helpers import approved_case_with_project

    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.patch(f"/api/v1/projects/{project.id}/schedule", json={
        "technician_user_id": str(active_technician_user.id), "scheduled_date": _date.today().isoformat()},
        headers=headers)
    assert resp.status_code == 200, resp.text
    assert (await refreshed_case(db, case)).stage_code == "ready_to_install"
