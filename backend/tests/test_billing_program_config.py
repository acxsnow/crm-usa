"""Configuración de cobro por programa (módulo 6, spec D6.2).

Con los programas reales de Delta HVAC: TECH ($4.000, San Fernando este año),
LADWP ($7.500, Los Ángeles) y GoZero ($3.000, zonas desfavorecidas).
"""
from datetime import date

import pytest

from app.modules.billing import program_config
from app.modules.cases.models import Program
from tests.field_helpers import headers_for


async def _program(db, org_id, code, name):
    p = Program(organization_id=org_id, code=code, name=name)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


# ---------------------------------------------------------------------------
# Tarifas con vigencia
# ---------------------------------------------------------------------------

async def test_the_rate_is_the_one_in_force_on_the_date(app_client, db, seeded_org, active_accounting_user):
    tech = await _program(db, seeded_org["org"].id, "TECH", "TECH Clean California")
    headers = await headers_for(app_client, active_accounting_user.email)
    r = await app_client.post(f"/api/v1/billing/programs/{tech.id}/rates",
                              json={"amount": 4000, "valid_from": "2026-01-01", "valid_to": "2026-12-31"}, headers=headers)
    assert r.status_code == 201, r.text
    r = await app_client.post(f"/api/v1/billing/programs/{tech.id}/rates",
                              json={"amount": 4250, "valid_from": "2027-01-01"}, headers=headers)
    assert r.status_code == 201, r.text

    org = seeded_org["org"].id
    dic = await program_config.rate_for(db, organization_id=org, program_id=tech.id, on=date(2026, 12, 20))
    ene = await program_config.rate_for(db, organization_id=org, program_id=tech.id, on=date(2027, 1, 5))
    antes = await program_config.rate_for(db, organization_id=org, program_id=tech.id, on=date(2025, 6, 1))
    assert (str(dic.amount), str(ene.amount), antes) == ("4000.00", "4250.00", None)


async def test_overlapping_rates_are_rejected(app_client, db, seeded_org, active_accounting_user):
    tech = await _program(db, seeded_org["org"].id, "TECH", "TECH Clean California")
    headers = await headers_for(app_client, active_accounting_user.email)
    await app_client.post(f"/api/v1/billing/programs/{tech.id}/rates",
                          json={"amount": 4000, "valid_from": "2026-01-01"}, headers=headers)
    r = await app_client.post(f"/api/v1/billing/programs/{tech.id}/rates",
                              json={"amount": 4250, "valid_from": "2027-01-01"}, headers=headers)
    assert r.status_code == 409
    assert "Cierra esa vigencia" in r.json()["detail"]


async def test_closing_a_rate_makes_room_for_next_year(app_client, db, seeded_org, active_accounting_user):
    tech = await _program(db, seeded_org["org"].id, "TECH", "TECH Clean California")
    headers = await headers_for(app_client, active_accounting_user.email)
    rate = (await app_client.post(f"/api/v1/billing/programs/{tech.id}/rates",
                                  json={"amount": 4000, "valid_from": "2026-01-01"}, headers=headers)).json()
    r = await app_client.patch(f"/api/v1/billing/programs/rates/{rate['id']}/close",
                               json={"valid_to": "2026-12-31"}, headers=headers)
    assert r.status_code == 200
    r = await app_client.post(f"/api/v1/billing/programs/{tech.id}/rates",
                              json={"amount": 4250, "valid_from": "2027-01-01"}, headers=headers)
    assert r.status_code == 201


async def test_a_period_that_ends_before_it_starts_is_rejected(app_client, db, seeded_org, active_accounting_user):
    tech = await _program(db, seeded_org["org"].id, "TECH", "TECH Clean California")
    headers = await headers_for(app_client, active_accounting_user.email)
    r = await app_client.post(f"/api/v1/billing/programs/{tech.id}/rates",
                              json={"amount": 4000, "valid_from": "2026-12-31", "valid_to": "2026-01-01"}, headers=headers)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Jurisdicciones con vigencia
# ---------------------------------------------------------------------------

async def test_programs_for_an_address_by_city_and_zip(app_client, db, seeded_org, active_accounting_user):
    org = seeded_org["org"].id
    ladwp = await _program(db, org, "LADWP", "LADWP")
    tech = await _program(db, org, "TECH", "TECH Clean California")
    gozero = await _program(db, org, "GOZERO", "GoZero")
    headers = await headers_for(app_client, active_accounting_user.email)
    for pid, kind, value in [(ladwp.id, "city", "Mission Hills"), (tech.id, "city", "San Fernando"),
                             (gozero.id, "zip", "91345-1234")]:
        r = await app_client.post(f"/api/v1/billing/programs/{pid}/jurisdictions",
                                  json={"kind": kind, "value": value, "valid_from": "2026-01-01", "valid_to": "2026-12-31"},
                                  headers=headers)
        assert r.status_code == 201, r.text

    # Mission Hills, 91345: LADWP por ciudad y GoZero por código postal.
    aplica = await program_config.programs_for_address(db, organization_id=org, city="  mission HILLS ",
                                                       zip_code="91345", on=date(2026, 9, 28))
    assert set(aplica) == {ladwp.id, gozero.id}

    # En 2027 la jurisdicción de 2026 ya no rige.
    assert await program_config.programs_for_address(db, organization_id=org, city="Mission Hills",
                                                      zip_code="91345", on=date(2027, 2, 1)) == {}


