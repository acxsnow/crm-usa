import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_permission
from app.db.session import get_db
from app.modules.organizations.models import Organization, PlanLimit
from app.modules.organizations.schemas import (
    OrganizationSettingsResponse,
    OrganizationSettingsUpdate,
    PermissionResponse,
    RoleResponse,
)
from app.modules.users.models import Permission, Role
from app.shared.audit import record_audit_event

router = APIRouter(tags=["organization"])


@router.get("/organization/settings", response_model=OrganizationSettingsResponse)
async def get_organization_settings(
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user=Depends(require_permission("settings.manage")),
):
    org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalar_one()
    plan_limit = (
        await db.execute(select(PlanLimit).where(PlanLimit.organization_id == organization_id))
    ).scalar_one_or_none()
    return OrganizationSettingsResponse(
        id=org.id, name=org.name, logo_url=org.logo_url, primary_address=org.primary_address,
        timezone=org.timezone, currency=org.currency, contact_email=org.contact_email,
        contact_phone=org.contact_phone, max_active_users=plan_limit.max_active_users if plan_limit else 30,
    )


@router.patch("/organization/settings", response_model=OrganizationSettingsResponse)
async def update_organization_settings(
    payload: OrganizationSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user=Depends(require_permission("settings.manage")),
):
    org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalar_one()
    before = {"name": org.name, "timezone": org.timezone, "currency": org.currency}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(org, field, value)

    await record_audit_event(
        db,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="organization.settings_updated",
        entity_type="Organization",
        entity_id=str(organization_id),
        before_data=before,
        after_data=payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    await db.refresh(org)

    plan_limit = (
        await db.execute(select(PlanLimit).where(PlanLimit.organization_id == organization_id))
    ).scalar_one_or_none()
    return OrganizationSettingsResponse(
        id=org.id, name=org.name, logo_url=org.logo_url, primary_address=org.primary_address,
        timezone=org.timezone, currency=org.currency, contact_email=org.contact_email,
        contact_phone=org.contact_phone, max_active_users=plan_limit.max_active_users if plan_limit else 30,
    )


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user=Depends(require_permission("roles.manage")),
):
    result = await db.execute(
        select(Role).where((Role.organization_id == organization_id) | (Role.organization_id.is_(None)))
    )
    roles = result.scalars().all()
    # An org can have its own copy of a system-default role code (see seed.py,
    # which creates both a NULL-org catalog entry and a per-org copy for the
    # demo org) — dedupe by code so the org-specific row always wins over the
    # NULL-org one, instead of listing both.
    deduped: dict[str, Role] = {}
    for r in roles:
        existing = deduped.get(r.code)
        if existing is None or existing.organization_id is None:
            deduped[r.code] = r
    return [RoleResponse(code=r.code, name=r.name, permissions=[p.code for p in r.permissions]) for r in deduped.values()]


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("roles.manage")),
):
    result = await db.execute(select(Permission).order_by(Permission.code))
    return [PermissionResponse(code=p.code, description=p.description) for p in result.scalars().all()]
