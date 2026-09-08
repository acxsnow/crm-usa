"""Fixed-window rate limiter (spec 6.1, 6.3).

Backed by Redis (INCR + EXPIRE) when available, so counters are shared
across API instances in production — falls back automatically to an
in-process store when Redis isn't reachable (local dev without
docker-compose, or the test suite). See app/core/redis_client.py for the
availability check.
"""
import time
from collections import defaultdict

from app.core.redis_client import get_redis_if_available

# In-memory fallback store.
_buckets: dict[str, list[float]] = defaultdict(list)


def _is_rate_limited_in_memory(key: str, *, max_attempts: int, window_seconds: int) -> bool:
    now = time.time()
    attempts = _buckets[key]
    cutoff = now - window_seconds
    while attempts and attempts[0] < cutoff:
        attempts.pop(0)
    if len(attempts) >= max_attempts:
        return True
    attempts.append(now)
    return False


async def is_rate_limited(key: str, *, max_attempts: int, window_seconds: int) -> bool:
    redis = await get_redis_if_available()
    if redis is None:
        return _is_rate_limited_in_memory(key, max_attempts=max_attempts, window_seconds=window_seconds)

    redis_key = f"ratelimit:{key}"
    try:
        count = await redis.incr(redis_key)
        if count == 1:
            await redis.expire(redis_key, window_seconds)
        return count > max_attempts
    except Exception:
        # Redis flaked mid-request: fail open to the in-memory store rather
        # than blocking login entirely.
        return _is_rate_limited_in_memory(key, max_attempts=max_attempts, window_seconds=window_seconds)


async def reset_bucket(key: str) -> None:
    _buckets.pop(key, None)
    redis = await get_redis_if_available()
    if redis is not None:
        try:
            await redis.delete(f"ratelimit:{key}")
        except Exception:
            pass


def clear_all_buckets() -> None:
    """Test helper only — clears the in-memory fallback store."""
    _buckets.clear()
