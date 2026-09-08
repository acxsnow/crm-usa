from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_effective_permissions
from app.core.config import get_settings
from app.core.rate_limit import is_rate_limited
from app.db.session import get_db
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import (
    CurrentUserResponse,
    InvitationAcceptSchema,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
    RefreshRequest,
    TokenPair,
)
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

GENERIC_LOGIN_ERROR = "Invalid email or password."


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
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
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.")

    user = await auth_service.authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    access_token, refresh_token = await auth_service.issue_token_pair(db, user)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    access_token, refresh_token = await auth_service.refresh_access_token(db, payload.refresh_token)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(payload: LogoutRequest):
    await auth_service.logout(payload.refresh_token)
    return MessageResponse(message="Logged out.")


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
        return MessageResponse(message="If an active account exists for this email, a recovery link has been sent.")

    await auth_service.request_password_reset(db, payload.email, client_ip)
    return MessageResponse(message="If an active account exists for this email, a recovery link has been sent.")


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(payload: PasswordResetConfirmSchema, db: AsyncSession = Depends(get_db)):
    await auth_service.confirm_password_reset(db, payload.token, payload.new_password)
    return MessageResponse(message="Your password was changed.")


@router.post("/invitations/accept", response_model=CurrentUserResponse)
async def accept_invitation(payload: InvitationAcceptSchema, db: AsyncSession = Depends(get_db)):
    user = await auth_service.accept_invitation(db, payload.token, payload.password)
    perms = get_effective_permissions(user)
    return CurrentUserResponse(
        id=user.id,
        email=user.email_display,
        full_name=user.full_name,
        organization_id=user.organization_id,
        roles=[ur.role.code for ur in user.roles],
        permissions=sorted(perms),
    )


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    perms = get_effective_permissions(current_user)
    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email_display,
        full_name=current_user.full_name,
        organization_id=current_user.organization_id,
        roles=[ur.role.code for ur in current_user.roles],
        permissions=sorted(perms),
    )
