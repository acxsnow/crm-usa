import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetConfirmSchema(BaseModel):
    token: str
    new_password: str = Field(min_length=12)


class InvitationAcceptSchema(BaseModel):
    token: str
    password: str = Field(min_length=12)


class CurrentUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    organization_id: uuid.UUID
    roles: list[str]
    permissions: list[str]

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
