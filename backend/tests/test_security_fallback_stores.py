from app.core import rate_limit, token_denylist


class _RedisCounter:
    def __init__(self):
        self.count = 0
        self.expire_calls = []

    async def incr(self, key: str) -> int:
        self.count += 1
        return self.count

    async def expire(self, key: str, window_seconds: int) -> None:
        self.expire_calls.append((key, window_seconds))


class _RedisBrokenCounter:
    async def incr(self, key: str) -> int:
        raise RuntimeError("redis down")


class _RedisDenylist:
    def __init__(self):
        self.values: dict[str, str] = {}

    async def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        self.values[key] = value

    async def exists(self, key: str) -> int:
        return int(key in self.values)


class _RedisBrokenDenylist:
    async def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        raise RuntimeError("write failed")

    async def exists(self, key: str) -> int:
        raise RuntimeError("read failed")


async def test_rate_limit_in_memory_window_expires(monkeypatch):
    rate_limit.clear_all_buckets()
    now = [100.0]
    monkeypatch.setattr(rate_limit.time, "time", lambda: now[0])
    assert rate_limit._is_rate_limited_in_memory("login:1", max_attempts=2, window_seconds=5) is False
    assert rate_limit._is_rate_limited_in_memory("login:1", max_attempts=2, window_seconds=5) is False
    assert rate_limit._is_rate_limited_in_memory("login:1", max_attempts=2, window_seconds=5) is True
    now[0] = 106.0
    assert rate_limit._is_rate_limited_in_memory("login:1", max_attempts=2, window_seconds=5) is False


async def test_rate_limit_uses_redis_when_available(monkeypatch):
    redis = _RedisCounter()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(rate_limit, "get_redis_if_available", fake_get_redis)
    assert await rate_limit.is_rate_limited("login:redis", max_attempts=2, window_seconds=30) is False
    assert await rate_limit.is_rate_limited("login:redis", max_attempts=2, window_seconds=30) is False
    assert await rate_limit.is_rate_limited("login:redis", max_attempts=2, window_seconds=30) is True
    assert redis.expire_calls == [("ratelimit:login:redis", 30)]


async def test_rate_limit_falls_back_if_redis_breaks(monkeypatch):
    async def fake_get_redis():
        return _RedisBrokenCounter()

    monkeypatch.setattr(rate_limit, "get_redis_if_available", fake_get_redis)
    calls = {"count": 0}

    def fake_memory(*args, **kwargs):
        calls["count"] += 1
        return True

    monkeypatch.setattr(rate_limit, "_is_rate_limited_in_memory", fake_memory)
    assert await rate_limit.is_rate_limited("login:fallback", max_attempts=1, window_seconds=10) is True
    assert calls["count"] == 1


async def test_reset_bucket_clears_local_and_redis_key(monkeypatch):
    rate_limit.clear_all_buckets()
    rate_limit._buckets["login:reset"] = [1.0]

    class _RedisDelete:
        def __init__(self):
            self.deleted = []

        async def delete(self, key: str) -> None:
            self.deleted.append(key)

    redis = _RedisDelete()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(rate_limit, "get_redis_if_available", fake_get_redis)
    await rate_limit.reset_bucket("login:reset")
    assert "login:reset" not in rate_limit._buckets
    assert redis.deleted == ["ratelimit:login:reset"]


async def test_denylist_uses_redis_store(monkeypatch):
    token_denylist.clear_denylist()
    redis = _RedisDenylist()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(token_denylist, "get_redis_if_available", fake_get_redis)
    await token_denylist.denylist_jti("abc", 120)
    assert await token_denylist.is_denylisted("abc") is True


async def test_denylist_falls_back_to_memory_and_prunes_expired(monkeypatch):
    token_denylist.clear_denylist()
    now = [100.0]
    monkeypatch.setattr(token_denylist.time, "time", lambda: now[0])

    async def fake_get_redis():
        return _RedisBrokenDenylist()

    monkeypatch.setattr(token_denylist, "get_redis_if_available", fake_get_redis)
    await token_denylist.denylist_jti("fallback", 5)
    assert await token_denylist.is_denylisted("fallback") is True
    now[0] = 106.0
    assert await token_denylist.is_denylisted("fallback") is False


async def test_denylist_ignores_non_positive_ttl():
    token_denylist.clear_denylist()
    await token_denylist.denylist_jti("nope", 0)
    assert await token_denylist.is_denylisted("nope") is False
