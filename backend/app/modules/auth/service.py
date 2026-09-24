import uuid
from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_jwt_token,
    decode_jwt_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.token_denylist import denylist_jti, is_denylisted
from app.modules.notifications.email import send_email
from app.modules.users.models import Invitation, PasswordResetToken, User, UserStatus
from app.shared.audit import record_audit_event
from app.shared.errors import AuthenticationError, InvalidInputError
from app.shared.datetime_utils import as_utc

settings = get_settings()


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    normalized_email = email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if user.status != UserStatus.active:
        return None
    return user


async def issue_token_pair(db: AsyncSession, user: User) -> tuple[str, str]:
    access_token, _ = create_jwt_token(str(user.id), "access", {"org": str(user.organization_id), "ver": user.token_version})
    refresh_token, _ = create_jwt_token(str(user.id), "refresh", {"ver": user.token_version})
    user.last_login_at = datetime.now(timezone.utc)
    await record_audit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="auth.login.success",
        entity_type="User",
        entity_id=str(user.id),
    )
    await db.commit()
    return access_token, refresh_token


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    invalid = AuthenticationError("La sesión no es válida. Vuelve a iniciar sesión.")

    payload = decode_jwt_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise invalid

    jti = payload.get("jti")
    if jti and await is_denylisted(jti):
        raise invalid

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or user.status != UserStatus.active:
        raise invalid
    if payload.get("ver") != user.token_version:
        raise invalid

    # Rotate: issue a brand new pair, and denylist the old refresh token so a
    # captured-then-replayed old token can't also be used (spec 6.1/6.3.7).
    access_token, _ = create_jwt_token(str(user.id), "access", {"org": str(user.organization_id), "ver": user.token_version})
    new_refresh_token, new_refresh_exp = create_jwt_token(str(user.id), "refresh", {"ver": user.token_version})

    if jti:
        remaining_seconds = int((datetime.fromtimestamp(payload["exp"], tz=timezone.utc) - datetime.now(timezone.utc)).total_seconds())
        await denylist_jti(jti, remaining_seconds)

    return access_token, new_refresh_token


async def logout(refresh_token: str) -> None:
    """Revokes this one refresh token immediately (spec 6.1). To kill every
    session at once — e.g. after a password reset — token_version is bumped
    instead; see confirm_password_reset."""
    payload = decode_jwt_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        return  # already invalid/expired — nothing to revoke
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return
    remaining_seconds = int((datetime.fromtimestamp(exp, tz=timezone.utc) - datetime.now(timezone.utc)).total_seconds())
    await denylist_jti(jti, remaining_seconds)


async def request_password_reset(db: AsyncSession, email: str, ip_address: str | None) -> None:
    normalized_email = email.strip().lower()
    result = await db.execute(
        select(User).where(User.email == normalized_email, User.status == UserStatus.active)
    )
    user = result.scalar_one_or_none()
    # Always behave the same regardless of whether the account exists (spec 6.3 step 3).
    if not user:
        return

    raw_token, token_hash = generate_secure_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    reset_token = PasswordResetToken(
        user_id=user.id, token_hash=token_hash, expires_at=expires_at, created_ip=ip_address
    )
    db.add(reset_token)
    await record_audit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="auth.password_reset.requested",
        entity_type="User",
        entity_id=str(user.id),
        ip_address=ip_address,
    )
    await db.commit()

    reset_link = f"{settings.FRONTEND_APP_URL}/reset-password?token={raw_token}"
    await send_email(to=user.email_display, template="password_reset_request", context={"reset_link": reset_link})


async def confirm_password_reset(db: AsyncSession, raw_token: str, new_password: str) -> None:
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    reset_token = result.scalar_one_or_none()

    invalid = InvalidInputError(
        "El enlace para restablecer la contraseña no es válido o ya venció.",
        code="invalid_reset_token",
    )
    if not reset_token or reset_token.used_at is not None:
        raise invalid
    if as_utc(reset_token.expires_at) < datetime.now(timezone.utc):
        raise invalid

    result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise invalid

    user.password_hash = hash_password(new_password)
    user.token_version += 1  # spec 6.3.7: revoke every outstanding session at once
    reset_token.used_at = datetime.now(timezone.utc)

    await record_audit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="auth.password_reset.completed",
        entity_type="User",
        entity_id=str(user.id),
    )
    await db.commit()

    await send_email(to=user.email_display, template="password_changed", context={})


async def accept_invitation(db: AsyncSession, raw_token: str, password: str) -> User:
    token_hash = hash_token(raw_token)
    result = await db.execute(select(Invitation).where(Invitation.token_hash == token_hash))
    invitation = result.scalar_one_or_none()

    invalid = InvalidInputError(
        "La invitación no es válida o ya venció.", code="invalid_invitation"
    )
    if not invitation or invitation.accepted_at is not None:
        raise invalid
    if as_utc(invitation.expires_at) < datetime.now(timezone.utc):
        raise invalid

    result = await db.execute(
        select(User).where(User.organization_id == invitation.organization_id, User.email == invitation.email)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise invalid

    user.password_hash = hash_password(password)
    user.status = UserStatus.active
    invitation.accepted_at = datetime.now(timezone.utc)

    await record_audit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="auth.invitation.accepted",
        entity_type="User",
        entity_id=str(user.id),
    )
    await db.commit()
    await db.refresh(user)
    return user
