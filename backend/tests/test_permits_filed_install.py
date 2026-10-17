"""Instalar con el permiso solo radicado (spec 2026-10-16).

`PERMIT_FILED_ALLOWS_INSTALL` en `false` (por defecto): como siempre, para pasar a
«Listo para instalar» cada permiso tiene que estar aprobado y vigente o «No
requerido». En `true` también deja pasar un permiso radicado. En los dos casos
bloquean el rechazado y el aprobado vencido, y el cobro sigue pidiendo el
permiso aprobado.
"""
import uuid
from datetime import date, timedelta

import pytest

from app.core.config import get_settings
from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.field_ops import case_hooks
from tests.field_helpers import approved_case_with_project, headers_for, refreshed_case

HOY = date.today()


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()


@pytest.fixture
def radicado_basta(monkeypatch):
    monkeypatch.setattr(get_settings(), "PERMIT_FILED_ALLOWS_INSTALL", True)


async def _radicar(app_client, headers, project_id, **extra):
    r = await app_client.post(f"/api/v1/projects/{project_id}/permits",
                              json={"jurisdiction": "Miami-Dade", "filed_on": str(HOY), **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_by_default_a_filed_permit_does_not_allow_installing(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    permiso = await _radicar(app_client, headers, project.id)
    assert permiso["allows_install"] is False
    assert (await refreshed_case(db, case)).stage_code == "permit_in_progress"


async def test_with_the_switch_a_filed_permit_moves_to_ready_to_install(app_client, db, seeded_org,
                                                                       active_admin_staff_user, radicado_basta):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    permiso = await _radicar(app_client, headers, project.id)
    assert (permiso["allows_install"], permiso["is_cleared"]) == (True, False)  # instala, pero no está aprobado
    assert (await refreshed_case(db, case)).stage_code == "ready_to_install"
    # El cobro usa `is_cleared` / `all_cleared` (estricto): sigue en falso hasta que se apruebe.


@pytest.mark.parametrize("estado", ["rejected", "expired"])
async def test_with_the_switch_rejected_or_expired_still_block(app_client, db, seeded_org, active_admin_staff_user,
                                                              radicado_basta, estado):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    if estado == "rejected":
        permiso = await _radicar(app_client, headers, project.id, status="rejected", notes="Falta el plano")
    else:
        permiso = await _radicar(app_client, headers, project.id, status="approved",
                                 approved_on=str(HOY - timedelta(days=200)), expires_on=str(HOY - timedelta(days=1)))
    assert permiso["allows_install"] is False
    assert (await refreshed_case(db, case)).stage_code == "permit_in_progress"


async def test_by_default_the_manual_path_needs_the_approval(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    await _radicar(app_client, headers, project.id)
    case = await refreshed_case(db, case)
    from app.shared.errors import InvalidInputError

    with pytest.raises(InvalidInputError, match="aprobados y vigentes"):
        await case_service.transition(db, case=case, to_stage="ready_to_install", actor_id=uuid.uuid4(),
                                      actor_permissions=stages.SYSTEM_ACTOR)


async def test_with_the_switch_the_manual_path_lets_a_filed_permit_through(app_client, db, seeded_org,
                                                                          active_admin_staff_user, monkeypatch):
    """La guarda de la ruta manual usa la misma regla que el avance automático."""
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    await _radicar(app_client, headers, project.id)  # interruptor apagado: se queda en «Permiso en trámite»
    case = await refreshed_case(db, case)
    assert case.stage_code == "permit_in_progress"
    monkeypatch.setattr(get_settings(), "PERMIT_FILED_ALLOWS_INSTALL", True)
    case = await case_service.transition(db, case=case, to_stage="ready_to_install", actor_id=uuid.uuid4(),
                                         actor_permissions=stages.SYSTEM_ACTOR)
    assert case.stage_code == "ready_to_install"
