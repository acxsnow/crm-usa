from app.modules.crm.models import Customer, CustomerStatus
from app.modules.field_ops.models import Project, ProjectStatus


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


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


async def test_customers_invalid_status_returns_422(app_client, active_admin_user, seeded_org):
    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await app_client.get("/api/v1/customers", params={"status": "bogus"}, headers=headers)
    assert resp.status_code == 422


async def test_projects_invalid_status_returns_422(app_client, active_admin_user, seeded_org):
    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await app_client.get("/api/v1/projects", params={"status": "bogus"}, headers=headers)
    assert resp.status_code == 422


async def test_users_q_status_and_role_filters(app_client, active_admin_user, active_technician_user, seeded_org):
    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.get("/api/v1/users", params={"q": "technician"}, headers=headers)
    assert resp.status_code == 200
    assert [u["full_name"] for u in resp.json()["items"]] == ["Tom Technician"]

    resp = await app_client.get("/api/v1/users", params={"role": "field_technician"}, headers=headers)
    assert [u["full_name"] for u in resp.json()["items"]] == ["Tom Technician"]

    resp = await app_client.get("/api/v1/users", params={"status": "active", "q": "ada"}, headers=headers)
    assert [u["full_name"] for u in resp.json()["items"]] == ["Ada Admin"]

    resp = await app_client.get("/api/v1/users", params={"status": "bogus"}, headers=headers)
    assert resp.status_code == 422


async def test_audit_events_action_and_actor_filters_and_pagination_header(app_client, db, active_admin_user, seeded_org):
    from app.shared.audit_models import AuditEvent

    org_id = seeded_org["org"].id
    db.add_all([
        AuditEvent(organization_id=org_id, actor_user_id=active_admin_user.id, action="user.invited", entity_type="User"),
        AuditEvent(organization_id=org_id, actor_user_id=None, action="password_reset.requested", entity_type="User"),
    ])
    await db.commit()

    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.get("/api/v1/audit-events", params={"action": "invited"}, headers=headers)
    assert resp.status_code == 200
    assert [e["action"] for e in resp.json()] == ["user.invited"]
    assert resp.headers["x-total-count"] == "1"

    # Logging in itself records an "auth.login.success" audit event for this
    # actor, so combine with the action filter to isolate the seeded row.
    resp = await app_client.get(
        "/api/v1/audit-events",
        params={"actor_user_id": str(active_admin_user.id), "action": "invited"},
        headers=headers,
    )
    assert [e["action"] for e in resp.json()] == ["user.invited"]
