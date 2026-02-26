"""PR5 tests: Redis job store, impact endpoint, job polling."""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.insight_job_store import (
    JobStoreUnavailableError,
    _build_cache_key,
    get_or_create_job,
    get_job,
    update_job,
    finish_job,
    _job_key,
    _jobmap_key,
)


# ── Helpers ──────────────────────────────────────────────────

class FakeRedis:
    """Minimal async Redis mock backed by dicts."""

    def __init__(self):
        self._strings: dict[str, str] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._expiry: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._strings.get(key)

    async def set(self, key: str, value: str, *, ex: int | None = None, nx: bool = False) -> bool | None:
        if nx and key in self._strings:
            return False  # NX failed — key already exists
        self._strings[key] = value
        if ex:
            self._expiry[key] = ex
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._strings:
                del self._strings[key]
                count += 1
            if key in self._hashes:
                del self._hashes[key]
                count += 1
        return count

    async def hset(self, key: str, *, mapping: dict[str, str]) -> None:
        if key not in self._hashes:
            self._hashes[key] = {}
        self._hashes[key].update(mapping)

    async def hgetall(self, key: str) -> dict[str, str]:
        return self._hashes.get(key, {})

    async def expire(self, key: str, ttl: int) -> None:
        self._expiry[key] = ttl

    async def ping(self) -> bool:
        return True


# ── Job key tests ────────────────────────────────────────────

class TestJobKeys:

    def test_job_key_format(self):
        assert _job_key("abc123") == "insight:job:abc123"

    def test_jobmap_key_deterministic(self):
        a = _jobmap_key("t1", "ds1", "kpi1", "30d", 50)
        b = _jobmap_key("t1", "ds1", "kpi1", "30d", 50)
        assert a == b

    def test_jobmap_key_different_params(self):
        a = _jobmap_key("t1", "ds1", "kpi1", "30d", 50)
        b = _jobmap_key("t1", "ds1", "kpi2", "30d", 50)
        assert a != b

    def test_jobmap_key_prefix(self):
        key = _jobmap_key("t1", "ds1", "kpi1", "30d", 50)
        assert key.startswith("insight:jobmap:")

    def test_jobmap_includes_datasource_id(self):
        """Different datasource_id must produce a different jobmap key (C-1 fix)."""
        key_ds1 = _jobmap_key("t1", "ds1", "kpi1", "30d", 50)
        key_ds2 = _jobmap_key("t1", "ds2", "kpi1", "30d", 50)
        assert key_ds1 != key_ds2


# ── get_or_create_job tests ──────────────────────────────────

class TestGetOrCreateJob:

    @pytest.mark.asyncio
    async def test_creates_new_job(self):
        rd = FakeRedis()
        job_id, is_new = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        assert is_new is True
        assert len(job_id) == 32  # uuid hex

    @pytest.mark.asyncio
    async def test_dedup_returns_existing_job(self):
        rd = FakeRedis()
        job_id_1, is_new_1 = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        assert is_new_1 is True

        job_id_2, is_new_2 = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        assert is_new_2 is False
        assert job_id_1 == job_id_2

    @pytest.mark.asyncio
    async def test_different_kpi_creates_different_job(self):
        rd = FakeRedis()
        id1, _ = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        id2, _ = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi2", time_range="30d", top=50,
        )
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_none_redis_raises(self):
        with pytest.raises(JobStoreUnavailableError):
            await get_or_create_job(
                None, tenant_id="t1", datasource_id="ds1",
                kpi_fingerprint="kpi1",
            )

    @pytest.mark.asyncio
    async def test_failed_job_gets_replaced(self):
        rd = FakeRedis()
        job_id_1, _ = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        # Mark as failed
        await finish_job(rd, job_id_1, error="boom")

        job_id_2, is_new = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        assert is_new is True
        assert job_id_2 != job_id_1


# ── get_job tests ────────────────────────────────────────────

class TestGetJob:

    @pytest.mark.asyncio
    async def test_returns_none_for_missing(self):
        rd = FakeRedis()
        assert await get_job(rd, "nonexistent") is None

    @pytest.mark.asyncio
    async def test_returns_job_data(self):
        rd = FakeRedis()
        job_id, _ = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1",
        )
        job = await get_job(rd, job_id)
        assert job is not None
        assert job["job_id"] == job_id
        assert job["tenant_id"] == "t1"
        assert job["status"] == "queued"

    @pytest.mark.asyncio
    async def test_none_redis_raises(self):
        with pytest.raises(JobStoreUnavailableError):
            await get_job(None, "abc")


# ── update_job tests ─────────────────────────────────────────

class TestUpdateJob:

    @pytest.mark.asyncio
    async def test_updates_fields(self):
        rd = FakeRedis()
        job_id, _ = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1",
        )
        await update_job(rd, job_id, status="running", progress="50")
        job = await get_job(rd, job_id)
        assert job["status"] == "running"
        assert job["progress"] == "50"

    @pytest.mark.asyncio
    async def test_none_redis_raises(self):
        with pytest.raises(JobStoreUnavailableError):
            await update_job(None, "abc", status="running")


# ── finish_job tests ─────────────────────────────────────────

