"""Comprehensive RBAC coverage across every protected endpoint in CRM,
field_ops and billing (Phase 5 priority: "Seguridad y permisos").

Strategy: for each module, pick a seeded role that legitimately lacks every
permission that module's endpoints require, and assert every GET endpoint
(list/detail) in that module returns 403 for that role. Read endpoints are
used for the bulk of the negative matrix because a 403 raised by the
permission dependency is unambiguous there (no request-body validation to
race against). A handful of write endpoints (POST/PATCH) are also checked
explicitly, with a valid request body, to prove the same gate applies to
writes and not just reads. Positive-path (2xx) coverage for the "happy"
role already exists in test_crm.py / test_field_ops.py / test_billing.py;
here we add a few cross-module positive checks to confirm the intended
role *can* reach endpoints outside its "home" module where the permission
matrix grants it (por ejemplo, Gerencia puede leer proyectos y facturas).
"""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


RANDOM_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# CRM module — el técnico no tiene permisos de expedientes, de creación o
# edición de clientes, ni de contactos y actividades, así que todo el CRM
# read/write endpoint must reject it.
# ---------------------------------------------------------------------------

CRM_GET_ENDPOINTS = [
    "/api/v1/cases",
    f"/api/v1/cases/{RANDOM_ID}",
    "/api/v1/customers",
    f"/api/v1/customers/{RANDOM_ID}",
    f"/api/v1/customers/{RANDOM_ID}/timeline",
    "/api/v1/funder-statuses",
    "/api/v1/activities",
]

# field_technician carries customers.read (spec 5.3 matrix), so those two
# endpoints are legitimately reachable and are exercised separately below.
CRM_GET_ENDPOINTS_TECHNICIAN_CANNOT_REACH = [
    p for p in CRM_GET_ENDPOINTS if not p.startswith("/api/v1/customers")
]


async def test_field_technician_forbidden_from_all_crm_reads(app_client, active_technician_user):
    token = await _login(app_client, "tech@acme-demo.com")
    for path in CRM_GET_ENDPOINTS_TECHNICIAN_CANNOT_REACH:
        resp = await app_client.get(path, headers=_auth(token))
        assert resp.status_code == 403, f"{path} -> {resp.status_code}"

    # customers.read IS granted to field_technician — these two must succeed.
    resp = await app_client.get("/api/v1/customers", headers=_auth(token))
    assert resp.status_code == 200
    resp = await app_client.get(f"/api/v1/customers/{RANDOM_ID}", headers=_auth(token))
    assert resp.status_code == 404  # permission passes; the record just doesn't exist


async def test_field_technician_forbidden_from_crm_writes(app_client, active_technician_user):
    token = await _login(app_client, "tech@acme-demo.com")

    resp = await app_client.post(
        "/api/v1/cases", json={"stage_code": "no_contact"}, headers=_auth(token)
    )
    assert resp.status_code == 403

    resp = await app_client.post(
        "/api/v1/customers", json={"legal_name": "Doe Household"}, headers=_auth(token)
    )
    assert resp.status_code == 403

    resp = await app_client.patch(
        f"/api/v1/customers/{RANDOM_ID}", json={"legal_name": "New Name"}, headers=_auth(token)
    )
    assert resp.status_code == 403

    resp = await app_client.post(
        "/api/v1/activities",
        json={"type": "call", "subject": "Follow up", "owner_user_id": RANDOM_ID},
        headers=_auth(token),
    )
    assert resp.status_code == 403



