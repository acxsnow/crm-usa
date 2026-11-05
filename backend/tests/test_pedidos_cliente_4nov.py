"""Pedidos del cliente del 4 nov 2026: permiso «En trámite», cotización con
artículos de bodega, búsqueda de cliente por dirección y Administración con los
permisos de Contabilidad."""
import uuid
from datetime import date

import pytest

from app.modules.cases import service as case_service
from app.modules.cases import stages
from app.modules.cases.models import Case
from app.modules.crm.models import Customer
from app.modules.field_ops import case_hooks
from app.modules.field_ops.catalogs import PermitStatus
from app.modules.field_ops.models import Permit
from app.modules.field_ops.permits import all_allow_install, all_cleared
from app.modules.warehouse.models import WarehouseItem
from app.shared.errors import InvalidInputError
from app.shared.permissions import DEFAULT_ROLE_PERMISSIONS
from tests.field_helpers import approved_case_with_project, headers_for, refreshed_case


@pytest.fixture(autouse=True)
def _clean_registries():
    yield
    stages.clear_guards()
    stages.clear_effects()
    case_hooks._reset_for_tests()


HOY = date.today()


# --- Permiso «En trámite» ---------------------------------------------------

def test_in_process_allows_install_but_not_billing():
    """Deja instalar como «No requerido», pero el cobro sigue pidiendo el aprobado."""
    permiso = Permit(status=PermitStatus.in_process, jurisdiction="Miami-Dade")
    assert all_allow_install([permiso], HOY) is True
    assert all_cleared([permiso], HOY) is False


