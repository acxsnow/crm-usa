"""Seed script: default permission catalog, default roles, and (optionally) a demo
organization with an initial active admin user. Safe to re-run (idempotent).

Usage:
    python -m scripts.seed                     # catalog + roles only
    python -m scripts.seed --demo-org           # also creates a demo org + admin
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.modules.crm.defaults import DEFAULT_FUNDER_STATUSES
from app.modules.crm.models import FunderStatus
from app.modules.field_ops.defaults import DEFAULT_CHECKLIST_TEMPLATE
from app.modules.field_ops.models import ChecklistTemplate, ChecklistTemplateItem
from app.modules.organizations.models import Organization, PlanLimit
# Todos los modelos registrados antes de la primera consulta: `Project.case`
# apunta a "Case" por nombre y, sin esto, el seed falla al configurar los mappers.
from app.modules.billing import models as _billing_models  # noqa: F401
from app.modules.cases import models as _cases_models  # noqa: F401
from app.modules.programs import models as _programs_models  # noqa: F401
from app.modules.notifications import models as _notifications_models  # noqa: F401
from app.modules.finance import models as _finance_models  # noqa: F401
from app.modules.warehouse import models as _warehouse_models  # noqa: F401
from app.shared import audit_models as _audit_models  # noqa: F401
from app.modules.users.models import (
    Permission,
    PermissionModule,
    PermissionModuleItem,
    Role,
    User,
    UserRole,
    UserStatus,
)
from app.shared.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSION_CATALOG, ROLE_LABELS


def build_permission_modules(
    organization_id, permissions: dict[str, "Permission"]
) -> list["PermissionModule"]:
    """Crea los módulos de permisos a partir de `DEFAULT_MODULES` (decisión D9).

    `organization_id=None` produce la plantilla del sistema; con un id produce
    la copia editable de esa organización. Mismo patrón que los roles."""
    from app.modules.users.models import PermissionModule, PermissionModuleItem
    from app.shared.permissions import DEFAULT_MODULES

    modules = []
    for order, (key, module) in enumerate(DEFAULT_MODULES.items()):
        row = PermissionModule(
            organization_id=organization_id,
            key=key,
            label=module.label,
            sort_order=order,
            is_system=True,
        )
        row.items = [
            PermissionModuleItem(permission_id=permissions[code].id, sort_order=i)
            for i, code in enumerate(module.permissions)
            if code in permissions
        ]
        modules.append(row)
    return modules


async def seed_permission_catalog(db) -> dict[str, Permission]:
    result = await db.execute(select(Permission))
    existing = {p.code: p for p in result.scalars().all()}
    for code, description in PERMISSION_CATALOG:
        if code not in existing:
            perm = Permission(code=code, description=description)
            db.add(perm)
            existing[code] = perm
    await db.flush()
    return existing


async def seed_system_roles(db, permissions: dict[str, Permission]) -> dict[str, Role]:
    """System roles have organization_id = NULL and act as templates; each org also gets
    its own copies on creation so admins can customize permissions per organization."""
    result = await db.execute(select(Role).where(Role.organization_id.is_(None)))
    existing = {r.code: r for r in result.scalars().all()}
    for role_code, perm_codes in DEFAULT_ROLE_PERMISSIONS.items():
        if role_code in existing:
            continue
        role = Role(organization_id=None, code=role_code, name=ROLE_LABELS[role_code], is_system=True)
        role.permissions = [permissions[c] for c in perm_codes]
        db.add(role)
        existing[role_code] = role
    await db.flush()
    return existing


async def seed_system_permission_modules(db, permissions: dict[str, Permission]) -> None:
    """Plantilla del sistema de los módulos de permisos (organization_id NULL)."""
    result = await db.execute(
        select(PermissionModule).where(PermissionModule.organization_id.is_(None))
    )
    if result.scalars().first():
        return
    for module in build_permission_modules(None, permissions):
        db.add(module)
    await db.flush()


async def seed_demo_organization(db, permissions: dict[str, Permission]) -> None:
    result = await db.execute(select(Organization).where(Organization.name == "Demo Organization"))
    org = result.scalar_one_or_none()
    if org:
        print("Demo organization already exists, skipping.")
        return

    org = Organization(name="Demo Organization", timezone="America/Bogota", currency="USD")
    db.add(org)
    await db.flush()
    db.add(PlanLimit(organization_id=org.id, max_active_users=30))

    org_roles: dict[str, Role] = {}
    for role_code, perm_codes in DEFAULT_ROLE_PERMISSIONS.items():
        role = Role(organization_id=org.id, code=role_code, name=ROLE_LABELS[role_code], is_system=True)
        role.permissions = [permissions[c] for c in perm_codes]
        db.add(role)
        org_roles[role_code] = role
    await db.flush()

    admin = User(
        organization_id=org.id,
        email="admin@demo-org.com",
        email_display="admin@demo-org.com",
        full_name="Demo Admin",
        password_hash=hash_password("ChangeMe123!"),
        status=UserStatus.active,
    )
    db.add(admin)
    await db.flush()
    db.add(UserRole(user_id=admin.id, role_id=org_roles["organization_admin"].id))

    for module in build_permission_modules(org.id, permissions):
        db.add(module)
    await db.flush()

    for funder_status in DEFAULT_FUNDER_STATUSES:
        db.add(FunderStatus(organization_id=org.id, **funder_status))

    template = ChecklistTemplate(
        organization_id=org.id, name=DEFAULT_CHECKLIST_TEMPLATE["name"], project_type=DEFAULT_CHECKLIST_TEMPLATE["project_type"],
    )
    db.add(template)
    await db.flush()
    for item in DEFAULT_CHECKLIST_TEMPLATE["items"]:
        db.add(ChecklistTemplateItem(template_id=template.id, **item))

    print("Created demo organization with admin login: admin@demo-org.com / ChangeMe123!")


DEMO_USERS = [
    ("salesperson", "vendedor@demo-org.com", "Vicky Vendedora"),
    ("admin_staff", "administracion@demo-org.com", "Andrés Administración"),
    ("field_technician", "tecnico@demo-org.com", "Tito Técnico"),
    ("accounting", "contabilidad@demo-org.com", "Clara Contable"),
    ("management", "gerencia@demo-org.com", "Gabriel Gerencia"),
]

DEMO_USER_PASSWORD = "ChangeMe123!"


async def seed_demo_users(db) -> None:
    """Un usuario activo por cada rol del PDF, para revisar la aplicación con
    los ojos de cada área. Solo para desarrollo: todos comparten contraseña."""
    result = await db.execute(select(Organization).where(Organization.name == "Demo Organization"))
    org = result.scalar_one_or_none()
    if org is None:
        print("No existe la organización demo; corre primero con --demo-org.")
        return

    roles = {
        r.code: r
        for r in (
            await db.execute(select(Role).where(Role.organization_id == org.id))
        ).scalars().all()
    }

    creados = 0
    for role_code, email, full_name in DEMO_USERS:
        role = roles.get(role_code)
        if role is None:
            print(f"  falta el rol {role_code}, se omite {email}")
            continue
        existing = (
            await db.execute(
                select(User).where(User.organization_id == org.id, User.email == email)
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        user = User(
            organization_id=org.id,
            email=email,
            email_display=email,
            full_name=full_name,
            password_hash=hash_password(DEMO_USER_PASSWORD),
            status=UserStatus.active,
        )
        db.add(user)
        await db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        creados += 1

    await db.flush()
    print(f"Usuarios de prueba: {creados} creados (contraseña {DEMO_USER_PASSWORD}).")


async def seed_demo_programs(db) -> None:
    """Catálogo de campos y programas de Arizona y TECH (módulo 1). Idempotente:
    se puede correr sobre una base que ya los tenga."""
    from app.modules.programs.service import install_defaults

    org = (await db.execute(select(Organization).where(Organization.name == "Demo Organization"))).scalar_one_or_none()
    if org is None:
        return
    resultado = await install_defaults(db, organization_id=org.id)
    print(f"Programas: {resultado['fields_created']} campos y {resultado['programs_created'] or 'ningún'} programa nuevos.")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo-org", action="store_true", help="Also create a demo organization + admin user")
    parser.add_argument(
        "--demo-users",
        action="store_true",
        help="Crea un usuario activo por cada rol del PDF (solo desarrollo)",
    )
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        permissions = await seed_permission_catalog(db)
        await seed_system_roles(db, permissions)
        await seed_system_permission_modules(db, permissions)
        if args.demo_org:
            await seed_demo_organization(db, permissions)
        if args.demo_users:
            await seed_demo_users(db)
        await db.commit()
        if args.demo_org:
            await seed_demo_programs(db)
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
