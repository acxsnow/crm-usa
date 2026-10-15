"""Contador de días en «Pendiente de aprobación» (spec 2026-10-14).

Misma regla que la alerta diaria del módulo 7: días hábiles (lunes a viernes)
desde `submitted_at` en la zona de la organización, contra el umbral de
Notificaciones → Alertas. «Hoy» queda fijo en el miércoles 14 de octubre de
2026 reemplazando el reloj (`field_ops.clock._utcnow`)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.modules.cases import approval_clock
from app.modules.cases import service as case_service
from app.modules.field_ops import clock
from app.modules.notifications.models import NotificationSettings

HOY = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)  # miércoles


def _dia(d: int) -> datetime:
    """Mediodía UTC del día `d` de octubre de 2026 (mismo día en Phoenix y en UTC)."""
    return datetime(2026, 10, d, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _hoy_fijo(monkeypatch):
    monkeypatch.setattr(clock, "_utcnow", lambda: HOY)


async def _caso(db, org_id, vendedor_id, *, stage="pending_approval", enviado=None):
    case = await case_service.create_case(db, organization_id=org_id, actor_id=vendedor_id, stage_code="new_prospect",
                                          assigned_salesperson_id=vendedor_id, address_street="1200 W Sunrise Dr")
    case.stage_code, case.submitted_at = stage, enviado
    await db.commit()
    return case


async def _umbral(db, org_id, dias):
    db.add(NotificationSettings(organization_id=org_id, approval_alert_business_days=dias,
                                permit_expiry_alert_days=7, customer_sms_enabled=False))
    await db.commit()


# --- Tarea 1: el cálculo ---------------------------------------------------

async def test_business_days_and_overdue_against_the_limit(db, seeded_org, active_salesperson_user):
    org, vendedor = seeded_org["org"].id, active_salesperson_user.id
    await _umbral(db, org, 3)
    hoy = await _caso(db, org, vendedor, enviado=_dia(14))
    dos = await _caso(db, org, vendedor, enviado=_dia(12))      # lunes → mar 13, mié 14
    cuatro = await _caso(db, org, vendedor, enviado=_dia(8))    # jueves → vie 9, lun 12, mar 13, mié 14
    ctx = await approval_clock.wait_context(db, org)
    assert approval_clock.approval_wait(hoy, ctx) == {"business_days": 0, "overdue": False, "limit": 3}
    assert approval_clock.approval_wait(dos, ctx) == {"business_days": 2, "overdue": False, "limit": 3}
    assert approval_clock.approval_wait(cuatro, ctx) == {"business_days": 4, "overdue": True, "limit": 3}


async def test_a_weekend_in_between_does_not_count(db, seeded_org, active_salesperson_user):
    org = seeded_org["org"].id
    viernes = await _caso(db, org, active_salesperson_user.id, enviado=_dia(9))
    ctx = await approval_clock.wait_context(db, org)
    assert approval_clock.approval_wait(viernes, ctx)["business_days"] == 3  # lun 12, mar 13, mié 14


async def test_only_cases_waiting_for_approval_have_a_counter(db, seeded_org, active_salesperson_user):
    org, vendedor = seeded_org["org"].id, active_salesperson_user.id
    ctx = await approval_clock.wait_context(db, org)
    for stage in ("on_hold", "approved", "new_prospect"):
        assert approval_clock.approval_wait(await _caso(db, org, vendedor, stage=stage, enviado=_dia(8)), ctx) is None
    assert approval_clock.approval_wait(await _caso(db, org, vendedor, enviado=None), ctx) is None


async def test_without_settings_the_limit_is_3_and_nothing_is_written(db, seeded_org, active_salesperson_user):
    org = seeded_org["org"].id
    caso = await _caso(db, org, active_salesperson_user.id, enviado=_dia(8))
    ctx = await approval_clock.wait_context(db, org)
    assert approval_clock.approval_wait(caso, ctx) == {"business_days": 4, "overdue": True, "limit": 3}
    await db.commit()
    filas = (await db.execute(select(NotificationSettings).where(NotificationSettings.organization_id == org))).all()
    assert filas == []


# --- Tarea 2: el dato en el tablero, la cola y el formulario -----------------

PUERTA = {"address_street": "1200 W Sunrise Dr", "address_unit": "Spc 14", "address_city": "San Fernando",
          "address_state": "CA", "address_zip": "91340", "latitude": 34.28, "longitude": -118.44}


async def _enviado_hace_cuatro_dias(app_client, db, seeded_org):
    """Expediente real (TECH, abierto por el vendedor) enviado el jueves 8, con
    un documento por revisar para que salga en la cola."""
    from app.modules.cases.models import EXTRA_DOCUMENT_KEY, Case, CaseFile
    from app.modules.programs import service as programs
    from tests.field_helpers import headers_for

    org = seeded_org["org"].id
    await programs.install_defaults(db, organization_id=org)
    tech = next(p for p in await programs.list_programs(db, organization_id=org) if p.code == "TECH_CLEAN_CA")
    vendedor = await headers_for(app_client, "vendedor@acme-demo.com")
    r = await app_client.post("/api/v1/visits", json={**PUERTA, "result": "opened", "program_id": str(tech.id)},
                              headers=vendedor)
    assert r.status_code == 201, r.text
    caso = await db.get(Case, r.json()["case"]["id"])
    caso.stage_code, caso.substatus_code, caso.submitted_at = "pending_approval", "pending_review", _dia(8)
    db.add(CaseFile(organization_id=org, case_id=caso.id, field_key=EXTRA_DOCUMENT_KEY, label="Factura de luz",
                    file_path="x/factura.pdf", original_filename="factura.pdf", mime_type="application/pdf"))
    await db.commit()
    return caso, vendedor


ESPERADO = {"business_days": 4, "overdue": True, "limit": 3}


async def test_board_queue_and_form_bring_the_counter(app_client, db, seeded_org, active_salesperson_user,
                                                      active_admin_staff_user):
    from tests.field_helpers import headers_for

    caso, _ = await _enviado_hace_cuatro_dias(app_client, db, seeded_org)
    admin = await headers_for(app_client, "admin-staff@acme-demo.com")

    tablero = (await app_client.get("/api/v1/case-board", headers=admin)).json()
    tarjetas = {t["id"]: t for col in tablero for t in col["cases"]}
    assert tarjetas[str(caso.id)]["approval_wait"] == ESPERADO

    cola = (await app_client.get("/api/v1/documents/review-queue", headers=admin)).json()
    assert {f["case_id"]: f for f in cola}[str(caso.id)]["approval_wait"] == ESPERADO

    form = (await app_client.get(f"/api/v1/cases/{caso.id}/form", headers=admin)).json()
    assert form["approval_wait"] == ESPERADO


async def test_other_stages_bring_null_on_the_board(app_client, db, seeded_org, active_salesperson_user,
                                                    active_admin_staff_user):
    from tests.field_helpers import headers_for

    caso, _ = await _enviado_hace_cuatro_dias(app_client, db, seeded_org)
    caso.stage_code, caso.substatus_code = "approved", None
    await db.commit()
    admin = await headers_for(app_client, "admin-staff@acme-demo.com")
    tablero = (await app_client.get("/api/v1/case-board", headers=admin)).json()
    assert {t["id"]: t for col in tablero for t in col["cases"]}[str(caso.id)]["approval_wait"] is None


async def test_the_salesperson_sees_the_counter_of_their_case(app_client, db, seeded_org, active_salesperson_user):
    caso, vendedor = await _enviado_hace_cuatro_dias(app_client, db, seeded_org)
    tablero = (await app_client.get("/api/v1/case-board", headers=vendedor)).json()
    assert {t["id"]: t for col in tablero for t in col["cases"]}[str(caso.id)]["approval_wait"] == ESPERADO
    form = (await app_client.get(f"/api/v1/cases/{caso.id}/form", headers=vendedor)).json()
    assert form["approval_wait"] == ESPERADO


async def test_returning_to_the_salesperson_does_not_reset_the_days(app_client, db, seeded_org,
                                                                    active_salesperson_user, active_admin_staff_user):
    from tests.field_helpers import headers_for

    caso, _ = await _enviado_hace_cuatro_dias(app_client, db, seeded_org)
    admin = await headers_for(app_client, "admin-staff@acme-demo.com")
    r = await app_client.post(f"/api/v1/cases/{caso.id}/substatus",
                              json={"substatus": "returned", "reason": "Falta la factura de luz"}, headers=admin)
    assert r.status_code == 200, r.text
    form = (await app_client.get(f"/api/v1/cases/{caso.id}/form", headers=admin)).json()
    assert form["approval_wait"] == ESPERADO


# --- Tarea 3: «Revisar ahora» ---------------------------------------------

async def _avisos_de_demora(db, case_id):
    from app.modules.notifications.models import Notification

    return (await db.execute(select(Notification).where(Notification.event == "case.approval_overdue",
                                                        Notification.entity_id == str(case_id)))).scalars().all()


async def test_run_now_creates_the_overdue_alert_once(app_client, db, seeded_org, second_org,
                                                      active_salesperson_user, active_admin_staff_user):
    from tests.field_helpers import headers_for

    org = seeded_org["org"].id
    demorado = await _caso(db, org, active_salesperson_user.id, enviado=_dia(8))
    ajeno = await _caso(db, second_org["org"].id, active_salesperson_user.id, enviado=_dia(8))
    admin = await headers_for(app_client, "admin-staff@acme-demo.com")

    r = await app_client.post("/api/v1/notifications/alerts/run", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["created"] >= 1
    assert len(await _avisos_de_demora(db, demorado.id)) == 1
    assert await _avisos_de_demora(db, ajeno.id) == []  # solo la organización del token

    otra = await app_client.post("/api/v1/notifications/alerts/run", headers=admin)
    assert otra.json() == {"created": 0}  # mismo día: no repite
    assert len(await _avisos_de_demora(db, demorado.id)) == 1


async def test_run_now_needs_notifications_manage(app_client, db, seeded_org, active_salesperson_user):
    from tests.field_helpers import headers_for

    vendedor = await headers_for(app_client, "vendedor@acme-demo.com")
    r = await app_client.post("/api/v1/notifications/alerts/run", headers=vendedor)
    assert r.status_code == 403
