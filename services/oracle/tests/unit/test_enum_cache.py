"""Enum 캐시 부트스트랩 테스트 (#8 P1-1).

인메모리 캐시 저장/조회, 컬럼 필터링 패턴, 힌트 생성을 검증한다.
실제 DB 연결 없이 캐시 조회 API만 단위 테스트한다.
"""

import pytest
from app.pipelines.enum_cache_bootstrap import (
    _should_cache_column,
    _enum_cache_store,
    get_enum_values,
    get_enum_hints_for_tables,
    get_cache_stats,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """각 테스트 전후에 캐시를 비운다."""
    _enum_cache_store.clear()
    yield
    _enum_cache_store.clear()


# ──────────────────────────────────────────────────────────────
# 컬럼 필터링 패턴 테스트
# ──────────────────────────────────────────────────────────────

class TestShouldCacheColumn:
    """_should_cache_column() 패턴 매칭 테스트."""

    def test_varchar_type_matches(self):
        """varchar 타입은 캐시 대상이다."""
        assert _should_cache_column("any_column", "character varying") is True

    def test_text_type_matches(self):
        """text 타입은 캐시 대상이다."""
        assert _should_cache_column("any_column", "text") is True

    def test_character_type_matches(self):
        """character 타입은 캐시 대상이다."""
        assert _should_cache_column("any_column", "character") is True

    def test_integer_type_not_matches(self):
        """integer 타입은 캐시 대상이 아니다."""
        assert _should_cache_column("status", "integer") is False

    def test_numeric_type_not_matches(self):
        """numeric 타입은 캐시 대상이 아니다."""
        assert _should_cache_column("revenue", "numeric") is False

    def test_date_type_not_matches(self):
        """date 타입은 캐시 대상이 아니다."""
        assert _should_cache_column("sale_date", "date") is False

    def test_timestamp_type_not_matches(self):
        """timestamp 타입은 캐시 대상이 아니다."""
        assert _should_cache_column("created_at", "timestamp") is False

    def test_boolean_type_not_matches(self):
        """boolean 타입은 캐시 대상이 아니다."""
        assert _should_cache_column("is_active", "boolean") is False


# ──────────────────────────────────────────────────────────────
# 캐시 저장 및 조회 테스트
# ──────────────────────────────────────────────────────────────

class TestCacheLookup:
    """인메모리 캐시 저장/조회 테스트."""

    def test_get_enum_values_hit(self):
        """캐시에 있는 값을 정확히 반환한다."""
        _enum_cache_store["public.sales.region"] = {
            "values": [
                {"value": "서울", "count": 25},
                {"value": "부산", "count": 12},
                {"value": "대전", "count": 7},
            ],
            "cardinality": 3,
        }

        result = get_enum_values("public.sales.region")
        assert result is not None
        assert len(result) == 3
        assert result[0]["value"] == "서울"
        assert result[0]["count"] == 25

    def test_get_enum_values_miss(self):
        """캐시에 없는 키는 None을 반환한다."""
        result = get_enum_values("public.nonexistent.column")
        assert result is None

    def test_get_enum_values_case_insensitive(self):
        """캐시 키는 대소문자 구분 없이 조회된다."""
        _enum_cache_store["public.sales.region"] = {
            "values": [{"value": "서울", "count": 1}],
            "cardinality": 1,
        }

        # 대문자로 조회해도 매칭 (fqn.lower())
        result = get_enum_values("PUBLIC.SALES.REGION")
        assert result is not None

    def test_get_enum_values_empty_fqn(self):
        """빈 FQN은 None을 반환한다."""
        result = get_enum_values("")
        assert result is None


# ──────────────────────────────────────────────────────────────
# 테이블별 힌트 조회 테스트
# ──────────────────────────────────────────────────────────────

class TestGetEnumHintsForTables:
    """get_enum_hints_for_tables() 테스트."""

    def _seed_cache(self):
        """테스트용 캐시 데이터 시딩."""
        _enum_cache_store["public.sales.region"] = {
            "values": [
                {"value": "서울", "count": 25},
                {"value": "부산", "count": 12},
            ],
            "cardinality": 2,
        }
        _enum_cache_store["public.sales.product_category"] = {
            "values": [
                {"value": "반도체", "count": 10},
                {"value": "디스플레이", "count": 8},
            ],
            "cardinality": 2,
        }
        _enum_cache_store["public.operations.status"] = {
            "values": [
                {"value": "COMPLETED", "count": 30},
                {"value": "IN_PROGRESS", "count": 1},
            ],
            "cardinality": 2,
        }

    def test_returns_hints_for_requested_tables(self):
        """요청된 테이블의 enum 힌트만 반환한다."""
        self._seed_cache()

        hints = get_enum_hints_for_tables(["sales"])
        assert len(hints) == 2  # region, product_category

        tables = {h["table"] for h in hints}
        assert tables == {"sales"}

        columns = {h["column"] for h in hints}
        assert "region" in columns
        assert "product_category" in columns

    def test_returns_empty_for_unknown_table(self):
        """캐시에 없는 테이블은 빈 리스트를 반환한다."""
        self._seed_cache()
        hints = get_enum_hints_for_tables(["nonexistent"])
        assert hints == []

    def test_returns_hints_for_multiple_tables(self):
        """여러 테이블의 힌트를 한번에 반환한다."""
        self._seed_cache()

        hints = get_enum_hints_for_tables(["sales", "operations"])
        assert len(hints) == 3  # sales: 2 + operations: 1

    def test_hint_values_limited_to_10(self):
        """힌트 값은 최대 10개만 반환한다."""
        _enum_cache_store["public.sales.region"] = {
            "values": [{"value": f"city_{i}", "count": i} for i in range(20)],
            "cardinality": 20,
        }

        hints = get_enum_hints_for_tables(["sales"])
        assert len(hints) == 1
        assert len(hints[0]["values"]) == 10

    def test_hint_format_correct(self):
        """힌트 딕셔너리의 필드가 올바르다."""
        self._seed_cache()

        hints = get_enum_hints_for_tables(["sales"])
        for h in hints:
            assert "table" in h
            assert "column" in h
            assert "values" in h
            assert "cardinality" in h
            assert isinstance(h["values"], list)
            # values는 문자열 리스트여야 한다 (dict가 아님)
            for v in h["values"]:
                assert isinstance(v, str)

    def test_empty_table_list(self):
        """빈 테이블 목록은 빈 리스트를 반환한다."""
        self._seed_cache()
        hints = get_enum_hints_for_tables([])
        assert hints == []


# ──────────────────────────────────────────────────────────────
# 캐시 통계 테스트
# ──────────────────────────────────────────────────────────────

class TestCacheStats:
    """get_cache_stats() 테스트."""

    def test_empty_stats(self):
        """빈 캐시의 통계."""
        stats = get_cache_stats()
        assert stats["total_columns"] == 0
        assert stats["total_values"] == 0

    def test_populated_stats(self):
        """데이터가 있는 캐시의 통계."""
        _enum_cache_store["public.sales.region"] = {
            "values": [{"value": "서울", "count": 1}],
            "cardinality": 1,
        }
        _enum_cache_store["public.sales.status"] = {
            "values": [{"value": "A", "count": 1}, {"value": "B", "count": 1}],
            "cardinality": 2,
        }

        stats = get_cache_stats()
        assert stats["total_columns"] == 2
        assert stats["total_values"] == 3  # 1 + 2


# ──────────────────────────────────────────────────────────────
# EnumCacheBootstrap 클래스 테스트
# ──────────────────────────────────────────────────────────────

class TestEnumCacheBootstrap:
    """EnumCacheBootstrap 클래스 테스트."""

    @pytest.mark.asyncio
    async def test_run_disabled(self):
        """ENUM_CACHE_ENABLED=False이면 None을 반환한다."""
        from app.pipelines.enum_cache_bootstrap import EnumCacheBootstrap
        from unittest.mock import patch

        bootstrap = EnumCacheBootstrap()
        with patch("app.pipelines.enum_cache_bootstrap.settings") as mock_settings:
            mock_settings.ENUM_CACHE_ENABLED = False
            result = await bootstrap.run()
            assert result is None
