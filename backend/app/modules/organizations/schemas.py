import uuid

from pydantic import BaseModel


class OrganizationSettingsResponse(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    primary_address: str | None
    timezone: str
    currency: str
    contact_email: str | None
    contact_phone: str | None
    max_active_users: int

    model_config = {"from_attributes": True}


class OrganizationSettingsUpdate(BaseModel):
    name: str | None = None
    logo_url: str | None = None
    primary_address: str | None = None
    timezone: str | None = None
    currency: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None


class RoleResponse(BaseModel):
    code: str
    name: str
    permissions: list[str]


class PermissionResponse(BaseModel):
    code: str
    description: str | None
