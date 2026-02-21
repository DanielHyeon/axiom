import json

from fastapi import HTTPException

from app.services.request_guard import (
    InMemoryIdempotencyStore,
    InMemoryRateLimiter,
    RedisIdempotencyStore,
    RedisRateLimiter,
)


class _FakeRedis:
    def __init__(self) -> None:
        self._kv: dict[str, str] = {}
        self._counter: dict[str, int] = {}
        self._ttl: dict[str, int] = {}

    def scan_iter(self, pattern: str):  # type: ignore[no-untyped-def]
        prefix = pattern.rstrip("*")
        for key in list(self._kv.keys()) + list(self._counter.keys()):
            if key.startswith(prefix):
                yield key

    def delete(self, key: str) -> None:
        self._kv.pop(key, None)
        self._counter.pop(key, None)
        self._ttl.pop(key, None)

    def incr(self, key: str) -> int:
        value = self._counter.get(key, 0) + 1
        self._counter[key] = value
        return value

    def expire(self, key: str, seconds: int) -> None:
        self._ttl[key] = seconds

    def ttl(self, key: str) -> int:
        return self._ttl.get(key, -1)

    def get(self, key: str):  # type: ignore[no-untyped-def]
        return self._kv.get(key)

    def set(self, key: str, value: str, ex: int, nx: bool = False):  # type: ignore[no-untyped-def]
        if nx and key in self._kv:
            return False
        self._kv[key] = value
        self._ttl[key] = ex
        return True

    def eval(self, script: str, numkeys: int, *args):  # type: ignore[no-untyped-def]
        assert numkeys == 1
        key = str(args[0])
        if "RG_IDEM_RESERVE" in script:
            reserve_value = str(args[1])
            ttl = int(args[2])
            current = self._kv.get(key)
            if current is None:
                self._kv[key] = reserve_value
                self._ttl[key] = ttl
                return ["RESERVED"]
            return ["EXISTS", current]
        if "RG_IDEM_COMPLETE" in script:
            fingerprint = str(args[1])
            completed_value = str(args[2])
            ttl = int(args[3])
            current = self._kv.get(key)
            if current is None:
                self._kv[key] = completed_value
                self._ttl[key] = ttl
                return ["CREATED"]
            row = json.loads(current)
            if row["fingerprint"] != fingerprint:
                return ["MISMATCH"]
            self._kv[key] = completed_value
            self._ttl[key] = ttl
            return ["COMPLETED"]
        raise AssertionError("unexpected eval script")


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter()
    limiter.check("u1:/x:write", limit=2, window_seconds=60)
    limiter.check("u1:/x:write", limit=2, window_seconds=60)
    try:
        limiter.check("u1:/x:write", limit=2, window_seconds=60)
        assert False, "expected rate limit exception"
    except HTTPException as exc:
        assert exc.status_code == 429
        assert exc.detail["code"] == "RATE_LIMITED"


def test_idempotency_fingerprint_and_replay() -> None:
    store = InMemoryIdempotencyStore()
    payload = {"a": 1, "b": "x"}
    fp = store.fingerprint(payload)
    store.set("idem-1", fingerprint=fp, status_code=200, response={"ok": True}, ttl_seconds=60)
    cached = store.ensure(key="idem-1", payload=payload)
    assert cached is not None
    assert cached["response"]["ok"] is True


def test_idempotency_mismatch_raises_conflict() -> None:
    store = InMemoryIdempotencyStore()
    payload = {"a": 1}
    store.set("idem-1", fingerprint=store.fingerprint(payload), status_code=200, response={"ok": True}, ttl_seconds=60)
    try:
        store.ensure(key="idem-1", payload={"a": 2})
        assert False, "expected idempotency conflict"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail["code"] == "IDEMPOTENCY_KEY_REUSE_MISMATCH"


def test_idempotency_in_progress_raises_conflict() -> None:
    store = InMemoryIdempotencyStore()
    payload = {"a": 1}
    assert store.ensure(key="idem-1", payload=payload) is None
    try:
        store.ensure(key="idem-1", payload=payload)
        assert False, "expected in progress conflict"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail["code"] == "IDEMPOTENCY_IN_PROGRESS"


def test_redis_rate_limiter_blocks_after_limit() -> None:
    limiter = RedisRateLimiter(_FakeRedis(), key_prefix="test")
    limiter.check("u1:/x:write", limit=2, window_seconds=60)
    limiter.check("u1:/x:write", limit=2, window_seconds=60)
    try:
        limiter.check("u1:/x:write", limit=2, window_seconds=60)
        assert False, "expected rate limit exception"
    except HTTPException as exc:
        assert exc.status_code == 429
        assert exc.detail["code"] == "RATE_LIMITED"


def test_redis_idempotency_fingerprint_and_replay() -> None:
    store = RedisIdempotencyStore(_FakeRedis(), key_prefix="test")
    payload = {"a": 1, "b": "x"}
    fp = store.fingerprint(payload)
    store.set("idem-1", fingerprint=fp, status_code=200, response={"ok": True}, ttl_seconds=60)
    cached = store.ensure(key="idem-1", payload=payload)
    assert cached is not None
    assert cached["response"]["ok"] is True


def test_redis_idempotency_mismatch_raises_conflict() -> None:
    store = RedisIdempotencyStore(_FakeRedis(), key_prefix="test")
    payload = {"a": 1}
    store.set("idem-1", fingerprint=store.fingerprint(payload), status_code=200, response={"ok": True}, ttl_seconds=60)
    try:
        store.ensure(key="idem-1", payload={"a": 2})
        assert False, "expected idempotency conflict"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail["code"] == "IDEMPOTENCY_KEY_REUSE_MISMATCH"


def test_redis_idempotency_in_progress_raises_conflict() -> None:
    store = RedisIdempotencyStore(_FakeRedis(), key_prefix="test")
    payload = {"a": 1}
    assert store.ensure(key="idem-1", payload=payload) is None
    try:
        store.ensure(key="idem-1", payload=payload)
        assert False, "expected in progress conflict"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail["code"] == "IDEMPOTENCY_IN_PROGRESS"
