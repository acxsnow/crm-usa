"""Shared async Redis client with a fast, cached availability check.

Rate limiting and refresh-token revocation both want a shared store across
API instances (spec 6.1/6.3). Redis is that store in production
(docker-compose runs a `redis` service). In local/test runs where Redis
isn't up, both callers fall back to an in-process store automatically —
correct for a single process, and it means `pytest` never needs a real
Redis server. The availability check is cached briefly so a down Redis
doesn't add a connection-timeout delay to every single request.
"""
import time

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

_client: aioredis.Redis | None = None
_available: bool | None = None
_last_checked_at: float = 0.0
_RECHECK_INTERVAL_SECONDS = 15.0


def _get_client() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True, socket_connect_timeout=0.2, socket_timeout=0.2,
        )
    return _client


async def get_redis_if_available() -> aioredis.Redis | None:
    """Returns a connected Redis client, or None if Redis is unreachable
    right now. Caches the negative result briefly to avoid repeated
    connection-timeout delays when Redis is simply not running."""
    global _available, _last_checked_at

    now = time.monotonic()
    if _available is False and (now - _last_checked_at) < _RECHECK_INTERVAL_SECONDS:
        return None

    client = _get_client()
    try:
        await client.ping()
        _available = True
        return client
    except Exception:
        _available = False
        _last_checked_at = now
        return None
