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
    assert r["summary"] == {"total": 2, "with_consent": 0, "without_consent": 2, "opted_out": 0, "no_address": 0}
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
    monkeypatch.setattr(svc, "next_allowed", lambda moment, zone: moment)  # siempre de día
    await app_client.post("/api/v1/campaigns/consents", headers=admin,
                          json={"customer_ids": [str(marge.id)], "source": "Formulario firmado", "confirm": True})
    c = (await app_client.post("/api/v1/campaigns", headers=admin, json={"name": "X", "message": "Oferta"})).json()
    await app_client.post(f"/api/v1/campaigns/{c['id']}/launch", json={}, headers=admin)
    assert await svc.send_due(db) == 1
    r = (await app_client.get(f"/api/v1/campaigns/{c['id']}", headers=admin)).json()
    assert r["status"] == "sent" and r["stats"]["skipped"] == 1


async def test_campaigns_need_notifications_manage(app_client, db, seeded_org, active_salesperson_user):
    vendedor = await headers_for(app_client, "vendedor@acme-demo.com")
    assert (await app_client.get("/api/v1/campaigns", headers=vendedor)).status_code == 403
    assert (await app_client.post("/api/v1/campaigns/audience", json={}, headers=vendedor)).status_code == 403


async def test_office_cannot_undo_a_stop_only_the_customer_can(app_client, db, seeded_org, admin):
    marge, _, _ = await _clientes(db, seeded_org["org"].id)
    body = {"customer_ids": [str(marge.id)], "source": "Formulario firmado", "confirm": True}
    await app_client.post("/api/v1/campaigns/consents", headers=admin, json=body)
    await svc.handle_inbound(db, phone="8185550101", text="STOP")
    r = await app_client.post("/api/v1/campaigns/consents", headers=admin, json=body)
    assert r.json()["granted"] == 0
    await svc.handle_inbound(db, phone="+1 818 555 0101", text="START")
    permiso = (await db.execute(select(MarketingConsent))).scalars().one()
    await db.refresh(permiso)
    assert permiso.status == "granted" and "START" in permiso.source


async def test_test_send_only_goes_to_your_own_phone(app_client, db, seeded_org, admin):
    c = (await app_client.post("/api/v1/campaigns", headers=admin, json={"name": "X", "message": "Oferta"})).json()
    r = await app_client.post(f"/api/v1/campaigns/{c['id']}/test", json={"phone": "8185550199"}, headers=admin)
    assert r.status_code == 400 and r.json()["code"] == "test_phone_not_own"
    await app_client.put("/api/v1/notifications/preferences", headers=admin,
                         json={"email_enabled": False, "sms_enabled": True, "sms_phone": "(818) 555-0199"})
    r = await app_client.post(f"/api/v1/campaigns/{c['id']}/test", json={"phone": "8185550199"}, headers=admin)
    assert r.status_code == 200 and r.json()["result"] == "test"


async def test_start_does_not_reactivate_manual_opt_outs_or_new_numbers(app_client, db, seeded_org, admin):
    marge, ned, _ = await _clientes(db, seeded_org["org"].id)
    await app_client.post("/api/v1/campaigns/consents", headers=admin,
                          json={"customer_ids": [str(marge.id)], "source": "Formulario firmado", "confirm": True})
    await app_client.post("/api/v1/campaigns/opt-outs", headers=admin, json={"phone": "8185550101"})
    await app_client.post("/api/v1/campaigns/opt-outs", headers=admin, json={"phone": "8185550102"})
    for tel, palabra in (("8185550101", "START"), ("8185550102", "START"), ("8185550101", "YES")):
        await svc.handle_inbound(db, phone=tel, text=palabra)
    permisos = (await db.execute(select(MarketingConsent))).scalars().all()
    for p in permisos:
        await db.refresh(p)
    assert {p.status for p in permisos} == {"revoked"}



