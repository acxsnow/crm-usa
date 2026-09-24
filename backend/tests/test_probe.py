import pytest

async def test_probe(app_client, active_admin_user, seeded_org):
    from tests.test_field_ops import _admin_headers, _create_customer_and_project
    headers = await _admin_headers(app_client, active_admin_user)
    _, project_id, _ = await _create_customer_and_project(app_client, headers)
    files = {"file": ("clip.mp4", b"not-really-a-video", "video/mp4")}
    resp = await app_client.post(f"/api/v1/projects/{project_id}/evidence", files=files, data={"category": "other"}, headers=headers)
    print("STATUS", resp.status_code)
    print("BODY", resp.text[:600])
