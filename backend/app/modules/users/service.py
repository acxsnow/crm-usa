import uuid
from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.security import generate_secure_token
from app.modules.notifications.email import send_email
from app.modules.organizations.models import PlanLimit
from app.modules.users.models import Invitation, Permission, Role, User, UserRole, UserStatus
from app.modules.users.selectors import LOCKED_ROLE_CODES, get_org_role_or_404
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError

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
        raise ConflictError(
            f"La organización llegó a su límite de {max_users} usuarios activos. "
            "Desactiva a alguien o solicita ampliar el plan.",
            code="plan_limit_reached",
        )

    existing = await db.execute(
        select(User).where(User.organization_id == organization_id, User.email == normalized_email)
    )
    if existing.scalar_one_or_none():
        raise ConflictError(
            "Ya existe un usuario con ese correo.", code="email_already_used"
        )

    # Un rol del sistema existe dos veces: la plantilla (`organization_id`
    # nulo) y la copia de la organización. Sin deduplicar por código, el
    # invitado quedaba con el mismo rol asignado dos veces y su nombre salía
    # repetido en pantalla. Gana la copia de la organización, que es la que el
    # administrador puede editar.
    _require_exactly_one_role(list(dict.fromkeys(role_codes)))
    await _require_admin_to_grant_admin(db, actor=inviter, codes=list(role_codes))
    result = await db.execute(
        select(Role).where(
            Role.code.in_(role_codes),
            (Role.organization_id == organization_id) | (Role.organization_id.is_(None)),
        )
    )
    por_codigo: dict[str, Role] = {}
    for role in result.scalars().all():
        existente = por_codigo.get(role.code)
        if existente is None or existente.organization_id is None:
            por_codigo[role.code] = role
    roles = list(por_codigo.values())
    if not roles:
        raise InvalidInputError("No se indicó ningún rol válido.", code="no_valid_roles")

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
        raise NotFoundError("El usuario no existe.", code="user_not_found")

    if active:
        max_users = await get_max_active_users(db, organization_id)
        active_count = await get_active_user_count(db, organization_id)
        if user.status != UserStatus.active and active_count >= max_users:
            raise ConflictError(
                f"La organización llegó a su límite de {max_users} usuarios activos.",
                code="plan_limit_reached",
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


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

async def _permissions_by_code(db: AsyncSession, codes: list[str]) -> list[Permission]:
    """Traduce códigos a filas de `permissions`, rechazando los que no existen.

    Un código inventado no debe guardarse en silencio: quedaría un rol con un
    permiso que nunca autoriza nada y nadie sabría por qué."""
    unique = list(dict.fromkeys(codes))
    rows = (await db.execute(select(Permission).where(Permission.code.in_(unique)))).scalars().all()
    found = {p.code: p for p in rows}
    missing = [code for code in unique if code not in found]
    if missing:
        raise InvalidInputError(
            f"Estos permisos no existen: {', '.join(sorted(missing))}.",
            code="unknown_permissions",
        )
    return [found[code] for code in unique]


async def create_role(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor: User,
    code: str,
    name: str,
    permission_codes: list[str],
) -> Role:
    existing = (
        await db.execute(
            select(Role).where(
                Role.code == code,
                (Role.organization_id == organization_id) | (Role.organization_id.is_(None)),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(
            f"Ya existe un rol con el código '{code}'.", code="role_code_taken"
        )

    role = Role(organization_id=organization_id, code=code, name=name, is_system=False)
    role.permissions = await _permissions_by_code(db, permission_codes)
    db.add(role)
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action="roles.created",
        entity_type="Role",
        entity_id=str(role.id),
        after_data={"code": code, "name": name, "permissions": permission_codes},
    )
    await db.commit()
    await db.refresh(role)
    return role


async def update_role(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor: User,
    code: str,
    name: str | None = None,
    permission_codes: list[str] | None = None,
) -> Role:
    if code in LOCKED_ROLE_CODES:
        raise ConflictError(
            "El rol de Administrador no se puede modificar: siempre conserva "
            "todos los permisos para que nadie quede sin acceso a la "
            "configuración.",
            code="role_locked",
        )

    role = await get_org_role_or_404(db, organization_id, code)
    before = {"name": role.name, "permissions": sorted(p.code for p in role.permissions)}

    if name is not None:
        role.name = name
    if permission_codes is not None:
        role.permissions = await _permissions_by_code(db, permission_codes)
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action="roles.updated",
        entity_type="Role",
        entity_id=str(role.id),
        before_data=before,
        after_data={"name": role.name, "permissions": sorted(p.code for p in role.permissions)},
    )
    await db.commit()
    await db.refresh(role)
    return role


async def delete_role(
    db: AsyncSession, *, organization_id: uuid.UUID, actor: User, code: str
) -> None:
    role = (
        await db.execute(
            select(Role).where(Role.organization_id == organization_id, Role.code == code)
        )
    ).scalar_one_or_none()
    if role is None:
        raise NotFoundError("El rol no existe.", code="role_not_found")

    if role.is_system or code in LOCKED_ROLE_CODES:
        raise ConflictError(
            "Los roles del sistema no se pueden eliminar; sí se pueden "
            "renombrar y cambiarles los permisos.",
            code="system_role_not_deletable",
        )

    in_use = (
        await db.execute(select(func.count(UserRole.id)).where(UserRole.role_id == role.id))
    ).scalar_one()
    if in_use:
        raise ConflictError(
            f"Este rol lo tienen {in_use} usuario(s). Cámbiales el rol antes "
            "de eliminarlo.",
            code="role_in_use",
        )

    await record_audit_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action="roles.deleted",
        entity_type="Role",
        entity_id=str(role.id),
        before_data={"code": role.code, "name": role.name},
    )
    await db.delete(role)
    await db.commit()


async def _require_admin_to_grant_admin(db: AsyncSession, *, actor: User, codes: list[str]) -> None:
    """Solo un administrador reparte el rol de administrador.

    Sin esto, cualquier rol propio con `users.manage` —un "Coordinador de zona",
    por ejemplo— podría ascender a alguien a Administrador, o ascenderse a sí
    mismo, y quedarse con los 72 permisos. Es escalada de privilegios: el
    permiso de administrar usuarios no incluye el de crear administradores.

    Se consulta por `actor.id` y no por `actor.roles` porque el actor llega de
    la dependencia de autenticación y su relación puede no venir cargada."""
    if "organization_admin" not in codes or actor.is_platform_super_admin:
        return
    es_admin = (
        await db.execute(
            select(func.count(UserRole.id))
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == actor.id, Role.code == "organization_admin")
        )
    ).scalar_one()
    if not es_admin:
        raise ForbiddenError(
            "Solo un administrador puede otorgar el rol de Administrador.",
            code="cannot_grant_admin",
        )


