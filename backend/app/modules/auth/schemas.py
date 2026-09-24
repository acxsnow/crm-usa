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
    # Etiquetas visibles de los roles ("Técnico"), para no mostrar códigos.
    role_names: list[str] = []
    permissions: list[str]
    # Módulos que este usuario puede abrir. El menú y las rutas del frontend se
    # construyen con esto, en vez de repetir allá la lógica de agrupamiento.
    modules: list[str] = []

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
