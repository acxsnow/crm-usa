from app.modules.users.models import Role


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_roles_deduped_org_override_wins_over_system_default(app_client, db, active_admin_user, seeded_org):
    org_id = seeded_org["org"].id
    # Same code as one of seeded_org's own org-scoped roles, but as a
    # NULL-org (system) entry — mirrors what scripts/seed.py produces for
    # the demo organization and is what caused duplicate role checkboxes.
    db.add(Role(organization_id=None, code="field_technician", name="Field Technician (system)", is_system=True))
    await db.commit()

    token = await _login(app_client, "admin@acme-demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await app_client.get("/api/v1/roles", headers=headers)
    assert resp.status_code == 200
    codes = [r["code"] for r in resp.json()]
    assert codes.count("field_technician") == 1

    # The org-specific copy's name must win, not the system one.
    match = next(r for r in resp.json() if r["code"] == "field_technician")
    assert match["name"] != "Field Technician (system)"
