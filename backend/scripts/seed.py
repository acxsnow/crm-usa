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
from app.modules.crm.defaults import DEFAULT_FUNDER_STATUSES, DEFAULT_PIPELINE_STAGES
from app.modules.crm.models import FunderStatus, PipelineStage
from app.modules.field_ops.defaults import DEFAULT_CHECKLIST_TEMPLATE
from app.modules.field_ops.models import ChecklistTemplate, ChecklistTemplateItem
from app.modules.organizations.models import Organization, PlanLimit
from app.modules.users.models import Permission, Role, User, UserRole, UserStatus
from app.shared.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSION_CATALOG, ROLE_LABELS


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

    for stage in DEFAULT_PIPELINE_STAGES:
        db.add(PipelineStage(organization_id=org.id, **stage))

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


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo-org", action="store_true", help="Also create a demo organization + admin user")
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        permissions = await seed_permission_catalog(db)
        await seed_system_roles(db, permissions)
        if args.demo_org:
            await seed_demo_organization(db, permissions)
        await db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
