import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.modules.users.models import UserStatus


class UserInviteRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    # Una persona tiene un rol y solo uno. Se mantiene como lista porque
    # `user_roles` sigue siendo muchos a muchos: si la regla cambia, se
    # sube este tope y no hay que migrar nada.
    role_codes: list[str] = Field(min_length=1, max_length=1)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    status: UserStatus
    roles: list[str]
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    active_user_count: int
    max_active_users: int


# --- Roles, permisos y módulos ---------------------------------------------


class PermissionResponse(BaseModel):
    code: str
    description: str


class PermissionModuleResponse(BaseModel):
    key: str
    label: str
    permissions: list[str]


class PermissionCatalogResponse(BaseModel):
    """El catálogo completo más los módulos de la organización.

    La pantalla de roles lo usa para pintar las casillas agrupadas; los
    módulos vienen de la base, no del código, porque el administrador puede
    haberlos editado."""

    modules: list[PermissionModuleResponse]
    permissions: list[PermissionResponse]


class RoleResponse(BaseModel):
    code: str
    name: str
    is_system: bool
    is_locked: bool
    permissions: list[str]
    user_count: int


class RoleCreate(BaseModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{2,49}$")
    name: str = Field(min_length=1, max_length=150)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    permissions: list[str] | None = None


class UserRolesUpdate(BaseModel):
    # Una persona tiene un rol y solo uno. Se mantiene como lista porque
    # `user_roles` sigue siendo muchos a muchos: si la regla cambia, se
    # sube este tope y no hay que migrar nada.
    role_codes: list[str] = Field(min_length=1, max_length=1)


class UserUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
