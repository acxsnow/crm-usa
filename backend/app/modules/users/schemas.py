import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.modules.users.models import UserStatus


class UserInviteRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role_codes: list[str] = Field(min_length=1)


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
