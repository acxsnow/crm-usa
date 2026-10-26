import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_permission
from app.db.session import get_db
from app.shared.audit_models import AuditEvent
from app.shared.pagination import paginate, pagination_params
from app.shared.text_search import LIKE_ESCAPE, contains_pattern

router = APIRouter(tags=["audit"])


@router.get("/audit-events")
async def list_audit_events(
    response: Response,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user=Depends(require_permission("audit.read")),
    action: str | None = Query(None),
    actor_user_id: uuid.UUID | None = Query(None),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """Only organization administrators can view org audit logs (spec 14) — enforced via audit.read permission."""
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.created_at.desc())
    )
    if action:
        stmt = stmt.where(AuditEvent.action.ilike(contains_pattern(action), escape=LIKE_ESCAPE))
    if actor_user_id:
        stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)
    limit, offset = pagination
    events = await paginate(db, stmt, limit=limit, offset=offset, response=response)
    return [
        {
            "id": str(e.id),
            "actor_user_id": str(e.actor_user_id) if e.actor_user_id else None,
            "action": e.action,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "created_at": e.created_at.isoformat(),
            # D-020: el antes y el después, y desde dónde; la base los guardaba
            # pero la pantalla no los mostraba.
            "before_data": e.before_data,
            "after_data": e.after_data,
            "ip_address": e.ip_address,
        }
        for e in events
    ]
