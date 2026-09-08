import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_permission
from app.db.session import get_db
from app.shared.audit_models import AuditEvent

router = APIRouter(tags=["audit"])


@router.get("/audit-events")
async def list_audit_events(
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user=Depends(require_permission("audit.read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Only organization administrators can view org audit logs (spec 14) — enforced via audit.read permission."""
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    events = (await db.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "id": str(e.id),
                "actor_user_id": str(e.actor_user_id) if e.actor_user_id else None,
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
        "page": page,
        "page_size": page_size,
    }
