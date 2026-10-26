import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions, get_organization_id, require_any_permission
from app.db.session import get_db
from app.modules.organizations.models import Organization, PlanLimit
from app.modules.organizations.schemas import (
    OrganizationSettingsResponse,
    OrganizationSettingsUpdate,
)
from app.shared.audit import record_audit_event
from app.shared.errors import ForbiddenError

router = APIRouter(tags=["organization"])

# D-014: los dos permisos existían y solo uno hacía algo. Los datos de la
# empresa son de `organization.manage`; la configuración (zona horaria y
# moneda), de `settings.manage`. Para leer basta cualquiera de los dos.
_any_settings = require_any_permission("organization.manage", "settings.manage")
ORGANIZATION_FIELDS = {"name", "logo_url", "primary_address", "contact_email", "contact_phone"}
CONFIGURATION_FIELDS = {"timezone", "currency"}


@router.get("/organization/settings", response_model=OrganizationSettingsResponse)
async def get_organization_settings(
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user=Depends(_any_settings),
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
    current_user=Depends(_any_settings),
):
    cambios = payload.model_dump(exclude_unset=True)
    permisos = get_effective_permissions(current_user)
    if ORGANIZATION_FIELDS & set(cambios) and "organization.manage" not in permisos:
        raise ForbiddenError("No tienes permiso para cambiar los datos de la organización.",
                             code="organization_manage_required")
    if CONFIGURATION_FIELDS & set(cambios) and "settings.manage" not in permisos:
        raise ForbiddenError("No tienes permiso para cambiar la zona horaria ni la moneda.",
                             code="settings_manage_required")
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
