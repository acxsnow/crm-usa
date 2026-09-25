"""Cambiar los roles de una persona y lo que `/auth/me` le devuelve al frontend.

`/auth/me` incluye `modules`: la lista de módulos que ese usuario puede abrir.
El menú y las rutas del frontend se construyen con eso, así que si aquí se
calcula mal, alguien ve ítems que no puede usar o deja de ver los suyos."""
import pytest

from app.modules.users import service as user_service
from app.shared.errors import ForbiddenError


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


async def test_inviting_assigns_each_role_once(app_client, active_admin_user, db, seeded_org):
    """Un rol del sistema existe dos veces —la plantilla y la copia de la
    organización— y la búsqueda traía ambas, así que el invitado quedaba con el
    mismo rol dos veces y su nombre salía repetido en pantalla."""
    from sqlalchemy import func, select

    from app.modules.users.models import Role, User, UserRole

    # La base real tiene las plantillas del sistema que crea `scripts/seed.py`;
    # sin ellas aquí, el test no reproduciría la condición que causa el fallo.
    db.add(
        Role(
            organization_id=None,
            code="field_technician",
            name="Técnico",
            is_system=True,
        )
    )
    await db.commit()

    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.post(
        "/api/v1/users",
        json={
            "email": "unico@acme-demo.com",
            "full_name": "Uno Solo",
            "role_codes": ["field_technician"],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["roles"] == ["field_technician"]

    invitado = (
        await db.execute(select(User).where(User.email == "unico@acme-demo.com"))
    ).scalar_one()
    asignaciones = (
        await db.execute(select(func.count(UserRole.id)).where(UserRole.user_id == invitado.id))
    ).scalar_one()
    assert asignaciones == 1, "el rol quedó asignado más de una vez"


# ---------------------------------------------------------------------------
# Un usuario, un rol
# ---------------------------------------------------------------------------

async def test_a_user_cannot_be_invited_with_two_roles(app_client, active_admin_user):
    """Regla de negocio: una persona tiene un rol y solo uno. La pantalla ofrece
    botones de opción, pero la regla vive en la API: esconder la posibilidad en
    la interfaz no impide mandar dos por HTTP."""
    headers = await _login(app_client, "admin@acme-demo.com")
    resp = await app_client.post(
        "/api/v1/users",
        json={
            "email": "dos-roles@acme-demo.com",
            "full_name": "Dos Roles",
            "role_codes": ["salesperson", "field_technician"],
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text

    listado = (await app_client.get("/api/v1/users", headers=headers)).json()
    assert "dos-roles@acme-demo.com" not in [u["email"] for u in listado["items"]]


async def test_a_user_cannot_be_given_two_roles(app_client, active_admin_user):
    headers = await _login(app_client, "admin@acme-demo.com")
    creado = await app_client.post(
        "/api/v1/users",
        json={
            "email": "un-rol@acme-demo.com",
            "full_name": "Un Rol",
            "role_codes": ["salesperson"],
        },
        headers=headers,
    )
    assert creado.status_code == 201, creado.text
    user_id = creado.json()["id"]

    resp = await app_client.patch(
        f"/api/v1/users/{user_id}/roles",
        json={"role_codes": ["salesperson", "accounting"]},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text

    # El rol que ya tenía no se tocó.
    actual = (await app_client.get("/api/v1/users", headers=headers)).json()["items"]
    fila = next(u for u in actual if u["email"] == "un-rol@acme-demo.com")
    assert fila["roles"] == ["salesperson"]


async def test_changing_to_a_single_role_still_works(app_client, active_admin_user):
    """El caso normal no se rompe: cambiar de un rol a otro."""
    headers = await _login(app_client, "admin@acme-demo.com")
    creado = await app_client.post(
        "/api/v1/users",
        json={
            "email": "cambia-rol@acme-demo.com",
            "full_name": "Cambia Rol",
            "role_codes": ["salesperson"],
        },
        headers=headers,
    )
    user_id = creado.json()["id"]

    resp = await app_client.patch(
        f"/api/v1/users/{user_id}/roles",
        json={"role_codes": ["accounting"]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["roles"] == ["accounting"]


# ---------------------------------------------------------------------------
# Solo un administrador reparte el rol de administrador
# ---------------------------------------------------------------------------

async def test_a_non_admin_cannot_grant_the_admin_role(
    db, seeded_org, active_admin_staff_user, active_salesperson_user
):
    """Escalada de privilegios: quien pueda administrar usuarios sin ser
    administrador (un rol propio con `users.manage`, por ejemplo "Coordinador
    de zona") no puede repartir el rol de Administrador — ni a otro ni a sí
    mismo, que sería darse todos los permisos."""
    with pytest.raises(ForbiddenError):
        await user_service.set_user_roles(
            db,
            organization_id=seeded_org["org"].id,
            actor=active_admin_staff_user,
            user_id=active_salesperson_user.id,
            role_codes=["organization_admin"],
        )


async def test_a_non_admin_cannot_invite_an_admin(db, seeded_org, active_admin_staff_user):
    with pytest.raises(ForbiddenError):
        await user_service.invite_user(
            db,
            organization_id=seeded_org["org"].id,
            inviter=active_admin_staff_user,
            email="nuevo-admin@acme-demo.com",
            full_name="Nuevo Admin",
            role_codes=["organization_admin"],
        )


async def test_an_admin_can_grant_the_admin_role(
    db, seeded_org, active_admin_user, active_salesperson_user
):
    actualizado = await user_service.set_user_roles(
        db,
        organization_id=seeded_org["org"].id,
        actor=active_admin_user,
        user_id=active_salesperson_user.id,
        role_codes=["organization_admin"],
    )
    assert [ur.role.code for ur in actualizado.roles] == ["organization_admin"]


async def test_a_non_admin_can_still_assign_any_other_role(
    db, seeded_org, active_admin_staff_user, active_salesperson_user
):
    """La restricción es solo sobre el rol de Administrador; lo demás sigue
    siendo trabajo normal de quien administra usuarios."""
    actualizado = await user_service.set_user_roles(
        db,
        organization_id=seeded_org["org"].id,
        actor=active_admin_staff_user,
        user_id=active_salesperson_user.id,
        role_codes=["accounting"],
    )
    assert [ur.role.code for ur in actualizado.roles] == ["accounting"]


async def test_me_says_whether_the_person_can_grant_the_admin_role(
    app_client, active_admin_user, active_admin_staff_user
):
    """El frontend esconde la opción "Administrador" con esto. La regla real la
    impone la API; este campo solo evita ofrecer algo que va a ser rechazado."""
    admin = await _login(app_client, "admin@acme-demo.com")
    assert (await app_client.get("/api/v1/auth/me", headers=admin)).json()["can_grant_admin"] is True

    otro = await _login(app_client, "admin-staff@acme-demo.com")
    assert (await app_client.get("/api/v1/auth/me", headers=otro)).json()["can_grant_admin"] is False
