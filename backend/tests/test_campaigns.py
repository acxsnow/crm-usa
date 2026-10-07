"""Campañas de SMS: permiso de mercadeo, horario del cliente y STOP."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.modules.crm.models import Customer
from app.modules.notifications import campaigns as svc
from app.modules.notifications.models import CampaignRecipient, MarketingConsent
from tests.field_helpers import headers_for


@pytest.fixture
async def admin(app_client, active_admin_user):
    return await headers_for(app_client, "admin@acme-demo.com")


async def _clientes(db, org_id):
    filas = [Customer(organization_id=org_id, legal_name=n, main_phone=t) for n, t in (
        ("Marge Simpson", "(818) 555-0101"), ("Ned Flanders", "+1 818 555 0102"), ("Sin Teléfono", None))]
    db.add_all(filas)
    await db.commit()
    return filas


async def test_audience_lists_people_with_phone_and_their_consent(app_client, db, seeded_org, admin):
    marge, ned, _ = await _clientes(db, seeded_org["org"].id)
    r = (await app_client.post("/api/v1/campaigns/audience", json={}, headers=admin)).json()
    assert r["summary"] == {"total": 2, "with_consent": 0, "without_consent": 2, "opted_out": 0}
    r = await app_client.post("/api/v1/campaigns/consents", headers=admin,
                              json={"customer_ids": [str(marge.id)], "source": "Firmó en la visita", "confirm": False})
    assert r.status_code == 400
    r = await app_client.post("/api/v1/campaigns/consents", headers=admin,
                              json={"customer_ids": [str(marge.id)], "source": "Firmó en la visita", "confirm": True})
    assert r.json()["granted"] == 1
    r = (await app_client.post("/api/v1/campaigns/audience", json={"search": "marge"}, headers=admin)).json()
    assert [c["consent"] for c in r["contacts"]] == ["granted"]


async def test_a_campaign_only_queues_people_with_consent_and_adds_stop(app_client, db, seeded_org, admin):
    marge, ned, _ = await _clientes(db, seeded_org["org"].id)
    p = (await app_client.post("/api/v1/products", json={"name": "Mantenimiento de A/C", "price": "$89"},
                               headers=admin)).json()
    c = (await app_client.post("/api/v1/campaigns", headers=admin, json={
        "name": "Verano", "product_id": p["id"], "message": "Hola {{nombre}}, {{producto}} a {{precio}}."})).json()
    assert c["preview"] == "Hola María, Mantenimiento de A/C a $89. Responde STOP para no recibir más."
    r = await app_client.post(f"/api/v1/campaigns/{c['id']}/launch", json={}, headers=admin)
    assert r.status_code == 400 and r.json()["code"] == "campaign_no_consented_recipients"
    await app_client.post("/api/v1/campaigns/consents", headers=admin,
                          json={"customer_ids": [str(marge.id)], "source": "Formulario firmado", "confirm": True})
    r = await app_client.post(f"/api/v1/campaigns/{c['id']}/launch", json={}, headers=admin)
    assert r.status_code == 200, r.text
    assert (r.json()["summary"]["queued"], r.json()["summary"]["without_consent"]) == (1, 1)
    envios = (await db.execute(select(CampaignRecipient))).scalars().all()
    assert [e.body for e in envios] == ["Hola Marge, Mantenimiento de A/C a $89. Responde STOP para no recibir más."]
    assert (await app_client.put(f"/api/v1/campaigns/{c['id']}", headers=admin, json={
        "name": "x", "message": "y"})).status_code == 409


def test_messages_wait_for_daytime_in_the_customer_zone():
    # 3 a. m. en Phoenix (10:00 UTC) → espera a las 8 a. m. de Phoenix (15:00 UTC).
    madrugada = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc)
    assert svc.next_allowed(madrugada, "America/Phoenix") == datetime(2026, 10, 7, 15, 0, tzinfo=timezone.utc)
    mediodia = datetime(2026, 10, 7, 19, 0, tzinfo=timezone.utc)
    assert svc.next_allowed(mediodia, "America/Los_Angeles") == mediodia
    noche = datetime(2026, 10, 8, 5, 0, tzinfo=timezone.utc)  # 10 p. m. en California
    assert svc.next_allowed(noche, "America/Los_Angeles") == datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc)


async def test_stop_removes_the_number_even_from_queued_campaigns(app_client, db, seeded_org, admin, monkeypatch):
    marge, _, _ = await _clientes(db, seeded_org["org"].id)
    await app_client.post("/api/v1/campaigns/consents", headers=admin,
                          json={"customer_ids": [str(marge.id)], "source": "Formulario firmado", "confirm": True})
    c = (await app_client.post("/api/v1/campaigns", headers=admin, json={"name": "X", "message": "Oferta"})).json()
    await app_client.post(f"/api/v1/campaigns/{c['id']}/launch", json={}, headers=admin)
    monkeypatch.setattr(svc.get_settings(), "MASIV_WEBHOOK_TOKEN", "secreto")
    assert (await app_client.post("/api/v1/webhooks/masiv/inbound?token=malo",
                                  json={"from": "+18185550101", "message": "STOP"})).status_code == 404
    r = await app_client.post("/api/v1/webhooks/masiv/inbound?token=secreto",
                              json={"from": "+18185550101", "message": "Stop por favor"})
    assert r.json()["opted_out"] is True
    envio = (await db.execute(select(CampaignRecipient))).scalars().one()
    await db.refresh(envio)
    assert envio.status == "skipped" and "STOP" in envio.last_error
    permiso = (await db.execute(select(MarketingConsent))).scalars().one()
    assert permiso.status == "revoked"


async def test_sending_in_test_mode_marks_not_sent(app_client, db, seeded_org, admin, monkeypatch):
    marge, _, _ = await _clientes(db, seeded_org["org"].id)
    await app_client.post("/api/v1/campaigns/consents", headers=admin,
                          json={"customer_ids": [str(marge.id)], "source": "Formulario firmado", "confirm": True})
    c = (await app_client.post("/api/v1/campaigns", headers=admin, json={"name": "X", "message": "Oferta"})).json()
    await app_client.post(f"/api/v1/campaigns/{c['id']}/launch", json={}, headers=admin)
    monkeypatch.setattr(svc, "next_allowed", lambda moment, zone: moment)  # siempre de día
    assert await svc.send_due(db) == 1
    r = (await app_client.get(f"/api/v1/campaigns/{c['id']}", headers=admin)).json()
    assert r["status"] == "sent" and r["stats"]["skipped"] == 1


async def test_campaigns_need_notifications_manage(app_client, db, seeded_org, active_salesperson_user):
    vendedor = await headers_for(app_client, "vendedor@acme-demo.com")
    assert (await app_client.get("/api/v1/campaigns", headers=vendedor)).status_code == 403
    assert (await app_client.post("/api/v1/campaigns/audience", json={}, headers=vendedor)).status_code == 403