async def test_an_in_process_permit_lets_the_case_reach_ready_to_install(
        app_client, db, seeded_org, active_admin_staff_user):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    resp = await app_client.post(f"/api/v1/projects/{project.id}/permits",
                                 json={"jurisdiction": "Miami-Dade", "status": "in_process"}, headers=headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["allows_install"] is True and resp.json()["is_cleared"] is False
    assert (await refreshed_case(db, case)).stage_code == "ready_to_install"

    catalogos = (await app_client.get("/api/v1/field-ops/catalogs", headers=headers)).json()
    assert catalogos["permit_statuses"]["in_process"] == "En trámite"


# --- Cotización con artículos de bodega -------------------------------------

async def _articulo(db, org_id, nombre="Caja de aire"):
    item = WarehouseItem(organization_id=org_id, name=nombre, unit_cost=30, sale_price=50)
    db.add(item)
    await db.commit()
    return item


async def test_quote_lines_remember_the_warehouse_item_and_flag_the_rest(
        app_client, db, seeded_org, active_admin_staff_user):
    org_id = seeded_org["org"].id
    cliente = Customer(organization_id=org_id, legal_name="José Miranda")
    db.add(cliente)
    await db.commit()
    item = await _articulo(db, org_id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    lineas = [
        {"kind": "material", "description": "Caja de aire", "quantity": 1, "unit_price": 50,
         "warehouse_item_id": str(item.id)},
        {"kind": "material", "description": "Soporte especial", "quantity": 1, "unit_price": 15},
        # La mano de obra no está en bodega: ni se liga ni queda por validar.
        {"kind": "labor", "description": "Instalación", "quantity": 1, "unit_price": 20,
         "warehouse_item_id": str(item.id)},
    ]
    r = await app_client.post("/api/v1/billing/quotes", json={"customer_id": str(cliente.id), "lines": lineas},
                              headers=headers)
    assert r.status_code == 201, r.text
    q = r.json()
    assert [(l["warehouse_item_id"], l["needs_warehouse_check"]) for l in q["lines"]] == [
        (str(item.id), False), (None, True), (None, False)]

    # La versión siguiente conserva el vínculo.
    await app_client.post(f"/api/v1/billing/quotes/{q['id']}/send", headers=headers)
    v2 = (await app_client.post(f"/api/v1/billing/quotes/{q['id']}/revise", headers=headers)).json()
    assert v2["lines"][0]["warehouse_item_id"] == str(item.id)


async def test_a_warehouse_item_of_another_org_is_rejected(
        app_client, db, seeded_org, active_admin_staff_user, second_org_admin_user):
    cliente = Customer(organization_id=seeded_org["org"].id, legal_name="Ned Flanders")
    db.add(cliente)
    await db.commit()
    ajeno = await _articulo(db, second_org_admin_user.organization_id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    r = await app_client.post("/api/v1/billing/quotes", json={"customer_id": str(cliente.id), "lines": [
        {"kind": "material", "description": "X", "quantity": 1, "unit_price": 5, "warehouse_item_id": str(ajeno.id)}]},
        headers=headers)
    assert r.status_code == 400
    assert r.json()["code"] == "quote_item_not_found"


# --- Buscar cliente por dirección -------------------------------------------

async def test_customers_are_found_by_billing_or_case_address(app_client, db, seeded_org, active_admin_staff_user):
    org_id = seeded_org["org"].id
    por_factura = Customer(organization_id=org_id, legal_name="Homer", billing_address="12 Desert Palm Rd, Mesa")
    por_casa = Customer(organization_id=org_id, legal_name="Marge")
    otro = Customer(organization_id=org_id, legal_name="Bart", billing_address="1 Main St")
    db.add_all([por_factura, por_casa, otro])
    await db.flush()
    db.add(Case(organization_id=org_id, case_number="EXP-T-1", stage_code="new_prospect", customer_id=por_casa.id,
                address_street="88 Desert Palm Rd", address_unit="Spc 4"))
    await db.commit()
    headers = await headers_for(app_client, active_admin_staff_user.email)
    nombres = {c["legal_name"] for c in (await app_client.get("/api/v1/customers?q=desert palm", headers=headers)).json()}
    assert nombres == {"Homer", "Marge"}
    assert {c["legal_name"] for c in (await app_client.get("/api/v1/customers?q=spc 4", headers=headers)).json()} == {"Marge"}


# --- Administración con los permisos de Contabilidad ------------------------

def test_admin_staff_has_every_accounting_permission():
    assert set(DEFAULT_ROLE_PERMISSIONS["accounting"]) <= set(DEFAULT_ROLE_PERMISSIONS["admin_staff"])


async def test_admin_staff_opens_the_accounting(app_client, seeded_org, active_admin_staff_user):
    headers = await headers_for(app_client, active_admin_staff_user.email)
    assert (await app_client.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200


# --- Respuestas del cliente del 5 nov 2026 ----------------------------------

async def test_by_default_a_filed_permit_allows_installing(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    r = await app_client.post(f"/api/v1/projects/{project.id}/permits",
                              json={"jurisdiction": "Phoenix", "filed_on": str(HOY)}, headers=headers)
    assert (r.json()["allows_install"], r.json()["is_cleared"]) == (True, False)
    assert (await refreshed_case(db, case)).stage_code == "ready_to_install"


async def test_the_case_does_not_close_without_the_approved_permit(app_client, db, seeded_org, active_admin_staff_user):
    case, project = await approved_case_with_project(db, seeded_org["org"].id)
    headers = await headers_for(app_client, active_admin_staff_user.email)
    permiso = (await app_client.post(f"/api/v1/projects/{project.id}/permits",
                                     json={"jurisdiction": "Phoenix", "status": "in_process"}, headers=headers)).json()
    case = await refreshed_case(db, case)
    with pytest.raises(InvalidInputError) as error:
        await case_service.transition(db, case=case, to_stage="closed", actor_id=uuid.uuid4(),
                                      actor_permissions=stages.SYSTEM_ACTOR)
    assert error.value.code == "permit_required_to_close"

    r = await app_client.patch(f"/api/v1/permits/{permiso['id']}", json={"status": "approved", "approved_on": str(HOY)},
                               headers=headers)
    assert r.status_code == 200, r.text
    case = await refreshed_case(db, case)
    case = await case_service.transition(db, case=case, to_stage="closed", actor_id=uuid.uuid4(),
                                         actor_permissions=stages.SYSTEM_ACTOR)
    assert case.stage_code == "closed"


async def test_a_case_without_permits_or_installation_closes_administratively(db, seeded_org):
    case, _ = await approved_case_with_project(db, seeded_org["org"].id)
    case = await case_service.transition(db, case=case, to_stage="closed", actor_id=uuid.uuid4(),
                                         actor_permissions=stages.SYSTEM_ACTOR)
    assert case.stage_code == "closed"
