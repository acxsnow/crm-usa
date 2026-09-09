from app.modules.crm.models import Customer, CustomerStatus, Lead, LeadStatus


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_leads_q_filter_matches_name_phone_or_email(app_client, db, active_admin_user, seeded_org):
    org_id = seeded_org["org"].id
    db.add_all([
        Lead(organization_id=org_id, full_name="Rosa Gutierrez", phone="7142320526", email="rosa@example.com", status=LeadStatus.new),
        Lead(organization_id=org_id, full_name="Miguel Vargas", phone="7142776702", email="miguel@example.com", status=LeadStatus.new),
    ])
    await db.commit()

    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.get("/api/v1/leads", params={"q": "rosa"}, headers=headers)
    assert resp.status_code == 200
    names = [lead["full_name"] for lead in resp.json()]
    assert names == ["Rosa Gutierrez"]

    resp = await app_client.get("/api/v1/leads", params={"q": "7142776702"}, headers=headers)
    assert [lead["full_name"] for lead in resp.json()] == ["Miguel Vargas"]

    resp = await app_client.get("/api/v1/leads", params={"q": "no-such-lead"}, headers=headers)
    assert resp.json() == []


async def test_customers_q_and_status_filters(app_client, db, active_admin_user, seeded_org):
    org_id = seeded_org["org"].id
    db.add_all([
        Customer(organization_id=org_id, legal_name="Acme Roofing", email="ops@acme.test", status=CustomerStatus.active),
        Customer(organization_id=org_id, legal_name="Old Client Inc", email="old@client.test", status=CustomerStatus.inactive),
    ])
    await db.commit()

    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.get("/api/v1/customers", params={"q": "acme"}, headers=headers)
    assert [c["legal_name"] for c in resp.json()] == ["Acme Roofing"]

    resp = await app_client.get("/api/v1/customers", params={"status": "inactive"}, headers=headers)
    assert [c["legal_name"] for c in resp.json()] == ["Old Client Inc"]
