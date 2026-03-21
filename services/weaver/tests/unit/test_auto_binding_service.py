"""자동 데이터소스 바인딩 서비스 단위 테스트."""
from __future__ import annotations

import pytest

from app.services.auto_binding_service import (
    BindingCandidate,
    BindingResult,
    _ko_to_en_candidates,
    _normalize_name,
    auto_bind_entities,
    phase1_name_matching,
)


# ── 이름 정규화 테스트 ────────────────────────────────────────────

class TestNormalizeName:
    """이름 정규화 함수 테스트."""

    def test_소문자_변환(self):
        assert _normalize_name("MyTable") == "mytable"

    def test_공백_언더스코어_변환(self):
        assert _normalize_name("my table") == "my_table"

    def test_하이픈_언더스코어_변환(self):
        assert _normalize_name("my-table") == "my_table"

    def test_앞뒤_언더스코어_제거(self):
        assert _normalize_name("_test_") == "test"


# ── 한국어 → 영어 변환 테스트 ────────────────────────────────────

class TestKoEnCandidates:
    """한국어-영어 변환 테스트."""

    def test_탁도_변환(self):
        candidates = _ko_to_en_candidates("탁도")
        assert "turbidity" in candidates
        assert "ntu" in candidates

    def test_매출_변환(self):
        candidates = _ko_to_en_candidates("매출")
        assert "sales" in candidates
        assert "revenue" in candidates

    def test_알_수_없는_용어(self):
        candidates = _ko_to_en_candidates("알수없는용어")
        assert candidates == []


# ── Phase 1 이름 매칭 테스트 ──────────────────────────────────────

SAMPLE_TABLES = [
    {"name": "sales", "schema": "public", "columns": ["id", "revenue", "region"]},
    {"name": "operations", "schema": "public", "columns": ["id", "status", "duration_minutes"]},
    {"name": "turbidity_readings", "schema": "sensor", "columns": ["id", "ntu_value", "timestamp"]},
    {"name": "inventory", "schema": "warehouse", "columns": ["id", "stock_level", "product_id"]},
]


class TestPhase1NameMatching:
    """Phase 1 이름 기반 매칭 테스트."""

    def test_정확매칭(self):
        candidates = phase1_name_matching("sales", SAMPLE_TABLES, datasource="demo")
        assert len(candidates) >= 1
        best = candidates[0]
        assert best.match_method == "exact"
        assert best.confidence == 1.0
        assert best.fqn == "demo.public.sales"

    def test_부분매칭(self):
        # "sale"은 "sales"에 포함됨
        candidates = phase1_name_matching("sale", SAMPLE_TABLES, datasource="demo")
        assert len(candidates) >= 1
        assert any(c.match_method == "fuzzy" for c in candidates)

    def test_한국어_매칭(self):
        # "탁도" -> turbidity -> turbidity_readings 테이블 매칭
        candidates = phase1_name_matching("탁도", SAMPLE_TABLES, datasource="demo")
        assert len(candidates) >= 1
        assert any(c.table_name == "turbidity_readings" for c in candidates)

    def test_컬럼_레벨_매칭(self):
        candidates = phase1_name_matching("revenue", SAMPLE_TABLES, datasource="demo")
        assert len(candidates) >= 1
        assert any(c.match_method == "column_match" for c in candidates)
        col_match = [c for c in candidates if c.match_method == "column_match"][0]
        assert col_match.column_name == "revenue"

    def test_매칭_실패시_빈_리스트(self):
        candidates = phase1_name_matching("존재하지않는엔티티xyz", SAMPLE_TABLES, datasource="demo")
        assert candidates == []

    def test_confidence_내림차순_정렬(self):
        candidates = phase1_name_matching("sales", SAMPLE_TABLES, datasource="demo")
        for i in range(len(candidates) - 1):
            assert candidates[i].confidence >= candidates[i + 1].confidence


# ── 통합 바인딩 테스트 ────────────────────────────────────────────

class TestAutoBindEntities:
    """auto_bind_entities 통합 테스트."""

    @pytest.mark.asyncio
    async def test_복수_엔티티_바인딩(self):
        results = await auto_bind_entities(
            ["sales", "탁도", "알수없는것"],
            SAMPLE_TABLES,
            datasource="demo",
        )
        assert len(results) == 3

        # sales -> bound (정확 매칭)
        assert results[0].status == "bound"
        assert results[0].best_match is not None
        assert results[0].best_match.table_name == "sales"

        # 탁도 -> vocabulary 매칭 (confidence 0.6 -> partial)
        assert results[1].status == "partial"

        # 알수없는것 -> unbound
        assert results[2].status == "unbound"
        assert results[2].best_match is None

    @pytest.mark.asyncio
    async def test_빈_엔티티_리스트(self):
        results = await auto_bind_entities([], SAMPLE_TABLES, datasource="demo")
        assert results == []

    @pytest.mark.asyncio
    async def test_빈_테이블_리스트(self):
        results = await auto_bind_entities(["sales"], [], datasource="demo")
        assert len(results) == 1
        assert results[0].status == "unbound"
