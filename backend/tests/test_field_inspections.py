"""Inspección municipal con intentos (spec D5.6)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.field_ops import case_hooks
from app.shared import events as domain_events
from app.shared.errors import InvalidInputError
from tests.field_helpers import (
    approved_case_with_project,
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


async def _agendar(app_client, headers, project_id):
    resp = await app_client.post(
        f"/api/v1/projects/{project_id}/inspections",
        json={"scheduled_for": _cuando(), "inspector_name": "City of Phoenix"}, headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _subir_permiso_firmado(app_client, headers, inspection_id):
    """Aprobar la inspección exige el permiso firmado por el inspector (módulo 6)."""
    resp = await app_client.post(
        f"/api/v1/inspections/{inspection_id}/signed-permit",
        files={"file": ("permiso.jpg", jpeg_bytes(), "image/jpeg")}, headers=headers,
    )
    assert resp.status_code == 201, resp.text


async def test_scheduling_the_inspection_moves_the_case_to_inspection_pending(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await installed_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    inspeccion = await _agendar(app_client, headers, project.id)
    assert inspeccion["result"] == "pending"
    assert (await refreshed_case(db, case)).stage_code == "inspection_pending"


async def test_an_inspection_before_the_installation_is_closed_is_rejected(app_client, db, seeded_org, active_admin_staff_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.post(f"/api/v1/projects/{project.id}/inspections",
                                 json={"scheduled_for": _cuando()}, headers=headers)
    assert resp.status_code == 409


async def test_only_one_inspection_can_be_pending(app_client, db, seeded_org, active_admin_staff_user):
    _, project = await installed_case(db, seeded_org["org"].id)
    project_id = project.id
    headers = await headers_for(app_client, active_admin_staff_user.email)
    await _agendar(app_client, headers, project_id)
    resp = await app_client.post(f"/api/v1/projects/{project_id}/inspections",
                                 json={"scheduled_for": _cuando()}, headers=headers)
    assert resp.status_code == 409


async def test_a_passed_inspection_marks_the_substatus_and_unlocks_billing(app_client, db, seeded_org, active_admin_staff_user):
    events = []
    domain_events.subscribe("inspection.recorded", lambda n, p: events.append(p["result"]))
    case, project = await installed_case(db, seeded_org["org"].id)
    project_id = project.id
    headers = await headers_for(app_client, active_admin_staff_user.email)
    inspeccion = await _agendar(app_client, headers, project_id)
    await _subir_permiso_firmado(app_client, headers, inspeccion["id"])

    resp = await app_client.post(f"/api/v1/inspections/{inspeccion['id']}/result",
                                 json={"result": "passed"}, headers=headers)
    assert resp.status_code == 200, resp.text
    case = await refreshed_case(db, case)
    assert (case.stage_code, case.substatus_code) == ("inspection_pending", "inspection_approved")
    assert events == ["passed"]

    # Con el acta confirmada por Administración, la guarda de cobro deja pasar.
    resp = await app_client.post(f"/api/v1/projects/{project_id}/review/confirm", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    case = await refreshed_case(db, case)
    case = await case_service.transition(
        db, case=case, to_stage="billing_in_progress", actor_id=uuid.uuid4(), actor_permissions=stages.SYSTEM_ACTOR
    )
    assert case.stage_code == "billing_in_progress"


async def test_a_failed_inspection_sends_the_order_back_and_keeps_the_attempt(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await installed_case(db, seeded_org["org"].id)
    project_id = project.id
    headers = await headers_for(app_client, active_admin_staff_user.email)
    inspeccion = await _agendar(app_client, headers, project_id)

    resp = await app_client.post(f"/api/v1/inspections/{inspeccion['id']}/result",
                                 json={"result": "failed"}, headers=headers)
    assert resp.status_code == 400  # sin observaciones no se sabe qué corregir

    resp = await app_client.post(
        f"/api/v1/inspections/{inspeccion['id']}/result",
        json={"result": "failed", "observations": "Falta soporte antivibración en la unidad exterior"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert (await refreshed_case(db, case)).stage_code == "ready_to_install"

    proyecto = (await app_client.get(f"/api/v1/projects/{project_id}", headers=headers)).json()
    assert proyecto["status"] == "scheduled"
    assert proyecto["completed_date"] is None

    intentos = (await app_client.get(f"/api/v1/projects/{project_id}/inspections", headers=headers)).json()
    assert [i["result"] for i in intentos] == ["failed"]


async def test_a_result_cannot_be_recorded_twice(app_client, db, seeded_org, active_admin_staff_user):
    _, project = await installed_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    inspeccion = await _agendar(app_client, headers, project.id)
    await _subir_permiso_firmado(app_client, headers, inspeccion["id"])
    url = f"/api/v1/inspections/{inspeccion['id']}/result"
    assert (await app_client.post(url, json={"result": "passed"}, headers=headers)).status_code == 200
    assert (await app_client.post(url, json={"result": "passed"}, headers=headers)).status_code == 409


async def test_the_manual_path_cannot_skip_scheduling_the_inspection(db, seeded_org):
    case, _ = await installed_case(db, seeded_org["org"].id)
    with pytest.raises(InvalidInputError, match="Agenda la inspección"):
        await case_service.transition(
            db, case=case, to_stage="inspection_pending", actor_id=uuid.uuid4(), actor_permissions=stages.SYSTEM_ACTOR
        )


async def test_billing_is_blocked_until_the_acta_is_confirmed(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await installed_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    await _agendar(app_client, headers, project.id)
    case = await refreshed_case(db, case)
    with pytest.raises(InvalidInputError, match="confirme la información"):
        await case_service.transition(
            db, case=case, to_stage="billing_in_progress", actor_id=uuid.uuid4(), actor_permissions=stages.SYSTEM_ACTOR
        )


async def test_a_technician_cannot_record_inspections(app_client, db, seeded_org, active_technician_user):
    _, project = await installed_case(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    headers = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.post(f"/api/v1/projects/{project.id}/inspections",
                                 json={"scheduled_for": _cuando()}, headers=headers)
    assert resp.status_code == 403


async def test_approving_a_case_announces_the_project_after_commit(db, seeded_org):
    anunciados = []
    case_hooks.register()
    domain_events.subscribe("project.created", lambda n, p: anunciados.append(p["case_number"]))
    case, _ = await approved_case_with_project(db, seeded_org["org"].id)
    assert anunciados == [case.case_number]


async def test_the_catalogs_are_exposed_with_labels(app_client, active_technician_user):
    headers = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.get("/api/v1/field-ops/catalogs", headers=headers)
    assert resp.status_code == 200
    cuerpo = resp.json()
    assert len(cuerpo["evidence_categories"]) == 16
    assert cuerpo["permit_statuses"]["not_required"] == "No requerido"


async def test_the_full_retry_loop_after_a_failed_inspection(app_client, db, seeded_org, active_admin_staff_user):
    """Falla → re-trabajo → nuevo cierre → segunda inspección aprobada. Los dos
    intentos quedan en el historial: es la métrica de inspecciones fallidas."""
    case, project = await installed_case(db, seeded_org["org"].id)
    project_id = project.id
    headers = await headers_for(app_client, active_admin_staff_user.email)

    primera = await _agendar(app_client, headers, project_id)
    await app_client.post(f"/api/v1/inspections/{primera['id']}/result",
                          json={"result": "failed", "observations": "Falta sellado de ductos"}, headers=headers)

    resp = await app_client.post(f"/api/v1/projects/{project_id}/installation/close",
                                 json={"observations": "Ductos sellados"}, headers=headers)
    assert resp.status_code == 200, resp.text

    segunda = await _agendar(app_client, headers, project_id)
    await _subir_permiso_firmado(app_client, headers, segunda["id"])
    resp = await app_client.post(f"/api/v1/inspections/{segunda['id']}/result",
                                 json={"result": "passed"}, headers=headers)
    assert resp.status_code == 200, resp.text

    case = await refreshed_case(db, case)
    assert (case.stage_code, case.substatus_code) == ("inspection_pending", "inspection_approved")
    intentos = (await app_client.get(f"/api/v1/projects/{project_id}/inspections", headers=headers)).json()
    assert [i["result"] for i in intentos] == ["failed", "passed"]
