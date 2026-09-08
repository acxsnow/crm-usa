"""Refresh-token revocation registry (spec 6.1, 6.3.7: logout and password
reset must invalidate outstanding sessions).

Two mechanisms, matching what each action needs:
- `denylist_jti` / `is_denylisted`: revokes ONE specific refresh token (used
  by /auth/logout, and to invalidate the old refresh token on each rotation
  so a stolen-then-replayed old token can't be reused). Backed by Redis with
  a TTL; falls back to an in-process dict when Redis isn't reachable.
- User.token_version (see users/models.py): revokes EVERY session for a user
  at once (used by password reset — spec 6.3.7 "revoke all sessions"). That
  one is a plain DB column rather than Redis, so "kill everything" survives
  even if Redis is down or was never configured.
"""
import time

from app.core.redis_client import get_redis_if_available

# In-memory fallback: jti -> expiry epoch seconds.
_denylist: dict[str, float] = {}


def _prune_expired() -> None:
    now = time.time()
    expired = [jti for jti, expires_at in _denylist.items() if expires_at <= now]
    for jti in expired:
        _denylist.pop(jti, None)


async def denylist_jti(jti: str, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    redis = await get_redis_if_available()
    if redis is not None:
        try:
            await redis.setex(f"denylist:{jti}", ttl_seconds, "1")
            return
        except Exception:
            pass
    _prune_expired()
    _denylist[jti] = time.time() + ttl_seconds


async def is_denylisted(jti: str) -> bool:
    redis = await get_redis_if_available()
    if redis is not None:
        try:
            return bool(await redis.exists(f"denylist:{jti}"))
        except Exception:
            pass
    _prune_expired()
    return jti in _denylist


def clear_denylist() -> None:
    """Test helper only — clears the in-memory fallback store."""
    _denylist.clear()
