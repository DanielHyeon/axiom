"""
품질 수집 파이프라인 9차원 테스트

각 차원별 측정 로직의 정확성, 가중치 v2 공식, 경계값을 검증한다.
DB 의존 없이 순수 로직 테스트 위주로 작성.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.services.quality_collector import QualityCollector, _compute_overall, _WEIGHTS_V2


# ── 가중치 v2 공식 테스트 ──


class TestComputeOverall:
    """가중 평균 계산 로직 테스트"""

    def test_all_perfect_scores(self):
        """9개 차원 모두 100점이면 overall = 100"""
        scores = {dim: 100.0 for dim in _WEIGHTS_V2}
        assert _compute_overall(scores) == 100.0

    def test_all_zero_scores(self):
        """9개 차원 모두 0점이면 overall = 0"""
        scores = {dim: 0.0 for dim in _WEIGHTS_V2}
        assert _compute_overall(scores) == 0.0

    def test_partial_dimensions_renormalize(self):
        """일부 차원만 있으면 가중치 재정규화"""
        # freshness(0.20)=80, completeness(0.15)=60 → 두 차원만
        scores = {"freshness": 80.0, "completeness": 60.0}
        # 가중 합: 80*0.20 + 60*0.15 = 16 + 9 = 25
        # 총 가중치: 0.20 + 0.15 = 0.35
        # 결과: 25 / 0.35 ≈ 71.43
        result = _compute_overall(scores)
        assert abs(result - 71.43) < 0.01

    def test_none_values_skipped(self):
        """None 값은 계산에서 제외"""
        scores = {"freshness": 100.0, "completeness": None, "uniqueness": 80.0}
        # freshness(0.20)=100, uniqueness(0.10)=80
        # 가중 합: 100*0.20 + 80*0.10 = 28
        # 총 가중치: 0.30
        # 결과: 28/0.30 ≈ 93.33
        result = _compute_overall(scores)
        assert abs(result - 93.33) < 0.01

    def test_empty_scores(self):
        """빈 딕셔너리면 0"""
        assert _compute_overall({}) == 0.0

    def test_weights_sum_to_one(self):
        """v2 가중치 합계가 1.0인지 확인"""
        total = sum(_WEIGHTS_V2.values())
        assert abs(total - 1.0) < 0.001

    def test_nine_dimensions_exist(self):
        """9개 차원이 모두 정의되어 있는지 확인"""
        expected = {
            "freshness", "completeness", "validity", "uniqueness",
            "referential_integrity", "owner", "lineage",
            "test_coverage", "incident_health",
        }
        assert set(_WEIGHTS_V2.keys()) == expected

    def test_realistic_mixed_scores(self):
        """현실적 혼합 점수 시나리오"""
        scores = {
            "freshness": 95.0,
            "completeness": 88.0,
            "validity": 100.0,
            "uniqueness": 99.0,
            "referential_integrity": 92.0,
            "owner": 100.0,
            "lineage": 50.0,
            "test_coverage": 100.0,
            "incident_health": 80.0,
        }
        result = _compute_overall(scores)
        # 수동 계산: 95*0.20 + 88*0.15 + 100*0.10 + 99*0.10 + 92*0.10 + 100*0.10 + 50*0.10 + 100*0.05 + 80*0.10
        # = 19 + 13.2 + 10 + 9.9 + 9.2 + 10 + 5 + 5 + 8 = 89.3
        assert 88 < result < 91


# ── 차원별 측정 로직 테스트 (Mocked DB) ──


class TestIncidentHealth:
    """Incident Health 차원 — 최근 30일 breach 횟수 기반"""

    @pytest.fixture
    def collector(self):
        store = MagicMock()
        return QualityCollector(store)

    @pytest.mark.asyncio
    async def test_zero_breaches_perfect_score(self, collector):
        """breach 0회 → 100점"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"breach_count": 0})
        score, details = await collector._measure_incident_health(conn, "t1", "ds1", "tbl1")
        assert score == 100.0
        assert details["breach_count_30d"] == 0

    @pytest.mark.asyncio
    async def test_one_breach_eighty(self, collector):
        """breach 1회 → 80점"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"breach_count": 1})
        score, _ = await collector._measure_incident_health(conn, "t1", "ds1", "tbl1")
        assert score == 80.0

    @pytest.mark.asyncio
    async def test_two_breaches_sixty(self, collector):
        """breach 2회 → 60점"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"breach_count": 2})
        score, _ = await collector._measure_incident_health(conn, "t1", "ds1", "tbl1")
        assert score == 60.0

    @pytest.mark.asyncio
    async def test_five_plus_breaches_twenty(self, collector):
        """breach 5회 이상 → 20점"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"breach_count": 7})
        score, _ = await collector._measure_incident_health(conn, "t1", "ds1", "tbl1")
        assert score == 20.0

    @pytest.mark.asyncio
    async def test_query_failure_graceful(self, collector):
        """DB 조회 실패 시 보수적 통과 (100점)"""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=Exception("connection lost"))
        score, details = await collector._measure_incident_health(conn, "t1", "ds1", "tbl1")
        assert score == 100.0
        assert "error" in details


class TestValidityDimension:
    """Validity 차원 — CHECK 제약 위반 비율"""

    @pytest.fixture
    def collector(self):
        store = MagicMock()
        return QualityCollector(store)

    @pytest.mark.asyncio
    async def test_unsafe_table_name_rejected(self, collector):
        """SQL 인젝션 위험 테이블명은 0점"""
        conn = AsyncMock()
        score, details = await collector._measure_validity(conn, "; DROP TABLE--")
        assert score == 0.0
        assert "오류" in details.get("error", "")

    @pytest.mark.asyncio
    async def test_no_constraints_returns_100(self, collector):
        """CHECK 제약 없고 text 컬럼도 없으면 100 (검증 불가 → 통과)"""
        conn = AsyncMock()
        # CHECK 제약 없음
        conn.fetch = AsyncMock(return_value=[])
        score, details = await collector._measure_validity(conn, "clean_table")
        assert score == 100.0
        assert details["method"] == "no_constraints_found"


class TestReferentialIntegrity:
    """Referential Integrity 차원 — FK orphan 비율"""

    @pytest.fixture
    def collector(self):
        store = MagicMock()
        return QualityCollector(store)

    @pytest.mark.asyncio
    async def test_no_fk_returns_100(self, collector):
        """FK 없으면 100점 (검증 생략)"""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        score, details = await collector._measure_referential_integrity(conn, "no_fk_table")
        assert score == 100.0
        assert "FK 없음" in details["note"]


class TestLineageCompleteness:
    """Lineage Completeness 차원 — upstream/downstream 존재 여부"""

    @pytest.fixture
    def collector(self):
        store = MagicMock()
        return QualityCollector(store)

    @pytest.mark.asyncio
    async def test_olap_failure_returns_zero(self, collector):
        """OLAP Studio 연결 실패 시 0점"""
        # httpx 호출이 실패하도록
        score, details = await collector._measure_lineage_completeness("t1", "ds1", "tbl1")
        # 로컬 테스트에서는 OLAP Studio가 없으므로 0점
        assert score == 0.0


class TestTestCoverage:
    """Test Coverage 차원 — QualityContract 연결 여부"""

    @pytest.fixture
    def collector(self):
        store = MagicMock()
        return QualityCollector(store)

    @pytest.mark.asyncio
    async def test_synapse_failure_returns_zero(self, collector):
        """Synapse 연결 실패 시 0점"""
        score, details = await collector._measure_test_coverage("t1", "ds1", "tbl1")
        assert score == 0.0
