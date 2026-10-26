from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_effective_permissions, require_permission
from app.core.config import get_settings
from app.core.rate_limit import is_rate_limited
from app.db.session import get_db
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import (
    CurrentUserResponse,
    InvitationAcceptSchema,
    AccessToken,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
)
from app.modules.users.models import User
from app.modules.users.schemas import UserUpdate
from app.modules.users.selectors import modules_for_organization
from app.shared.permissions import modules_for_permissions

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

GENERIC_LOGIN_ERROR = "El correo o la contraseña no son correctos."
# D-005: el bloqueo se dice tal cual, para que quien quedó bloqueado no siga
# probando claves creyendo que la suya está mal.
LOCKED_LOGIN_ERROR = ("Demasiados intentos de ingreso. Espera {minutos} minutos e inténtalo de nuevo, "
                      "o recupera tu contraseña.")
RESET_SENT = "Si hay una cuenta activa con ese correo, te enviamos un enlace para recuperar la contraseña."

# SEG-04: el refresh token (dura días) viaja solo en una cookie HttpOnly que
# JavaScript no puede leer; el navegador la manda sola a /auth/*. El access
# token (15 min) va en el cuerpo y el frontend lo guarda solo en memoria.
REFRESH_COOKIE = "crm_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE, token, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, path=REFRESH_COOKIE_PATH,
        httponly=True, secure=settings.ENVIRONMENT in ("staging", "production"), samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True,
                           secure=settings.ENVIRONMENT in ("staging", "production"), samesite="strict")


@router.post("/login", response_model=AccessToken)
async def login(payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    normalized_email = payload.email.strip().lower()

    # Rate limit by IP and by normalized email (spec 6.1).
    ip_limited = await is_rate_limited(
        f"login:ip:{client_ip}",
        max_attempts=settings.LOGIN_MAX_ATTEMPTS,
        window_seconds=settings.LOGIN_WINDOW_MINUTES * 60,
    )
    email_limited = await is_rate_limited(
        f"login:email:{normalized_email}",
        max_attempts=settings.LOGIN_MAX_ATTEMPTS,
        window_seconds=settings.LOGIN_WINDOW_MINUTES * 60,
    )
    if ip_limited or email_limited:
        # D-006: el bloqueo queda en la auditoría una vez por ventana, no en
        # cada intento bloqueado (si no, un ataque llenaría la tabla).
        primera_vez = not await is_rate_limited(
            f"login:locked-audit:{normalized_email}", max_attempts=1,
            window_seconds=settings.LOGIN_WINDOW_MINUTES * 60)
        if primera_vez:
            await auth_service.record_failed_login(db, normalized_email, reason="locked", ip=client_ip)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=LOCKED_LOGIN_ERROR.format(minutos=settings.LOGIN_WINDOW_MINUTES))

    user = await auth_service.authenticate_user(db, payload.email, payload.password)
    if not user:
        await auth_service.record_failed_login(db, normalized_email, reason="invalid_credentials", ip=client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    access_token, refresh_token = await auth_service.issue_token_pair(db, user)
    _set_refresh_cookie(response, refresh_token)
    return AccessToken(access_token=access_token)


@router.post("/refresh", response_model=AccessToken)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Renueva la sesión con la cookie: rota el refresh token y entrega un
    access token nuevo. Sin cookie válida responde 401 y el frontend va al ingreso."""
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La sesión no es válida. Vuelve a iniciar sesión.")
    access_token, refresh_token = await auth_service.refresh_access_token(db, token)
    _set_refresh_cookie(response, refresh_token)
    return AccessToken(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request, response: Response):
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        await auth_service.logout(token)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Sesión cerrada.")


@router.post("/password-reset/request", response_model=MessageResponse)
async def request_password_reset(
    payload: PasswordResetRequestSchema, request: Request, db: AsyncSession = Depends(get_db)
):
    client_ip = request.client.host if request.client else "unknown"
    normalized_email = payload.email.strip().lower()

    email_limited = await is_rate_limited(
        f"pwreset:email:{normalized_email}",
        max_attempts=settings.PASSWORD_RESET_MAX_PER_EMAIL_PER_HOUR,
        window_seconds=3600,
    )
    ip_limited = await is_rate_limited(
        f"pwreset:ip:{client_ip}",
        max_attempts=settings.PASSWORD_RESET_MAX_PER_IP_PER_HOUR,
        window_seconds=3600,
    )
    if email_limited or ip_limited:
        # Still return the generic message; do not reveal rate-limit state either.
        return MessageResponse(message=RESET_SENT)

    await auth_service.request_password_reset(db, payload.email, client_ip)
    return MessageResponse(message=RESET_SENT)


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(payload: PasswordResetConfirmSchema, db: AsyncSession = Depends(get_db)):
    await auth_service.confirm_password_reset(db, payload.token, payload.new_password)
    return MessageResponse(message="Tu contraseña se cambió.")


async def _current_user_response(db: AsyncSession, user: User) -> CurrentUserResponse:
    """Arma la respuesta que el frontend usa para construir el menú.

    `modules` se calcula con los módulos de la organización (que el
    administrador pudo haber editado), no con los valores de código; el
    super admin de plataforma los ve todos."""
    perms = get_effective_permissions(user)
    modules = await modules_for_organization(db, user.organization_id)
    if user.is_platform_super_admin:
        open_modules = set(modules)
    else:
        open_modules = modules_for_permissions(perms, modules)

    return CurrentUserResponse(
        id=user.id,
        email=user.email_display,
        full_name=user.full_name,
        organization_id=user.organization_id,
        roles=[ur.role.code for ur in user.roles],
        role_names=[ur.role.name for ur in user.roles],
        permissions=sorted(perms),
        modules=sorted(open_modules),
        can_grant_admin=user.is_platform_super_admin
        or any(ur.role.code == "organization_admin" for ur in user.roles),
    )


@router.post("/invitations/accept", response_model=CurrentUserResponse)
async def accept_invitation(payload: InvitationAcceptSchema, db: AsyncSession = Depends(get_db)):
    user = await auth_service.accept_invitation(db, payload.token, payload.password)
    return await _current_user_response(db, user)


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _current_user_response(db, current_user)


@router.patch("/me", response_model=CurrentUserResponse)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("profile.manage")),
):
    """«Mi perfil»: cada uno corrige su propio nombre (D-014: `profile.manage`
    existía y no hacía nada). El correo y el rol no se tocan aquí."""
    from app.modules.users import service as users_service

    user = await users_service.update_user(db, organization_id=current_user.organization_id, actor=current_user,
                                           user_id=current_user.id, full_name=payload.full_name.strip())
    return await _current_user_response(db, user)
