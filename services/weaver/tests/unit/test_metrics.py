from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.metrics import metrics_service
from app.services.request_guard import InMemoryIdempotencyStore, InMemoryRateLimiter


def test_request_guard_metrics_increment() -> None:
    metrics_service.clear()
    limiter = InMemoryRateLimiter()
    limiter.check("u1:/x:write", limit=1, window_seconds=60)
    try:
        limiter.check("u1:/x:write", limit=1, window_seconds=60)
        assert False, "expected rate limit"
    except Exception:
        pass

    store = InMemoryIdempotencyStore()
    payload = {"a": 1}
    store.set("idem-1", fingerprint=store.fingerprint(payload), status_code=200, response={"ok": True})
    try:
        store.ensure(key="idem-1", payload={"a": 2})
        assert False, "expected mismatch"
    except Exception:
        pass

    store2 = InMemoryIdempotencyStore()
    assert store2.ensure(key="idem-2", payload=payload) is None
    try:
        store2.ensure(key="idem-2", payload=payload)
        assert False, "expected in progress"
    except Exception:
        pass

    snap = metrics_service.snapshot()
    assert any(k.startswith("weaver_request_guard_rate_limited_total{") and v >= 1 for k, v in snap.items())
    assert any(k.startswith("weaver_request_guard_idempotency_mismatch_total{") and v >= 1 for k, v in snap.items())
    assert any(k.startswith("weaver_request_guard_idempotency_in_progress_total{") and v >= 1 for k, v in snap.items())


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_counters() -> None:
    metrics_service.clear()
    metrics_service.inc(
        "weaver_request_guard_rate_limited_total",
        labels={"mode": "memory", "endpoint": "/api/x", "operation": "write"},
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/metrics")
        assert res.status_code == 200
        body = res.text
        assert "weaver_request_guard_rate_limited_total" in body
        assert "# TYPE weaver_request_guard_rate_limited_total counter" in body
        assert 'weaver_request_guard_rate_limited_total{endpoint="/api/x",mode="memory",operation="write"} 1' in body