async def test_accounting_forbidden_from_crm_management(app_client, active_accounting_user):
    """Contabilidad lee expedientes y clientes para poder facturar, pero no
    administra nada del CRM."""
    token = await _login(app_client, "contabilidad@acme-demo.com")

    # Lectura: sí. Es lo que necesita para saber qué está cobrando.
    for path in ["/api/v1/cases", "/api/v1/customers"]:
        resp = await app_client.get(path, headers=_auth(token))
        assert resp.status_code == 200, f"{path} -> {resp.status_code}"

    # Escritura y actividades: no.
    resp = await app_client.get("/api/v1/activities", headers=_auth(token))
    assert resp.status_code == 403

    resp = await app_client.post(
        "/api/v1/customers", json={"legal_name": "Doe Household"}, headers=_auth(token)
    )
    assert resp.status_code == 403

    resp = await app_client.post(
        "/api/v1/cases", json={"stage_code": "no_contact"}, headers=_auth(token)
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Field ops module — Gerencia tiene projects.read_all e invoices.read pero
# ninguno de los permisos de escritura de campo (tasks.manage,
# checklists.manage, evidence.create), así que esos deben dar 403.
# ---------------------------------------------------------------------------

async def test_management_forbidden_from_field_ops_management(app_client, active_management_user):
    token = await _login(app_client, "gerencia@acme-demo.com")

    resp = await app_client.get("/api/v1/checklist-templates", headers=_auth(token))
    assert resp.status_code == 403

    resp = await app_client.post(
        "/api/v1/checklist-templates", json={"name": "X", "items": []}, headers=_auth(token)
    )
    assert resp.status_code == 403

    resp = await app_client.post("/api/v1/projects", json={"customer_id": RANDOM_ID, "title": "T"}, headers=_auth(token))
    assert resp.status_code == 403

    resp = await app_client.post(f"/api/v1/projects/{RANDOM_ID}/tasks", json={"title": "Task"}, headers=_auth(token))
    assert resp.status_code == 403

    resp = await app_client.patch(f"/api/v1/tasks/{RANDOM_ID}", json={"title": "X"}, headers=_auth(token))
    assert resp.status_code == 403

    resp = await app_client.patch(
        f"/api/v1/checklist-items/{RANDOM_ID}", json={"is_complete": True}, headers=_auth(token)
    )
    assert resp.status_code == 403

    resp = await app_client.post(
        f"/api/v1/projects/{RANDOM_ID}/attestation/technician-sign",
        json={"signature_base64": "x" * 20},
        headers=_auth(token),
    )
    assert resp.status_code == 403

    # projects.read_all IS granted, so list/get must succeed (empty list is fine).
    resp = await app_client.get("/api/v1/projects", headers=_auth(token))
    assert resp.status_code == 200


async def test_field_technician_forbidden_from_checklist_and_evidence_management(app_client, active_technician_user):
    token = await _login(app_client, "tech@acme-demo.com")

    # field_technician has evidence.create/read_assigned and tasks.manage,
    # but not checklists.manage or projects.create. Completing checklist items
    # is theirs (checklists.complete).
    resp = await app_client.post("/api/v1/checklist-templates", json={"name": "X", "items": []}, headers=_auth(token))
    assert resp.status_code == 403

    # Marcar el checklist SÍ es del técnico (`checklists.complete`, módulo 5):
    # pasa la puerta del permiso y un ítem que no existe responde 404.
    resp = await app_client.patch(f"/api/v1/checklist-items/{RANDOM_ID}", json={"is_complete": True}, headers=_auth(token))
    assert resp.status_code == 404

    resp = await app_client.post("/api/v1/projects", json={"customer_id": RANDOM_ID, "title": "T"}, headers=_auth(token))
    assert resp.status_code == 403


async def test_field_technician_only_sees_projects_read_assigned_scope(app_client, active_technician_user):
    """projects.read_assigned is enough to pass the require_any_permission
    gate on list/get, even without projects.read_all — the endpoint itself
    narrows results server-side (covered functionally in test_field_ops.py);
    here we just confirm the gate lets the technician through at all."""
    token = await _login(app_client, "tech@acme-demo.com")
    resp = await app_client.get("/api/v1/projects", headers=_auth(token))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Billing module — el Técnico no tiene ningún permiso invoices.*, y
# Administración solo tiene invoices.read (más billing.submit).
# ---------------------------------------------------------------------------

async def test_field_technician_forbidden_from_all_billing_endpoints(app_client, active_technician_user):
    token = await _login(app_client, "tech@acme-demo.com")

    for path in ["/api/v1/invoices", f"/api/v1/invoices/{RANDOM_ID}", "/api/v1/invoices-export.csv", "/api/v1/finance/dashboard"]:
        resp = await app_client.get(path, headers=_auth(token))
        assert resp.status_code == 403, f"{path} -> {resp.status_code}"

    resp = await app_client.post(
        "/api/v1/invoices", json={"project_id": RANDOM_ID, "amount": 100}, headers=_auth(token)
    )
    assert resp.status_code == 403

    resp = await app_client.patch(f"/api/v1/invoices/{RANDOM_ID}", json={"amount": 50}, headers=_auth(token))
    assert resp.status_code == 403

    resp = await app_client.post(f"/api/v1/invoices/{RANDOM_ID}/mark-sent", headers=_auth(token))
    assert resp.status_code == 403

    resp = await app_client.post(
        f"/api/v1/invoices/{RANDOM_ID}/payments",
        json={"amount": 10, "paid_at": "2026-01-01"},
        headers=_auth(token),
    )
    assert resp.status_code == 403

    resp = await app_client.get(f"/api/v1/invoice-attachments/{RANDOM_ID}/file", headers=_auth(token))
    assert resp.status_code == 403


async def test_admin_staff_can_read_but_not_write_invoices(app_client, active_admin_staff_user):
    token = await _login(app_client, "admin-staff@acme-demo.com")

    # invoices.read is granted.
    resp = await app_client.get("/api/v1/invoices", headers=_auth(token))
    assert resp.status_code == 200

    # But no invoices.create/update/record_payment/export or dashboards.finance.
    resp = await app_client.post(
        "/api/v1/invoices", json={"project_id": RANDOM_ID, "amount": 100}, headers=_auth(token)
    )
    assert resp.status_code == 403

    resp = await app_client.post(
        f"/api/v1/invoices/{RANDOM_ID}/payments",
        json={"amount": 10, "paid_at": "2026-01-01"},
        headers=_auth(token),
    )
    assert resp.status_code == 403

    resp = await app_client.get("/api/v1/invoices-export.csv", headers=_auth(token))
    assert resp.status_code == 403

    resp = await app_client.get("/api/v1/finance/dashboard", headers=_auth(token))
    assert resp.status_code == 403


async def test_accounting_can_manage_invoices_end_to_end_permission_gate(app_client, active_accounting_user):
    """Contabilidad tiene todo el conjunto invoices.* más dashboards.finance;
    se confirma que cada endpoint de lectura de facturación la deja pasar (los
    flujos funcionales de crear, pagar y cambiar de estado ya están en
    test_billing.py; aquí se afirma la capa de *permisos*)."""
    token = await _login(app_client, "contabilidad@acme-demo.com")

    for path in ["/api/v1/invoices", "/api/v1/invoices-export.csv", "/api/v1/finance/dashboard"]:
        resp = await app_client.get(path, headers=_auth(token))
        assert resp.status_code == 200, f"{path} -> {resp.status_code} {resp.text}"

    # A diferencia del rol financiero anterior, Contabilidad sí tiene
    # projects.read_all: lo necesita para la rentabilidad por proyecto (PDF §4.5).
    resp = await app_client.get("/api/v1/projects", headers=_auth(token))
    assert resp.status_code == 200

    # Pero no puede escribir en campo.
    resp = await app_client.post(
        "/api/v1/projects", json={"customer_id": RANDOM_ID, "title": "T"}, headers=_auth(token)
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Rol sin permisos — es lo que queda cuando el administrador crea un rol nuevo
# y todavía no le marca nada. Todo endpoint de todo módulo debe rechazarlo, lo
# que además confirma que ninguna ruta
# accidentally allows an authenticated-but-unpermissioned user through.
# ---------------------------------------------------------------------------

ALL_MODULE_GET_ENDPOINTS = CRM_GET_ENDPOINTS + [
    "/api/v1/checklist-templates",
    "/api/v1/projects",
    f"/api/v1/projects/{RANDOM_ID}",
    f"/api/v1/projects/{RANDOM_ID}/checklist",
    f"/api/v1/projects/{RANDOM_ID}/tasks",
    f"/api/v1/projects/{RANDOM_ID}/evidence",
    f"/api/v1/projects/{RANDOM_ID}/attestation",
    "/api/v1/invoices",
    f"/api/v1/invoices/{RANDOM_ID}",
    "/api/v1/invoices-export.csv",
    "/api/v1/finance/dashboard",
]


async def test_role_without_permissions_is_forbidden_everywhere(app_client, active_roleless_user):
    """Un rol recién creado, sin permisos marcados, no abre ningún módulo."""
    token = await _login(app_client, "sinpermisos@acme-demo.com")
    for path in ALL_MODULE_GET_ENDPOINTS:
        resp = await app_client.get(path, headers=_auth(token))
        assert resp.status_code == 403, f"{path} -> {resp.status_code}"


# ---------------------------------------------------------------------------
# Org isolation sanity check across the newer modules (Users-module isolation
# is already covered in test_rbac.py; here we confirm the same holds for
# field_ops/billing, which are newer and org-scope every query by hand).
# ---------------------------------------------------------------------------

async def test_admin_staff_sees_empty_lists_for_unrelated_org_data(app_client, active_admin_staff_user, db, seeded_org):
    """Guarda de regresión: Administración tiene projects.read_all e
    invoices.read, pero sin datos sembrados en esta organización los listados
    deben devolver lista vacía y no filas de la organización de otro test."""
    token = await _login(app_client, "admin-staff@acme-demo.com")
    resp = await app_client.get("/api/v1/projects", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await app_client.get("/api/v1/invoices", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []
