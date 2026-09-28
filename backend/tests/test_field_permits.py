"""Permiso municipal y el avance del expediente (spec D5.1 y D5.5).

La etapa es consecuencia del hecho: registrar el permiso pasa el expediente a
«Permiso en trámite» y despejarlos todos, a «Listo para instalar». Por el
camino manual, las guardas impiden saltarse el hecho.
"""
import uuid
from datetime import date, timedelta

import pytest

from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.field_ops import case_hooks
from tests.field_helpers import approved_case_with_project, headers_for, refreshed_case


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()


HOY = date.today()


def _aprobado(**extra):
    datos = {"jurisdiction": "Phoenix", "status": "approved", "approved_on": str(HOY),
             "expires_on": str(HOY + timedelta(days=180))}
    datos.update(extra)
    return datos


async def test_recording_the_first_permit_moves_the_case_to_permit_in_progress(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)

    resp = await app_client.post(
        f"/api/v1/projects/{project.id}/permits",
        json={"jurisdiction": "Phoenix", "permit_number": "MEC-2026-114", "filed_on": str(HOY)},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["is_cleared"] is False
    assert (await refreshed_case(db, case)).stage_code == "permit_in_progress"


async def test_approving_the_permit_moves_the_case_to_ready_to_install(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    permiso = (await app_client.post(
        f"/api/v1/projects/{project.id}/permits", json={"jurisdiction": "Phoenix"}, headers=headers
    )).json()

    resp = await app_client.patch(
        f"/api/v1/permits/{permiso['id']}",
        json={"status": "approved", "approved_on": str(HOY), "expires_on": str(HOY + timedelta(days=90))},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_cleared"] is True
    assert (await refreshed_case(db, case)).stage_code == "ready_to_install"


async def test_a_permit_recorded_already_approved_moves_both_steps(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.post(f"/api/v1/projects/{project.id}/permits", json=_aprobado(), headers=headers)
    assert resp.status_code == 201, resp.text

    eventos = await case_service.list_stage_events(db, organization_id=case.organization_id, case_id=case.id)
    # Las dos etapas quedan en el historial: el reporte de tiempos las necesita.
    assert [e.to_stage_code for e in eventos][-2:] == ["permit_in_progress", "ready_to_install"]


async def test_with_two_permits_one_pending_does_not_move(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    await app_client.post(f"/api/v1/projects/{project.id}/permits",
                          json={"jurisdiction": "Phoenix", "permit_type": "Eléctrico"}, headers=headers)
    await app_client.post(f"/api/v1/projects/{project.id}/permits",
                          json=_aprobado(permit_type="Mecánico"), headers=headers)
    assert (await refreshed_case(db, case)).stage_code == "permit_in_progress"


async def test_an_expired_permit_does_not_clear(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.post(
        f"/api/v1/projects/{project.id}/permits",
        json=_aprobado(approved_on=str(HOY - timedelta(days=400)), expires_on=str(HOY - timedelta(days=35))),
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["is_expired"] is True
    assert (await refreshed_case(db, case)).stage_code == "permit_in_progress"


async def test_not_required_needs_a_reason_and_then_clears(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.post(f"/api/v1/projects/{project.id}/permits",
                                 json={"jurisdiction": "Maricopa", "status": "not_required"}, headers=headers)
    assert resp.status_code == 400
    assert "motivo" in resp.json()["detail"]

    resp = await app_client.post(
        f"/api/v1/projects/{project.id}/permits",
        json={"jurisdiction": "Maricopa", "status": "not_required",
              "not_required_reason": "Reemplazo de equipo equivalente, exento en el condado"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert (await refreshed_case(db, case)).stage_code == "ready_to_install"


async def test_an_approved_permit_without_date_is_rejected(app_client, db, seeded_org, active_admin_staff_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.post(f"/api/v1/projects/{project.id}/permits",
                                 json={"jurisdiction": "Phoenix", "status": "approved"}, headers=headers)
    assert resp.status_code == 400


async def test_without_the_next_stage_permission_the_fact_is_saved_but_the_case_waits(app_client, db, seeded_org):
    """Separación de funciones: quien registra permisos pero no puede liberar
    órdenes (`dispatch.manage`) deja el dato y el expediente espera."""
    from sqlalchemy import select

    from app.modules.users.models import Permission, Role
    from tests.conftest import _make_role_user

    org = seeded_org["org"]
    permisos = (
        await db.execute(select(Permission).where(Permission.code.in_(["permits.manage", "projects.read_all"])))
    ).scalars().all()
    rol = Role(organization_id=org.id, code="permit_clerk", name="Tramitador de permisos", permissions=list(permisos))
    db.add(rol)
    await db.commit()
    seeded_org["roles"]["permit_clerk"] = rol
    await _make_role_user(db, seeded_org, role_code="permit_clerk", email="permisos@acme-demo.com", full_name="Pat Permits")

    case, project = await approved_case_with_project(db, org.id)
    headers = await headers_for(app_client, "permisos@acme-demo.com")
    resp = await app_client.post(f"/api/v1/projects/{project.id}/permits", json=_aprobado(), headers=headers)
    assert resp.status_code == 201, resp.text
    # permits.manage sí le alcanza para «Permiso en trámite»; «Listo para
    # instalar» exige dispatch.manage.
    assert (await refreshed_case(db, case)).stage_code == "permit_in_progress"


async def test_the_manual_path_cannot_skip_the_permit(db, seeded_org):
    case, _ = await approved_case_with_project(db, seeded_org["org"].id)
    from app.shared.errors import InvalidInputError

    with pytest.raises(InvalidInputError, match="Registra el permiso"):
        await case_service.transition(
            db, case=case, to_stage="permit_in_progress", actor_id=uuid.uuid4(),
            actor_permissions=stages.SYSTEM_ACTOR,
        )


async def test_a_technician_cannot_record_permits(app_client, db, seeded_org, active_technician_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    headers = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.post(f"/api/v1/projects/{project.id}/permits", json={"jurisdiction": "Phoenix"}, headers=headers)
    assert resp.status_code == 403


async def test_a_legacy_project_without_case_records_permits_normally(app_client, db, seeded_org, active_admin_user):
    from tests.test_field_ops import _create_customer_and_project

    headers = await headers_for(app_client, "admin@acme-demo.com")
    _, project_id, _ = await _create_customer_and_project(app_client, headers)
    resp = await app_client.post(f"/api/v1/projects/{project_id}/permits", json=_aprobado(), headers=headers)
    assert resp.status_code == 201, resp.text


async def test_permits_of_another_organization_are_invisible(app_client, db, seeded_org, second_org_admin_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, second_org_admin_user.email)
    resp = await app_client.get(f"/api/v1/projects/{project.id}/permits", headers=headers)
    assert resp.status_code == 404
