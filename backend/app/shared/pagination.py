"""Shared limit/offset pagination for list endpoints (Phase 5 hardening).

Every list endpoint originally returned its full, unbounded result set —
fine at demo data volumes, but a real gap once an org has thousands of
leads/opportunities/invoices: an unauthenticated cost blow-up isn't the
concern here (every list endpoint already requires a permission), but an
unbounded query is still a resource-exhaustion risk (OWASP API4:2023
Unrestricted Resource Consumption) and a plain usability problem long
before that. `DEFAULT_LIMIT`/`MAX_LIMIT` cap the worst case while keeping
today's callers working unchanged: nobody has enough data yet to notice
the cap, and the response shape doesn't change — the total count travels
in an `X-Total-Count` response header rather than wrapping the JSON body,
so existing frontend code (`res.data` as a plain array) keeps working."""
import uuid
from typing import TypeVar

from fastapi import Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

DEFAULT_LIMIT = 100
MAX_LIMIT = 500

T = TypeVar("T")


def pagination_params(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> tuple[int, int]:
    return limit, offset


async def paginate(
    db: AsyncSession, stmt: Select, *, limit: int, offset: int, response: Response,
) -> list:
    """Runs a count query + a limited/offset page of `stmt`, and sets
    X-Total-Count on the response. `stmt` should already carry its
    org-scope filter and ORDER BY."""
    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    response.headers["X-Total-Count"] = str(total)
    result = await db.execute(stmt.limit(limit).offset(offset))
    return list(result.scalars().all())