class TestFinishJob:

    @pytest.mark.asyncio
    async def test_finish_success(self):
        rd = FakeRedis()
        job_id, _ = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1",
        )
        graph = {"nodes": [{"id": "n1"}], "edges": []}
        await finish_job(rd, job_id, graph_json=graph)

        job = await get_job(rd, job_id)
        assert job["status"] == "done"
        assert job["progress"] == "100"
        result = json.loads(job["result"])
        assert result["nodes"][0]["id"] == "n1"

    @pytest.mark.asyncio
    async def test_finish_failure(self):
        rd = FakeRedis()
        job_id, _ = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1",
        )
        await finish_job(rd, job_id, error="analysis failed")

        job = await get_job(rd, job_id)
        assert job["status"] == "failed"
        assert job["error"] == "analysis failed"

    @pytest.mark.asyncio
    async def test_none_redis_raises(self):
        with pytest.raises(JobStoreUnavailableError):
            await finish_job(None, "abc", graph_json={})


# ── Job state transitions ───────────────────────────────────

class TestJobStateTransitions:

    @pytest.mark.asyncio
    async def test_queued_to_running_to_done(self):
        rd = FakeRedis()
        job_id, _ = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1",
        )

        job = await get_job(rd, job_id)
        assert job["status"] == "queued"

        await update_job(rd, job_id, status="running", progress="10")
        job = await get_job(rd, job_id)
        assert job["status"] == "running"

        await finish_job(rd, job_id, graph_json={"nodes": [], "edges": []})
        job = await get_job(rd, job_id)
        assert job["status"] == "done"
        assert job["progress"] == "100"

    @pytest.mark.asyncio
    async def test_queued_to_running_to_failed(self):
        rd = FakeRedis()
        job_id, _ = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1",
        )

        await update_job(rd, job_id, status="running")
        await finish_job(rd, job_id, error="timeout")

        job = await get_job(rd, job_id)
        assert job["status"] == "failed"
        assert job["error"] == "timeout"


# ── insight_redis module tests ───────────────────────────────

class TestInsightRedis:

    @pytest.mark.asyncio
    async def test_get_insight_redis_returns_none_when_unavailable(self):
        """When aioredis is None or connection fails, returns None."""
        from app.core import insight_redis as mod
        # Reset state
        mod._client = None
        mod._initialised = False

        with patch.object(mod, "aioredis", None):
            result = await mod.get_insight_redis()
            assert result is None

        # Reset for other tests
        mod._client = None
        mod._initialised = False

    @pytest.mark.asyncio
    async def test_close_insight_redis_idempotent(self):
        from app.core import insight_redis as mod
        mod._client = None
        mod._initialised = False
        # Should not raise even when nothing to close
        await mod.close_insight_redis()
        assert mod._initialised is False


# ── datasource_id isolation tests (C-1 fix) ─────────────────

class TestDatasourceIsolation:

    @pytest.mark.asyncio
    async def test_different_datasource_creates_different_job(self):
        """Requests for different datasource_ids must not share a job."""
        rd = FakeRedis()
        id_ds1, is_new1 = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        id_ds2, is_new2 = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds2",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        assert is_new1 is True
        assert is_new2 is True
        assert id_ds1 != id_ds2

    @pytest.mark.asyncio
    async def test_same_datasource_deduped(self):
        """Same tenant+datasource+kpi must reuse an existing non-failed job."""
        rd = FakeRedis()
        id1, _ = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        id2, is_new2 = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        assert is_new2 is False
        assert id1 == id2


# ── cache key tests (C-2 fix) ────────────────────────────────

class TestCacheKey:

    def test_cache_key_deterministic(self):
        """Same inputs always produce the same cache key."""
        k1 = _build_cache_key("t1", "ds1", "kpi1", "30d", 50)
        k2 = _build_cache_key("t1", "ds1", "kpi1", "30d", 50)
        assert k1 == k2

    def test_cache_key_includes_datasource_id(self):
        """Cache keys for different datasources must differ."""
        k_ds1 = _build_cache_key("t1", "ds1", "kpi1", "30d", 50)
        k_ds2 = _build_cache_key("t1", "ds2", "kpi1", "30d", 50)
        assert k_ds1 != k_ds2

    def test_cache_key_prefix(self):
        k = _build_cache_key("t1", "ds1", "kpi1", "30d", 50)
        assert k.startswith("insight:cache:")


# ── SETNX dedup tests (H-1 fix) ──────────────────────────────

class TestSetnxDedup:

    @pytest.mark.asyncio
    async def test_nx_prevents_duplicate_on_concurrent_create(self):
        """Simulate concurrent requests: second NX attempt must fail and return existing."""
        rd = FakeRedis()

        # First call creates a job and owns the map_key via NX
        id1, new1 = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        assert new1 is True

        # Second call (same params) — NX fails, existing job is returned
        id2, new2 = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        assert new2 is False
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_failed_job_allows_new_creation(self):
        """After a job fails the jobmap entry should allow a fresh job."""
        rd = FakeRedis()
        id1, _ = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        await finish_job(rd, id1, error="pipeline_crash")

        # The jobmap key still points to the failed job; get_or_create_job should
        # detect the failed status and issue a new job.
        id2, new2 = await get_or_create_job(
            rd, tenant_id="t1", datasource_id="ds1",
            kpi_fingerprint="kpi1", time_range="30d", top=50,
        )
        assert new2 is True
        assert id2 != id1