def _require_exactly_one_role(codes: list[str]) -> None:
    """Una persona tiene un rol y solo uno.

    Va en el servicio y no solo en el esquema HTTP porque `invite_user` y
    `set_user_roles` también se llaman desde `scripts/seed.py` y desde tareas,
    donde Pydantic no interviene. `user_roles` sigue siendo muchos a muchos: la
    regla es de negocio, no de la base."""
    if len(codes) != 1:
        raise InvalidInputError(
            "Una persona solo puede tener un rol.", code="single_role_required"
        )


async def set_user_roles(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor: User,
    user_id: uuid.UUID,
    role_codes: list[str],
) -> User:
    """Reemplaza el conjunto de roles de un usuario.

    Impide dejar a la organización sin ningún administrador activo: si el
    último se quita el rol, nadie podría volver a entrar a Usuarios y Roles."""
    user = (
        await db.execute(
            select(User).where(User.id == user_id, User.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError("El usuario no existe.", code="user_not_found")

    codes = list(dict.fromkeys(role_codes))
    _require_exactly_one_role(codes)
    await _require_admin_to_grant_admin(db, actor=actor, codes=codes)
    roles = [await get_org_role_or_404(db, organization_id, code) for code in codes]
    before = sorted(ur.role.code for ur in user.roles)

    if "organization_admin" in before and "organization_admin" not in {r.code for r in roles}:
        remaining = (
            await db.execute(
                select(func.count(UserRole.id))
                .join(Role, Role.id == UserRole.role_id)
                .join(User, User.id == UserRole.user_id)
                .where(
                    Role.organization_id == organization_id,
                    Role.code == "organization_admin",
                    User.status == UserStatus.active,
                    User.id != user.id,
                )
            )
        ).scalar_one()
        if not remaining:
            raise ConflictError(
                "Es el único administrador activo. Asigna el rol de "
                "Administrador a otra persona antes de quitárselo.",
                code="last_admin",
            )

    await db.execute(sa_delete(UserRole).where(UserRole.user_id == user.id))
    for role in roles:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action="users.roles_changed",
        entity_type="User",
        entity_id=str(user.id),
        before_data={"roles": before},
        after_data={"roles": sorted(r.code for r in roles)},
    )
    await db.commit()

    # `user.roles` quedó cacheada con los roles anteriores; hay que releerla
    # para que la respuesta muestre los nuevos y no los de antes del cambio.
    refreshed = (
        await db.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.id == user.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    return refreshed


async def update_user(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor: User,
    user_id: uuid.UUID,
    full_name: str,
) -> User:
    user = (
        await db.execute(
            select(User).where(User.id == user_id, User.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError("El usuario no existe.", code="user_not_found")

    before = {"full_name": user.full_name}
    user.full_name = full_name
    await db.flush()

    await record_audit_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action="users.updated",
        entity_type="User",
        entity_id=str(user.id),
        before_data=before,
        after_data={"full_name": full_name},
    )
    await db.commit()
    await db.refresh(user)
    return user
