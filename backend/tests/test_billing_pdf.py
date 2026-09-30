"""PDF de la factura (módulo 6, spec D6.9): plantillas rebate y particular y
vista previa."""
import re
import uuid
import zlib
from datetime import date

import pytest
from sqlalchemy import func, select

from app.modules.billing import case_hooks as billing_hooks
from app.modules.billing.models import BillingProgramProfile, DocumentSequence, Invoice
from app.modules.cases import stages
from app.modules.field_ops import case_hooks
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


def pdf_text(content: bytes) -> str:
    """El texto dibujado en el PDF: ReportLab codifica cada página en ASCII85
    y la comprime con zlib."""
    import base64

    assert content[:4] == b"%PDF"
    partes = []
    for stream in re.findall(rb"stream\r?\n(.*?)endstream", content, re.S):
        datos = stream.strip()
        try:
            if datos.endswith(b"~>"):
                datos = base64.a85decode(datos[:-2].replace(b"\n", b"").replace(b"\r", b""))
            partes.append(zlib.decompress(datos).decode("latin-1"))
        except (ValueError, zlib.error):
            continue
    return "\n".join(partes)


async def _perfil(db, program_id, org_id):
    db.add(BillingProgramProfile(organization_id=org_id, program_id=program_id,
                                 issuer_name="Delta HVAC Service Inc.", issuer_address="100 Main St, Phoenix AZ",
                                 legal_text="Rebate paid directly by the program administrator."))
    await db.commit()


async def test_the_rebate_pdf_has_program_address_equipment_rebate_and_zero_for_the_customer(
        app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    await _perfil(db, progs["TECH"].id, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()

    r = await app_client.get(f"/api/v1/invoices/{cobro['invoice']['id']}/pdf", headers=headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    texto = pdf_text(r.content)
    for esperado in ("TECH Clean California", "Delta HVAC Service Inc.", "742 Evergreen Terrace",
                     "San Fernando", "Carrier 25HCE4", "SN-0001", "-$4,000.00", "Customer responsibility",
                     "$0.00", "Amount due from program", "TECH-APR-77",
                     "Rebate paid directly by the program administrator.", cobro["invoice"]["invoice_number"]):
        assert esperado in texto, esperado


async def test_the_particular_pdf_has_lines_payments_and_balance(app_client, db, seeded_org, active_accounting_user):
    from app.modules.crm.models import Customer

    org = seeded_org["org"].id
    cliente = Customer(organization_id=org, legal_name="Ned Flanders", billing_address="744 Evergreen Terrace")
    db.add(cliente)
    await db.commit()
    headers = await headers_for(app_client, active_accounting_user.email)
    factura = (await app_client.post("/api/v1/invoices", json={
        "customer_id": str(cliente.id),
        "lines": [{"kind": "labor", "description": "Duct repair", "quantity": 2, "unit_price": 150},
                  {"kind": "material", "description": "Flex duct 25 ft", "quantity": 1, "unit_price": 89.5}],
    }, headers=headers)).json()
    await app_client.post(f"/api/v1/invoices/{factura['id']}/payments",
                          json={"amount": 100, "paid_at": "2026-09-28", "reference": "ZELLE-77"}, headers=headers)

    texto = pdf_text((await app_client.get(f"/api/v1/invoices/{factura['id']}/pdf", headers=headers)).content)
    for esperado in ("Ned Flanders", "744 Evergreen Terrace", "Duct repair", "Flex duct 25 ft", "$389.50",
                     "ZELLE-77", "Balance due", "$289.50"):
        assert esperado in texto, esperado
    assert "Amount due from program" not in texto


async def test_a_void_invoice_says_so(app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()
    anterior = cobro["invoice"]
    nuevo = (await app_client.post(f"/api/v1/claims/{cobro['id']}/invoice/reissue",
                                   json={"reason": "Wrong space number"}, headers=headers)).json()
    texto_viejo = pdf_text((await app_client.get(f"/api/v1/invoices/{anterior['id']}/pdf", headers=headers)).content)
    assert "VOID" in texto_viejo
    texto_nuevo = pdf_text((await app_client.get(f"/api/v1/invoices/{nuevo['invoice']['id']}/pdf",
                                                 headers=headers)).content)
    assert f"Replaces invoice: {anterior['invoice_number']}" in texto_nuevo


async def test_the_rebate_preview_saves_nothing_and_uses_no_number(app_client, db, seeded_org, active_admin_staff_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    r = await app_client.post("/api/v1/invoices/preview", json={
        "kind": "rebate", "project_id": str(project.id), "program_id": str(progs["LADWP"].id),
    }, headers=headers)
    assert r.status_code == 200, r.text
    texto = pdf_text(r.content)
    assert "PREVIEW" in texto and "LADWP" in texto and "-$7,500.00" in texto

    assert (await db.execute(select(func.count()).select_from(Invoice))).scalar_one() == 0
    assert (await db.execute(select(func.count()).select_from(DocumentSequence))).scalar_one() == 0
    assert (await db.execute(select(func.count()).select_from(BillingProgramProfile))).scalar_one() == 0

    # La primera factura real sigue siendo la 0001.
    cobro = (await _crear(app_client, headers, project.id, progs["LADWP"].id)).json()
    assert cobro["invoice"]["invoice_number"].endswith("-0001")


async def test_the_particular_preview_renders_the_lines(app_client, db, seeded_org, active_accounting_user):
    from app.modules.crm.models import Customer

    org = seeded_org["org"].id
    cliente = Customer(organization_id=org, legal_name="Moe Szyslak")
    db.add(cliente)
    await db.commit()
    headers = await headers_for(app_client, active_accounting_user.email)
    r = await app_client.post("/api/v1/invoices/preview", json={
        "customer_id": str(cliente.id),
        "lines": [{"kind": "service", "description": "Thermostat replacement", "quantity": 1, "unit_price": 240}],
    }, headers=headers)
    assert r.status_code == 200, r.text
    texto = pdf_text(r.content)
    assert "Moe Szyslak" in texto and "Thermostat replacement" in texto and "$240.00" in texto

    r = await app_client.post("/api/v1/invoices/preview", json={"customer_id": str(cliente.id)}, headers=headers)
    assert r.status_code == 400


async def test_pdfs_of_another_organization_are_invisible(
        app_client, db, seeded_org, active_admin_staff_user, second_org_admin_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()
    ajeno = await headers_for(app_client, second_org_admin_user.email)
    assert (await app_client.get(f"/api/v1/invoices/{cobro['invoice']['id']}/pdf", headers=ajeno)).status_code == 404
    r = await app_client.post("/api/v1/invoices/preview", json={
        "kind": "rebate", "project_id": str(project.id), "program_id": str(progs["TECH"].id)}, headers=ajeno)
    assert r.status_code == 404


async def test_a_technician_cannot_download_invoices(app_client, db, seeded_org, active_admin_staff_user,
                                                     active_technician_user):
    org = seeded_org["org"].id
    progs = await _programas(db, org)
    _, project = await _listo_para_cobrar(db, org)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    cobro = (await _crear(app_client, headers, project.id, progs["TECH"].id)).json()
    tecnico = await headers_for(app_client, "tech@acme-demo.com")
    assert (await app_client.get(f"/api/v1/invoices/{cobro['invoice']['id']}/pdf",
                                 headers=tecnico)).status_code == 403
