"""쿼리 유사도 클러스터링 서비스 단위 테스트.

QuerySimilarityService의 핵심 기능을 검증한다:
- 코사인 유사도 계산
- 유사 쿼리 검색 (find_similar)
- 클러스터 생성 및 재사용 (cluster)
- 임계값 필터링
- 스토어 크기 제한
"""
from __future__ import annotations

import math
from unittest.mock import AsyncMock, patch

import pytest

from app.pipelines.query_similarity import (
    QuerySimilarityService,
    SimilarQuery,
    _cosine_similarity,
)


# ── 코사인 유사도 계산 테스트 ──────────────────────────────────────


class TestCosineSimilarity:
    """_cosine_similarity 함수의 수학적 정확성을 검증한다."""

    def test_identical_vectors(self):
        """동일한 벡터는 유사도 1.0을 반환해야 한다."""
        vec = [1.0, 2.0, 3.0]
        assert math.isclose(_cosine_similarity(vec, vec), 1.0, rel_tol=1e-9)

    def test_orthogonal_vectors(self):
        """직교 벡터는 유사도 0.0을 반환해야 한다."""
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert math.isclose(_cosine_similarity(a, b), 0.0, abs_tol=1e-9)

    def test_opposite_vectors(self):
        """반대 방향 벡터는 유사도 -1.0을 반환해야 한다."""
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert math.isclose(_cosine_similarity(a, b), -1.0, rel_tol=1e-9)

    def test_empty_vectors(self):
        """빈 벡터는 0.0을 반환해야 한다."""
        assert _cosine_similarity([], []) == 0.0

    def test_different_length_vectors(self):
        """길이가 다른 벡터는 0.0을 반환해야 한다."""
        assert _cosine_similarity([1.0, 2.0], [1.0]) == 0.0

    def test_zero_vector(self):
        """영벡터는 0.0을 반환해야 한다."""
        assert _cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_similar_vectors(self):
        """유사한 벡터는 높은 유사도를 반환해야 한다."""
        a = [1.0, 2.0, 3.0]
        b = [1.1, 2.1, 3.1]
        score = _cosine_similarity(a, b)
        assert score > 0.99, f"유사한 벡터의 유사도가 너무 낮음: {score}"


# ── 헬퍼: 목 임베딩 함수 생성 ──────────────────────────────────────


def _make_mock_embed_fn(embeddings: dict[str, list[float]]) -> AsyncMock:
    """질문 텍스트를 미리 정의된 임베딩에 매핑하는 목 함수를 만든다."""

    async def _embed(text: str) -> list[float] | None:
        return embeddings.get(text)

    return AsyncMock(side_effect=_embed)


# ── find_similar 테스트 ────────────────────────────────────────────


class TestFindSimilar:
    """find_similar 메서드의 유사 쿼리 검색을 검증한다."""

    @pytest.mark.asyncio
    async def test_find_similar_with_exact_match(self):
        """동일한 임베딩이 저장되어 있으면 유사 쿼리를 반환해야 한다."""
        embed_vec = [1.0, 0.0, 0.0]
        embed_fn = _make_mock_embed_fn({
            "매출 합계": embed_vec,
            "총 매출": embed_vec,  # 동일 벡터 → 유사도 1.0
        })

        svc = QuerySimilarityService(embed_fn=embed_fn, high_threshold=0.95)

        # 먼저 하나 등록
        await svc.cluster("매출 합계", "SELECT SUM(revenue) FROM sales", "q-1")

        # 동일 벡터로 검색
        result = await svc.find_similar("총 매출")
        assert result is not None
        assert isinstance(result, SimilarQuery)
        assert result.query_id == "q-1"
        assert math.isclose(result.similarity_score, 1.0, rel_tol=1e-9)

    @pytest.mark.asyncio
    async def test_find_similar_below_threshold(self):
        """임계값 미만이면 None을 반환해야 한다."""
        embed_fn = _make_mock_embed_fn({
            "매출 합계": [1.0, 0.0, 0.0],
            "직원 수": [0.0, 1.0, 0.0],  # 직교 → 유사도 0.0
        })

        svc = QuerySimilarityService(embed_fn=embed_fn, high_threshold=0.95)
        await svc.cluster("매출 합계", "SELECT SUM(revenue) FROM sales", "q-1")

        result = await svc.find_similar("직원 수")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_similar_empty_store(self):
        """스토어가 비어있으면 None을 반환해야 한다."""
        embed_fn = _make_mock_embed_fn({"테스트": [1.0, 0.0]})
        svc = QuerySimilarityService(embed_fn=embed_fn)

        result = await svc.find_similar("테스트")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_similar_no_embed_fn(self):
        """임베딩 함수가 없으면 None을 반환해야 한다."""
        svc = QuerySimilarityService(embed_fn=None)
        result = await svc.find_similar("테스트")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_similar_custom_threshold(self):
        """커스텀 임계값을 적용할 수 있어야 한다."""
        # 유사도 약 0.87 정도 되는 벡터 쌍 (코사인 유사도 직접 계산 확인)
        embed_fn = _make_mock_embed_fn({
            "매출": [1.0, 0.0, 0.0],
            "수익": [0.8, 0.6, 0.0],  # cos(a,b) = 0.8 → 0.95 미만
        })

        svc = QuerySimilarityService(embed_fn=embed_fn, high_threshold=0.95)
        await svc.cluster("매출", "SELECT revenue FROM sales", "q-1")

        # 기본 임계값(0.95)으로는 못 찾음 (유사도 0.8)
        result_strict = await svc.find_similar("수익")
        assert result_strict is None

        # 낮은 임계값으로 검색하면 찾음
        result_loose = await svc.find_similar("수익", threshold=0.7)
        assert result_loose is not None


