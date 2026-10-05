import base64
import io

from PIL import Image


def _png_bytes(color=(255, 0, 0)) -> bytes:
    img = Image.new("RGB", (200, 150), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _signature_png_base64() -> str:
    img = Image.new("RGBA", (300, 120), (255, 255, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _admin_headers(app_client, active_admin_user):
    token = await _login(app_client, "admin@acme-demo.com")
    return {"Authorization": f"Bearer {token}"}


async def _create_customer_and_project(app_client, headers, *, technician_id=None):
    customer_resp = await app_client.post("/api/v1/customers", json={"legal_name": "Field Ops Customer"}, headers=headers)
    customer_id = customer_resp.json()["id"]

    template_resp = await app_client.post("/api/v1/checklist-templates/seed-default", headers=headers)
    assert template_resp.status_code == 201
    template_id = template_resp.json()["id"]

    payload = {
        "customer_id": customer_id,
        "title": "Instalación HVAC — 123 Main St",
        "project_type": "hvac_install",
        "address_street": "123 Main St",
        "apply_checklist_template_id": template_id,
    }
    if technician_id:
        payload["primary_technician_user_id"] = technician_id
    project_resp = await app_client.post("/api/v1/projects", json=payload, headers=headers)
    assert project_resp.status_code == 201
    return customer_id, project_resp.json()["id"], template_id


async def test_project_creation_applies_checklist_template(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    _, project_id, _ = await _create_customer_and_project(app_client, headers)

    resp = await app_client.get(f"/api/v1/projects/{project_id}/checklist", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    from app.modules.field_ops.defaults import DEFAULT_CHECKLIST_TEMPLATE

    assert len(items) == len(DEFAULT_CHECKLIST_TEMPLATE["items"])
    assert any(item["requires_evidence"] for item in items)


async def test_checklist_item_requiring_evidence_blocks_completion_until_uploaded(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    _, project_id, _ = await _create_customer_and_project(app_client, headers)

    checklist = (await app_client.get(f"/api/v1/projects/{project_id}/checklist", headers=headers)).json()
    evidence_item = next(i for i in checklist if i["requires_evidence"])

    resp = await app_client.patch(f"/api/v1/checklist-items/{evidence_item['id']}", json={"is_complete": True}, headers=headers)
    assert resp.status_code == 400

    files = {"file": ("before.jpg", _png_bytes(), "image/jpeg")}
    data = {"checklist_item_id": evidence_item["id"], "latitude": "33.7455", "longitude": "-117.8677"}
    upload_resp = await app_client.post(f"/api/v1/projects/{project_id}/evidence", files=files, data=data, headers=headers)
    assert upload_resp.status_code == 201
    body = upload_resp.json()
    assert body["watermarked"] is True
    assert body["latitude"] == 33.7455

    resp = await app_client.patch(f"/api/v1/checklist-items/{evidence_item['id']}", json={"is_complete": True}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_complete"] is True


async def test_evidence_download_returns_watermarked_file(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    _, project_id, _ = await _create_customer_and_project(app_client, headers)

    files = {"file": ("photo.jpg", _png_bytes(), "image/jpeg")}
    data = {"category": "additional_photo"}
    upload_resp = await app_client.post(f"/api/v1/projects/{project_id}/evidence", files=files, data=data, headers=headers)
    evidence_id = upload_resp.json()["id"]

    resp = await app_client.get(f"/api/v1/evidence/{evidence_id}/file", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert len(resp.content) > 0


async def test_attestation_requires_both_signatures_before_pdf_generated(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    _, project_id, _ = await _create_customer_and_project(app_client, headers)

    resp = await app_client.post(
        f"/api/v1/projects/{project_id}/attestation/technician-sign",
        json={"signature_base64": _signature_png_base64()},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_fully_signed"] is False
    assert body["pdf_path"] is None

    resp = await app_client.post(
        f"/api/v1/projects/{project_id}/attestation/customer-sign",
        json={"customer_name": "Rosa Gutierrez", "signature_base64": _signature_png_base64()},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_fully_signed"] is True

    attestation_resp = await app_client.get(f"/api/v1/projects/{project_id}/attestation", headers=headers)
    attestation_id = attestation_resp.json()["id"]

    pdf_resp = await app_client.get(f"/api/v1/attestations/{attestation_id}/pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content[:4] == b"%PDF"


async def test_evidence_upload_rejects_unsupported_file_types(app_client, active_admin_user, seeded_org):
    """Solo se aceptan fotos y videos; cualquier otro tipo se rechaza con 400."""
    headers = await _admin_headers(app_client, active_admin_user)
    _, project_id, _ = await _create_customer_and_project(app_client, headers)

    files = {"file": ("contrato.pdf", b"%PDF-1.4 fake", "application/pdf")}
    resp = await app_client.post(f"/api/v1/projects/{project_id}/evidence", files=files, data={"category": "additional_photo"}, headers=headers)
    assert resp.status_code == 400
    assert "application/pdf" in resp.json()["detail"]


async def test_evidence_upload_rejects_a_corrupt_video_without_leaking_internals(
    app_client, active_admin_user, seeded_org
):
    """Un archivo que dice ser video pero no lo es debe dar 400 con un mensaje
    para el usuario. Antes devolvía 422 con el volcado de error de ffmpeg, que
    expone rutas internas del servidor y versiones de librerías."""
    headers = await _admin_headers(app_client, active_admin_user)
    _, project_id, _ = await _create_customer_and_project(app_client, headers)

    files = {"file": ("clip.mp4", b"not-really-a-video", "video/mp4")}
    resp = await app_client.post(f"/api/v1/projects/{project_id}/evidence", files=files, data={"category": "additional_photo"}, headers=headers)
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "video" in detail.lower()
    for leak in ("/tmp/", "ffmpeg", "libav", "Error opening input"):
        assert leak not in detail, f"el detalle filtra información interna: {detail}"


async def test_field_technician_only_sees_assigned_projects(app_client, active_admin_user, active_technician_user, seeded_org):
    admin_headers = await _admin_headers(app_client, active_admin_user)
    tech_id = str(active_technician_user.id)
    await _create_customer_and_project(app_client, admin_headers, technician_id=tech_id)
    await _create_customer_and_project(app_client, admin_headers)  # unassigned, other technician's

    tech_token = await _login(app_client, "tech@acme-demo.com")
    tech_headers = {"Authorization": f"Bearer {tech_token}"}

    resp = await app_client.get("/api/v1/projects", headers=tech_headers)
    assert resp.status_code == 200
    projects = resp.json()
    assert len(projects) == 1
    assert projects[0]["primary_technician_user_id"] == tech_id


async def test_overdue_tasks_endpoint_and_scoping(app_client, active_admin_user, active_technician_user, seeded_org):
    from datetime import datetime, timedelta, timezone

    admin_headers = await _admin_headers(app_client, active_admin_user)
    tech_id = str(active_technician_user.id)
    _, tech_project_id, _ = await _create_customer_and_project(app_client, admin_headers, technician_id=tech_id)
    _, other_project_id, _ = await _create_customer_and_project(app_client, admin_headers)

    past_due = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    future_due = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    overdue_task_resp = await app_client.post(
        f"/api/v1/projects/{tech_project_id}/tasks", json={"title": "Confirmar cita", "due_date": past_due}, headers=admin_headers
    )
    assert overdue_task_resp.status_code == 201

    not_overdue_task_resp = await app_client.post(
        f"/api/v1/projects/{tech_project_id}/tasks", json={"title": "Preparar equipo", "due_date": future_due}, headers=admin_headers
    )
    assert not_overdue_task_resp.status_code == 201

    other_overdue_resp = await app_client.post(
        f"/api/v1/projects/{other_project_id}/tasks", json={"title": "Tarea de otro proyecto", "due_date": past_due}, headers=admin_headers
    )
    assert other_overdue_resp.status_code == 201

    # Admin (projects.read_all) sees every overdue task across both projects.
    admin_overdue = await app_client.get("/api/v1/tasks/overdue", headers=admin_headers)
    assert admin_overdue.status_code == 200
    assert len(admin_overdue.json()) == 2
    assert all(t["is_overdue"] for t in admin_overdue.json())

    # Technician (projects.read_assigned only) sees only their own project's overdue task.
    tech_token = await _login(app_client, "tech@acme-demo.com")
    tech_headers = {"Authorization": f"Bearer {tech_token}"}
    tech_overdue = await app_client.get("/api/v1/tasks/overdue", headers=tech_headers)
    assert tech_overdue.status_code == 200
    assert len(tech_overdue.json()) == 1
    assert tech_overdue.json()[0]["title"] == "Confirmar cita"
    assert tech_overdue.json()[0]["project_title"]


async def test_task_comments_create_and_list(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    _, project_id, _ = await _create_customer_and_project(app_client, headers)

    task_resp = await app_client.post(f"/api/v1/projects/{project_id}/tasks", json={"title": "Confirmar cita"}, headers=headers)
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]

    empty = await app_client.get(f"/api/v1/tasks/{task_id}/comments", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == []

    comment_resp = await app_client.post(
        f"/api/v1/tasks/{task_id}/comments", json={"body": "Cliente confirmó para el jueves 9am."}, headers=headers
    )
    assert comment_resp.status_code == 201
    assert comment_resp.json()["body"] == "Cliente confirmó para el jueves 9am."

    listing = await app_client.get(f"/api/v1/tasks/{task_id}/comments", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_field_technician_cannot_touch_task_on_unassigned_project(
    app_client, active_admin_user, active_technician_user, seeded_org
):
    """A technician's tasks.manage permission only covers their own assigned
    projects (spec: same assigned-vs-all scoping as everywhere else in
    field_ops) — patching or commenting on a task from a project they are
    NOT assigned to must 404, not silently succeed just because the org
    matches."""
    admin_headers = await _admin_headers(app_client, active_admin_user)
    _, other_project_id, _ = await _create_customer_and_project(app_client, admin_headers)  # not assigned to the tech

    task_resp = await app_client.post(
        f"/api/v1/projects/{other_project_id}/tasks", json={"title": "Reparar ducto"}, headers=admin_headers
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]

    tech_token = await _login(app_client, "tech@acme-demo.com")
    tech_headers = {"Authorization": f"Bearer {tech_token}"}

    patch_resp = await app_client.patch(f"/api/v1/tasks/{task_id}", json={"status": "done"}, headers=tech_headers)
    assert patch_resp.status_code == 404

    comment_resp = await app_client.post(
        f"/api/v1/tasks/{task_id}/comments", json={"body": "intento"}, headers=tech_headers
    )
    assert comment_resp.status_code == 404


async def test_legacy_project_patch_only_edits_descriptive_data(app_client, active_admin_user, seeded_org):
    headers = await _admin_headers(app_client, active_admin_user)
    _, project_id, _ = await _create_customer_and_project(app_client, headers)
    url = f"/api/v1/projects/{project_id}"
    assert (await app_client.patch(url, json={"status": "completed"}, headers=headers)).status_code == 422
    r = await app_client.patch(url, json={"notes": "Portón azul"}, headers=headers)
    assert r.status_code == 200 and r.json()["notes"] == "Portón azul" and r.json()["status"] != "completed"
