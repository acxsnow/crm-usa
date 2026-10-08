import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_effective_permissions, get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.shared.errors import NotFoundError
from app.shared.pagination import paginate, pagination_params
from app.modules.users import service as users_service
from app.modules.users.models import Invitation, Role, User, UserRole, UserStatus
from app.modules.users.schemas import (
    UserInviteRequest,
    UserListResponse,
    UserProfileResponse,
    UserZoneInfo,
    UserResponse,
    UserRolesUpdate,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    response: Response,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    # Listar no es administrar: `users.read` basta para ver quién es quién
    # (asignar vendedores a una zona, filtros por persona). Invitar, activar,
    # desactivar, cambiar rol y editar siguen exigiendo `users.manage`.
    current_user: User = Depends(require_any_permission("users.read", "users.manage")),
    q: str | None = Query(None),
    status_filter: UserStatus | None = Query(None, alias="status"),
    role: str | None = Query(None),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    stmt = select(User).where(User.organization_id == organization_id).order_by(User.full_name)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((User.full_name.ilike(like)) | (User.email_display.ilike(like)))
    if status_filter:
        stmt = stmt.where(User.status == status_filter)
    if role:
        stmt = stmt.where(
            User.id.in_(
                select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(Role.code == role)
            )
        )
    limit, offset = pagination
    users = await paginate(db, stmt, limit=limit, offset=offset, response=response)
    active_count = await users_service.get_active_user_count(db, organization_id)
    max_users = await users_service.get_max_active_users(db, organization_id)
    return UserListResponse(
        items=[
            UserResponse(
                id=u.id,
                email=u.email_display,
                full_name=u.full_name,
                status=u.status,
                roles=[ur.role.code for ur in u.roles],
                last_login_at=u.last_login_at,
            )
            for u in users
        ],
        total=int(response.headers["X-Total-Count"]),
        active_user_count=active_count,
        max_active_users=max_users,
    )


@router.post("", response_model=UserResponse, status_code=201)
async def invite_user(
    payload: UserInviteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("users.manage")),
):
    client_ip = request.client.host if request.client else None
    user = await users_service.invite_user(
        db,
        organization_id=organization_id,
        inviter=current_user,
        email=payload.email,
        full_name=payload.full_name,
        role_codes=payload.role_codes,
        client_ip=client_ip,
    )
    return UserResponse(
        id=user.id,
        email=user.email_display,
        full_name=user.full_name,
        status=user.status,
        roles=payload.role_codes,
        last_login_at=None,
    )


@router.post("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("users.manage")),
):
    user = await users_service.set_user_active_state(
        db, organization_id=organization_id, user_id=user_id, actor=current_user, active=True
    )
    return UserResponse(
        id=user.id, email=user.email_display, full_name=user.full_name, status=user.status,
        roles=[ur.role.code for ur in user.roles], last_login_at=user.last_login_at,
    )


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("users.manage")),
):
    user = await users_service.set_user_active_state(
        db, organization_id=organization_id, user_id=user_id, actor=current_user, active=False
    )
    return UserResponse(
        id=user.id, email=user.email_display, full_name=user.full_name, status=user.status,
        roles=[ur.role.code for ur in user.roles], last_login_at=user.last_login_at,
    )


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
async def user_profile(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("users.read", "users.manage")),
):
    """Ficha de solo lectura: quién es, cuándo entró al equipo y, si es
    vendedor, en qué programas y zonas trabaja. Nada aquí se edita."""
    user = (
        await db.execute(select(User).where(User.id == user_id, User.organization_id == organization_id))
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError("El usuario no existe.", code="user_not_found")

    invitacion = (
        await db.execute(
            select(Invitation)
            .where(Invitation.organization_id == organization_id, Invitation.email == user.email)
            .order_by(Invitation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    invito = None
    if invitacion and invitacion.invited_by_user_id:
        invito = (await db.execute(select(User.full_name).where(User.id == invitacion.invited_by_user_id))).scalar()

    # Las zonas son datos de Configuración de programas: solo se muestran a
    # quien puede ver programas, para que la ficha no abra una puerta trasera.
    zonas = None
    permisos = get_effective_permissions(current_user)
    if permisos & {"programs.read", "programs.manage", "zones.manage"}:
        from app.modules.cases.models import Program, ProgramZone
        from app.modules.programs.models import ZoneAssignment

        filas = (
            await db.execute(
                select(Program.code, Program.name, ProgramZone.name, ProgramZone.city, ProgramZone.state, ProgramZone.active)
                .select_from(ZoneAssignment)
                .join(ProgramZone, ProgramZone.id == ZoneAssignment.zone_id)
                .join(Program, Program.id == ProgramZone.program_id)
                .where(ZoneAssignment.organization_id == organization_id, ZoneAssignment.user_id == user.id)
                .order_by(Program.name, ProgramZone.name)
            )
        ).all()
        zonas = [
            UserZoneInfo(program_code=pc, program_name=pn, zone_name=zn, city=ci, state=st, active=ac)
            for pc, pn, zn, ci, st, ac in filas
        ]

    return UserProfileResponse(
        id=user.id,
        email=user.email_display,
        full_name=user.full_name,
        status=user.status,
        roles=[ur.role.code for ur in user.roles],
        role_names=[ur.role.name for ur in user.roles],
        invited_at=user.created_at,
        invited_by=invito,
        joined_at=invitacion.accepted_at if invitacion else None,
        has_invitation=invitacion is not None,
        last_login_at=user.last_login_at,
        zones=zonas,
    )


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email_display,
        full_name=user.full_name,
        status=user.status,
        roles=[ur.role.code for ur in user.roles],
        last_login_at=user.last_login_at,
    )


@router.patch("/{user_id}/roles", response_model=UserResponse)
async def set_user_roles(
    user_id: uuid.UUID,
    payload: UserRolesUpdate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("users.manage")),
):
    user = await users_service.set_user_roles(
        db,
        organization_id=organization_id,
        actor=current_user,
        user_id=user_id,
        role_codes=payload.role_codes,
    )
    return _user_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("users.manage")),
):
    user = await users_service.update_user(
        db,
        organization_id=organization_id,
        actor=current_user,
        user_id=user_id,
        full_name=payload.full_name,
    )
    return _user_response(user)
