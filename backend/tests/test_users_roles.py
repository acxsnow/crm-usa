"""Cambiar los roles de una persona y lo que `/auth/me` le devuelve al frontend.

`/auth/me` incluye `modules`: la lista de módulos que ese usuario puede abrir.
El menú y las rutas del frontend se construyen con eso, así que si aquí se
calcula mal, alguien ve ítems que no puede usar o deja de ver los suyos."""


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------

async def test_me_exposes_modules_and_role_names(app_client, active_technician_user):
    headers = await _login(app_client, "tech@acme-demo.com")
    me = (await app_client.get("/api/v1/auth/me", headers=headers)).json()

    assert me["role_names"] == ["Técnico"]
    assert set(me["modules"]) >= {"projects", "customers", "dispatch", "expenses"}
    # El técnico no administra usuarios, ni factura, ni configura programas.
    assert "team" not in me["modules"]
    assert "billing" not in me["modules"]
    assert "config" not in me["modules"]


async def test_me_modules_for_an_admin_include_everything(app_client, active_admin_user):
    from app.shared.permissions import DEFAULT_MODULES

    headers = await _login(app_client, "admin@acme-demo.com")
    me = (await app_client.get("/api/v1/auth/me", headers=headers)).json()
    assert set(me["modules"]) == set(DEFAULT_MODULES)
    assert me["role_names"] == ["Administrador"]


async def test_me_modules_follow_the_organization_copy_not_the_code(
    app_client, active_accounting_user, db, seeded_org
):
    """Si el administrador saca un permiso de un módulo, ese módulo deja de
    abrirse para quien solo entraba por ese permiso."""
    from sqlalchemy import select

    from app.modules.users.models import Permission, PermissionModule, PermissionModuleItem

    headers = await _login(app_client, "contabilidad@acme-demo.com")
    me = (await app_client.get("/api/v1/auth/me", headers=headers)).json()
    assert "payables" in me["modules"]

    payables = (
        await db.execute(
            select(PermissionModule).where(
                PermissionModule.organization_id == seeded_org["org"].id,
                PermissionModule.key == "payables",
            )
        )
    ).scalar_one()
    codes = (
        await db.execute(
            select(Permission.id).where(Permission.code.in_(["suppliers.manage", "payables.manage"]))
        )
    ).scalars().all()
    await db.execute(
        PermissionModuleItem.__table__.delete().where(
            PermissionModuleItem.module_id == payables.id,
            PermissionModuleItem.permission_id.in_(codes),
        )
    )
    await db.commit()

    me = (await app_client.get("/api/v1/auth/me", headers=headers)).json()
    assert "payables" not in me["modules"]
    # Los demás módulos de Contabilidad siguen intactos.
    assert "billing" in me["modules"]


# ---------------------------------------------------------------------------
# Cambiar roles de un usuario
# ---------------------------------------------------------------------------

async def test_change_user_roles(app_client, active_admin_user, active_technician_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.patch(
        f"/api/v1/users/{active_technician_user.id}/roles",
        json={"role_codes": ["accounting"]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["roles"] == ["accounting"]


async def test_role_change_updates_what_the_user_can_reach(
    app_client, active_admin_user, active_technician_user
):
    """El cambio de rol se refleja en la siguiente carga del usuario: es lo que
    hace que el menú cambie sin tocar código."""
    admin_headers = await _login(app_client, "admin@acme-demo.com")
    await app_client.patch(
        f"/api/v1/users/{active_technician_user.id}/roles",
        json={"role_codes": ["accounting"]},
        headers=admin_headers,
    )

    tech_headers = await _login(app_client, "tech@acme-demo.com")
    me = (await app_client.get("/api/v1/auth/me", headers=tech_headers)).json()
    assert me["role_names"] == ["Contabilidad"]
    assert "invoices.read" in me["permissions"]
    assert "billing" in me["modules"]
    assert "dispatch" not in me["modules"]

    # Y el acceso real cambia, no solo lo que dice /auth/me.
    assert (await app_client.get("/api/v1/invoices", headers=tech_headers)).status_code == 200


async def test_change_user_roles_requires_permission(app_client, active_technician_user):
    headers = await _login(app_client, "tech@acme-demo.com")
    resp = await app_client.patch(
        f"/api/v1/users/{active_technician_user.id}/roles",
        json={"role_codes": ["accounting"]},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_cannot_remove_the_last_organization_admin(app_client, active_admin_user):
    """Si el último administrador se quita el rol, nadie podría volver a entrar
    a Usuarios y Roles."""
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.patch(
        f"/api/v1/users/{active_admin_user.id}/roles",
        json={"role_codes": ["management"]},
        headers=headers,
    )
    assert resp.status_code == 409
    assert "administrador" in resp.json()["detail"].lower()


async def test_can_remove_an_admin_when_another_one_remains(
    app_client, active_admin_user, active_technician_user
):
    headers = await _login(app_client, "admin@acme-demo.com")
    await app_client.patch(
        f"/api/v1/users/{active_technician_user.id}/roles",
        json={"role_codes": ["organization_admin"]},
        headers=headers,
    )
    resp = await app_client.patch(
        f"/api/v1/users/{active_admin_user.id}/roles",
        json={"role_codes": ["management"]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


async def test_change_roles_of_a_user_from_another_organization_is_404(
    app_client, active_admin_user, second_org, db
):
    from app.core.security import hash_password
    from app.modules.users.models import User, UserRole, UserStatus

    other = User(
        organization_id=second_org["org"].id,
        email="otro@beta-demo.com",
        email_display="otro@beta-demo.com",
        full_name="Otro Usuario",
        password_hash=hash_password("SuperSecret123"),
        status=UserStatus.active,
    )
    db.add(other)
    await db.flush()
    db.add(UserRole(user_id=other.id, role_id=second_org["roles"]["management"].id))
    await db.commit()

    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.patch(
        f"/api/v1/users/{other.id}/roles", json={"role_codes": ["accounting"]}, headers=headers
    )
    assert resp.status_code == 404


async def test_update_user_name(app_client, active_admin_user, active_technician_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.patch(
        f"/api/v1/users/{active_technician_user.id}",
        json={"full_name": "Nombre Nuevo"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["full_name"] == "Nombre Nuevo"
