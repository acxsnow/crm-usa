"""Tablero de cobros (módulo 6, spec D6.10)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.billing import case_hooks as billing_hooks
from app.modules.cases import stages
from app.modules.field_ops import case_hooks, clock
from app.shared import events as domain_events
from tests.field_helpers import headers_for
from tests.test_billing_claims import _crear, _listo_para_cobrar, _programas, _radicar


@pytest.fixture(autouse=True)
def _registries():
    billing_hooks.register()
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()
    billing_hooks._reset_for_tests()
    domain_events.clear_subscribers()


def _mover_reloj(monkeypatch, dias: int):
    futuro = datetime.now(timezone.utc) + timedelta(days=dias)
    monkeypatch.setattr(clock, "_utcnow", lambda: futuro)


async def _tablero(app_client, headers):
    r = await app_client.get("/api/v1/billing/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def test_a_confirmed_acta_without_a_claim_alerts_from_the_next_day(
        app_client, db, seeded_org, active_admin_staff_user, monkeypatch):
    org = seeded_org["org"].id
    await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    hoy = await _tablero(app_client, headers)
    assert [(i["project_id"], i["alert"]) for i in hoy["to_create"]] == [(str(project.id), False)]
    assert hoy["to_create"][0]["customer_name"] == "Marge Simpson"

    _mover_reloj(monkeypatch, 1)
    manana = await _tablero(app_client, headers)
    assert (manana["to_create"][0]["days"], manana["to_create"][0]["alert"]) == (1, True)


async def test_a_created_claim_moves_to_submit_with_its_pending_requirements(
        app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    await _crear(app_client, headers, project.id, progs["TECH"].id)
    tablero = await _tablero(app_client, headers)
    assert tablero["to_create"] == []
    item = tablero["to_submit"][0]
    assert (item["program_code"], item["amount"], item["ready_to_submit"], item["pending_requirements"]) == (
        "TECH", 4000, False, 3)


async def test_submitted_claims_alert_after_the_program_payment_days(
        app_client, db, seeded_org, active_admin_staff_user, active_accounting_user, monkeypatch):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    contabilidad = await headers_for(app_client, active_accounting_user.email)
    await app_client.put(f"/api/v1/billing/programs/{progs['TECH'].id}/profile",
                         json={"expected_payment_days": 30}, headers=contabilidad)
    await _radicar(app_client, headers, (await _crear(app_client, headers, project.id, progs["TECH"].id)).json())

    _mover_reloj(monkeypatch, 30)
    item = (await _tablero(app_client, headers))["submitted"][0]
    assert (item["days"], item["expected_payment_days"], item["alert"]) == (30, 30, False)
    _mover_reloj(monkeypatch, 31)
    assert (await _tablero(app_client, headers))["submitted"][0]["alert"] is True


async def test_rejected_claims_show_the_reason_and_days(app_client, db, seeded_org, active_admin_staff_user,
                                                        monkeypatch):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = await _radicar(app_client, headers,
                           (await _crear(app_client, headers, project.id, progs["TECH"].id)).json())
    await app_client.post(f"/api/v1/claims/{cobro['id']}/reject",
                          json={"reason": "Falta la firma del cliente", "category": "documentary"}, headers=headers)
    _mover_reloj(monkeypatch, 12)
    item = (await _tablero(app_client, headers))["rejected"][0]
    assert (item["days"], item["rejection_reason"], item["rejection_category"]) == (
        12, "Falta la firma del cliente", "documentary")


async def test_paid_this_month_and_expected_by_program(app_client, db, seeded_org, active_admin_staff_user,
                                                       active_accounting_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    contabilidad = await headers_for(app_client, active_accounting_user.email)
    ladwp = await _radicar(app_client, headers, (await _crear(app_client, headers, project.id, progs["LADWP"].id)).json())
    await _crear(app_client, headers, project.id, progs["TECH"].id)
    hoy = (await _tablero(app_client, headers))["today"]
    await app_client.post(f"/api/v1/claims/{ladwp['id']}/payment", json={"amount": 7400, "paid_on": hoy},
                          headers=contabilidad)

    por_programa = {p["program_code"]: p for p in (await _tablero(app_client, headers))["by_program"]}
    assert (por_programa["LADWP"]["paid_this_month"], por_programa["LADWP"]["expected"]) == (7400, 0)
    assert (por_programa["TECH"]["paid_this_month"], por_programa["TECH"]["expected"]) == (0, 4000)
    assert "GOZERO" not in por_programa


async def test_particular_overdue_invoices(app_client, db, seeded_org, active_accounting_user):
    from app.modules.crm.models import Customer

    cliente = Customer(organization_id=seeded_org["org"].id, legal_name="Ned Flanders")
    db.add(cliente)
    await db.commit()
    headers = await headers_for(app_client, active_accounting_user.email)
    ayer = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    r = await app_client.post("/api/v1/invoices", json={"customer_id": str(cliente.id), "amount": 250,
                                                        "due_date": ayer}, headers=headers)
    assert r.status_code == 201, r.text
    particular = (await _tablero(app_client, headers))["particular"]
    assert (particular["overdue_count"], particular["overdue_total"]) == (1, 250)


async def test_the_dashboard_is_per_organization_and_needs_invoices_read(
        app_client, db, seeded_org, active_admin_staff_user, second_org_admin_user, active_technician_user):
    org = seeded_org["org"].id
    await _programas(db, org)
    await _listo_para_cobrar(db, org)
    ajeno = await headers_for(app_client, second_org_admin_user.email)
    tablero = await _tablero(app_client, ajeno)
    assert (tablero["to_create"], tablero["to_submit"], tablero["by_program"]) == ([], [], [])
    tecnico = await headers_for(app_client, "tech@acme-demo.com")
    assert (await app_client.get("/api/v1/billing/dashboard", headers=tecnico)).status_code == 403


async def test_aging_and_paid_this_month(app_client, db, seeded_org, active_admin_staff_user, active_accounting_user,
                                         monkeypatch):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    project_id = project.id
    headers = await headers_for(app_client, active_admin_staff_user.email)
    contabilidad = await headers_for(app_client, active_accounting_user.email)
    await _crear(app_client, headers, project_id, progs["TECH"].id)
    ladwp = await _radicar(app_client, headers, (await _crear(app_client, headers, project_id, progs["LADWP"].id)).json())

    aging = (await _tablero(app_client, headers))["aging"]
    assert (aging["d0_30"], aging["open_total"]) == (11500, 11500)
    _mover_reloj(monkeypatch, 40)
    aging = (await _tablero(app_client, headers))["aging"]
    assert (aging["d0_30"], aging["d31_45"]) == (0, 11500)

    monkeypatch.undo()
    hoy = (await _tablero(app_client, headers))["today"]
    await app_client.post(f"/api/v1/claims/{ladwp['id']}/payment", json={"amount": 7400, "paid_on": hoy},
                          headers=contabilidad)
    tablero = await _tablero(app_client, headers)
    assert [(p["program_code"], p["paid_amount"], p["difference"]) for p in tablero["paid_this_month"]] == [
        ("LADWP", 7400, -100)]
    assert tablero["aging"]["open_total"] == 4000


async def test_the_claim_carries_customer_case_and_address(app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()
    assert cobro["customer_name"] == "Marge Simpson"
    assert cobro["case_number"].startswith("CASE-") and "San Fernando" in cobro["address"]
    lista = (await app_client.get("/api/v1/claims", headers=headers)).json()
    assert lista[0]["customer_name"] == "Marge Simpson"


async def test_days_use_the_organization_date_not_utc(app_client, db, seeded_org, active_admin_staff_user, monkeypatch):
    """Un cobro creado a las 6 p. m. en Phoenix (01:09 UTC del día siguiente)
    es del 28; al mediodía del 29 lleva 1 día. Con la fecha UTC diría 0."""
    org = seeded_org["org"]
    org.timezone = "America/Phoenix"
    await db.commit()
    progs = await _programas(db, org.id)
    _, project = await _listo_para_cobrar(db, org.id)
    noche_utc = datetime(2026, 9, 29, 1, 9, tzinfo=timezone.utc)  # 28 sep, 6:09 p. m. en Phoenix
    monkeypatch.setattr(clock, "_utcnow", lambda: noche_utc)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()
    from app.modules.billing.models import RebateClaim

    claim = await db.get(RebateClaim, __import__("uuid").UUID(cobro["id"]))
    claim.created_at = noche_utc
    await db.commit()
    mediodia = datetime(2026, 9, 29, 19, 0, tzinfo=timezone.utc)  # 29 sep, 12 m. en Phoenix
    monkeypatch.setattr(clock, "_utcnow", lambda: mediodia)
    item = (await _tablero(app_client, headers))["to_submit"][0]
    assert (item["days"], item["alert"]) == (1, True)