# ── cluster 테스트 ─────────────────────────────────────────────────


class TestCluster:
    """cluster 메서드의 클러스터 생성 및 재사용을 검증한다."""

    @pytest.mark.asyncio
    async def test_cluster_creates_new_canonical_id(self):
        """새로운 쿼리는 새 canonical_id를 생성해야 한다."""
        embed_fn = _make_mock_embed_fn({"쿼리 A": [1.0, 0.0]})
        svc = QuerySimilarityService(embed_fn=embed_fn)

        canonical = await svc.cluster("쿼리 A", "SELECT 1", "q-1")

        # canonical_id는 비어있지 않은 문자열이어야 한다
        assert canonical
        assert isinstance(canonical, str)
        # 스토어에 저장되었는지 확인
        assert svc.store_size == 1

    @pytest.mark.asyncio
    async def test_cluster_reuses_existing_canonical_id(self):
        """유사한 쿼리는 기존 canonical_id를 재사용해야 한다."""
        same_vec = [1.0, 0.5, 0.3]
        embed_fn = _make_mock_embed_fn({
            "매출 합계를 보여줘": same_vec,
            "총 매출을 알려줘": same_vec,  # 동일 벡터 → 유사도 1.0
        })

        svc = QuerySimilarityService(embed_fn=embed_fn, high_threshold=0.95)

        canonical_1 = await svc.cluster(
            "매출 합계를 보여줘", "SELECT SUM(revenue) FROM sales", "q-1"
        )
        canonical_2 = await svc.cluster(
            "총 매출을 알려줘", "SELECT SUM(revenue) FROM sales", "q-2"
        )

        # 동일 클러스터에 속해야 한다
        assert canonical_1 == canonical_2
        assert svc.store_size == 2

    @pytest.mark.asyncio
    async def test_cluster_different_queries_get_different_ids(self):
        """의미가 다른 쿼리는 서로 다른 canonical_id를 받아야 한다."""
        embed_fn = _make_mock_embed_fn({
            "매출 합계": [1.0, 0.0, 0.0],
            "직원 목록": [0.0, 1.0, 0.0],
        })

        svc = QuerySimilarityService(embed_fn=embed_fn, high_threshold=0.95)

        canonical_1 = await svc.cluster("매출 합계", "SELECT SUM(revenue)", "q-1")
        canonical_2 = await svc.cluster("직원 목록", "SELECT * FROM employees", "q-2")

        assert canonical_1 != canonical_2

    @pytest.mark.asyncio
    async def test_cluster_without_embed_fn_returns_query_id(self):
        """임베딩 함수가 없으면 query_id 자체를 canonical_id로 사용해야 한다."""
        svc = QuerySimilarityService(embed_fn=None)
        canonical = await svc.cluster("테스트", "SELECT 1", "q-42")
        assert canonical == "q-42"

    @pytest.mark.asyncio
    async def test_cluster_disabled_returns_query_id(self):
        """ENABLE_QUERY_SIMILARITY=False이면 query_id를 반환해야 한다."""
        embed_fn = _make_mock_embed_fn({"테스트": [1.0, 0.0]})
        svc = QuerySimilarityService(embed_fn=embed_fn)

        with patch("app.pipelines.query_similarity.settings") as mock_settings:
            mock_settings.ENABLE_QUERY_SIMILARITY = False
            canonical = await svc.cluster("테스트", "SELECT 1", "q-99")

        assert canonical == "q-99"


