from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from fastapi import HTTPException

from app.core.config import settings
from app.services.metrics import metrics_service

try:
    import redis
except Exception:  # pragma: no cover - optional dependency in some environments
    redis = None

logger = logging.getLogger("weaver.request_guard")


def _parse_rate_limit_key(key: str) -> tuple[str, str]:
    # Expected pattern: "{user_id}:{endpoint}:{operation}"
    try:
        head, operation = key.rsplit(":", 1)
        _, endpoint = head.split(":", 1)
        return endpoint, operation
    except Exception:
        return "unknown", "unknown"


def _parse_idempotency_key(key: str) -> str:
    # Preferred pattern: "{tenant_id}:{endpoint}:{client_key}"
    parts = key.split(":", 2)
    if len(parts) == 3 and parts[1].startswith("/"):
        return parts[1]
    return "unknown"


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._windows: dict[str, dict[str, float | int]] = {}

    def clear(self) -> None:
        self._windows.clear()

    def check(self, key: str, *, limit: int, window_seconds: int = 60) -> None:
        now = time.time()
        row = self._windows.get(key)
        if not row or now - float(row["start"]) >= window_seconds:
            row = {"start": now, "count": 0}
            self._windows[key] = row
        count = int(row["count"]) + 1
        row["count"] = count
        if count > limit:
            retry_after = max(1, window_seconds - int(now - float(row["start"])))
            endpoint, operation = _parse_rate_limit_key(key)
            metrics_service.inc(
                "weaver_request_guard_rate_limited_total",
                labels={"mode": "memory", "endpoint": endpoint, "operation": operation},
            )
            raise HTTPException(
                status_code=429,
                detail={"code": "RATE_LIMITED", "retry_after_seconds": retry_after},
            )


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def clear(self) -> None:
        self._store.clear()

    @staticmethod
    def fingerprint(payload: Any) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        row = self._store.get(key)
        if not row:
            return None
        if row["expires_at"] < time.time():
            del self._store[key]
            return None
        return row

    def set(self, key: str, *, fingerprint: str, status_code: int, response: Any, ttl_seconds: int = 600) -> None:
        existing = self.get(key) if key else None
        if existing and existing["fingerprint"] != fingerprint:
            metrics_service.inc(
                "weaver_request_guard_idempotency_mismatch_total",
                labels={"mode": "memory", "endpoint": _parse_idempotency_key(key)},
            )
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_KEY_REUSE_MISMATCH"},
            )
        self._store[key] = {
            "fingerprint": fingerprint,
            "status_code": status_code,
            "response": response,
            "state": "completed",
            "expires_at": time.time() + ttl_seconds,
        }

    def ensure(self, *, key: str | None, payload: Any) -> dict[str, Any] | None:
        if not key:
            return None
        fp = self.fingerprint(payload)
        existing = self.get(key)
        if not existing:
            self._store[key] = {
                "fingerprint": fp,
                "status_code": None,
                "response": None,
                "state": "in_progress",
                "expires_at": time.time() + settings.request_guard_idempotency_ttl_seconds,
            }
            return None
        if existing["fingerprint"] != fp:
            metrics_service.inc(
                "weaver_request_guard_idempotency_mismatch_total",
                labels={"mode": "memory", "endpoint": _parse_idempotency_key(key)},
            )
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_KEY_REUSE_MISMATCH"},
            )
        if existing.get("state") == "in_progress":
            metrics_service.inc(
                "weaver_request_guard_idempotency_in_progress_total",
                labels={"mode": "memory", "endpoint": _parse_idempotency_key(key)},
            )
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_IN_PROGRESS"},
            )
        return existing


class RedisRateLimiter:
    def __init__(self, client: Any, key_prefix: str = "weaver") -> None:
        self._client = client
        self._key_prefix = key_prefix

    def _key(self, raw_key: str) -> str:
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return f"{self._key_prefix}:rl:{key_hash}"

    def clear(self) -> None:
        for key in self._client.scan_iter(f"{self._key_prefix}:rl:*"):
            self._client.delete(key)

    def check(self, key: str, *, limit: int, window_seconds: int = 60) -> None:
        redis_key = self._key(key)
        count = int(self._client.incr(redis_key))
        if count == 1:
            self._client.expire(redis_key, window_seconds)
        if count > limit:
            ttl = int(self._client.ttl(redis_key))
            retry_after = max(1, ttl if ttl > 0 else window_seconds)
            endpoint, operation = _parse_rate_limit_key(key)
            metrics_service.inc(
                "weaver_request_guard_rate_limited_total",
                labels={"mode": "redis", "endpoint": endpoint, "operation": operation},
            )
            raise HTTPException(
                status_code=429,
                detail={"code": "RATE_LIMITED", "retry_after_seconds": retry_after},
            )


