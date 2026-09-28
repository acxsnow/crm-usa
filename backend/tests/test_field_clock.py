""""Hoy" es el de la organización, no el del servidor.

El servidor corre en UTC. A las 7 p. m. en Bogotá (5 p. m. en Phoenix) en UTC ya
es el día siguiente: agendar la instalación de "hoy" se rechazaba como fecha
pasada, y cerrar una instalación le ponía la fecha de mañana. Lo encontró el
recorrido de punta a punta contra la app real el 27 de septiembre de 2026.
"""
from datetime import date, datetime, timezone

import pytest

from app.modules.cases import stages
from app.modules.field_ops import case_hooks, clock
from tests.field_helpers import headers_for, ready_to_install_case

# 27 de septiembre, 11 p. m. en Bogotá = 28 de septiembre, 4 a. m. UTC.
NOCHE_EN_BOGOTA = datetime(2026, 9, 28, 4, 0, tzinfo=timezone.utc)
HOY_EN_BOGOTA = date(2026, 9, 27)


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()


@pytest.fixture
def noche_en_bogota(monkeypatch, db, seeded_org):
    monkeypatch.setattr(clock, "_utcnow", lambda: NOCHE_EN_BOGOTA)
    seeded_org["org"].timezone = "America/Bogota"


async def test_today_is_the_organization_local_date(db, seeded_org, noche_en_bogota):
    await db.commit()
    assert await clock.org_today(db, seeded_org["org"].id) == HOY_EN_BOGOTA


async def test_an_unknown_timezone_falls_back_to_utc(db, seeded_org, monkeypatch):
    monkeypatch.setattr(clock, "_utcnow", lambda: NOCHE_EN_BOGOTA)
    seeded_org["org"].timezone = "Marte/Olympus"
    await db.commit()
    assert await clock.org_today(db, seeded_org["org"].id) == date(2026, 9, 28)


async def test_scheduling_today_in_the_evening_is_not_the_past(
    app_client, db, seeded_org, active_admin_staff_user, active_technician_user, noche_en_bogota
):
    _, project = await ready_to_install_case(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.patch(
        f"/api/v1/projects/{project.id}/schedule",
        json={"technician_user_id": str(active_technician_user.id), "scheduled_date": str(HOY_EN_BOGOTA)},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
