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
matrix grants it (e.g. commercial_manager can read projects/invoices).
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
# CRM module — field_technician has none of leads/customers.create-update/
# contacts/opportunities/quotes/activities permissions, so every CRM
# read/write endpoint must reject it.
# ---------------------------------------------------------------------------

CRM_GET_ENDPOINTS = [
    "/api/v1/leads",
    f"/api/v1/leads/{RANDOM_ID}",
    "/api/v1/customers",
    f"/api/v1/customers/{RANDOM_ID}",
    f"/api/v1/customers/{RANDOM_ID}/timeline",
    "/api/v1/pipeline-stages",
    "/api/v1/funder-statuses",
    "/api/v1/opportunities",
    "/api/v1/activities",
    "/api/v1/quotes",
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
        "/api/v1/leads", json={"full_name": "Jane Doe"}, headers=_auth(token)
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
        "/api/v1/opportunities",
        json={"customer_id": RANDOM_ID, "title": "New opp", "stage_code": "new"},
        headers=_auth(token),
    )
    assert resp.status_code == 403

    resp = await app_client.post(
        "/api/v1/activities",
        json={"type": "call", "subject": "Follow up", "owner_user_id": RANDOM_ID},
        headers=_auth(token),
    )
    assert resp.status_code == 403

    resp = await app_client.post(
        "/api/v1/quotes", json={"customer_id": RANDOM_ID}, headers=_auth(token)
    )
    assert resp.status_code == 403


async def test_finance_user_forbidden_from_crm_management(app_client, active_finance_user):
    """finance_user only has customers.read in CRM — everything else must 403."""
    token = await _login(app_client, "finance@acme-demo.com")
    for path in ["/api/v1/leads", "/api/v1/opportunities", "/api/v1/activities", "/api/v1/quotes"]:
        resp = await app_client.get(path, headers=_auth(token))
        assert resp.status_code == 403, f"{path} -> {resp.status_code}"

    # customers.read IS granted, so this must succeed.
    resp = await app_client.get("/api/v1/customers", headers=_auth(token))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Field ops module — commercial_manager has projects.read_all and
# invoices.read but none of the field_ops write/management permissions
# (tasks.manage, checklists.manage, evidence.create), so those must 403.
# ---------------------------------------------------------------------------

async def test_commercial_manager_forbidden_from_field_ops_management(app_client, active_commercial_manager_user):
    token = await _login(app_client, "commercial@acme-demo.com")

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
    # but not checklists.manage or projects.create.
    resp = await app_client.post("/api/v1/checklist-templates", json={"name": "X", "items": []}, headers=_auth(token))
    assert resp.status_code == 403

    resp = await app_client.patch(f"/api/v1/checklist-items/{RANDOM_ID}", json={"is_complete": True}, headers=_auth(token))
    assert resp.status_code == 403

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
# Billing module — field_technician and commercial_manager both lack every
# invoices.* permission (commercial_manager only has invoices.read).
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


async def test_commercial_manager_can_read_but_not_write_invoices(app_client, active_commercial_manager_user):
    token = await _login(app_client, "commercial@acme-demo.com")

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


async def test_finance_user_can_manage_invoices_end_to_end_permission_gate(app_client, active_finance_user):
    """finance_user has the full invoices.* set plus dashboards.finance —
    confirm every billing read endpoint's permission gate lets it through
    (functional create/payment/status-transition flows are already covered
    in test_billing.py; this asserts the *permission* layer specifically)."""
    token = await _login(app_client, "finance@acme-demo.com")

    for path in ["/api/v1/invoices", "/api/v1/invoices-export.csv", "/api/v1/finance/dashboard"]:
        resp = await app_client.get(path, headers=_auth(token))
        assert resp.status_code == 200, f"{path} -> {resp.status_code} {resp.text}"

    # finance_user has no projects.read_all/read_assigned, so field_ops stays out of reach.
    resp = await app_client.get("/api/v1/projects", headers=_auth(token))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# read_only role — carries zero permissions in the default catalog (granted
# per-resource individually by an admin per spec 5.3). Every endpoint in
# every module must reject it, which is a good sanity check that no route
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


async def test_read_only_role_forbidden_everywhere(app_client, active_read_only_user):
    token = await _login(app_client, "readonly@acme-demo.com")
    for path in ALL_MODULE_GET_ENDPOINTS:
        resp = await app_client.get(path, headers=_auth(token))
        assert resp.status_code == 403, f"{path} -> {resp.status_code}"


# ---------------------------------------------------------------------------
# Org isolation sanity check across the newer modules (Users-module isolation
# is already covered in test_rbac.py; here we confirm the same holds for
# field_ops/billing, which are newer and org-scope every query by hand).
# ---------------------------------------------------------------------------

async def test_project_manager_sees_empty_lists_for_unrelated_org_data(app_client, active_project_manager_user, db, seeded_org):
    """Regression guard: project_manager has projects.read_all/invoices.read,
    but with no data seeded in this org, list endpoints must return an empty
    list rather than leaking rows from another test's org (each test gets a
    fresh in-memory DB, so this also doubles as a not-found-isn't-500 check)."""
    token = await _login(app_client, "pm@acme-demo.com")
    resp = await app_client.get("/api/v1/projects", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await app_client.get("/api/v1/invoices", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []
