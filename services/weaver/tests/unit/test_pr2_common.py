"""PR2 tests: InsightError handler, RLS session."""
from __future__ import annotations

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from app.core.insight_errors import InsightError, insight_error_handler
from app.core.rls_session import rls_session


# ── InsightError tests ───────────────────────────────────────

class TestInsightError:

    def test_error_is_exception(self):
        err = InsightError(status_code=400, error_code="BAD", error_message="bad input")
        assert isinstance(err, Exception)

    def test_retryable_default_false(self):
        err = InsightError(status_code=500, error_code="X", error_message="boom")
        assert err.retryable is False
        assert err.hint == ""

    def test_retryable_set(self):
        err = InsightError(
            status_code=503, error_code="OVERLOADED", error_message="try again",
            retryable=True, hint="Wait 5 seconds", poll_after_ms=5000,
        )
        assert err.retryable is True
        assert err.hint == "Wait 5 seconds"
        assert err.poll_after_ms == 5000


class TestInsightErrorHandler:

    @pytest.mark.asyncio
    async def test_handler_returns_json_with_error_fields(self):
        request = MagicMock()
        request.state.request_id = "trace-123"
        request.headers = {}

        exc = InsightError(status_code=422, error_code="INVALID_SQL", error_message="parse failed")
        resp = await insight_error_handler(request, exc)

        assert resp.status_code == 422
        import json
        body = json.loads(resp.body)
        assert body["error"]["code"] == "INVALID_SQL"
        assert body["error"]["message"] == "parse failed"
        assert body["error"]["retryable"] is False
        assert body["trace_id"] == "trace-123"

    @pytest.mark.asyncio
    async def test_handler_includes_poll_after_ms_when_set(self):
        request = MagicMock()
        request.state.request_id = "t-1"
        request.headers = {}

        exc = InsightError(
            status_code=503, error_code="BUSY", error_message="overloaded",
            retryable=True, poll_after_ms=3000,
        )
        resp = await insight_error_handler(request, exc)

        import json
        body = json.loads(resp.body)
        assert body["poll_after_ms"] == 3000
        assert body["error"]["retryable"] is True

    @pytest.mark.asyncio
    async def test_handler_falls_back_to_header_trace_id(self):
        request = MagicMock()
        request.state = MagicMock(spec=[])  # no request_id attribute
        request.headers = {"X-Request-Id": "from-header"}

        exc = InsightError(status_code=400, error_code="X", error_message="y")
        resp = await insight_error_handler(request, exc)

        import json
        body = json.loads(resp.body)
        assert body["trace_id"] == "from-header"


# ── RLS Session tests ────────────────────────────────────────

def _make_mock_pool():
    conn = AsyncMock()
    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire

    # conn.transaction() must also be an async context manager
    @asynccontextmanager
    async def _transaction():
        yield

    conn.transaction = _transaction

    return pool, conn


class TestRlsSession:

    @pytest.mark.asyncio
    async def test_sets_current_tenant_id(self):
        pool, conn = _make_mock_pool()

        async with rls_session(pool, "tenant-42") as c:
            assert c is conn

        conn.execute.assert_called_once_with(
            "SELECT set_config('app.current_tenant_id', $1, true)",
            "tenant-42",
        )

    @pytest.mark.asyncio
    async def test_yields_connection_inside_transaction(self):
        pool, conn = _make_mock_pool()

        async with rls_session(pool, "t1") as c:
            # Should be usable for queries
            await c.fetch("SELECT 1")

        conn.fetch.assert_called_once_with("SELECT 1")
