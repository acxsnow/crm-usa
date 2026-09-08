from datetime import date, timedelta


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _admin_headers(app_client, active_admin_user):
    token = await _login(app_client, "admin@acme-demo.com")
    return {"Authorization": f"Bearer {token}"}


async def _create_project(app_client, headers):
    customer_resp = await app_client.post("/api/v1/customers", json={"legal_name": "Billing Customer"}, headers=headers)
    customer_id = customer_resp.json()["id"]
    project_resp = await app_client.post(
        "/api/v1/projects", json={"customer_id": customer_id, "title": "Instalación facturable"}, headers=headers,
    )
    assert project_resp.status_code == 201
    return project_resp.json()["id"]


async def test_invoice_creation_and_sequential_numbering(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)

    resp = await app_client.post(
        "/api/v1/invoices",
        json={"project_id": project_id, "amount": 4500, "funder_program": "HEEHRA", "due_date": str(date.today() + timedelta(days=30))},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["invoice_number"] == "FAC-0001"
    assert body["status"] == "pending"
    assert body["balance"] == 4500.0

    resp2 = await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 100}, headers=headers)
    assert resp2.json()["invoice_number"] == "FAC-0002"


async def test_partial_then_full_payment_transitions_status(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)

    invoice = (await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 1000}, headers=headers)).json()
    invoice_id = invoice["id"]

    resp = await app_client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": 400, "paid_at": str(date.today())},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "sent"  # partial payment implies it reached the funder
    assert body["balance"] == 600.0

    resp = await app_client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount": 600, "paid_at": str(date.today())},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "paid"
    assert body["balance"] == 0.0
    assert len(body["payments"]) == 2


async def test_overdue_invoice_detected_on_read(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)

    invoice = (
        await app_client.post(
            "/api/v1/invoices",
            json={"project_id": project_id, "amount": 500, "due_date": str(date.today() - timedelta(days=5))},
            headers=headers,
        )
    ).json()

    resp = await app_client.get(f"/api/v1/invoices/{invoice['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "overdue"


async def test_sweep_overdue_invoices_flips_status_without_a_read(app_client, db, active_admin_user, seeded_org):
    """The Celery beat task (app/workers/tasks.py) calls
    billing_service.sweep_overdue_invoices directly — this proves that
    function marks an invoice overdue on its own, not just as a side effect
    of GET /invoices/{id} (which already has its own coverage above)."""
    from app.modules.billing.service import sweep_overdue_invoices

    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)

    invoice = (
        await app_client.post(
            "/api/v1/invoices",
            json={"project_id": project_id, "amount": 250, "due_date": str(date.today() - timedelta(days=1))},
            headers=headers,
        )
    ).json()
    assert invoice["status"] == "pending"

    changed = await sweep_overdue_invoices(db)
    assert changed == 1

    resp = await app_client.get(f"/api/v1/invoices/{invoice['id']}", headers=headers)
    assert resp.json()["status"] == "overdue"

    # Running it again is a no-op — nothing left pending/sent-and-overdue to flip.
    assert await sweep_overdue_invoices(db) == 0


async def test_finance_dashboard_aggregates(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)

    await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 1000}, headers=headers)
    overdue_invoice = (
        await app_client.post(
            "/api/v1/invoices",
            json={"project_id": project_id, "amount": 200, "due_date": str(date.today() - timedelta(days=1))},
            headers=headers,
        )
    ).json()

    resp = await app_client.get("/api/v1/finance/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_invoiced"] == 1200.0
    assert body["invoice_count"] == 2
    assert body["overdue_count"] == 1
    assert body["total_overdue"] == 200.0


async def test_invoices_csv_export(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 300}, headers=headers)

    resp = await app_client.get("/api/v1/invoices-export.csv", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "FAC-0001" in resp.text
