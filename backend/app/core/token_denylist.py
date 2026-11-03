"""Refresh-token revocation registry (spec 6.1, 6.3.7: logout and password
reset must invalidate outstanding sessions).

Two mechanisms, matching what each action needs:
- `denylist_jti` / `is_denylisted`: revokes ONE specific refresh token (used
  by /auth/logout, and to invalidate the old refresh token on each rotation
  so a stolen-then-replayed old token can't be reused). Backed by Redis with
  a TTL; falls back to an in-process dict when Redis isn't reachable.
  On rotation the old token gets a short grace (`grace_seconds`, see
  `in_grace`): if the response carrying the new cookie never reached the
  browser (signal dropped, page reloaded mid-refresh, two devices), the next
  refresh still arrives with the old token, and without the grace that closed
  the session (client report, 3 nov 2026). Logout stays strict: no grace.
- User.token_version (see users/models.py): revokes EVERY session for a user
  at once (used by password reset — spec 6.3.7 "revoke all sessions"). That
  one is a plain DB column rather than Redis, so "kill everything" survives
  even if Redis is down or was never configured.
"""
import time

import structlog

from app.core.redis_client import get_redis_if_available

logger = structlog.get_logger(__name__)

# In-memory fallback: jti -> (expiry epoch seconds, grace-until epoch seconds; 0 = no grace).
_denylist: dict[str, tuple[float, float]] = {}

# Stored value for a revocation without grace (logout).
_STRICT = "1"


def _prune_expired() -> None:
    now = time.time()
    expired = [jti for jti, (expires_at, _) in _denylist.items() if expires_at <= now]
    for jti in expired:
        _denylist.pop(jti, None)


async def denylist_jti(jti: str, ttl_seconds: int, *, grace_seconds: int = 0) -> None:
    if ttl_seconds <= 0:
        return
    gracia = time.time() + grace_seconds if grace_seconds > 0 else 0.0
    redis = await get_redis_if_available()
    if redis is not None:
        try:
            await redis.setex(f"denylist:{jti}", ttl_seconds, repr(gracia) if gracia else _STRICT)
            return
        except Exception as exc:
            # El token queda revocado solo en este proceso: otro worker podría
            # seguir aceptándolo hasta que expire. Hay que saberlo.
            logger.warning("denylist.redis_write_failed", error=str(exc))
    _prune_expired()
    _denylist[jti] = (time.time() + ttl_seconds, gracia)


async def is_denylisted(jti: str) -> bool:
    redis = await get_redis_if_available()
    if redis is not None:
        try:
            return bool(await redis.exists(f"denylist:{jti}"))
        except Exception as exc:
            logger.warning("denylist.redis_read_failed", error=str(exc))
    _prune_expired()
    return jti in _denylist


async def in_grace(jti: str) -> bool:
    """True if `jti` was revoked by a rotation less than `grace_seconds` ago."""
    redis = await get_redis_if_available()
    if redis is not None:
        try:
            valor = await redis.get(f"denylist:{jti}")
            if isinstance(valor, bytes):
                valor = valor.decode()
            return bool(valor) and valor != _STRICT and float(valor) > time.time()
        except Exception as exc:
            logger.warning("denylist.redis_read_failed", error=str(exc))
    _prune_expired()
    entrada = _denylist.get(jti)
    return entrada is not None and entrada[1] > time.time()


def clear_denylist() -> None:
    """Test helper only — clears the in-memory fallback store."""
    _denylist.clear()