async def test_own_contacts_can_be_imported_and_receive_campaigns(app_client, db, seeded_org, admin):
    texto = "Homer Simpson, (818) 555-0300, homer@example.com\nsolo-correo@example.com\nlinea sin datos\n7025550400; Lenny"
    r = await app_client.post("/api/v1/campaigns/contacts/import", headers=admin,
                              json={"text": texto, "source": "Lista de la feria de Phoenix", "confirm": True})
    assert r.status_code == 200, r.text
    assert (r.json()["created"], r.json()["invalid"]) == (3, ["linea sin datos"])
    contactos = (await app_client.get("/api/v1/campaigns/contacts", headers=admin)).json()
    assert {c["name"] for c in contactos} == {"Homer Simpson", None, "Lenny"}
    a = (await app_client.post("/api/v1/campaigns/audience", json={}, headers=admin)).json()
    assert a["summary"]["with_consent"] == 2 and a["email_summary"]["with_consent"] == 2
    c = (await app_client.post("/api/v1/campaigns", headers=admin, json={
        "name": "Feria", "channel": "both", "subject": "Oferta para {{nombre}}", "message": "Hola {{nombre}}"})).json()
    r = await app_client.post(f"/api/v1/campaigns/{c['id']}/launch", json={}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["queued"] == 4
    envios = (await db.execute(select(CampaignRecipient).where(CampaignRecipient.channel == "email"))).scalars().all()
    homer = next(e for e in envios if e.address == "homer@example.com")
    assert (homer.subject, homer.body) == ("Oferta para Homer", "Hola Homer")  # el correo no lleva el STOP


async def test_the_email_unsubscribe_link_works_without_login(app_client, db, seeded_org, admin):
    from app.modules.notifications.models import EmailMarketingConsent

    await app_client.post("/api/v1/campaigns/contacts/import", headers=admin,
                          json={"text": "ana@example.com", "source": "Formulario web", "confirm": True})
    token = (await db.execute(select(EmailMarketingConsent))).scalars().one().unsubscribe_token
    assert (await app_client.post("/api/v1/unsubscribe/no-existe-este-token-xx")).status_code == 404
    # Abrir el enlace (lo hacen los escáneres de correo) no da de baja.
    r = await app_client.get(f"/api/v1/unsubscribe/{token}")
    assert r.status_code == 200 and "method=\"post\"" in r.text
    permiso = (await db.execute(select(EmailMarketingConsent))).scalars().one()
    assert permiso.status == "granted"
    r = await app_client.post(f"/api/v1/unsubscribe/{token}")
    assert r.status_code == 200 and "baja" in r.text
    permiso = (await db.execute(select(EmailMarketingConsent))).scalars().one()
    await db.refresh(permiso)
    assert permiso.status == "revoked"
    # Volver a importarlo no lo reactiva.
    await app_client.post("/api/v1/campaigns/contacts/import", headers=admin,
                          json={"text": "ana@example.com", "source": "Formulario web", "confirm": True})
    await db.refresh(permiso)
    assert permiso.status == "revoked"


async def test_an_email_campaign_needs_a_subject(app_client, db, seeded_org, admin):
    await app_client.post("/api/v1/campaigns/contacts/import", headers=admin,
                          json={"text": "ana@example.com", "source": "Formulario web", "confirm": True})
    c = (await app_client.post("/api/v1/campaigns", headers=admin,
                               json={"name": "X", "channel": "email", "message": "Hola"})).json()
    r = await app_client.post(f"/api/v1/campaigns/{c['id']}/launch", json={}, headers=admin)
    assert r.status_code == 400 and r.json()["code"] == "campaign_subject_required"


def test_masiv_payload_and_marketing_email_footer():
    from app.modules.notifications import marketing_email
    from app.modules.notifications.sms import masiv_payload

    p = masiv_payload(to="(818) 555-0101", message="x" * 200)
    assert (p["to"], p["text"], p["isLongmessage"]) == ("18185550101", "x" * 200, True)
    m = marketing_email.build_message(to="ana@example.com", subject="Hola", body="Oferta", unsubscribe_token="tok123")
    assert m["List-Unsubscribe"].endswith("/api/v1/unsubscribe/tok123>")
    assert "Darme de baja" in m.get_body(("html",)).get_content()


# ---------------------------------------------------------------------------
# Paginación (limit/offset, total en X-Total-Count)
# ---------------------------------------------------------------------------

async def test_contacts_are_paginated(app_client, admin):
    texto = "\n".join(f"Contacto {i}, (818) 555-04{i:02d}" for i in range(5))
    await app_client.post("/api/v1/campaigns/contacts/import", headers=admin,
                          json={"text": texto, "source": "Feria", "confirm": True})
    r = await app_client.get("/api/v1/campaigns/contacts?limit=2&offset=0", headers=admin)
    assert r.headers["X-Total-Count"] == "5" and len(r.json()) == 2
    r = await app_client.get("/api/v1/campaigns/contacts?limit=2&offset=4", headers=admin)
    assert len(r.json()) == 1


async def test_sms_and_email_opt_outs_are_paginated_together(app_client, admin):
    """Las bajas de SMS y de correo están en dos tablas; se unen en la base
    para paginarlas juntas."""
    for tel in ("8185550101", "8185550102"):
        await app_client.post("/api/v1/campaigns/opt-outs", headers=admin, json={"phone": tel})
    await app_client.post("/api/v1/campaigns/opt-outs", headers=admin, json={"email": "baja@example.com"})
    r = await app_client.get("/api/v1/campaigns/opt-outs?limit=2", headers=admin)
    assert r.headers["X-Total-Count"] == "3" and len(r.json()) == 2
    todas = (await app_client.get("/api/v1/campaigns/opt-outs", headers=admin)).json()
    assert {(b["channel"], b["address"]) for b in todas} == {
        ("sms", "8185550101"), ("sms", "8185550102"), ("email", "baja@example.com")}
    assert all(b["phone"] == (b["address"] if b["channel"] == "sms" else None) for b in todas)


async def test_campaign_recipients_are_paginated(app_client, db, seeded_org, admin):
    marge, ned, _ = await _clientes(db, seeded_org["org"].id)
    await app_client.post("/api/v1/campaigns/consents", headers=admin,
                          json={"customer_ids": [str(marge.id), str(ned.id)], "source": "Formulario", "confirm": True})
    c = (await app_client.post("/api/v1/campaigns", headers=admin, json={"name": "X", "message": "Oferta"})).json()
    await app_client.post(f"/api/v1/campaigns/{c['id']}/launch", json={}, headers=admin)
    r = await app_client.get(f"/api/v1/campaigns/{c['id']}/recipients?limit=1", headers=admin)
    assert r.headers["X-Total-Count"] == "2" and len(r.json()) == 1
