"""Phase 5 OWASP-review fixes: path traversal in storage, invoice attachment
upload limits, pagination on list endpoints, and the security-headers
middleware. Each test targets one concrete finding rather than being a
generic smoke test."""
import io
import uuid

from app.shared.files.storage import _sanitize_filename, save_bytes


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Path traversal (CWE-22)
# ---------------------------------------------------------------------------

def test_sanitize_filename_strips_traversal_sequences():
    assert _sanitize_filename("../../etc/passwd") == "passwd"
    assert _sanitize_filename("../../../secrets.env") == "secrets.env"
    assert _sanitize_filename("/etc/shadow") == "shadow"
    assert _sanitize_filename("normal_photo.jpg") == "normal_photo.jpg"
    assert _sanitize_filename(None) == "file"
    assert _sanitize_filename("..") == "file"


def test_save_bytes_never_escapes_storage_root(tmp_path, monkeypatch):
    from app.shared.files import storage as storage_module

    monkeypatch.setattr(storage_module.settings, "STORAGE_DIR", str(tmp_path / "storage"))
    org_id = uuid.uuid4()

    relative_path = save_bytes(
        organization_id=org_id, subfolder="evidence", filename="../../../../etc/passwd", data=b"not actually passwd",
    )
    resolved = (tmp_path / "storage" / relative_path).resolve()
    storage_root = (tmp_path / "storage").resolve()
    assert storage_root in resolved.parents
    assert resolved.name.endswith("_passwd")
    assert resolved.read_bytes() == b"not actually passwd"


# ---------------------------------------------------------------------------
# Invoice attachment upload validation (previously unrestricted upload)
# ---------------------------------------------------------------------------

async def test_invoice_attachment_rejects_disallowed_mime_type(app_client, db, active_admin_user, seeded_org):
    from app.modules.crm.models import Customer
    from app.modules.field_ops.models import Project

    token = await _login(app_client, "admin@acme-demo.com")

    customer = Customer(organization_id=seeded_org["org"].id, legal_name="Test Household")
    db.add(customer)
    await db.flush()
    project = Project(organization_id=seeded_org["org"].id, customer_id=customer.id, title="Install")
    db.add(project)
    await db.commit()
    await db.refresh(project)

    inv_resp = await app_client.post(
        "/api/v1/invoices", json={"project_id": str(project.id), "amount": 500}, headers=_auth(token)
    )
    assert inv_resp.status_code == 201
    invoice_id = inv_resp.json()["id"]

    resp = await app_client.post(
        f"/api/v1/invoices/{invoice_id}/attachments",
        files={"file": ("script.exe", io.BytesIO(b"MZ..."), "application/x-msdownload")},
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert "photos, scans, or PDF" in resp.json()["detail"]

    ok_resp = await app_client.post(
        f"/api/v1/invoices/{invoice_id}/attachments",
        files={"file": ("proof.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        headers=_auth(token),
    )
    assert ok_resp.status_code == 201
    assert ok_resp.json()["original_filename"] == "proof.pdf"


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

async def test_list_is_paginated_with_total_count_header(app_client, active_admin_user, seeded_org):
    token = await _login(app_client, "admin@acme-demo.com")

    for i in range(5):
        resp = await app_client.post(
            "/api/v1/customers", json={"legal_name": f"Cliente {i}"}, headers=_auth(token)
        )
        assert resp.status_code == 201

    resp = await app_client.get("/api/v1/customers?limit=2&offset=0", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert resp.headers["X-Total-Count"] == "5"

    resp = await app_client.get("/api/v1/customers?limit=2&offset=4", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.headers["X-Total-Count"] == "5"


async def test_pagination_limit_is_capped(app_client, active_admin_user):
    token = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.get("/api/v1/customers?limit=99999", headers=_auth(token))
    assert resp.status_code == 422  # exceeds MAX_LIMIT, rejected by validation


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

async def test_security_headers_present_on_every_response(app_client):
    resp = await app_client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert "Permissions-Policy" in resp.headers
