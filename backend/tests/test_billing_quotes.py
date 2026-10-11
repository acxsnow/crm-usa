"""Trabajo particular: cotización con versiones → factura → pagos (módulo 6,
spec D6.7)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.cases import stages
from app.modules.crm.models import Customer
from app.modules.field_ops import case_hooks, clock
from app.shared import events as domain_events
from tests.field_helpers import headers_for, installed_case, refreshed_case


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()
    domain_events.clear_subscribers()


LINEAS = [
    {"kind": "labor", "description": "Duct repair", "quantity": 2, "unit_price": 150},
    {"kind": "material", "description": "Flex duct 25 ft", "quantity": 1, "unit_price": "89.50"},
]


async def _cliente(db, org_id, nombre="Ned Flanders"):
    c = Customer(organization_id=org_id, legal_name=nombre)
    db.add(c)
    await db.commit()
    return c


def _en(dias: int):
    return (datetime.now(timezone.utc) + timedelta(days=dias)).date().isoformat()


async def _cotizacion_enviada(app_client, headers, customer_id, **extra):
    q = (await app_client.post("/api/v1/billing/quotes", json={"customer_id": str(customer_id), "lines": LINEAS,
                                                       "valid_until": _en(15), **extra}, headers=headers))
    assert q.status_code == 201, q.text
    q = q.json()
    r = await app_client.post(f"/api/v1/billing/quotes/{q['id']}/send", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _mover_reloj(monkeypatch, dias: int):
    futuro = datetime.now(timezone.utc) + timedelta(days=dias)
    monkeypatch.setattr(clock, "_utcnow", lambda: futuro)


# ---------------------------------------------------------------------------

async def test_a_quote_gets_a_cot_number_and_its_total(app_client, db, seeded_org, active_admin_staff_user):
    cliente = await _cliente(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    r = await app_client.post("/api/v1/billing/quotes", json={"customer_id": str(cliente.id), "lines": LINEAS},
                              headers=headers)
    assert r.status_code == 201, r.text
    q = r.json()
    assert q["quote_number"].startswith("COT-") and q["quote_number"].endswith("-0001")
    assert (q["version"], q["status"], q["total"]) == (1, "draft", 389.5)


async def test_revising_creates_the_next_version_and_keeps_the_previous(
        app_client, db, seeded_org, active_admin_staff_user):
    cliente = await _cliente(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    v1 = await _cotizacion_enviada(app_client, headers, cliente.id)

    r = await app_client.post(f"/api/v1/billing/quotes/{v1['id']}/revise", headers=headers)
    assert r.status_code == 201, r.text
    v2 = r.json()
    assert (v2["quote_number"], v2["version"], v2["status"]) == (v1["quote_number"], 2, "draft")
    assert v2["previous_version_id"] == v1["id"]

    # El cliente pidió bajar el precio: se ajusta la versión 2.
    r = await app_client.patch(f"/api/v1/billing/quotes/{v2['id']}", json={"lines": [
        {"kind": "labor", "description": "Duct repair", "quantity": 2, "unit_price": 120}]}, headers=headers)
    assert r.status_code == 200 and r.json()["total"] == 240

    anterior = (await app_client.get(f"/api/v1/billing/quotes/{v1['id']}", headers=headers)).json()
    assert (anterior["status"], anterior["total"]) == ("superseded", 389.5)
    assert [v["version"] for v in r.json()["versions"]] == [1, 2]
    # La anterior ya no se toca.
    assert (await app_client.patch(f"/api/v1/billing/quotes/{v1['id']}", json={"notes": "x"},
                                   headers=headers)).status_code == 409
    # La lista muestra solo la vigente.
    lista = (await app_client.get("/api/v1/billing/quotes", headers=headers)).json()
    assert [q["version"] for q in lista] == [2]


async def test_a_sent_quote_is_not_edited_in_place(app_client, db, seeded_org, active_admin_staff_user):
    cliente = await _cliente(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    q = await _cotizacion_enviada(app_client, headers, cliente.id)
    r = await app_client.patch(f"/api/v1/billing/quotes/{q['id']}", json={"lines": LINEAS[:1]}, headers=headers)
    assert r.status_code == 409
    assert "ajústala" in r.json()["detail"]


async def test_accepting_creates_the_draft_invoice_with_the_same_lines(
        app_client, db, seeded_org, active_admin_staff_user):
    cliente = await _cliente(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    q = await _cotizacion_enviada(app_client, headers, cliente.id)
    r = await app_client.post(f"/api/v1/billing/quotes/{q['id']}/accept", headers=headers)
    assert r.status_code == 200, r.text
    factura = r.json()["invoice"]
    assert r.json()["quote"]["status"] == "accepted"
    assert (factura["kind"], factura["document_status"], factura["invoice_number"]) == ("particular", "draft", "BORRADOR")
    assert [l["description"] for l in factura["lines"]] == ["Duct repair", "Flex duct 25 ft"]
    assert (factura["amount"], factura["quote_id"]) == (389.5, q["id"])
    # Una aceptada no se acepta dos veces.
    assert (await app_client.post(f"/api/v1/billing/quotes/{q['id']}/accept", headers=headers)).status_code == 409


async def test_issuing_the_draft_assigns_a_fac_number_and_freezes_it(
        app_client, db, seeded_org, active_admin_staff_user, active_accounting_user):
    cliente = await _cliente(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    contabilidad = await headers_for(app_client, active_accounting_user.email)
    q = await _cotizacion_enviada(app_client, headers, cliente.id)
    factura = (await app_client.post(f"/api/v1/billing/quotes/{q['id']}/accept", headers=headers)).json()["invoice"]

    # Ajuste antes de emitir (se agregó un permiso).
    r = await app_client.put(f"/api/v1/invoices/{factura['id']}/lines", json={"lines": LINEAS + [
        {"kind": "permit", "description": "City permit", "quantity": 1, "unit_price": 75}]}, headers=contabilidad)
    assert r.status_code == 200 and r.json()["amount"] == 464.5

    r = await app_client.post(f"/api/v1/invoices/{factura['id']}/issue", json={"due_date": _en(30)},
                              headers=contabilidad)
    assert r.status_code == 200, r.text
    emitida = r.json()
    assert emitida["invoice_number"].startswith("FAC-") and emitida["document_status"] == "issued"
    assert emitida["status"] == "unpaid"

    r = await app_client.put(f"/api/v1/invoices/{factura['id']}/lines", json={"lines": LINEAS},
                             headers=contabilidad)
    assert r.status_code == 409
    assert (await app_client.post(f"/api/v1/invoices/{factura['id']}/issue", json={},
                                  headers=contabilidad)).status_code == 409


async def test_partial_payments_leave_the_real_balance_and_overdue_uses_the_org_date(
        app_client, db, seeded_org, active_admin_staff_user, active_accounting_user, monkeypatch):
    cliente = await _cliente(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    contabilidad = await headers_for(app_client, active_accounting_user.email)
    q = await _cotizacion_enviada(app_client, headers, cliente.id)
    factura = (await app_client.post(f"/api/v1/billing/quotes/{q['id']}/accept", headers=headers)).json()["invoice"]
    await app_client.post(f"/api/v1/invoices/{factura['id']}/issue", json={"due_date": _en(10)}, headers=contabilidad)

    r = await app_client.post(f"/api/v1/invoices/{factura['id']}/payments",
                              json={"amount": 100, "paid_at": _en(0), "reference": "ZELLE-1"}, headers=contabilidad)
    assert r.status_code == 201, r.text
    assert (r.json()["status"], r.json()["balance"]) == ("partial", 289.5)

    _mover_reloj(monkeypatch, 20)
    cuerpo = (await app_client.get(f"/api/v1/invoices/{factura['id']}", headers=contabilidad)).json()
    assert (cuerpo["status"], cuerpo["balance"]) == ("overdue", 289.5)

    await app_client.post(f"/api/v1/invoices/{factura['id']}/payments",
                          json={"amount": "289.50", "paid_at": _en(0)}, headers=contabilidad)
    cuerpo = (await app_client.get(f"/api/v1/invoices/{factura['id']}", headers=contabilidad)).json()
    assert (cuerpo["status"], cuerpo["balance"]) == ("paid", 0)


async def test_a_sent_quote_expires_by_the_org_date(app_client, db, seeded_org, active_admin_staff_user, monkeypatch):
    cliente = await _cliente(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    q = await _cotizacion_enviada(app_client, headers, cliente.id)
    _mover_reloj(monkeypatch, 30)
    cuerpo = (await app_client.get(f"/api/v1/billing/quotes/{q['id']}", headers=headers)).json()
    assert (cuerpo["status"], cuerpo["status_label"]) == ("expired", "Vencida")
    r = await app_client.post(f"/api/v1/billing/quotes/{q['id']}/accept", headers=headers)
    assert r.status_code == 409 and "vencida" in r.json()["detail"]
    # Se ajusta con vigencia nueva.
    assert (await app_client.post(f"/api/v1/billing/quotes/{q['id']}/revise", headers=headers)).status_code == 201


async def test_a_rejected_quote_needs_a_reason_and_can_be_revised(app_client, db, seeded_org, active_admin_staff_user):
    cliente = await _cliente(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    q = await _cotizacion_enviada(app_client, headers, cliente.id)
    assert (await app_client.post(f"/api/v1/billing/quotes/{q['id']}/reject", json={"reason": "no"},
                                  headers=headers)).status_code == 400
    r = await app_client.post(f"/api/v1/billing/quotes/{q['id']}/reject", json={"reason": "Too expensive"}, headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert (await app_client.post(f"/api/v1/billing/quotes/{q['id']}/revise", headers=headers)).status_code == 201


async def test_particular_work_never_moves_the_case(app_client, db, seeded_org, active_admin_staff_user,
                                                    active_accounting_user):
    case, project = await installed_case(db, seeded_org["org"].id)
    project_id, customer_id = project.id, project.customer_id
    headers = await headers_for(app_client, active_admin_staff_user.email)
    contabilidad = await headers_for(app_client, active_accounting_user.email)
    q = await _cotizacion_enviada(app_client, headers, customer_id, project_id=str(project_id))
    factura = (await app_client.post(f"/api/v1/billing/quotes/{q['id']}/accept", headers=headers)).json()["invoice"]
    await app_client.post(f"/api/v1/invoices/{factura['id']}/issue", json={}, headers=contabilidad)
    await app_client.post(f"/api/v1/invoices/{factura['id']}/payments",
                          json={"amount": "389.50", "paid_at": _en(0)}, headers=contabilidad)
    assert (await refreshed_case(db, case)).stage_code == "installed"


async def test_a_quote_for_a_project_of_another_customer_is_rejected(app_client, db, seeded_org,
                                                                     active_admin_staff_user):
    _, project = await installed_case(db, seeded_org["org"].id)
    otro = await _cliente(db, seeded_org["org"].id, "Otro cliente")
    headers = await headers_for(app_client, active_admin_staff_user.email)
    r = await app_client.post("/api/v1/billing/quotes", json={"customer_id": str(otro.id), "project_id": str(project.id),
                                                      "lines": LINEAS}, headers=headers)
    assert r.status_code == 400


async def test_quotes_need_quotes_manage(app_client, db, seeded_org, active_technician_user):
    cliente = await _cliente(db, seeded_org["org"].id)
    headers = await headers_for(app_client, "tech@acme-demo.com")
    r = await app_client.post("/api/v1/billing/quotes", json={"customer_id": str(cliente.id), "lines": LINEAS},
                              headers=headers)
    assert r.status_code == 403
    assert (await app_client.get("/api/v1/billing/quotes", headers=headers)).status_code == 403


async def test_quotes_of_another_organization_are_invisible(app_client, db, seeded_org, active_admin_staff_user,
                                                            second_org_admin_user):
    cliente = await _cliente(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    q = await _cotizacion_enviada(app_client, headers, cliente.id)
    ajeno = await headers_for(app_client, second_org_admin_user.email)
    assert (await app_client.get(f"/api/v1/billing/quotes/{q['id']}", headers=ajeno)).status_code == 404
    assert (await app_client.get("/api/v1/billing/quotes", headers=ajeno)).json() == []
    r = await app_client.post("/api/v1/billing/quotes", json={"customer_id": str(cliente.id), "lines": LINEAS},
                              headers=ajeno)
    assert r.status_code == 404


async def test_quotes_are_paginated(app_client, db, seeded_org, active_admin_staff_user):
    cliente = await _cliente(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    for _ in range(3):
        await app_client.post("/api/v1/billing/quotes", json={"customer_id": str(cliente.id), "lines": LINEAS},
                              headers=headers)
    r = await app_client.get("/api/v1/billing/quotes?limit=2", headers=headers)
    assert r.headers["X-Total-Count"] == "3" and len(r.json()) == 2
    r = await app_client.get("/api/v1/billing/quotes?limit=2&offset=2", headers=headers)
    assert len(r.json()) == 1
    # Con el filtro de estado (calculado con la fecha de hoy) también pagina.
    r = await app_client.get("/api/v1/billing/quotes?status=draft&limit=1", headers=headers)
    assert r.headers["X-Total-Count"] == "3" and len(r.json()) == 1


async def test_the_summary_counts_and_adds_up_by_status_and_several_statuses_can_be_filtered(
    app_client, db, seeded_org, active_admin_staff_user
):
    cliente = await _cliente(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    for _ in range(2):
        await app_client.post("/api/v1/billing/quotes", json={"customer_id": str(cliente.id), "lines": LINEAS},
                              headers=headers)
    await _cotizacion_enviada(app_client, headers, cliente.id)
    resumen = (await app_client.get("/api/v1/billing/quotes/summary", headers=headers)).json()
    assert resumen["draft"] == {"count": 2, "total": 779.0}
    assert resumen["sent"]["count"] == 1
    r = await app_client.get("/api/v1/billing/quotes?status=draft,sent", headers=headers)
    assert r.headers["X-Total-Count"] == "3"