async def test_an_invalid_zip_is_rejected(app_client, db, seeded_org, active_accounting_user):
    tech = await _program(db, seeded_org["org"].id, "TECH", "TECH Clean California")
    headers = await headers_for(app_client, active_accounting_user.email)
    r = await app_client.post(f"/api/v1/billing/programs/{tech.id}/jurisdictions",
                              json={"kind": "zip", "value": "913", "valid_from": "2026-01-01"}, headers=headers)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Requisitos de radicación
# ---------------------------------------------------------------------------

async def test_a_program_starts_with_the_real_process_checklist(app_client, db, seeded_org, active_accounting_user):
    tech = await _program(db, seeded_org["org"].id, "TECH", "TECH Clean California")
    headers = await headers_for(app_client, active_accounting_user.email)
    reqs = (await app_client.get(f"/api/v1/billing/programs/{tech.id}/requirements", headers=headers)).json()
    codes = [r["code"] for r in reqs]
    assert codes[0] == "benefit_documents"
    assert {"technician_info_confirmed", "permit_approved", "inspection_passed", "invoice_issued"} <= set(codes)
    assert all(r["active"] for r in reqs)


async def test_tech_can_turn_off_the_inspection_requirement(app_client, db, seeded_org, active_accounting_user):
    tech = await _program(db, seeded_org["org"].id, "TECH", "TECH Clean California")
    headers = await headers_for(app_client, active_accounting_user.email)
    reqs = (await app_client.get(f"/api/v1/billing/programs/{tech.id}/requirements", headers=headers)).json()
    inspeccion = next(r for r in reqs if r["code"] == "inspection_passed")
    r = await app_client.patch(f"/api/v1/billing/programs/requirements/{inspeccion['id']}",
                               json={"active": False}, headers=headers)
    assert r.status_code == 200 and r.json()["active"] is False


async def test_gozero_adds_the_gas_to_electric_rule_and_its_own_paperwork(app_client, db, seeded_org, active_accounting_user):
    gozero = await _program(db, seeded_org["org"].id, "GOZERO", "GoZero")
    headers = await headers_for(app_client, active_accounting_user.email)
    r = await app_client.post(f"/api/v1/billing/programs/{gozero.id}/requirements",
                              json={"auto_code": "gas_to_electric"}, headers=headers)
    assert r.status_code == 201 and r.json()["kind"] == "auto"
    r = await app_client.post(f"/api/v1/billing/programs/{gozero.id}/requirements",
                              json={"label": "Formulario de reducción de carbono"}, headers=headers)
    assert r.status_code == 201 and r.json()["kind"] == "manual"
    r = await app_client.post(f"/api/v1/billing/programs/{gozero.id}/requirements",
                              json={"auto_code": "gas_to_electric"}, headers=headers)
    assert r.status_code == 409


async def test_an_unknown_auto_rule_is_rejected(app_client, db, seeded_org, active_accounting_user):
    tech = await _program(db, seeded_org["org"].id, "TECH", "TECH Clean California")
    headers = await headers_for(app_client, active_accounting_user.email)
    r = await app_client.post(f"/api/v1/billing/programs/{tech.id}/requirements",
                              json={"auto_code": "adivinar"}, headers=headers)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Perfil, permisos y aislamiento
# ---------------------------------------------------------------------------

async def test_the_profile_holds_the_invoice_issuer(app_client, db, seeded_org, active_accounting_user):
    tech = await _program(db, seeded_org["org"].id, "TECH", "TECH Clean California")
    headers = await headers_for(app_client, active_accounting_user.email)
    r = await app_client.put(f"/api/v1/billing/programs/{tech.id}/profile",
                             json={"issuer_name": "Delta HVAC Service Inc.", "expected_payment_days": 30}, headers=headers)
    assert r.status_code == 200
    assert (r.json()["issuer_name"], r.json()["expected_payment_days"]) == ("Delta HVAC Service Inc.", 30)
    r = await app_client.put(f"/api/v1/billing/programs/{tech.id}/profile",
                             json={"expected_payment_days": 0}, headers=headers)
    assert r.status_code == 400


async def test_administration_can_read_but_not_configure(app_client, db, seeded_org, active_admin_staff_user):
    tech = await _program(db, seeded_org["org"].id, "TECH", "TECH Clean California")
    headers = await headers_for(app_client, active_admin_staff_user.email)
    assert (await app_client.get(f"/api/v1/billing/programs/{tech.id}/rates", headers=headers)).status_code == 200
    r = await app_client.post(f"/api/v1/billing/programs/{tech.id}/rates",
                              json={"amount": 4000, "valid_from": "2026-01-01"}, headers=headers)
    assert r.status_code == 403


async def test_programs_of_another_organization_are_invisible(app_client, db, seeded_org, second_org_admin_user):
    tech = await _program(db, seeded_org["org"].id, "TECH", "TECH Clean California")
    headers = await headers_for(app_client, second_org_admin_user.email)
    assert (await app_client.get(f"/api/v1/billing/programs/{tech.id}/rates", headers=headers)).status_code == 404
    assert (await app_client.get("/api/v1/billing/programs", headers=headers)).json() == []
