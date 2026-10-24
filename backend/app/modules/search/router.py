import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_organization_id, require_any_permission
from app.modules.search import service
from app.modules.users.models import User

router = APIRouter(tags=["search"])


class SearchResult(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    url: str


class SearchGroup(BaseModel):
    key: str
    label: str
    results: list[SearchResult]
    more_url: str


class SearchResponse(BaseModel):
    q: str
    groups: list[SearchGroup]


@router.get("/search", response_model=SearchResponse)
async def global_search(
    q: str = Query("", max_length=service.MAX_LENGTH),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    # Entra quien vea al menos uno de los grupos; cada grupo vuelve a mirar su
    # propio permiso y su recorte (vendedor, técnico) en `service.search`.
    current_user: User = Depends(require_any_permission(*service.SEARCH_PERMISSIONS)),
) -> dict:
    """El buscador de la barra superior. Resultados agrupados, pocos por grupo
    (no es un listado: no pagina), cada uno con la dirección de su pantalla."""
    return await service.search(db, organization_id=organization_id, user=current_user, q=q, limit=limit)
