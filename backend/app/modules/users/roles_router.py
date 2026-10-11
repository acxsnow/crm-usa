"""Administración de roles y consulta del catálogo de permisos.

Es lo que permite al administrador crear un rol, marcarle permisos y
asignárselo a alguien sin tocar código. Ver `docs/PERMISOS.md`."""
import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.users import service as users_service
from app.modules.users.models import Role, User
from app.modules.users.schemas import (
    PermissionCatalogResponse,
    PermissionModuleResponse,
    PermissionResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)
from app.modules.users.selectors import (
    LOCKED_ROLE_CODES,
    modules_for_organization,
    roles_for_organization,
    user_counts_by_role,
)
from app.shared.pagination import paginate_list, pagination_params
from app.shared.permissions import PERMISSION_CATALOG

router = APIRouter(tags=["roles"])


def _to_response(role: Role, user_count: int) -> RoleResponse:
    return RoleResponse(
        code=role.code,
        name=role.name,
        is_system=role.is_system,
        is_locked=role.code in LOCKED_ROLE_CODES,
        permissions=sorted(p.code for p in role.permissions),
        user_count=user_count,
    )


@router.get("/permissions", response_model=PermissionCatalogResponse)
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("roles.manage", "users.manage")),
):
    """Catálogo de permisos y los módulos que los agrupan."""
    modules = await modules_for_organization(db, organization_id)
    return PermissionCatalogResponse(
        modules=[
            PermissionModuleResponse(key=key, label=module.label, permissions=list(module.permissions))
            for key, module in modules.items()
        ],
        permissions=[
            PermissionResponse(code=code, description=description)
            for code, description in PERMISSION_CATALOG
        ],
    )


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    # Quien solo administra usuarios necesita leer los roles para asignarlos.
    current_user: User = Depends(require_any_permission("roles.manage", "users.manage")),
):
    limit, offset = pagination
    roles = paginate_list(await roles_for_organization(db, organization_id), limit=limit, offset=offset,
                          response=response)
    counts = await user_counts_by_role(db, organization_id)
    return [_to_response(role, counts.get(role.id, 0)) for role in roles]


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("roles.manage")),
):
    role = await users_service.create_role(
        db,
        organization_id=organization_id,
        actor=current_user,
        code=payload.code,
        name=payload.name,
        permission_codes=payload.permissions,
    )
    return _to_response(role, 0)


@router.patch("/roles/{code}", response_model=RoleResponse)
async def update_role(
    code: str,
    payload: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("roles.manage")),
):
    role = await users_service.update_role(
        db,
        organization_id=organization_id,
        actor=current_user,
        code=code,
        name=payload.name,
        permission_codes=payload.permissions,
    )
    counts = await user_counts_by_role(db, organization_id)
    return _to_response(role, counts.get(role.id, 0))


@router.delete("/roles/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    code: str,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("roles.manage")),
):
    await users_service.delete_role(
        db, organization_id=organization_id, actor=current_user, code=code
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
