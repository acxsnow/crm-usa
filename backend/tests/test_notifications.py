"""Módulo 7: del evento al aviso, la cola de envíos y las alertas diarias."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.modules.cases import service as case_service
from app.modules.cases.models import Case
from app.modules.notifications import service
from app.modules.notifications.models import Notification, NotificationDelivery, NotificationPreference
from tests.field_helpers import approved_case_with_project, headers_for

ORG_EVENT = lambda org, **kw: {"organization_id": str(org), **kw}


async def _caso(db, org_id, vendedor_id, stage="pending_approval"):
    case = await case_service.create_case(db, organization_id=org_id, actor_id=vendedor_id, stage_code="new_prospect",
                                          assigned_salesperson_id=vendedor_id, address_street="1200 W Sunrise Dr")
    case.stage_code, case.submitted_at = stage, datetime.now(timezone.utc)
    await db.commit()
    return case


async def _avisos(db, user_id):
    return (await db.execute(select(Notification).where(Notification.user_id == user_id))).scalars().all()


async def test_a_submitted_case_notifies_reviewers_not_the_salesperson(db, seeded_org, active_salesperson_user,
                                                                       active_admin_staff_user):
    org = seeded_org["org"].id
    case = await _caso(db, org, active_salesperson_user.id)
    creados = await service.process_event(db, "case.submitted", ORG_EVENT(org, case_id=str(case.id)))
    assert creados >= 1
    aviso = (await _avisos(db, active_admin_staff_user.id))[0]
    assert case.case_number in aviso.title and aviso.link == f"/cases/{case.id}/review"
    assert await _avisos(db, active_salesperson_user.id) == []
    # Correo pendiente por defecto; SMS no (preferencia apagada).
    envios = (await db.execute(select(NotificationDelivery).where(
        NotificationDelivery.notification_id == aviso.id))).scalars().all()
    assert [(e.channel, e.status) for e in envios] == [("email", "pending")]


async def test_a_returned_case_notifies_its_salesperson_with_the_reason(db, seeded_org, active_salesperson_user):
    org = seeded_org["org"].id
    case = await _caso(db, org, active_salesperson_user.id)
    case.stage_reason = "Falta la foto del panel"
    await db.commit()
    await service.process_event(db, "case.substatus_changed",
                                ORG_EVENT(org, case_id=str(case.id), substatus="returned"))
    aviso = (await _avisos(db, active_salesperson_user.id))[0]
    assert aviso.event == "case.returned" and "Falta la foto del panel" in aviso.body
    # Otros sub-estados no avisan al vendedor.
    assert await service.process_event(db, "case.substatus_changed",
                                       ORG_EVENT(org, case_id=str(case.id), substatus="ready_to_submit")) == 0


async def test_scheduling_notifies_the_technician(db, seeded_org, active_technician_user):
    org = seeded_org["org"].id
    _, project = await approved_case_with_project(db, org, technician_id=active_technician_user.id)
    await service.process_event(db, "installation.scheduled", ORG_EVENT(
        org, project_id=str(project.id), technician_user_id=str(active_technician_user.id), scheduled_date="2026-10-20"))
    aviso = (await _avisos(db, active_technician_user.id))[0]
    assert "2026-10-20" in aviso.title and aviso.link == f"/projects/{project.id}"


async def test_the_organization_edits_a_template(app_client, db, seeded_org, active_admin_user,
                                                 active_salesperson_user):
    org = seeded_org["org"].id
    headers = await headers_for(app_client, "admin@acme-demo.com")
    r = await app_client.put("/api/v1/notifications/templates/case.returned/in_app", headers=headers,
                             json={"subject": "Corrige {{expediente}}", "body": "Motivo: {{motivo}} {{nada}}"})
    assert r.status_code == 200, r.text
    case = await _caso(db, org, active_salesperson_user.id)
    case.stage_reason = "ilegible"
    await db.commit()
    await service.process_event(db, "case.substatus_changed", ORG_EVENT(org, case_id=str(case.id), substatus="returned"))
    aviso = (await _avisos(db, active_salesperson_user.id))[0]
    assert (aviso.title, aviso.body) == (f"Corrige {case.case_number}", "Motivo: ilegible")
    # El aviso en la app no se apaga; volver al texto de fábrica sí se puede.
    r = await app_client.put("/api/v1/notifications/templates/case.returned/in_app", headers=headers,
                             json={"body": "x", "active": False})
    assert r.status_code == 400
    assert (await app_client.delete("/api/v1/notifications/templates/case.returned/in_app",
                                    headers=headers)).status_code == 204


async def test_failed_deliveries_retry_and_then_stop(db, seeded_org, active_salesperson_user, monkeypatch):
    org = seeded_org["org"].id
    case = await _caso(db, org, active_salesperson_user.id)
    await service.process_event(db, "case.stage_changed", ORG_EVENT(org, case_id=str(case.id), to_stage="approved"))

    async def cae(d):
        raise ConnectionError("SMTP caído")

    monkeypatch.setattr(service, "_send", cae)
    envio = (await db.execute(select(NotificationDelivery))).scalars().one()
    for intento in range(1, 6):
        envio.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
        await service.deliver_pending(db)
        await db.refresh(envio)
        assert envio.attempts == intento
    assert envio.status == "failed" and "SMTP caído" in envio.last_error
    async def ok(d):
        return None

    monkeypatch.setattr(service, "_send", ok)  # nunca el proveedor real en pruebas
    envio = await service.resend(db, organization_id=org, delivery_id=envio.id)
    assert envio.status == "sent"


async def test_sms_stays_in_test_mode_without_masiv(db, seeded_org, active_salesperson_user):
    org = seeded_org["org"].id
    db.add(NotificationPreference(organization_id=org, user_id=active_salesperson_user.id, email_enabled=False,
                                  sms_enabled=True, sms_phone="+18185550101"))
    await db.commit()
    case = await _caso(db, org, active_salesperson_user.id)
    await service.process_event(db, "case.stage_changed", ORG_EVENT(org, case_id=str(case.id), to_stage="rejected",
                                                                    reason="No califica"))
    await service.deliver_pending(db)
    envio = (await db.execute(select(NotificationDelivery))).scalars().one()
    assert (envio.channel, envio.status) == ("sms", "skipped") and "prueba" in envio.last_error


async def test_daily_alert_for_a_case_waiting_too_long_is_sent_once(db, seeded_org, active_salesperson_user,
                                                                    active_admin_staff_user):
    org = seeded_org["org"].id
    case = await _caso(db, org, active_salesperson_user.id)
    case.submitted_at = datetime.now(timezone.utc) - timedelta(days=10)
    reciente = await _caso(db, org, active_salesperson_user.id)
    await db.commit()
    assert await service.daily_alerts(db, org) >= 1
    assert await service.daily_alerts(db, org) == 0  # mismo día: no se repite
    avisos = await _avisos(db, active_admin_staff_user.id)
    assert [a.entity_id for a in avisos if a.event == "case.approval_overdue"] == [str(case.id)]
    assert reciente.id


def test_business_days_skip_weekends():
    viernes = date(2026, 10, 2)
    assert service.business_days_between(viernes, date(2026, 10, 5)) == 1  # lunes
    assert service.business_days_between(viernes, date(2026, 10, 9)) == 5


async def test_my_notifications_are_mine(app_client, db, seeded_org, active_salesperson_user, active_admin_staff_user):
    org = seeded_org["org"].id
    case = await _caso(db, org, active_salesperson_user.id)
    await service.process_event(db, "case.submitted", ORG_EVENT(org, case_id=str(case.id)))
    admin = await headers_for(app_client, "admin-staff@acme-demo.com")
    vendedor = await headers_for(app_client, "vendedor@acme-demo.com")
    r = await app_client.get("/api/v1/notifications", headers=admin)
    assert r.status_code == 200, r.text
    assert r.headers["x-total-count"] == "1"
    assert (await app_client.get("/api/v1/notifications/unread-count", headers=admin)).json()["unread"] == 1
    nid = r.json()[0]["id"]
    assert (await app_client.post(f"/api/v1/notifications/{nid}/read", headers=vendedor)).status_code == 404
    assert (await app_client.post(f"/api/v1/notifications/{nid}/read", headers=admin)).json()["read"] is True
    assert (await app_client.get("/api/v1/notifications/unread-count", headers=admin)).json()["unread"] == 0
    # Administrar plantillas e historial es de quien tiene notifications.manage.
    assert (await app_client.get("/api/v1/notifications/deliveries", headers=vendedor)).status_code == 403
    r = await app_client.put("/api/v1/notifications/preferences", headers=vendedor,
                             json={"email_enabled": True, "sms_enabled": True, "sms_phone": ""})
    assert r.status_code == 400



async def test_my_notifications_are_paginated(app_client, db, seeded_org, active_salesperson_user,
                                             active_admin_staff_user):
    """«Mis avisos» por páginas (spec 2026-10-15-paginar-avisos): antes se
    cortaba en 100 y los más viejos desaparecían sin aviso."""
    org = seeded_org["org"].id
    base = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    for i in range(5):  # 5 de Administración: el 0 es el más viejo; 1 y 3 ya leídos
        db.add(Notification(organization_id=org, user_id=active_admin_staff_user.id, event="case.submitted",
                            title=f"Aviso {i}", body="", created_at=base + timedelta(hours=i),
                            read_at=base if i in (1, 3) else None))
    db.add(Notification(organization_id=org, user_id=active_salesperson_user.id, event="case.approved",
                        title="Del vendedor", body="", created_at=base))
    await db.commit()
    admin = await headers_for(app_client, "admin-staff@acme-demo.com")

    p1 = await app_client.get("/api/v1/notifications", params={"limit": 2, "offset": 0}, headers=admin)
    p2 = await app_client.get("/api/v1/notifications", params={"limit": 2, "offset": 2}, headers=admin)
    p3 = await app_client.get("/api/v1/notifications", params={"limit": 2, "offset": 4}, headers=admin)
    assert p1.headers["x-total-count"] == "5"
    titulos = [n["title"] for p in (p1, p2, p3) for n in p.json()]
    assert titulos == ["Aviso 4", "Aviso 3", "Aviso 2", "Aviso 1", "Aviso 0"]  # más nuevo primero, sin repetir

    sin_leer = await app_client.get("/api/v1/notifications", params={"unread": True, "limit": 2, "offset": 2},
                                    headers=admin)
    assert sin_leer.headers["x-total-count"] == "3"
    assert [n["title"] for n in sin_leer.json()] == ["Aviso 0"]

    assert (await app_client.get("/api/v1/notifications", params={"limit": 501}, headers=admin)).status_code == 422
