"""Consultas de lectura de usuarios, roles y módulos de permisos.

Capa de selectors: solo lectura, con el scope de organización siempre
explícito. La escritura y las reglas de negocio viven en `service.py`."""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.users.models import PermissionModule, Role, UserRole
from app.shared.permissions import DEFAULT_MODULES, Module

# El rol de administrador no se edita ni se borra: si se le pudieran quitar
# permisos, alguien podría dejarse sin acceso a Usuarios y Roles y quedar
# encerrado fuera de la configuración (decisión S2 del módulo 0).
LOCKED_ROLE_CODES = {"organization_admin"}


async def modules_for_organization(
    db: AsyncSession, organization_id: uuid.UUID
) -> dict[str, Module]:
    """Módulos de permisos de una organización, listos para `modules_for_permissions`.

    Devuelve la copia de la organización; si todavía no tiene (organizaciones
    creadas antes de la migración que introdujo los módulos), cae en la
    plantilla del sistema y, si tampoco existe, en los valores de código. Así
    el menú nunca queda vacío por un seed incompleto."""
    # `PermissionModuleItem.permission` es lazy="selectin", así que basta cargar
    # los items para tener también sus permisos sin N+1. `populate_existing`
    # hace que la consulta sobrescriba lo que la sesión ya tenga cacheado: el
    # menú siempre refleja la última edición del administrador, incluso si en
    # la misma sesión se acaba de cambiar un módulo.
    stmt = (
        select(PermissionModule)
        .options(selectinload(PermissionModule.items))
        .where(PermissionModule.organization_id == organization_id)
        .order_by(PermissionModule.sort_order, PermissionModule.key)
        .execution_options(populate_existing=True)
    )
    rows = (await db.execute(stmt)).scalars().all()

    if not rows:
        system_stmt = (
            select(PermissionModule)
            .options(selectinload(PermissionModule.items))
            .where(PermissionModule.organization_id.is_(None))
            .order_by(PermissionModule.sort_order, PermissionModule.key)
        )
        rows = (await db.execute(system_stmt)).scalars().all()

    if not rows:
        return dict(DEFAULT_MODULES)

    return {
        row.key: Module(
            label=row.label,
            permissions=[
                item.permission.code
                for item in sorted(row.items, key=lambda i: i.sort_order)
                if item.permission is not None
            ],
        )
        for row in rows
    }


async def user_counts_by_role(db: AsyncSession, organization_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Cuántos usuarios tiene cada rol de la organización. Se consulta de una
    sola vez para que el listado de roles no dispare una consulta por fila."""
    rows = await db.execute(
        select(UserRole.role_id, func.count(UserRole.id))
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.organization_id == organization_id)
        .group_by(UserRole.role_id)
    )
    return {role_id: count for role_id, count in rows.all()}


async def roles_for_organization(db: AsyncSession, organization_id: uuid.UUID) -> list[Role]:
    """Roles visibles para una organización.

    Incluye las plantillas del sistema (`organization_id` nulo) para las
    organizaciones que todavía no tienen su copia, pero si existe la copia
    propia esa gana: de lo contrario el mismo rol aparecería dos veces en la
    pantalla y con el nombre equivocado."""
    rows = (
        await db.execute(
            select(Role)
            .options(selectinload(Role.permissions))
            .where((Role.organization_id == organization_id) | (Role.organization_id.is_(None)))
            .order_by(Role.name)
            .execution_options(populate_existing=True)
        )
    ).scalars().all()

    deduped: dict[str, Role] = {}
    for role in rows:
        current = deduped.get(role.code)
        if current is None or current.organization_id is None:
            deduped[role.code] = role
    return sorted(deduped.values(), key=lambda r: r.name)


async def get_org_role_or_404(db: AsyncSession, organization_id: uuid.UUID, code: str) -> Role:
    """Rol editable de la organización.

    Si solo existe la plantilla del sistema, se crea la copia de la
    organización en ese momento: así editar un rol del sistema nunca modifica
    la plantilla que comparten todas las organizaciones."""
    role = (
        await db.execute(
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.organization_id == organization_id, Role.code == code)
        )
    ).scalar_one_or_none()
    if role is not None:
        return role

    template = (
        await db.execute(
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.organization_id.is_(None), Role.code == code)
        )
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rol no encontrado.")

    copy = Role(
        organization_id=organization_id,
        code=template.code,
        name=template.name,
        is_system=template.is_system,
    )
    copy.permissions = list(template.permissions)
    db.add(copy)
    await db.flush()
    return copy