class RedisIdempotencyStore:
    _RESERVE_SCRIPT = """
-- RG_IDEM_RESERVE
local current = redis.call("GET", KEYS[1])
if not current then
  redis.call("SET", KEYS[1], ARGV[1], "EX", tonumber(ARGV[2]))
  return {"RESERVED"}
end
return {"EXISTS", current}
"""

    _COMPLETE_SCRIPT = """
-- RG_IDEM_COMPLETE
local current = redis.call("GET", KEYS[1])
if not current then
  redis.call("SET", KEYS[1], ARGV[2], "EX", tonumber(ARGV[3]))
  return {"CREATED"}
end
local row = cjson.decode(current)
if row["fingerprint"] ~= ARGV[1] then
  return {"MISMATCH"}
end
redis.call("SET", KEYS[1], ARGV[2], "EX", tonumber(ARGV[3]))
return {"COMPLETED"}
"""

    def __init__(self, client: Any, key_prefix: str = "weaver") -> None:
        self._client = client
        self._key_prefix = key_prefix

    def _key(self, idempotency_key: str) -> str:
        return f"{self._key_prefix}:idem:{idempotency_key}"

    @staticmethod
    def fingerprint(payload: Any) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def clear(self) -> None:
        for key in self._client.scan_iter(f"{self._key_prefix}:idem:*"):
            self._client.delete(key)

    def get(self, key: str) -> dict[str, Any] | None:
        if not key:
            return None
        raw = self._client.get(self._key(key))
        if not raw:
            return None
        return json.loads(str(raw))

    def set(self, key: str, *, fingerprint: str, status_code: int, response: Any, ttl_seconds: int = 600) -> None:
        if not key:
            return
        ttl = ttl_seconds if ttl_seconds > 0 else settings.request_guard_idempotency_ttl_seconds
        value = json.dumps(
            {
                "fingerprint": fingerprint,
                "status_code": status_code,
                "response": response,
                "state": "completed",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        result = self._client.eval(self._COMPLETE_SCRIPT, 1, self._key(key), fingerprint, value, ttl)
        status = result[0] if isinstance(result, (list, tuple)) and result else result
        if status == "MISMATCH":
            metrics_service.inc(
                "weaver_request_guard_idempotency_mismatch_total",
                labels={"mode": "redis", "endpoint": _parse_idempotency_key(key)},
            )
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_KEY_REUSE_MISMATCH"},
            )

    def ensure(self, *, key: str | None, payload: Any) -> dict[str, Any] | None:
        if not key:
            return None
        fp = self.fingerprint(payload)
        reserve = json.dumps(
            {
                "fingerprint": fp,
                "status_code": None,
                "response": None,
                "state": "in_progress",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        result = self._client.eval(
            self._RESERVE_SCRIPT,
            1,
            self._key(key),
            reserve,
            settings.request_guard_idempotency_ttl_seconds,
        )
        status = result[0] if isinstance(result, (list, tuple)) and result else result
        if status == "RESERVED":
            return None
        raw_existing = result[1] if isinstance(result, (list, tuple)) and len(result) > 1 else None
        existing = json.loads(str(raw_existing)) if raw_existing else self.get(key)
        if not existing:
            return None
        if existing["fingerprint"] != fp:
            metrics_service.inc(
                "weaver_request_guard_idempotency_mismatch_total",
                labels={"mode": "redis", "endpoint": _parse_idempotency_key(key)},
            )
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_KEY_REUSE_MISMATCH"},
            )
        if existing.get("state") == "in_progress":
            metrics_service.inc(
                "weaver_request_guard_idempotency_in_progress_total",
                labels={"mode": "redis", "endpoint": _parse_idempotency_key(key)},
            )
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_IN_PROGRESS"},
            )
        return existing


def _build_request_guard() -> tuple[Any, Any]:
    if settings.request_guard_redis_mode:
        if redis is None:
            logger.warning("Redis mode enabled but redis package is unavailable; fallback to in-memory request guard")
            return InMemoryRateLimiter(), InMemoryIdempotencyStore()
        try:
            client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            client.ping()
            logger.info("Redis request guard enabled. redis_url=%s", settings.redis_url)
            return RedisRateLimiter(client), RedisIdempotencyStore(client)
        except Exception as exc:
            logger.warning("Redis request guard unavailable; fallback to in-memory: %s", exc)
    return InMemoryRateLimiter(), InMemoryIdempotencyStore()


rate_limiter, idempotency_store = _build_request_guard()
