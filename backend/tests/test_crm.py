async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _auth_headers(app_client, active_admin_user):
    token = await _login(app_client, "admin@acme-demo.com")
    return {"Authorization": f"Bearer {token}"}


async def test_create_lead_and_list(app_client, active_admin_user):
    headers = await _auth_headers(app_client, active_admin_user)
    resp = await app_client.post(
        "/api/v1/leads",
        json={
            "full_name": "Rosa Gutierrez",
            "phone": "(714) 232-0526",
            "email": "rosa@example.com",
            "benefit_type": "CARE",
            "funder_program": "HEEHRA",
            "address_street": "106 S Colombo Ln",
            "address_unit": "Spc 66",
            "address_city": "Tustin",
            "address_state": "CA",
            "address_zip": "92780",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["lead"]["status"] == "new"
    assert body["possible_duplicates"] == []

    resp = await app_client.get("/api/v1/leads", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_duplicate_lead_detection_by_phone(app_client, active_admin_user):
    headers = await _auth_headers(app_client, active_admin_user)
    await app_client.post(
        "/api/v1/leads", json={"full_name": "Rosa Gutierrez", "phone": "7142320526"}, headers=headers,
    )
    resp = await app_client.post(
        "/api/v1/leads", json={"full_name": "Rosa G.", "phone": "(714) 232-0526"}, headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["possible_duplicates"]) == 1
    assert "phone" in body["possible_duplicates"][0]["matched_on"]


async def test_lead_conversion_creates_customer_contact_opportunity(app_client, active_admin_user, seeded_org):
    headers = await _auth_headers(app_client, active_admin_user)
    create_resp = await app_client.post(
        "/api/v1/leads",
        json={"full_name": "Miguel Vargas", "phone": "7142776702", "benefit_type": "CALFRESH", "address_street": "1500 Warren St", "address_unit": "Spc 101"},
        headers=headers,
    )
    lead_id = create_resp.json()["lead"]["id"]

    resp = await app_client.post(f"/api/v1/leads/{lead_id}/convert", json={}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_id"] and body["contact_id"] and body["opportunity_id"]

    # Lead should now be marked converted and rejects a second conversion.
    lead_resp = await app_client.get(f"/api/v1/leads/{lead_id}", headers=headers)
    assert lead_resp.json()["status"] == "converted"

    second_convert = await app_client.post(f"/api/v1/leads/{lead_id}/convert", json={}, headers=headers)
    assert second_convert.status_code == 409

    # Opportunity should carry over the lead's address and benefit info.
    opp_resp = await app_client.get("/api/v1/opportunities", headers=headers)
    opp = opp_resp.json()[0]
    assert opp["address_street"] == "1500 Warren St"
    assert opp["benefit_type"] == "CALFRESH"
    assert opp["stage"]["code"] == "new"


async def test_opportunity_stage_change_requires_loss_reason(app_client, active_admin_user, seeded_org):
    headers = await _auth_headers(app_client, active_admin_user)
    customer_resp = await app_client.post(
        "/api/v1/customers", json={"legal_name": "Test Customer"}, headers=headers,
    )
    customer_id = customer_resp.json()["id"]

    opp_resp = await app_client.post(
        "/api/v1/opportunities",
        json={"customer_id": customer_id, "title": "Free AC enrollment", "stage_code": "new"},
        headers=headers,
    )
    opportunity_id = opp_resp.json()["id"]

    resp = await app_client.post(
        f"/api/v1/opportunities/{opportunity_id}/change-stage", json={"stage_code": "rejected"}, headers=headers,
    )
    assert resp.status_code == 400

    resp = await app_client.post(
        f"/api/v1/opportunities/{opportunity_id}/change-stage",
        json={"stage_code": "rejected", "loss_reason": "No califica para el programa"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["stage"]["code"] == "rejected"


async def test_quote_line_items_compute_total(app_client, active_admin_user, seeded_org):
    headers = await _auth_headers(app_client, active_admin_user)
    customer_resp = await app_client.post(
        "/api/v1/customers", json={"legal_name": "Paying Customer"}, headers=headers,
    )
    customer_id = customer_resp.json()["id"]

    resp = await app_client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer_id,
            "line_items": [
                {"description": "Unidad AC 2 toneladas", "quantity": 2, "unit_price": 1200, "discount": 100, "tax_value": 50},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["quote_number"] == "COT-0001"
    # 2 * 1200 - 100 + 50 = 2350
    assert body["total_amount"] == 2350.0
    assert body["line_items"][0]["line_total"] == 2350.0


async def test_customer_timeline_aggregates_related_records(app_client, active_admin_user, seeded_org):
    headers = await _auth_headers(app_client, active_admin_user)
    customer_resp = await app_client.post(
        "/api/v1/customers", json={"legal_name": "360 View Customer"}, headers=headers,
    )
    customer_id = customer_resp.json()["id"]

    await app_client.post(
        "/api/v1/opportunities",
        json={"customer_id": customer_id, "title": "Enrollment", "stage_code": "new"},
        headers=headers,
    )
    await app_client.post(
        "/api/v1/activities",
        json={"type": "call", "subject": "Llamada de seguimiento", "owner_user_id": active_admin_user.id.hex if hasattr(active_admin_user.id, "hex") else str(active_admin_user.id), "customer_id": customer_id},
        headers=headers,
    )

    resp = await app_client.get(f"/api/v1/customers/{customer_id}/timeline", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["opportunities"]) == 1
    assert len(body["activities"]) == 1


async def test_opportunity_funder_status_catalog_and_extra_fields(app_client, active_admin_user, seeded_org):
    headers = await _auth_headers(app_client, active_admin_user)
    customer_resp = await app_client.post(
        "/api/v1/customers", json={"legal_name": "HEEHRA Customer"}, headers=headers,
    )
    customer_id = customer_resp.json()["id"]

    resp = await app_client.post(
        "/api/v1/opportunities",
        json={
            "customer_id": customer_id,
            "title": "Instalación HEEHRA",
            "stage_code": "new",
            "funder_status_code": "pending",
            "utility_account_number": "UA-12345",
            "meter_number": "MTR-999",
            "unit_type": "Mobile home",
            "scheduled_install_date": "2026-10-01",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["funder_status"]["code"] == "pending"
    assert body["utility_account_number"] == "UA-12345"
    assert body["scheduled_install_date"] == "2026-10-01"

    opportunity_id = body["id"]
    resp = await app_client.patch(
        f"/api/v1/opportunities/{opportunity_id}", json={"funder_status_code": "approved"}, headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["funder_status"]["code"] == "approved"

    resp = await app_client.get("/api/v1/funder-statuses", headers=headers)
    assert resp.status_code == 200
    assert {s["code"] for s in resp.json()} >= {"pending", "approved", "installed", "rejected"}


async def test_opportunity_approved_stage_auto_creates_project(app_client, active_admin_user, seeded_org):
    headers = await _auth_headers(app_client, active_admin_user)
    customer_resp = await app_client.post(
        "/api/v1/customers", json={"legal_name": "Auto Project Customer"}, headers=headers,
    )
    customer_id = customer_resp.json()["id"]

    opp_resp = await app_client.post(
        "/api/v1/opportunities",
        json={"customer_id": customer_id, "title": "HEEHRA install", "stage_code": "new", "address_street": "42 Elm St"},
        headers=headers,
    )
    opportunity_id = opp_resp.json()["id"]

    # Moving to an intermediate stage should NOT create a project yet.
    resp = await app_client.post(
        f"/api/v1/opportunities/{opportunity_id}/change-stage", json={"stage_code": "under_review"}, headers=headers,
    )
    assert resp.status_code == 200
    projects_resp = await app_client.get("/api/v1/projects", headers=headers)
    assert projects_resp.json() == []

    resp = await app_client.post(
        f"/api/v1/opportunities/{opportunity_id}/change-stage", json={"stage_code": "approved"}, headers=headers,
    )
    assert resp.status_code == 200

    projects_resp = await app_client.get("/api/v1/projects", headers=headers)
    projects = projects_resp.json()
    assert len(projects) == 1
    assert projects[0]["opportunity_id"] == opportunity_id
    assert projects[0]["address_street"] == "42 Elm St"

    checklist_resp = await app_client.get(f"/api/v1/projects/{projects[0]['id']}/checklist", headers=headers)
    assert len(checklist_resp.json()) == 8

    # Moving to "installation" afterwards must not create a second project.
    resp = await app_client.post(
        f"/api/v1/opportunities/{opportunity_id}/change-stage", json={"stage_code": "installation"}, headers=headers,
    )
    assert resp.status_code == 200
    projects_resp = await app_client.get("/api/v1/projects", headers=headers)
    assert len(projects_resp.json()) == 1


async def test_crm_entities_are_org_isolated(app_client, active_admin_user, seeded_org, db):
    from app.core.security import hash_password
    from app.modules.organizations.models import Organization
    from app.modules.users.models import Role, User, UserRole, UserStatus
    from app.shared.permissions import ROLE_LABELS

    headers = await _auth_headers(app_client, active_admin_user)
    await app_client.post("/api/v1/customers", json={"legal_name": "Org1 Customer"}, headers=headers)

    org2 = Organization(name="Second Org")
    db.add(org2)
    await db.flush()
    admin_role_2 = Role(organization_id=org2.id, code="organization_admin", name=ROLE_LABELS["organization_admin"], is_system=True)
    admin_role_2.permissions = seeded_org["roles"]["organization_admin"].permissions
    db.add(admin_role_2)
    await db.flush()
    user2 = User(
        organization_id=org2.id, email="admin2@second-demo.com", email_display="admin2@second-demo.com",
        full_name="Second Admin", password_hash=hash_password("SuperSecret123"), status=UserStatus.active,
    )
    db.add(user2)
    await db.flush()
    db.add(UserRole(user_id=user2.id, role_id=admin_role_2.id))
    await db.commit()

    token2 = await _login(app_client, "admin2@second-demo.com")
    resp = await app_client.get("/api/v1/customers", headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 200
    assert resp.json() == []
