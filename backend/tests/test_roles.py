"""API de roles y permisos.

El administrador crea roles, les marca permisos y se los asigna a la gente sin
tocar código. Lo que aquí se protege: que no se pueda romper el acceso propio
(el rol Administrador está bloqueado), que no se borre un rol en uso, y que la
configuración de una organización no se vea ni se toque desde otra."""
from app.modules.users.models import Role


async def _login(app_client, email, password="SuperSecret123"):
    resp = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Catálogo de permisos agrupado por módulo
# ---------------------------------------------------------------------------

async def test_permission_catalog_is_grouped_by_module(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.get("/api/v1/permissions", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    keys = [m["key"] for m in body["modules"]]
    assert "billing" in keys
    billing = next(m for m in body["modules"] if m["key"] == "billing")
    assert billing["label"] == "Facturación y cobros"
    assert "invoices.read" in billing["permissions"]

    codes = {p["code"]: p["description"] for p in body["permissions"]}
    assert codes["invoices.read"] == "Ver facturas"


async def test_permission_catalog_shows_a_permission_in_several_modules(app_client, active_admin_user):
    """La relación es de muchos a muchos: el mismo permiso aparece en los dos
    módulos a los que pertenece."""
    headers = await _login(app_client, "admin@acme-demo.com")
    body = (await app_client.get("/api/v1/permissions", headers=headers)).json()
    with_finance = {
        m["key"] for m in body["modules"] if "dashboards.finance" in m["permissions"]
    }
    assert with_finance == {"billing", "reports"}


async def test_permission_catalog_requires_permission(app_client, active_technician_user):
    headers = await _login(app_client, "tech@acme-demo.com")
    resp = await app_client.get("/api/v1/permissions", headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Listado de roles
# ---------------------------------------------------------------------------

async def test_list_roles_returns_metadata(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.get("/api/v1/roles", headers=headers)
    assert resp.status_code == 200, resp.text
    roles = {r["code"]: r for r in resp.json()}

    assert roles["organization_admin"]["name"] == "Administrador"
    assert roles["organization_admin"]["is_system"] is True
    assert roles["organization_admin"]["is_locked"] is True
    assert roles["organization_admin"]["user_count"] == 1

    assert roles["salesperson"]["is_locked"] is False
    assert "cases.create" in roles["salesperson"]["permissions"]


async def test_roles_deduped_org_override_wins_over_system_default(app_client, db, active_admin_user, seeded_org):
    """La copia de la organización gana sobre la plantilla del sistema; si no,
    el mismo rol saldría dos veces en la pantalla."""
    db.add(Role(organization_id=None, code="field_technician", name="Técnico (sistema)", is_system=True))
    await db.commit()

    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.get("/api/v1/roles", headers=headers)
    assert resp.status_code == 200
    codes = [r["code"] for r in resp.json()]
    assert codes.count("field_technician") == 1

    match = next(r for r in resp.json() if r["code"] == "field_technician")
    assert match["name"] != "Técnico (sistema)"


async def test_list_roles_allows_user_managers(app_client, active_admin_user, db, seeded_org):
    """Quien solo administra usuarios necesita leer los roles para poder
    asignarlos; antes el endpoint exigía roles.manage y la pantalla de Equipo
    se quedaba sin la lista."""
    from app.modules.users.models import User, UserRole, UserStatus
    from app.core.security import hash_password

    org = seeded_org["org"]
    role = Role(organization_id=org.id, code="user_manager", name="Gestor de usuarios", is_system=False)
    role.permissions = [seeded_org["permissions"]["users.manage"]]
    db.add(role)
    await db.flush()
    user = User(
        organization_id=org.id, email="gestor@acme-demo.com", email_display="gestor@acme-demo.com",
        full_name="Gina Gestora", password_hash=hash_password("SuperSecret123"), status=UserStatus.active,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.commit()

    headers = await _login(app_client, "gestor@acme-demo.com")
    assert (await app_client.get("/api/v1/roles", headers=headers)).status_code == 200


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------

async def test_create_role(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.post(
        "/api/v1/roles",
        json={
            "code": "zone_coordinator",
            "name": "Coordinador de zona",
            "permissions": ["projects.read_all", "dispatch.manage"],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["is_system"] is False
    assert body["is_locked"] is False
    assert body["user_count"] == 0
    assert set(body["permissions"]) == {"projects.read_all", "dispatch.manage"}


async def test_create_role_rejects_unknown_permission(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.post(
        "/api/v1/roles",
        json={"code": "x_role", "name": "X", "permissions": ["no.existe"]},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "no.existe" in resp.json()["detail"]


async def test_create_role_rejects_duplicate_code(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.post(
        "/api/v1/roles",
        json={"code": "salesperson", "name": "Otro vendedor", "permissions": ["customers.read"]},
        headers=headers,
    )
    assert resp.status_code == 409


async def test_create_role_rejects_invalid_code(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.post(
        "/api/v1/roles",
        json={"code": "Rol Con Espacios", "name": "X", "permissions": ["customers.read"]},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_role_requires_permission(app_client, active_admin_staff_user):
    headers = await _login(app_client, "admin-staff@acme-demo.com")
    resp = await app_client.post(
        "/api/v1/roles",
        json={"code": "x_role", "name": "X", "permissions": ["customers.read"]},
        headers=headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Editar
# ---------------------------------------------------------------------------

async def test_update_system_role_permissions(app_client, active_admin_user):
    """Los roles del sistema se editan; lo que no se puede es borrarlos."""
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.patch(
        "/api/v1/roles/salesperson",
        json={"permissions": ["customers.read"], "name": "Asesor comercial"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["permissions"] == ["customers.read"]
    assert resp.json()["name"] == "Asesor comercial"


async def test_cannot_edit_locked_admin_role(app_client, active_admin_user):
    """El Administrador está bloqueado: si se le pudieran quitar permisos,
    alguien podría dejarse sin acceso a Usuarios y Roles y quedar encerrado."""
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.patch(
        "/api/v1/roles/organization_admin",
        json={"permissions": ["customers.read"]},
        headers=headers,
    )
    assert resp.status_code == 409


async def test_update_role_rejects_unknown_permission(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.patch(
        "/api/v1/roles/salesperson", json={"permissions": ["no.existe"]}, headers=headers
    )
    assert resp.status_code == 400


async def test_update_unknown_role_is_404(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.patch("/api/v1/roles/no_existe", json={"name": "X"}, headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Borrar
# ---------------------------------------------------------------------------

async def test_delete_role_without_users(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    await app_client.post(
        "/api/v1/roles",
        json={"code": "temp_role", "name": "Temporal", "permissions": ["customers.read"]},
        headers=headers,
    )
    resp = await app_client.delete("/api/v1/roles/temp_role", headers=headers)
    assert resp.status_code == 204

    remaining = [r["code"] for r in (await app_client.get("/api/v1/roles", headers=headers)).json()]
    assert "temp_role" not in remaining


async def test_cannot_delete_system_role(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.delete("/api/v1/roles/salesperson", headers=headers)
    assert resp.status_code == 409


async def test_delete_role_with_users_is_rejected(app_client, active_admin_user, active_technician_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    await app_client.post(
        "/api/v1/roles",
        json={"code": "temp_role", "name": "Temporal", "permissions": ["customers.read"]},
        headers=headers,
    )
    assigned = await app_client.patch(
        f"/api/v1/users/{active_technician_user.id}/roles",
        json={"role_codes": ["temp_role"]},
        headers=headers,
    )
    assert assigned.status_code == 200, assigned.text

    resp = await app_client.delete("/api/v1/roles/temp_role", headers=headers)
    assert resp.status_code == 409
    assert "usuario" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Aislamiento entre organizaciones
# ---------------------------------------------------------------------------

async def test_roles_are_scoped_to_the_organization(app_client, active_admin_user, second_org, db):
    """Un administrador de otra organización no ve ni edita los roles de esta."""
    from app.modules.users.models import User, UserRole, UserStatus
    from app.core.security import hash_password

    headers = await _login(app_client, "admin@acme-demo.com")
    await app_client.post(
        "/api/v1/roles",
        json={"code": "solo_acme", "name": "Solo Acme", "permissions": ["customers.read"]},
        headers=headers,
    )

    other = User(
        organization_id=second_org["org"].id, email="admin@beta-demo.com",
        email_display="admin@beta-demo.com", full_name="Beto Beta",
        password_hash=hash_password("SuperSecret123"), status=UserStatus.active,
    )
    db.add(other)
    await db.flush()
    db.add(UserRole(user_id=other.id, role_id=second_org["roles"]["organization_admin"].id))
    await db.commit()

    other_headers = await _login(app_client, "admin@beta-demo.com")
    codes = [r["code"] for r in (await app_client.get("/api/v1/roles", headers=other_headers)).json()]
    assert "solo_acme" not in codes

    resp = await app_client.patch(
        "/api/v1/roles/solo_acme", json={"name": "Hackeado"}, headers=other_headers
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Configuración de la organización
# ---------------------------------------------------------------------------

async def test_organization_settings_endpoint_works(app_client, active_admin_user):
    """Guarda de regresión: al mudar `GET /roles` y `GET /permissions` a su
    propio router, este endpoint quedó sin cobertura y un import mal borrado
    lo habría roto en producción sin que ningún test lo notara."""
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.get("/api/v1/organization/settings", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Acme Field Services"
    assert body["max_active_users"] == 30


async def test_organization_settings_requires_permission(app_client, active_technician_user):
    headers = await _login(app_client, "tech@acme-demo.com")
    resp = await app_client.get("/api/v1/organization/settings", headers=headers)
    assert resp.status_code == 403


async def test_permissions_endpoint_is_not_duplicated(app_client, active_admin_user):
    """Había dos rutas `GET /permissions` registradas —la nueva y una anterior
    que quedó viva en el router de organización—; la segunda no se alcanzaba
    nunca, pero salía duplicada en el contrato de la API."""
    from app.main import app

    rutas = [
        r for r in app.routes
        if getattr(r, "path", "") == "/api/v1/permissions" and "GET" in getattr(r, "methods", set())
    ]
    assert len(rutas) == 1, f"hay {len(rutas)} rutas GET /permissions registradas"
