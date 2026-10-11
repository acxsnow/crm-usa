import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AccessToken(BaseModel):
    """El refresh token no va aquí: viaja en la cookie HttpOnly (SEG-04)."""
    access_token: str
    token_type: str = "bearer"


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
    # Si esta persona puede otorgar el rol de Administrador. El frontend esconde
    # esa opción con esto; la regla la impone el servicio (`_require_admin_to_
    # grant_admin`), no la pantalla.
    can_grant_admin: bool = False

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
