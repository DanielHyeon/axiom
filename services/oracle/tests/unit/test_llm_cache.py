"""LLM 시맨틱 캐시 단위 테스트."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.llm_cache import (
    _make_cache_key,
    get_cached_response,
    get_cache_metrics,
    invalidate_cache,
    set_cached_response,
)


# ── 캐시 키 생성 테스트 ───────────────────────────────────────────

class TestMakeCacheKey:
    """캐시 키 생성 함수 테스트."""

    def test_동일_입력이면_동일_키(self):
        k1 = _make_cache_key("hello", "gpt-4o", "system")
        k2 = _make_cache_key("hello", "gpt-4o", "system")
        assert k1 == k2

    def test_다른_프롬프트면_다른_키(self):
        k1 = _make_cache_key("hello", "gpt-4o")
        k2 = _make_cache_key("world", "gpt-4o")
        assert k1 != k2

    def test_다른_모델이면_다른_키(self):
        k1 = _make_cache_key("hello", "gpt-4o")
        k2 = _make_cache_key("hello", "gpt-3.5")
        assert k1 != k2

    def test_키에_접두사_포함(self):
        key = _make_cache_key("test")
        assert key.startswith("axiom:oracle:llm-cache:")


# ── Redis 클라이언트 None 처리 테스트 ─────────────────────────────

class TestNoneRedis:
    """Redis 클라이언트가 None일 때 안전하게 처리되는지 검증."""

    @pytest.mark.asyncio
    async def test_get_returns_none(self):
        assert await get_cached_response(None, "prompt") is None

    @pytest.mark.asyncio
    async def test_set_returns_false(self):
        assert await set_cached_response(None, "prompt", "resp") is False

    @pytest.mark.asyncio
    async def test_metrics_returns_zeros(self):
        m = await get_cache_metrics(None)
        assert m["hits"] == 0
        assert m["hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_invalidate_returns_false(self):
        assert await invalidate_cache(None, "prompt") is False


# ── 캐시 조회/저장 테스트 (Mock Redis) ────────────────────────────

class TestCacheHitMiss:
    """Mock Redis를 사용한 캐시 적중/미적중 테스트."""

    def _make_redis(self) -> AsyncMock:
        redis = AsyncMock()
        redis.hincrby = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_미적중_시_none_반환(self):
        redis = self._make_redis()
        redis.get = AsyncMock(return_value=None)

        result = await get_cached_response(redis, "새 질문", model="gpt-4o")
        assert result is None

    @pytest.mark.asyncio
    async def test_적중_시_응답_반환(self):
        redis = self._make_redis()
        cached_data = json.dumps({"response": "cached answer", "model": "gpt-4o"})
        redis.get = AsyncMock(return_value=cached_data.encode())

        result = await get_cached_response(redis, "질문", model="gpt-4o")
        assert result == "cached answer"

    @pytest.mark.asyncio
    async def test_저장_성공(self):
        redis = self._make_redis()
        redis.set = AsyncMock()

        ok = await set_cached_response(redis, "질문", "응답", model="gpt-4o", ttl=600)
        assert ok is True
        redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_무효화_성공(self):
        redis = self._make_redis()
        redis.delete = AsyncMock()

        ok = await invalidate_cache(redis, "질문", model="gpt-4o")
        assert ok is True
        redis.delete.assert_called_once()


# ── 메트릭 조회 테스트 ────────────────────────────────────────────

class TestCacheMetrics:
    """캐시 메트릭 조회 테스트."""

    @pytest.mark.asyncio
    async def test_히트율_계산(self):
        redis = AsyncMock()
        redis.hgetall = AsyncMock(return_value={
            b"hits": b"75",
            b"misses": b"25",
            b"sets": b"100",
        })

        m = await get_cache_metrics(redis)
        assert m["hits"] == 75
        assert m["misses"] == 25
        assert m["hit_rate"] == 75.0

    @pytest.mark.asyncio
    async def test_히트율_0일때(self):
        redis = AsyncMock()
        redis.hgetall = AsyncMock(return_value={})

        m = await get_cache_metrics(redis)
        assert m["hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_redis_에러시_기본값(self):
        redis = AsyncMock()
        redis.hgetall = AsyncMock(side_effect=ConnectionError("disconnected"))

        m = await get_cache_metrics(redis)
        assert m == {"hits": 0, "misses": 0, "sets": 0, "hit_rate": 0.0}
