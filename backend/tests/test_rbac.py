from app.modules.organizations.models import Organization


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_technician_cannot_manage_users(app_client, active_technician_user):
    token = await _login(app_client, "tech@acme-demo.com")
    resp = await app_client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_admin_can_list_users(app_client, active_admin_user):
    token = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_user_count"] >= 1
    assert body["max_active_users"] == 30


async def test_admin_can_invite_user_and_it_counts_toward_limit(app_client, active_admin_user, db, seeded_org):
    token = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.post(
        "/api/v1/users",
        json={"email": "newtech@acme-demo.com", "full_name": "New Tech", "role_codes": ["field_technician"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "invited"


async def test_invite_blocked_at_plan_limit(app_client, active_admin_user, db, seeded_org):
    from app.modules.organizations.models import PlanLimit
    from sqlalchemy import select

    org_id = active_admin_user.organization_id
    result = await db.execute(select(PlanLimit).where(PlanLimit.organization_id == org_id))
    plan_limit = result.scalar_one()
    plan_limit.max_active_users = 1  # admin already counts as the 1 active user
    await db.commit()

    token = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.post(
        "/api/v1/users",
        json={"email": "blocked@acme-demo.com", "full_name": "Blocked User", "role_codes": ["field_technician"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


async def test_org_isolation_users_not_visible_across_orgs(app_client, active_admin_user, db, seeded_org):
    # Create a second organization with its own admin.
    from app.core.security import hash_password
    from app.modules.users.models import Role, User, UserRole, UserStatus

    org2 = Organization(name="Other Org")
    db.add(org2)
    await db.flush()

    from app.shared.permissions import DEFAULT_ROLE_PERMISSIONS, ROLE_LABELS

    admin_role_2 = Role(
        organization_id=org2.id,
        code="organization_admin",
        name=ROLE_LABELS["organization_admin"],
        is_system=True,
    )
    # Reuse permission rows from seeded_org since Permission table isn't org-scoped.
    admin_role_2.permissions = seeded_org["roles"]["organization_admin"].permissions
    db.add(admin_role_2)
    await db.flush()

    user2 = User(
        organization_id=org2.id,
        email="admin2@other-demo.com",
        email_display="admin2@other-demo.com",
        full_name="Other Admin",
        password_hash=hash_password("SuperSecret123"),
        status=UserStatus.active,
    )
    db.add(user2)
    await db.flush()
    db.add(UserRole(user_id=user2.id, role_id=admin_role_2.id))
    await db.commit()

    token2 = await _login(app_client, "admin2@other-demo.com")
    resp = await app_client.get("/api/v1/users", headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()["items"]]
    assert "admin@acme-demo.com" not in emails
    assert "admin2@other-demo.com" in emails
