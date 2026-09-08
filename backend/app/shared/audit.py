"""Audit event recording service (spec 14). Events are append-only; never updated or deleted."""
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.audit_models import AuditEvent


async def record_audit_event(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=_sanitize(before_data),
        after_data=_sanitize(after_data),
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(event)
    await db.flush()
    return event


_SENSITIVE_KEYS = {"password", "password_hash", "token", "token_hash", "refresh_token", "access_token"}


def _sanitize(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip secrets/tokens before persisting, per spec 13 (no passwords/tokens in logs)."""
    if not data:
        return data
    return {k: ("***" if k.lower() in _SENSITIVE_KEYS else v) for k, v in data.items()}
