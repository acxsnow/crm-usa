"""Shared FastAPI dependencies: DB session, current user, organization context, permission checks."""
import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_jwt_token
from app.db.session import get_db
from app.modules.users.models import User, UserStatus

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error

    payload = decode_jwt_token(token)
    if not payload or payload.get("type") != "access":
        raise credentials_error

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_error

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_error

    # A password reset bumps token_version to invalidate every previously
    # issued token at once (spec 6.3.7) — reject anything issued before that.
    if payload.get("ver") != user.token_version:
        raise credentials_error

    if user.status != UserStatus.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active.")

    request.state.current_user = user
    return user


def get_effective_permissions(user: User) -> set[str]:
    if user.is_platform_super_admin:
        from app.shared.permissions import PERMISSION_CATALOG

        return {code for code, _ in PERMISSION_CATALOG}
    perms: set[str] = set()
    for user_role in user.roles:
        for perm in user_role.role.permissions:
            perms.add(perm.code)
    return perms


def require_permission(permission_code: str) -> Callable:
    """Dependency factory enforcing server-side RBAC (spec 13: enforce on every API request)."""

    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if permission_code not in get_effective_permissions(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission_code}",
            )
        return current_user

    return _checker


def require_any_permission(*permission_codes: str) -> Callable:
    """Like require_permission, but passes if the user holds ANY of the given
    codes — used where a broader and a narrower permission both grant access
    to the same endpoint (e.g. projects.read_all vs projects.read_assigned),
    with the endpoint itself narrowing results for the assigned-only case."""

    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if not (set(permission_codes) & get_effective_permissions(current_user)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission (any of): {', '.join(permission_codes)}",
            )
        return current_user

    return _checker


def get_organization_id(current_user: User = Depends(get_current_user)) -> uuid.UUID:
    """The org id is always taken from the authenticated session, never from request payloads (spec 8.3)."""
    return current_user.organization_id
