"""임베딩 기반 시맨틱 캐시 단위 테스트.

코사인 유사도 계산, Redis 미연결 폴백, 캐시 저장/조회,
임계값 기반 매칭, 테넌트 격리, 만료 키 정리를 검증한다.
실제 OpenAI API 호출 없이 고정 벡터로 결정론적 테스트를 수행한다.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.services.embedding_cache import (
    _cosine_similarity,
    _embed_index_key,
    _embed_key,
    semantic_cache_get,
    semantic_cache_set,
    DEFAULT_SIMILARITY_THRESHOLD,
)


# ──────────────────────────────────────────────────────────────
# Mock Redis — get/set/sadd/srem/smembers/expire/delete 지원
# ──────────────────────────────────────────────────────────────

class MockRedis:
    """인메모리 Redis 모방 객체.

    비동기 인터페이스(get, set, sadd, srem, smembers, expire, delete)를
    딕셔너리 기반으로 구현하여 외부 Redis 의존성 없이 테스트한다.
    """

    def __init__(self):
        self._store: dict[str, bytes] = {}
        self._sets: dict[str, set[str]] = {}

    async def get(self, key: str) -> bytes | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value.encode() if isinstance(value, str) else value

    async def sadd(self, key: str, *members: str) -> None:
        if key not in self._sets:
            self._sets[key] = set()
        for m in members:
            self._sets[key].add(m)

    async def srem(self, key: str, *members: str) -> None:
        if key in self._sets:
            for m in members:
                self._sets[key].discard(m)

    async def smembers(self, key: str) -> set[str]:
        return self._sets.get(key, set())

    async def expire(self, key: str, seconds: int) -> None:
        pass  # TTL은 테스트에서 무시

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._sets.pop(key, None)


# ──────────────────────────────────────────────────────────────
# 테스트용 고정 임베딩 벡터
# ──────────────────────────────────────────────────────────────

# 3차원 단순 벡터 (코사인 유사도 검증용)
_VEC_A = [1.0, 0.0, 0.0]
_VEC_B = [0.0, 1.0, 0.0]
_VEC_SAME = [1.0, 0.0, 0.0]
_VEC_OPPOSITE = [-1.0, 0.0, 0.0]
_VEC_ZERO = [0.0, 0.0, 0.0]

# 1536차원 고정 벡터 (실제 임베딩 크기 시뮬레이션)
_EMBED_FULL = [0.01] * 1536
_EMBED_SIMILAR = [0.01] * 1535 + [0.02]  # 거의 동일
_EMBED_DIFFERENT = [0.99] * 768 + [-0.99] * 768  # 완전히 다름


# ──────────────────────────────────────────────────────────────
# 코사인 유사도 테스트
# ──────────────────────────────────────────────────────────────

class TestCosineSimilarity:
    """_cosine_similarity() — 벡터 유사도 계산 검증."""

    def test_코사인_유사도_동일벡터_1(self):
        """동일한 벡터의 코사인 유사도는 1.0이다."""
        score = _cosine_similarity(_VEC_A, _VEC_SAME)
        assert abs(score - 1.0) < 1e-6

    def test_코사인_유사도_직교_0(self):
        """직교(수직) 벡터의 코사인 유사도는 0.0이다."""
        score = _cosine_similarity(_VEC_A, _VEC_B)
        assert abs(score - 0.0) < 1e-6

    def test_코사인_유사도_반대_음수(self):
        """반대 방향 벡터의 코사인 유사도는 -1.0이다."""
        score = _cosine_similarity(_VEC_A, _VEC_OPPOSITE)
        assert abs(score - (-1.0)) < 1e-6

    def test_코사인_유사도_영벡터_0(self):
        """영벡터와의 코사인 유사도는 0.0이다 (0으로 나누기 방지)."""
        score = _cosine_similarity(_VEC_A, _VEC_ZERO)
        assert score == 0.0


# ──────────────────────────────────────────────────────────────
# Redis 미연결 / API 키 누락 폴백 테스트
# ──────────────────────────────────────────────────────────────

class TestNoneRedisAndApiKey:
    """Redis/API 키가 없을 때 안전하게 (None, 0.0) / False를 반환하는지 검증."""

    @pytest.mark.asyncio
    async def test_None_redis_캐시_조회_None(self):
        """redis_client가 None이면 (None, 0.0)을 반환한다."""
        result, score = await semantic_cache_get(None, "test prompt", api_key="sk-xxx")
        assert result is None
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_None_redis_캐시_저장_False(self):
        """redis_client가 None이면 False를 반환한다."""
        ok = await semantic_cache_set(None, "prompt", "response", api_key="sk-xxx")
        assert ok is False

    @pytest.mark.asyncio
    async def test_빈_API키_캐시_조회_None(self):
        """api_key가 빈 문자열이면 (None, 0.0)을 반환한다."""
        redis = MockRedis()
        result, score = await semantic_cache_get(redis, "test prompt", api_key="")
        assert result is None
        assert score == 0.0


# ──────────────────────────────────────────────────────────────
# 캐시 저장/조회 통합 테스트 (Mock 임베딩)
# ──────────────────────────────────────────────────────────────

class TestSemanticCacheSetAndGet:
    """semantic_cache_set/get — Mock 임베딩을 사용한 캐시 저장/조회 검증."""

    @pytest.mark.asyncio
    async def test_캐시_저장_후_조회(self):
        """저장한 프롬프트와 동일한 임베딩으로 조회하면 응답을 반환한다."""
        redis = MockRedis()

        # _get_embedding + logger를 모킹 (structlog 호환성 문제 회피)
        with patch(
            "app.services.embedding_cache._get_embedding",
            new_callable=AsyncMock,
            return_value=_EMBED_FULL,
        ), patch("app.services.embedding_cache.logger") as mock_logger:
            # 저장
            ok = await semantic_cache_set(
                redis, "매출 현황 알려줘", "매출은 100억입니다",
                api_key="sk-test", tenant_id="t1", project_id="p1",
            )
            assert ok is True

            # 동일 임베딩으로 조회 — 유사도 1.0이므로 적중
            result, score = await semantic_cache_get(
                redis, "매출 현황 알려줘",
                api_key="sk-test", tenant_id="t1", project_id="p1",
            )
            assert result == "매출은 100억입니다"
            assert score > DEFAULT_SIMILARITY_THRESHOLD

    @pytest.mark.asyncio
    async def test_임계값_미달_미적중(self):
        """유사도가 임계값 미만이면 None을 반환한다."""
        redis = MockRedis()

        # 저장 시 _EMBED_FULL, 조회 시 _EMBED_DIFFERENT 사용
        call_count = 0

        async def _mock_embed(text, api_key, model="text-embedding-3-small"):
            nonlocal call_count
            call_count += 1
            # 첫 번째 호출(저장) → FULL, 두 번째(조회) → DIFFERENT
            return _EMBED_FULL if call_count <= 1 else _EMBED_DIFFERENT

        with patch(
            "app.services.embedding_cache._get_embedding",
            side_effect=_mock_embed,
        ):
            await semantic_cache_set(
                redis, "prompt A", "response A",
                api_key="sk-test", tenant_id="t1", project_id="p1",
            )
            result, score = await semantic_cache_get(
                redis, "completely different",
                api_key="sk-test", tenant_id="t1", project_id="p1",
            )
            assert result is None
            assert score < DEFAULT_SIMILARITY_THRESHOLD

    @pytest.mark.asyncio
    async def test_임계값_초과_적중(self):
        """유사도가 임계값 이상이면 캐시된 응답을 반환한다."""
        redis = MockRedis()

        call_count = 0

        async def _mock_embed(text, api_key, model="text-embedding-3-small"):
            nonlocal call_count
            call_count += 1
            # 저장과 조회 모두 거의 동일한 벡터 → 유사도 ~1.0
            return _EMBED_FULL if call_count <= 1 else _EMBED_SIMILAR

        with patch(
            "app.services.embedding_cache._get_embedding",
            side_effect=_mock_embed,
        ):
            await semantic_cache_set(
                redis, "원가 분석 해줘", "원가는 50억입니다",
                api_key="sk-test", tenant_id="t1", project_id="p1",
            )
            result, score = await semantic_cache_get(
                redis, "원가 분석 부탁해",
                api_key="sk-test", tenant_id="t1", project_id="p1",
                similarity_threshold=0.90,
            )
            assert result == "원가는 50억입니다"
            assert score >= 0.90


# ──────────────────────────────────────────────────────────────
# 테넌트 격리 테스트
# ──────────────────────────────────────────────────────────────

class TestTenantIsolation:
    """테넌트/프로젝트별 키 격리 검증."""

    def test_테넌트_격리_키(self):
        """다른 테넌트는 다른 인덱스 키를 갖는다."""
        key_a = _embed_index_key("tenant-A", "proj-1")
        key_b = _embed_index_key("tenant-B", "proj-1")
        key_c = _embed_index_key("tenant-A", "proj-2")
        assert key_a != key_b, "다른 테넌트의 인덱스 키가 같으면 안 된다"
        assert key_a != key_c, "다른 프로젝트의 인덱스 키가 같으면 안 된다"
        assert "tenant-A" in key_a
        assert "tenant-B" in key_b


# ──────────────────────────────────────────────────────────────
# 만료된 키 정리 테스트
# ──────────────────────────────────────────────────────────────

class TestExpiredKeyCleanup:
    """인덱스에 있지만 실제 데이터가 만료된 키 정리 검증."""

    @pytest.mark.asyncio
    async def test_만료된_키_정리(self):
        """인덱스에 키가 있지만 데이터가 만료(삭제)된 경우, 조회 시 인덱스에서 제거된다."""
        redis = MockRedis()
        tenant_id, project_id = "t1", "p1"
        index_key = _embed_index_key(tenant_id, project_id)

        # 인덱스에 키를 직접 등록하되, 실제 데이터는 저장하지 않음 (만료 시뮬레이션)
        fake_cache_key = _embed_key(tenant_id, project_id, "expired_hash")
        await redis.sadd(index_key, fake_cache_key)

        # 조회 시 해당 키의 데이터가 없으므로 srem이 호출되어야 한다
        with patch(
            "app.services.embedding_cache._get_embedding",
            new_callable=AsyncMock,
            return_value=_EMBED_FULL,
        ):
            result, score = await semantic_cache_get(
                redis, "test",
                api_key="sk-test", tenant_id=tenant_id, project_id=project_id,
            )
            assert result is None

        # 만료된 키가 인덱스에서 제거되었는지 확인
        remaining = await redis.smembers(index_key)
        assert fake_cache_key not in remaining, "만료된 키가 인덱스에서 정리되어야 한다"
