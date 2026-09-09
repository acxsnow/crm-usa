from app.modules.crm.models import Customer, CustomerStatus, Lead, LeadStatus
from app.modules.field_ops.models import Project, ProjectStatus


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


async def test_projects_status_q_and_technician_filters(app_client, db, active_admin_user, seeded_org):
    org_id = seeded_org["org"].id
    customer = Customer(organization_id=org_id, legal_name="Acme Roofing", status=CustomerStatus.active)
    db.add(customer)
    await db.flush()

    tech_a = active_admin_user.id
    db.add_all([
        Project(organization_id=org_id, customer_id=customer.id, title="HVAC install - Main St", status=ProjectStatus.scheduled, primary_technician_user_id=tech_a),
        Project(organization_id=org_id, customer_id=customer.id, title="Roof repair - Oak Ave", status=ProjectStatus.completed, primary_technician_user_id=None),
    ])
    await db.commit()

    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.get("/api/v1/projects", params={"status": "completed"}, headers=headers)
    assert [p["title"] for p in resp.json()] == ["Roof repair - Oak Ave"]

    resp = await app_client.get("/api/v1/projects", params={"q": "main st"}, headers=headers)
    assert [p["title"] for p in resp.json()] == ["HVAC install - Main St"]

    resp = await app_client.get("/api/v1/projects", params={"technician_id": str(tech_a)}, headers=headers)
    assert [p["title"] for p in resp.json()] == ["HVAC install - Main St"]


from app.modules.crm.models import Application


async def test_applications_status_q_filters_and_pagination_header(app_client, db, active_admin_user, seeded_org):
    org_id = seeded_org["org"].id
    db.add_all([
        Application(organization_id=org_id, program_code="CARE", form_version="1", status="pending_review"),
        Application(organization_id=org_id, program_code="CALFRESH", form_version="1", status="approved"),
    ])
    await db.commit()

    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.get("/api/v1/applications", params={"status": "approved"}, headers=headers)
    assert resp.status_code == 200
    assert [a["program_code"] for a in resp.json()] == ["CALFRESH"]
    assert resp.headers["x-total-count"] == "1"

    resp = await app_client.get("/api/v1/applications", params={"q": "care"}, headers=headers)
    assert [a["program_code"] for a in resp.json()] == ["CARE"]
