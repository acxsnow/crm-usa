"""La orden de instalación: agenda, equipos, materiales y cierre (spec D5.7–D5.9)."""
import uuid
from datetime import date, timedelta

import pytest

from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.field_ops import case_hooks
from app.shared import events as domain_events
from app.shared.errors import InvalidInputError
from tests.field_helpers import (
    add_equipment_directly,
    approved_case_with_project,
    headers_for,
    ready_to_install_case,
    refreshed_case,
    resolve_whole_checklist,
)


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()
    domain_events.clear_subscribers()


@pytest.fixture
def emitted():
    vistos = []
    for nombre in ("installation.scheduled", "installation.closed"):
        domain_events.subscribe(nombre, lambda n, p: vistos.append((n, p)))
    return vistos


EQUIPO = {"equipment_type": "heat_pump_outdoor", "brand": "Carrier", "model": "25HCE4",
          "serial_number": "5219E12345", "quantity": 1, "unit_label": "Casa principal"}


# ---------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------

async def test_scheduling_marks_the_order_released(app_client, db, seeded_org, active_admin_staff_user, active_technician_user, emitted):
    case, project = await ready_to_install_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    manana = date.today() + timedelta(days=1)

    resp = await app_client.patch(
        f"/api/v1/projects/{project.id}/schedule",
        json={"technician_user_id": str(active_technician_user.id), "scheduled_date": str(manana)},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "scheduled"
    assert resp.json()["primary_technician_user_id"] == str(active_technician_user.id)

    case = await refreshed_case(db, case)
    assert (case.stage_code, case.substatus_code) == ("ready_to_install", "install_scheduled")
    assert [n for n, _ in emitted] == ["installation.scheduled"]


async def test_scheduling_someone_who_cannot_install_is_rejected(app_client, db, seeded_org, active_admin_staff_user, active_salesperson_user):
    _, project = await ready_to_install_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.patch(
        f"/api/v1/projects/{project.id}/schedule",
        json={"technician_user_id": str(active_salesperson_user.id), "scheduled_date": str(date.today())},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "instalaciones" in resp.json()["detail"]


async def test_scheduling_a_user_of_another_organization_is_rejected(app_client, db, seeded_org, active_admin_staff_user, second_org_admin_user):
    _, project = await ready_to_install_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.patch(
        f"/api/v1/projects/{project.id}/schedule",
        json={"technician_user_id": str(second_org_admin_user.id), "scheduled_date": str(date.today())},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_scheduling_in_the_past_is_rejected(app_client, db, seeded_org, active_admin_staff_user, active_technician_user):
    _, project = await ready_to_install_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.patch(
        f"/api/v1/projects/{project.id}/schedule",
        json={"technician_user_id": str(active_technician_user.id),
              "scheduled_date": str(date.today() - timedelta(days=1))},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_the_technician_agenda_only_shows_their_own_orders(app_client, db, seeded_org, active_technician_user):
    org_id = seeded_org["org"].id
    _, mio = await approved_case_with_project(db, org_id, technician_id=active_technician_user.id)
    _, ajeno = await approved_case_with_project(db, org_id)
    for p in (mio, ajeno):
        p.scheduled_date = date.today()
    await db.commit()

    headers = await headers_for(app_client, "tech@acme-demo.com")
    hoy = str(date.today())
    resp = await app_client.get(
        f"/api/v1/dispatch/agenda?date_from={hoy}&date_to={hoy}&technician_id={uuid.uuid4()}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert [r["project_id"] for r in resp.json()] == [str(mio.id)]
    assert resp.json()[0]["case_number"].startswith("CASE-")


async def test_an_agenda_range_too_long_is_rejected(app_client, db, seeded_org, active_admin_staff_user):
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.get("/api/v1/dispatch/agenda?date_from=2026-01-01&date_to=2026-12-31", headers=headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Equipos y materiales
# ---------------------------------------------------------------------------

async def test_the_assigned_technician_records_equipment(app_client, db, seeded_org, active_technician_user):
    _, project = await ready_to_install_case(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    headers = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.post(f"/api/v1/projects/{project.id}/equipment", json=EQUIPO, headers=headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["serial_number"] == "5219E12345"


async def test_a_technician_cannot_record_equipment_on_another_order(app_client, db, seeded_org, active_technician_user):
    _, project = await ready_to_install_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.post(f"/api/v1/projects/{project.id}/equipment", json=EQUIPO, headers=headers)
    assert resp.status_code == 404


async def test_an_unknown_equipment_type_is_rejected(app_client, db, seeded_org, active_admin_staff_user):
    _, project = await ready_to_install_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.post(f"/api/v1/projects/{project.id}/equipment",
                                 json={**EQUIPO, "equipment_type": "jacuzzi"}, headers=headers)
    assert resp.status_code == 400


async def test_materials_are_managed_by_administration_only(app_client, db, seeded_org, active_admin_staff_user, active_technician_user):
    _, project = await ready_to_install_case(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    material = {"description": "Línea de refrigerante 3/8 x 3/4", "quantity": 25, "unit": "ft"}

    tecnico = await headers_for(app_client, "tech@acme-demo.com")
    assert (await app_client.post(f"/api/v1/projects/{project.id}/materials", json=material, headers=tecnico)).status_code == 403

    admin = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.post(f"/api/v1/projects/{project.id}/materials", json=material, headers=admin)
    assert resp.status_code == 201, resp.text

    # El técnico sí la ve en su orden.
    resp = await app_client.get(f"/api/v1/projects/{project.id}/materials", headers=tecnico)
    assert [m["description"] for m in resp.json()] == ["Línea de refrigerante 3/8 x 3/4"]


# ---------------------------------------------------------------------------
# Cierre
# ---------------------------------------------------------------------------

async def test_closing_without_equipment_says_what_is_missing(app_client, db, seeded_org, active_technician_user):
    _, project = await ready_to_install_case(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    await resolve_whole_checklist(db, project.id)
    headers = await headers_for(app_client, "tech@acme-demo.com")

    gaps = (await app_client.get(f"/api/v1/projects/{project.id}/installation/gaps", headers=headers)).json()
    assert gaps["can_close"] is False

    resp = await app_client.post(f"/api/v1/projects/{project.id}/installation/close", json={}, headers=headers)
    assert resp.status_code == 400
    assert "equipo instalado" in resp.json()["detail"]


async def test_closing_with_the_checklist_incomplete_lists_the_items(app_client, db, seeded_org, active_technician_user):
    _, project = await ready_to_install_case(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    await add_equipment_directly(db, project)
    headers = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.post(f"/api/v1/projects/{project.id}/installation/close", json={}, headers=headers)
    assert resp.status_code == 400
    assert "Prueba de funcionamiento" in resp.json()["detail"]


async def test_closing_moves_the_case_to_installed_and_freezes_the_order(app_client, db, seeded_org, active_technician_user, emitted):
    case, project = await ready_to_install_case(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    await resolve_whole_checklist(db, project.id)
    await add_equipment_directly(db, project)
    project_id = project.id
    headers = await headers_for(app_client, "tech@acme-demo.com")

    resp = await app_client.post(f"/api/v1/projects/{project_id}/installation/close",
                                 json={"observations": "Cliente conforme"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"
    assert resp.json()["completed_date"] == str(date.today())
    assert (await refreshed_case(db, case)).stage_code == "installed"
    assert ("installation.closed" in [n for n, _ in emitted])

    # Congelado: lo instalado es lo que se inspecciona y se cobra.
    resp = await app_client.post(f"/api/v1/projects/{project_id}/equipment", json=EQUIPO, headers=headers)
    assert resp.status_code == 409


async def test_closing_before_the_order_is_released_is_rejected(app_client, db, seeded_org, active_technician_user):
    _, project = await approved_case_with_project(db, seeded_org["org"].id, technician_id=active_technician_user.id)
    await resolve_whole_checklist(db, project.id)
    await add_equipment_directly(db, project)
    headers = await headers_for(app_client, "tech@acme-demo.com")
    resp = await app_client.post(f"/api/v1/projects/{project.id}/installation/close", json={}, headers=headers)
    assert resp.status_code == 409
    assert "Listo para instalar" in resp.json()["detail"]


async def test_the_manual_path_cannot_mark_installed_with_gaps(db, seeded_org):
    case, _ = await ready_to_install_case(db, seeded_org["org"].id)
    with pytest.raises(InvalidInputError, match="Falta"):
        await case_service.transition(
            db, case=case, to_stage="installed", actor_id=uuid.uuid4(), actor_permissions=stages.SYSTEM_ACTOR
        )


async def test_the_manual_path_also_completes_the_project(db, seeded_org):
    case, project = await ready_to_install_case(db, seeded_org["org"].id)
    await resolve_whole_checklist(db, project.id)
    await add_equipment_directly(db, project)
    project_id = project.id
    await case_service.transition(
        db, case=case, to_stage="installed", actor_id=uuid.uuid4(), actor_permissions=stages.SYSTEM_ACTOR
    )
    from sqlalchemy import select

    from app.modules.field_ops.models import Project

    db.expire_all()
    proyecto = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one()
    assert proyecto.status.value == "completed"