# ── 스토어 크기 제한 테스트 ────────────────────────────────────────


class TestMaxStoreSize:
    """인메모리 스토어의 크기 제한과 FIFO 퇴출을 검증한다."""

    @pytest.mark.asyncio
    async def test_store_evicts_oldest_when_full(self):
        """스토어가 최대 크기에 도달하면 가장 오래된 항목을 제거해야 한다."""
        max_size = 3
        # 각 쿼리마다 서로 다른 직교 벡터 사용
        embeddings = {
            f"쿼리 {i}": [1.0 if j == i else 0.0 for j in range(5)]
            for i in range(5)
        }
        embed_fn = _make_mock_embed_fn(embeddings)

        svc = QuerySimilarityService(embed_fn=embed_fn, max_store=max_size)

        # 4개 쿼리 등록 (최대 3개 → 첫 번째가 퇴출되어야 함)
        for i in range(4):
            await svc.cluster(f"쿼리 {i}", f"SELECT {i}", f"q-{i}")

        # 스토어 크기가 max_size를 초과하지 않아야 한다
        assert svc.store_size == max_size

        # 첫 번째 항목(q-0)이 퇴출되었는지 확인
        members_all = []
        for entry in svc._store.values():
            members_all.append(entry.query_id)

        assert "q-0" not in members_all, "가장 오래된 항목이 퇴출되지 않았음"
        assert "q-3" in members_all, "최신 항목이 남아있지 않음"

    @pytest.mark.asyncio
    async def test_store_respects_max_boundary(self):
        """max_store=1일 때 항상 최신 항목만 유지해야 한다."""
        embeddings = {
            "A": [1.0, 0.0],
            "B": [0.0, 1.0],
        }
        embed_fn = _make_mock_embed_fn(embeddings)
        svc = QuerySimilarityService(embed_fn=embed_fn, max_store=1)

        await svc.cluster("A", "SELECT 1", "q-A")
        assert svc.store_size == 1

        await svc.cluster("B", "SELECT 2", "q-B")
        assert svc.store_size == 1

        # B만 남아있어야 한다
        assert list(svc._store.keys()) == ["q-B"]


# ── get_cluster_members 테스트 ─────────────────────────────────────


class TestGetClusterMembers:
    """get_cluster_members 메서드를 검증한다."""

    @pytest.mark.asyncio
    async def test_get_members_of_cluster(self):
        """같은 클러스터에 속한 쿼리들을 모두 조회할 수 있어야 한다."""
        same_vec = [1.0, 0.5, 0.3]
        embed_fn = _make_mock_embed_fn({
            "매출": same_vec,
            "수익": same_vec,
        })

        svc = QuerySimilarityService(embed_fn=embed_fn, high_threshold=0.95)

        canonical = await svc.cluster("매출", "SELECT SUM(revenue)", "q-1")
        await svc.cluster("수익", "SELECT SUM(income)", "q-2")

        members = svc.get_cluster_members(canonical)
        assert len(members) == 2
        member_ids = {m["query_id"] for m in members}
        assert member_ids == {"q-1", "q-2"}

    @pytest.mark.asyncio
    async def test_get_members_empty_cluster(self):
        """존재하지 않는 클러스터는 빈 리스트를 반환해야 한다."""
        svc = QuerySimilarityService()
        members = svc.get_cluster_members("nonexistent")
        assert members == []


# ── clear 테스트 ───────────────────────────────────────────────────


class TestClear:
    """clear 메서드가 스토어를 완전히 비우는지 검증한다."""

    @pytest.mark.asyncio
    async def test_clear_empties_store(self):
        embed_fn = _make_mock_embed_fn({"A": [1.0, 0.0]})
        svc = QuerySimilarityService(embed_fn=embed_fn)

        await svc.cluster("A", "SELECT 1", "q-1")
        assert svc.store_size == 1

        svc.clear()
        assert svc.store_size == 0
