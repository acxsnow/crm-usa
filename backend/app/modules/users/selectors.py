"""Consultas de lectura de usuarios, roles y módulos de permisos.

Capa de selectors: solo lectura, con el scope de organización siempre
explícito. La escritura y las reglas de negocio viven en `service.py`."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.users.models import PermissionModule
from app.shared.permissions import DEFAULT_MODULES, Module


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
