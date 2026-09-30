"""Cobro de rebate (módulo 6, spec D6.3 y D6.5).

Escenario: una casa en San Fernando, 91340, instalada el 20 de diciembre de
2026. TECH aplica por ciudad ($4.000 en 2026, $4.250 en 2027), LADWP por
código postal ($7.500) y GoZero no aplica ($3.000).
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.modules.billing import case_hooks as billing_hooks
from app.modules.billing import claims as claims_service
from app.modules.billing.models import (
    Invoice,
    ProgramJurisdiction,
    ProgramRebateRate,
    RebateClaim,
)
from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.cases.models import Program
from app.modules.field_ops import case_hooks
from app.modules.field_ops.models import Evidence, Inspection, ProjectReview
from app.shared import events as domain_events
from app.shared.errors import ConflictError, InvalidInputError
from tests.field_helpers import headers_for, installed_case, refreshed_case

INSTALADA = date(2026, 12, 20)


@pytest.fixture(autouse=True)
def _registries():
    billing_hooks.register()
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()
    billing_hooks._reset_for_tests()
    domain_events.clear_subscribers()


# ---------------------------------------------------------------------------
# Escenario
# ---------------------------------------------------------------------------

async def _programas(db, org_id) -> dict[str, Program]:
    progs = {}
    for code, name, amount, kind, value in [
        ("TECH", "TECH Clean California", "4000", "city", "san fernando"),
        ("LADWP", "LADWP", "7500", "zip", "91340"),
        ("GOZERO", "GoZero", "3000", "zip", "91345"),
    ]:
        p = Program(organization_id=org_id, code=code, name=name)
        db.add(p)
        await db.flush()
        db.add(ProgramRebateRate(organization_id=org_id, program_id=p.id, amount=Decimal(amount),
                                 valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31)))
        db.add(ProgramJurisdiction(organization_id=org_id, program_id=p.id, kind=kind, value=value,
                                   label=value.title(), valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31)))
        progs[code] = p
    db.add(ProgramRebateRate(organization_id=org_id, program_id=progs["TECH"].id, amount=Decimal("4250"),
                             valid_from=date(2027, 1, 1)))
    await db.commit()
    return progs


async def _listo_para_cobrar(db, org_id, *, confirmar=True):
    """Instalado, inspección aprobada con permiso firmado y acta confirmada;
    expediente en «Inspección pendiente»."""
    case, project = await installed_case(db, org_id)
    project.address_city, project.address_zip = "San Fernando", "91340"
    project.completed_date = INSTALADA
    project.scheduled_date = INSTALADA
    project.primary_technician_user_id = uuid.uuid4()
    case.approval_code = "TECH-APR-77"
    inspeccion = Inspection(organization_id=org_id, project_id=project.id,
                            scheduled_for=datetime(2026, 12, 22, tzinfo=timezone.utc))
    db.add(inspeccion)
    await db.flush()
    case = await case_service.transition(db, case=case, to_stage="inspection_pending", actor_id=uuid.uuid4(),
                                         actor_permissions=stages.SYSTEM_ACTOR)
    inspeccion.result = "passed"
    db.add(Evidence(organization_id=org_id, project_id=project.id, category="permit_signed",
                    file_path="x/permiso.jpg", uploaded_by_user_id=uuid.uuid4()))
    if confirmar:
        db.add(ProjectReview(organization_id=org_id, project_id=project.id, action="confirmed"))
    await db.commit()
    await db.refresh(project, attribute_names=["reviews"])
    return case, project


async def _crear(app_client, headers, project_id, program_id, **extra):
    return await app_client.post(f"/api/v1/projects/{project_id}/claims",
                                 json={"program_id": str(program_id), **extra}, headers=headers)


async def _confirmar_manuales(app_client, headers, claim):
    for req in claim["requirements"]:
        if req["kind"] == "manual" and not req["met"]:
            r = await app_client.post(f"/api/v1/claims/{claim['id']}/checks/{req['code']}", json={}, headers=headers)
            assert r.status_code == 200, r.text
            claim = r.json()
    return claim


async def _radicar(app_client, headers, claim):
    claim = await _confirmar_manuales(app_client, headers, claim)
    r = await app_client.post(f"/api/v1/claims/{claim['id']}/submit",
                              json={"portal_reference": "PORTAL-123"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Elegibilidad y creación
# ---------------------------------------------------------------------------

async def test_eligibility_suggests_the_programs_of_the_address_on_the_installation_date(
        app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    r = await app_client.get(f"/api/v1/projects/{project.id}/billing/eligibility", headers=headers)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    aplican = {p["program_code"]: p for p in cuerpo["programs"] if p["applies"]}
    assert set(aplican) == {"TECH", "LADWP"}
    assert (aplican["TECH"]["rate"], aplican["LADWP"]["rate"]) == (4000, 7500)
    assert cuerpo["installation_date"] == "2026-12-20"


async def test_the_claim_freezes_the_rate_of_the_installation_date_and_issues_the_invoice(
        app_client, db, seeded_org, active_admin_staff_user):
    """Instalada en diciembre, cobrada en enero: vale la tarifa de diciembre."""
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    case, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    r = await _crear(app_client, headers, project.id, progs["TECH"].id)
    assert r.status_code == 201, r.text
    cobro = r.json()
    assert (cobro["amount"], cobro["status"], cobro["applies"]) == (4000, "preparing", True)
    factura = cobro["invoice"]
    assert factura["invoice_number"].startswith("REB-")
    assert (factura["kind"], factura["amount"], factura["customer_total"]) == ("rebate", 4000, 0)
    assert factura["claim_id"] == cobro["id"]

    case = await refreshed_case(db, case)
    assert (case.stage_code, case.substatus_code) == ("billing_in_progress", "invoice_pending")


async def test_a_program_that_does_not_apply_needs_a_reason(app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    r = await _crear(app_client, headers, project.id, progs["GOZERO"].id)
    assert r.status_code == 400
    assert "motivo" in r.json()["detail"]
    r = await _crear(app_client, headers, project.id, progs["GOZERO"].id,
                     override_reason="El programa aceptó la zona por excepción")
    assert r.status_code == 201, r.text
    assert (r.json()["applies"], r.json()["override_reason"]) == (False, "El programa aceptó la zona por excepción")


async def test_a_second_claim_of_the_same_program_is_rejected_until_withdrawn(
        app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    primero = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()
    assert (await _crear(app_client, headers, project.id, progs["TECH"].id)).status_code == 409

    r = await app_client.post(f"/api/v1/claims/{primero['id']}/withdraw",
                              json={"reason": "Se cargó con la dirección equivocada"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "withdrawn" and r.json()["invoice"] is None
    assert (await _crear(app_client, headers, project.id, progs["TECH"].id)).status_code == 201


async def test_two_claims_created_at_once_leave_only_one(app_client, db, seeded_org, active_admin_staff_user,
                                                        monkeypatch):
    """Simula la carrera: el chequeo previo no ve el primer cobro (como pasa
    si dos personas crean a la vez) y es el índice único de la base el que
    responde 409."""
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    assert (await _crear(app_client, headers, project.id, progs["TECH"].id)).status_code == 201

    async def no_ve_nada(db, project_id):
        return []

    monkeypatch.setattr(claims_service, "_claims_of_project", no_ve_nada)
    r = await _crear(app_client, headers, project.id, progs["TECH"].id)
    assert r.status_code == 409, r.text
    vivos = (await db.execute(select(RebateClaim).where(RebateClaim.project_id == project.id))).scalars().all()
    assert len(vivos) == 1


async def test_a_claim_needs_the_confirmed_acta(app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org, confirmar=False)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    r = await _crear(app_client, headers, project.id, progs["TECH"].id)
    assert r.status_code == 409
    assert "confirmar la información técnica" in r.json()["detail"]


async def test_a_program_without_a_rate_on_the_installation_date_gives_a_clear_message(
        app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    sin_tarifa = Program(organization_id=org, code="NEW", name="Programa nuevo")
    db.add(sin_tarifa)
    await db.commit()
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    r = await _crear(app_client, headers, project.id, sin_tarifa.id, override_reason="Caso piloto")
    assert r.status_code == 400
    assert "no tiene tarifa vigente el 2026-12-20" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Checklist y radicación
# ---------------------------------------------------------------------------

async def test_submitting_with_pending_requirements_lists_them(app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()
    pendientes = {r["code"] for r in cobro["requirements"] if not r["met"]}
    assert pendientes == {"benefit_documents", "terms_signed", "program_paperwork"}
    assert cobro["ready_to_submit"] is False

    r = await app_client.post(f"/api/v1/claims/{cobro['id']}/submit", json={}, headers=headers)
    assert r.status_code == 400
    assert "Términos y condiciones firmados" in r.json()["detail"]


async def test_an_automatic_requirement_cannot_be_confirmed_by_hand(app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()
    r = await app_client.post(f"/api/v1/claims/{cobro['id']}/checks/inspection_passed", json={}, headers=headers)
    assert r.status_code == 400


async def test_submitting_a_complete_claim_records_the_attempt(app_client, db, seeded_org, active_admin_staff_user):
    eventos = []
    domain_events.subscribe("claim.submitted", lambda n, p: eventos.append(p["claim_id"]))
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    case, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()
    cobro = await _radicar(app_client, headers, cobro)
    assert cobro["status"] == "submitted"
    assert [(a["result"], a["portal_reference"]) for a in cobro["attempts"]] == [("pending", "PORTAL-123")]
    assert cobro["invoice"]["sent_at"] is not None
    assert eventos == [cobro["id"]]
    case = await refreshed_case(db, case)
    assert case.substatus_code == "submitted"


async def test_tech_without_inspection_only_needs_the_permit(app_client, db, seeded_org, active_admin_staff_user,
                                                             active_accounting_user):
    """Con la inspección desactivada para TECH, una inspección no aprobada no
    frena la radicación."""
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    inspeccion = (await db.execute(select(Inspection).where(Inspection.project_id == project.id))).scalar_one()
    inspeccion.result = "pending"
    await db.commit()
    contabilidad = await headers_for(app_client, active_accounting_user.email)
    reqs = (await app_client.get(f"/api/v1/billing/programs/{progs['TECH'].id}/requirements",
                                 headers=contabilidad)).json()
    req = next(r for r in reqs if r["code"] == "inspection_passed")
    await app_client.patch(f"/api/v1/billing/programs/requirements/{req['id']}", json={"active": False},
                           headers=contabilidad)

    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()
    assert "inspection_passed" not in {r["code"] for r in cobro["requirements"]}
    assert (await _radicar(app_client, headers, cobro))["status"] == "submitted"


# ---------------------------------------------------------------------------
# Rechazo y reintento
# ---------------------------------------------------------------------------

async def test_a_rejection_needs_a_reason_and_allows_retrying(app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    case, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = await _radicar(app_client, headers, (await _crear(app_client, headers, project.id, progs["TECH"].id)).json())
    url = f"/api/v1/claims/{cobro['id']}/reject"
    assert (await app_client.post(url, json={"reason": "x", "category": "documentary"}, headers=headers)).status_code == 400
    r = await app_client.post(url, json={"reason": "Falta la firma del cliente en el formulario",
                                         "category": "documentary"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"
    case = await refreshed_case(db, case)
    assert case.substatus_code == "rejected_by_program"

    r = await app_client.post(f"/api/v1/claims/{cobro['id']}/submit", json={"portal_reference": "PORTAL-124"},
                              headers=headers)
    assert r.status_code == 200, r.text
    assert [a["result"] for a in r.json()["attempts"]] == ["rejected", "pending"]


async def test_a_technical_rejection_can_send_the_acta_back(app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    case, project = await _listo_para_cobrar(db, org)
    project_id = project.id
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = await _radicar(app_client, headers, (await _crear(app_client, headers, project_id, progs["TECH"].id)).json())
    r = await app_client.post(f"/api/v1/claims/{cobro['id']}/reject",
                              json={"reason": "El serial no coincide con la foto", "category": "technical",
                                    "return_to_technician": True}, headers=headers)
    assert r.status_code == 200, r.text
    proyecto = (await app_client.get(f"/api/v1/projects/{project_id}", headers=headers)).json()
    assert (proyecto["status"], proyecto["technician_info_confirmed"]) == ("scheduled", False)
    assert "El serial no coincide" in proyecto["returned_reason"]
    # El expediente no retrocede: sigue en cobro.
    assert (await refreshed_case(db, case)).stage_code == "billing_in_progress"


# ---------------------------------------------------------------------------
# Pago y expediente pagado
# ---------------------------------------------------------------------------

async def test_a_payment_below_the_rate_keeps_the_difference_visible(
        app_client, db, seeded_org, active_admin_staff_user, active_accounting_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = await _radicar(app_client, headers, (await _crear(app_client, headers, project.id, progs["TECH"].id)).json())
    contabilidad = await headers_for(app_client, active_accounting_user.email)
    r = await app_client.post(f"/api/v1/claims/{cobro['id']}/payment",
                              json={"amount": 3800, "paid_on": "2026-09-28", "reference": "CHK-889"},
                              headers=contabilidad)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert (cuerpo["status"], cuerpo["paid_amount"], cuerpo["difference"]) == ("paid", 3800, -200)
    assert cuerpo["invoice"]["balance"] == 200


async def test_the_case_is_paid_only_when_every_claim_is_paid(
        app_client, db, seeded_org, active_admin_staff_user, active_accounting_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    case, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    contabilidad = await headers_for(app_client, active_accounting_user.email)
    tech = await _radicar(app_client, headers, (await _crear(app_client, headers, project.id, progs["TECH"].id)).json())
    ladwp = await _radicar(app_client, headers, (await _crear(app_client, headers, project.id, progs["LADWP"].id)).json())

    await app_client.post(f"/api/v1/claims/{tech['id']}/payment",
                          json={"amount": 4000, "paid_on": "2026-09-28"}, headers=contabilidad)
    assert (await refreshed_case(db, case)).stage_code == "billing_in_progress"

    await app_client.post(f"/api/v1/claims/{ladwp['id']}/payment",
                          json={"amount": 7500, "paid_on": "2026-09-28"}, headers=contabilidad)
    assert (await refreshed_case(db, case)).stage_code == "paid"


async def test_a_new_claim_on_a_paid_case_does_not_move_it_back(
        app_client, db, seeded_org, active_admin_staff_user, active_accounting_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    case, project = await _listo_para_cobrar(db, org)
    project_id, ladwp_id = project.id, progs["LADWP"].id
    headers = await headers_for(app_client, active_admin_staff_user.email)
    contabilidad = await headers_for(app_client, active_accounting_user.email)
    tech = await _radicar(app_client, headers, (await _crear(app_client, headers, project.id, progs["TECH"].id)).json())
    await app_client.post(f"/api/v1/claims/{tech['id']}/payment",
                          json={"amount": 4000, "paid_on": "2026-09-28"}, headers=contabilidad)
    assert (await refreshed_case(db, case)).stage_code == "paid"

    r = await _crear(app_client, headers, project_id, ladwp_id)
    assert r.status_code == 201, r.text
    assert (await refreshed_case(db, case)).stage_code == "paid"


async def test_the_manual_path_cannot_mark_paid_with_pending_claims(app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    case, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    await _crear(app_client, headers, project.id, progs["TECH"].id)
    case = await refreshed_case(db, case)
    with pytest.raises(InvalidInputError, match="todos sus cobros"):
        await case_service.transition(db, case=case, to_stage="paid", actor_id=uuid.uuid4(),
                                      actor_permissions=stages.SYSTEM_ACTOR)


async def test_the_manual_path_cannot_enter_billing_without_a_claim(db, seeded_org):
    org = seeded_org["org"].id
    case, _ = await _listo_para_cobrar(db, org)
    with pytest.raises(InvalidInputError, match="Crea el cobro"):
        await case_service.transition(db, case=case, to_stage="billing_in_progress", actor_id=uuid.uuid4(),
                                      actor_permissions=stages.SYSTEM_ACTOR)


# ---------------------------------------------------------------------------
# Refacturar, permisos y aislamiento
# ---------------------------------------------------------------------------

async def test_reissuing_voids_the_invoice_and_replaces_it(app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()
    anterior = cobro["invoice"]
    r = await app_client.post(f"/api/v1/claims/{cobro['id']}/invoice/reissue",
                              json={"reason": "Dirección con el número de espacio equivocado"}, headers=headers)
    assert r.status_code == 200, r.text
    nueva = r.json()["invoice"]
    assert nueva["id"] != anterior["id"] and nueva["replaces_invoice_id"] == anterior["id"]
    vieja = await db.get(Invoice, uuid.UUID(anterior["id"]), populate_existing=True)
    assert vieja.document_status == "void"


async def test_only_accounting_records_the_program_payment(app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = await _radicar(app_client, headers, (await _crear(app_client, headers, project.id, progs["TECH"].id)).json())
    r = await app_client.post(f"/api/v1/claims/{cobro['id']}/payment",
                              json={"amount": 4000, "paid_on": "2026-09-28"}, headers=headers)
    assert r.status_code == 403


async def test_a_technician_cannot_create_claims(app_client, db, seeded_org, active_technician_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, "tech@acme-demo.com")
    assert (await _crear(app_client, headers, project.id, progs["TECH"].id)).status_code == 403


async def test_claims_of_another_organization_are_invisible(
        app_client, db, seeded_org, active_admin_staff_user, second_org_admin_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()
    ajeno = await headers_for(app_client, second_org_admin_user.email)
    assert (await app_client.get(f"/api/v1/claims/{cobro['id']}", headers=ajeno)).status_code == 404
    assert (await app_client.get("/api/v1/claims", headers=ajeno)).json() == []
    assert (await _crear(app_client, ajeno, project.id, progs["TECH"].id)).status_code == 404
