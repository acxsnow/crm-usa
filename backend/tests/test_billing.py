"""Facturas (documento común, módulo 6 fase 1).

Mantiene lo que ya hacía la facturación anterior —crear, pagar en partes,
detectar vencidas, tablero y CSV— sobre la base nueva: dinero exacto,
numeración por serie y año, líneas y estado de pago calculado con la fecha de
la organización.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.modules.field_ops import clock


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


def _this_year():
    return date.today().year


async def test_invoice_creation_and_sequential_numbering(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)

    resp = await app_client.post(
        "/api/v1/invoices",
        json={"project_id": project_id, "amount": 4500, "due_date": str(date.today() + timedelta(days=30))},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["invoice_number"].startswith("FAC-") and body["invoice_number"].endswith("-0001")
    assert body["kind"] == "particular"
    assert body["document_status"] == "issued"
    assert body["status"] == "unpaid"
    assert body["balance"] == 4500.0
    # Sin líneas, el monto queda como una línea de servicio.
    assert [l["amount"] for l in body["lines"]] == [4500.0]

    resp2 = await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 100}, headers=headers)
    assert resp2.json()["invoice_number"].endswith("-0002")


async def test_invoice_with_lines_computes_totals_on_the_server(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    resp = await app_client.post(
        "/api/v1/invoices",
        json={"project_id": project_id, "lines": [
            {"kind": "labor", "description": "Mano de obra", "quantity": 3, "unit_price": "0.1"},
            {"kind": "material", "description": "Línea de cobre", "quantity": "2.5", "unit_price": 12},
        ]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # 3 × 0,10 = 0,30 exacto (con float sería 0.30000000000000004) + 30,00.
    assert body["amount"] == 30.3
    assert body["subtotal"] == 30.3


async def test_an_unknown_line_kind_is_rejected(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    resp = await app_client.post(
        "/api/v1/invoices",
        json={"project_id": project_id, "lines": [{"kind": "propina", "description": "x", "unit_price": 5}]},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_partial_then_full_payment(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    invoice_id = (await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 1000}, headers=headers)).json()["id"]

    resp = await app_client.post(f"/api/v1/invoices/{invoice_id}/payments",
                                 json={"amount": 400, "paid_at": str(date.today())}, headers=headers)
    assert resp.status_code == 201
    assert (resp.json()["status"], resp.json()["balance"]) == ("partial", 600.0)

    resp = await app_client.post(f"/api/v1/invoices/{invoice_id}/payments",
                                 json={"amount": 600, "paid_at": str(date.today())}, headers=headers)
    body = resp.json()
    assert (body["status"], body["balance"], len(body["payments"])) == ("paid", 0.0, 2)
    assert body["paid_at"] is not None


async def test_overdue_is_computed_on_read(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    invoice = (await app_client.post(
        "/api/v1/invoices",
        json={"project_id": project_id, "amount": 500, "due_date": str(date.today() - timedelta(days=5))},
        headers=headers,
    )).json()
    assert invoice["status"] == "overdue"
    resp = await app_client.get(f"/api/v1/invoices/{invoice['id']}", headers=headers)
    assert resp.json()["status"] == "overdue"


async def test_overdue_uses_the_organization_date(app_client, db, active_admin_user, seeded_org, monkeypatch):
    """COD-10: a las 11 p. m. en Bogotá en UTC ya es el día siguiente. Una
    factura que vence hoy no puede salir vencida por el reloj del servidor."""
    seeded_org["org"].timezone = "America/Bogota"
    await db.commit()
    monkeypatch.setattr(clock, "_utcnow", lambda: datetime(2026, 9, 28, 4, 0, tzinfo=timezone.utc))
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    invoice = (await app_client.post(
        "/api/v1/invoices", json={"project_id": project_id, "amount": 500, "due_date": "2026-09-27"}, headers=headers,
    )).json()
    assert invoice["status"] == "unpaid"


async def test_void_requires_a_reason_and_no_payments(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    invoice_id = (await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 100}, headers=headers)).json()["id"]

    assert (await app_client.post(f"/api/v1/invoices/{invoice_id}/void", json={"reason": ""}, headers=headers)).status_code == 422
    resp = await app_client.post(f"/api/v1/invoices/{invoice_id}/void", json={"reason": "Monto equivocado"}, headers=headers)
    assert resp.status_code == 200
    assert (resp.json()["status"], resp.json()["void_reason"]) == ("void", "Monto equivocado")
    # Anulada no recibe pagos.
    resp = await app_client.post(f"/api/v1/invoices/{invoice_id}/payments",
                                 json={"amount": 10, "paid_at": str(date.today())}, headers=headers)
    assert resp.status_code == 409


async def test_an_invoice_with_payments_cannot_be_voided(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    invoice_id = (await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 100}, headers=headers)).json()["id"]
    await app_client.post(f"/api/v1/invoices/{invoice_id}/payments", json={"amount": 10, "paid_at": str(date.today())}, headers=headers)
    resp = await app_client.post(f"/api/v1/invoices/{invoice_id}/void", json={"reason": "Error"}, headers=headers)
    assert resp.status_code == 409


async def test_an_issued_invoice_cannot_change_its_amount(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    invoice_id = (await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 100}, headers=headers)).json()["id"]
    resp = await app_client.patch(f"/api/v1/invoices/{invoice_id}", json={"amount": 999, "notes": "Llamar antes"}, headers=headers)
    assert resp.status_code == 200
    assert (resp.json()["amount"], resp.json()["notes"]) == (100.0, "Llamar antes")


async def test_count_overdue_invoices_for_the_daily_task(app_client, db, active_admin_user, seeded_org):
    from app.modules.billing.service import count_overdue_invoices

    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 250,
                                                    "due_date": str(date.today() - timedelta(days=2))}, headers=headers)
    await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 250}, headers=headers)
    assert await count_overdue_invoices(db) == 1


async def test_finance_dashboard_aggregates(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 1000}, headers=headers)
    await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 200,
                                                    "due_date": str(date.today() - timedelta(days=2))}, headers=headers)
    resp = await app_client.get("/api/v1/finance/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert (body["total_invoiced"], body["invoice_count"], body["overdue_count"], body["total_overdue"]) == (1200.0, 2, 1, 200.0)


async def test_invoices_csv_export(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 300}, headers=headers)
    resp = await app_client.get("/api/v1/invoices-export.csv", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "-0001" in resp.text and "particular" in resp.text


async def test_invoices_of_another_organization_are_invisible(app_client, active_admin_user, second_org_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    project_id = await _create_project(app_client, headers)
    invoice_id = (await app_client.post("/api/v1/invoices", json={"project_id": project_id, "amount": 100}, headers=headers)).json()["id"]
    otros = {"Authorization": f"Bearer {await _login(app_client, second_org_admin_user.email)}"}
    assert (await app_client.get(f"/api/v1/invoices/{invoice_id}", headers=otros)).status_code == 404
