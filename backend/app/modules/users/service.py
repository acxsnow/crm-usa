import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_secure_token
from app.modules.notifications.email import send_email
from app.modules.organizations.models import PlanLimit
from app.modules.users.models import Invitation, Role, User, UserStatus
from app.shared.audit import record_audit_event

settings = get_settings()


async def get_active_user_count(db: AsyncSession, organization_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(User.id)).where(
            User.organization_id == organization_id, User.status == UserStatus.active
        )
    )
    return result.scalar_one()


async def get_max_active_users(db: AsyncSession, organization_id: uuid.UUID) -> int:
    result = await db.execute(select(PlanLimit).where(PlanLimit.organization_id == organization_id))
    plan_limit = result.scalar_one_or_none()
    return plan_limit.max_active_users if plan_limit else settings.DEFAULT_MAX_ACTIVE_USERS


async def invite_user(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    inviter: User,
    email: str,
    full_name: str,
    role_codes: list[str],
    client_ip: str | None = None,
) -> User:
    normalized_email = email.strip().lower()

    active_count = await get_active_user_count(db, organization_id)
    max_users = await get_max_active_users(db, organization_id)
    if active_count >= max_users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This organization has reached its plan limit of {max_users} active users. "
                "Deactivate a user or contact support to increase the limit."
            ),
        )

    existing = await db.execute(
        select(User).where(User.organization_id == organization_id, User.email == normalized_email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists.")

    result = await db.execute(
        select(Role).where(Role.code.in_(role_codes), (Role.organization_id == organization_id) | (Role.organization_id.is_(None)))
    )
    roles = result.scalars().all()
    if not roles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid roles specified.")

    user = User(
        organization_id=organization_id,
        email=normalized_email,
        email_display=email.strip(),
        full_name=full_name,
        status=UserStatus.invited,
    )
    db.add(user)
    await db.flush()

    from app.modules.users.models import UserRole

    for role in roles:
        db.add(UserRole(user_id=user.id, role_id=role.id))

    raw_token, token_hash = generate_secure_token()
    invitation = Invitation(
        organization_id=organization_id,
        email=normalized_email,
        token_hash=token_hash,
        invited_by_user_id=inviter.id,
        role_ids=",".join(str(r.id) for r in roles),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.INVITATION_EXPIRE_HOURS),
    )
    db.add(invitation)

    await record_audit_event(
        db,
        organization_id=organization_id,
        actor_user_id=inviter.id,
        action="users.invited",
        entity_type="User",
        entity_id=str(user.id),
        after_data={"email": normalized_email, "roles": role_codes},
        ip_address=client_ip,
    )
    await db.commit()
    await db.refresh(user)

    invite_link = f"{settings.FRONTEND_APP_URL}/accept-invitation?token={raw_token}"
    await send_email(to=email, template="account_invitation", context={"invite_link": invite_link, "full_name": full_name})
    return user


async def set_user_active_state(
    db: AsyncSession, *, organization_id: uuid.UUID, user_id: uuid.UUID, actor: User, active: bool
) -> User:
    result = await db.execute(select(User).where(User.id == user_id, User.organization_id == organization_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if active:
        max_users = await get_max_active_users(db, organization_id)
        active_count = await get_active_user_count(db, organization_id)
        if user.status != UserStatus.active and active_count >= max_users:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This organization has reached its plan limit of {max_users} active users.",
            )
        before = user.status
        user.status = UserStatus.active
        action = "users.activated"
    else:
        before = user.status
        user.status = UserStatus.inactive
        action = "users.deactivated"

    await record_audit_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action=action,
        entity_type="User",
        entity_id=str(user.id),
        before_data={"status": before.value},
        after_data={"status": user.status.value},
    )
    await db.commit()
    await db.refresh(user)
    return user
