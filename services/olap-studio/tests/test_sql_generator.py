"""피벗 SQL 생성기 단위 테스트.

sql_generator.py의 generate_pivot_sql 함수와 _sanitize_identifier 헬퍼를
경계 조건까지 포함하여 철저하게 검증한다.
"""
from __future__ import annotations

import sys
import os

# 프로젝트 루트를 sys.path에 추가하여 app 패키지를 임포트할 수 있도록 한다
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.models.query import PivotQuery, PivotField, PivotMeasure, FilterCondition
from app.services.sql_generator import (
    generate_pivot_sql,
    _sanitize_identifier,
    ALLOWED_OPERATORS,
    ALLOWED_AGGREGATORS,
)


# ──────────────────────────────────────────────
# _sanitize_identifier 헬퍼 테스트
# ──────────────────────────────────────────────


class TestSanitizeIdentifier:
    """식별자 이스케이프 로직을 검증한다."""

    def test_simple_ascii_identifier_unchanged(self):
        """영문+숫자+언더스코어만 포함하면 그대로 반환한다."""
        assert _sanitize_identifier("sales_amount") == "sales_amount"

    def test_identifier_starting_with_underscore(self):
        """언더스코어로 시작하는 식별자도 안전하다."""
        assert _sanitize_identifier("_id") == "_id"

    def test_korean_dimension_name_quoted(self):
        """한글 차원 이름은 큰따옴표로 감싸야 한다."""
        result = _sanitize_identifier("매출액")
        assert result == '"매출액"'

    def test_identifier_with_space_quoted(self):
        """공백 포함 식별자는 큰따옴표로 감싼다."""
        result = _sanitize_identifier("sales amount")
        assert result == '"sales amount"'

    def test_identifier_with_embedded_double_quote_escaped(self):
        """내부 큰따옴표는 이중 이스케이프된다 (" -> "")."""
        result = _sanitize_identifier('column"name')
        assert result == '"column""name"'

    def test_identifier_starting_with_digit_quoted(self):
        """숫자로 시작하면 정규식 매치 실패 → 큰따옴표로 감싼다."""
        result = _sanitize_identifier("123abc")
        assert result == '"123abc"'

    def test_identifier_with_hyphen_quoted(self):
        """하이픈 포함 시 큰따옴표로 감싼다."""
        result = _sanitize_identifier("my-table")
        assert result == '"my-table"'


# ──────────────────────────────────────────────
# 기본 피벗 SQL 생성 테스트
# ──────────────────────────────────────────────


class TestGeneratePivotSqlBasic:
    """기본 피벗 질의 → SELECT/GROUP BY/LIMIT 생성을 검증한다."""

    def test_basic_pivot_with_rows_and_measures(self):
        """행 1개 + 측정값 1개 → SELECT, GROUP BY, ORDER BY, LIMIT 포함."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="revenue", aggregator="SUM")],
        )
        sql, params = generate_pivot_sql(query)

        # SELECT 절에 차원과 집계 포함 확인
        assert "dw.Time.year" in sql
        assert "SUM(revenue) AS revenue" in sql
        # GROUP BY 존재
        assert "GROUP BY dw.Time.year" in sql
        # ORDER BY 존재
        assert "ORDER BY dw.Time.year" in sql
        # LIMIT 기본값 1000
        assert "LIMIT 1000" in sql
        # 파라미터 없음 (필터 없으므로)
        assert params == []

    def test_multiple_rows_and_columns(self):
        """행 2개 + 열 1개 → 모두 SELECT와 GROUP BY에 포함."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[
                PivotField(dimension="Time", level="year"),
                PivotField(dimension="Time", level="quarter"),
            ],
            columns=[PivotField(dimension="Product", level="category")],
            measures=[PivotMeasure(name="qty", aggregator="COUNT")],
        )
        sql, params = generate_pivot_sql(query)

        assert "dw.Time.year" in sql
        assert "dw.Time.quarter" in sql
        assert "dw.Product.category" in sql
        assert "COUNT(qty) AS qty" in sql
        # GROUP BY에 3개 차원 모두 포함
        assert "dw.Time.year" in sql.split("GROUP BY")[1]
        assert "dw.Time.quarter" in sql.split("GROUP BY")[1]
        assert "dw.Product.category" in sql.split("GROUP BY")[1]

    def test_multiple_measures(self):
        """측정값 여러 개 → 각각 집계 함수 적용."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[
                PivotMeasure(name="revenue", aggregator="SUM"),
                PivotMeasure(name="qty", aggregator="AVG"),
                PivotMeasure(name="order_count", aggregator="COUNT"),
            ],
        )
        sql, params = generate_pivot_sql(query)

        assert "SUM(revenue) AS revenue" in sql
        assert "AVG(qty) AS qty" in sql
        assert "COUNT(order_count) AS order_count" in sql

    def test_from_clause_uses_schema_prefix(self):
        """FROM 절이 schema_prefix를 사용한다."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="revenue")],
        )
        sql, _ = generate_pivot_sql(query, schema_prefix="analytics")

        assert "FROM analytics.fact_table" in sql


# ──────────────────────────────────────────────
# 빈 measures → 빈 결과
# ──────────────────────────────────────────────


class TestEmptyMeasures:
    """측정값이 없으면 SQL 생성을 건너뛴다."""

    def test_empty_measures_returns_empty_tuple(self):
        """measures가 비어있으면 ("", [])를 반환한다."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[],
        )
        sql, params = generate_pivot_sql(query)
        assert sql == ""
        assert params == []


# ──────────────────────────────────────────────
# 필터 테스트 — 연산자별 파라미터 바인딩
# ──────────────────────────────────────────────


class TestFilters:
    """필터 조건별 WHERE 절과 파라미터 바인딩을 검증한다."""

    def test_equals_filter(self):
        """= 연산자 → $1 파라미터."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="revenue")],
            filters=[FilterCondition(dimension="Region", level="country", operator="=", value="Korea")],
        )
        sql, params = generate_pivot_sql(query)

        assert "WHERE" in sql
        assert "dw.Region.country = $1" in sql
        assert params == ["Korea"]

    def test_like_filter(self):
        """LIKE 연산자 → $1 파라미터 바인딩."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="revenue")],
            filters=[FilterCondition(dimension="Product", level="name", operator="LIKE", value="%Widget%")],
        )
        sql, params = generate_pivot_sql(query)

        assert "dw.Product.name LIKE $1" in sql
        assert params == ["%Widget%"]

    def test_in_filter_with_list(self):
        """IN 연산자 + 리스트 값 → 여러 플레이스홀더."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="revenue")],
            filters=[FilterCondition(
                dimension="Region", level="country",
                operator="IN", value=["Korea", "Japan", "China"],
            )],
        )
        sql, params = generate_pivot_sql(query)

        assert "dw.Region.country IN ($1, $2, $3)" in sql
        assert params == ["Korea", "Japan", "China"]

    def test_not_in_filter_with_list(self):
        """NOT IN 연산자 + 리스트 값 → 올바른 플레이스홀더."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="revenue")],
            filters=[FilterCondition(
                dimension="Region", level="country",
                operator="NOT IN", value=["US", "UK"],
            )],
        )
        sql, params = generate_pivot_sql(query)

        assert "NOT IN ($1, $2)" in sql
        assert params == ["US", "UK"]

    def test_multiple_filters_correct_param_ordering(self):
        """필터 2개 → $1, $2 순서 보장."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="revenue")],
            filters=[
                FilterCondition(dimension="Region", level="country", operator="=", value="Korea"),
                FilterCondition(dimension="Time", level="year", operator=">=", value="2024"),
            ],
        )
        sql, params = generate_pivot_sql(query)

        assert "$1" in sql
        assert "$2" in sql
        assert params == ["Korea", "2024"]
        # AND로 연결 확인
        assert " AND " in sql

    def test_mixed_scalar_and_list_filters(self):
        """스칼라 필터 + IN 리스트 필터 → 파라미터 번호가 올바르게 이어진다."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="revenue")],
            filters=[
                FilterCondition(dimension="Region", level="country", operator="=", value="Korea"),
                FilterCondition(dimension="Product", level="category", operator="IN", value=["A", "B"]),
            ],
        )
        sql, params = generate_pivot_sql(query)

        # 첫 번째 필터: $1
        assert "dw.Region.country = $1" in sql
        # 두 번째 필터: $2, $3
        assert "dw.Product.category IN ($2, $3)" in sql
        assert params == ["Korea", "A", "B"]

    def test_invalid_operator_raises_value_error(self):
        """허용되지 않은 연산자 → ValueError 발생."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="revenue")],
            filters=[FilterCondition(dimension="Region", level="country", operator="DROP TABLE", value="x")],
        )
        with pytest.raises(ValueError, match="허용되지 않은 연산자"):
            generate_pivot_sql(query)


# ──────────────────────────────────────────────
# 집계 함수 (Aggregator) 검증
# ──────────────────────────────────────────────


class TestAggregatorValidation:
    """허용되지 않은 집계 함수는 SUM으로 폴백한다."""

    def test_valid_aggregators_used_as_is(self):
        """허용된 집계 함수 (AVG, MIN, MAX 등) → 그대로 사용."""
        for agg in ["SUM", "COUNT", "AVG", "MIN", "MAX", "COUNT_DISTINCT"]:
            query = PivotQuery(
                cubeName="Sales",
                rows=[PivotField(dimension="Time", level="year")],
                measures=[PivotMeasure(name="val", aggregator=agg)],
            )
            sql, _ = generate_pivot_sql(query)
            assert f"{agg}(val)" in sql

    def test_unknown_aggregator_falls_back_to_sum(self):
        """알 수 없는 집계 함수 → SUM으로 폴백."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="val", aggregator="MEDIAN")],
        )
        sql, _ = generate_pivot_sql(query)
        assert "SUM(val) AS val" in sql

    def test_aggregator_case_insensitive(self):
        """소문자 집계 함수도 대문자로 변환하여 매칭한다."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="val", aggregator="avg")],
        )
        sql, _ = generate_pivot_sql(query)
        assert "AVG(val) AS val" in sql


# ──────────────────────────────────────────────
# LIMIT 캡핑 테스트
# ──────────────────────────────────────────────


class TestLimitCapping:
    """LIMIT 값은 10000을 초과할 수 없다."""

    def test_limit_default_1000(self):
        """기본 limit 1000."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="revenue")],
        )
        sql, _ = generate_pivot_sql(query)
        assert "LIMIT 1000" in sql

    def test_limit_capped_at_10000(self):
        """limit을 10000 초과로 설정해도 10000으로 캡핑된다.

        PivotQuery의 Pydantic 모델에서 le=10000 제약이 있어
        10000을 초과하면 ValidationError가 발생한다.
        그러나 generate_pivot_sql 내부에서도 min(query.limit, 10000)으로
        이중 보호하므로 최대값인 10000을 검증한다.
        """
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="revenue")],
            limit=10000,
        )
        sql, _ = generate_pivot_sql(query)
        assert "LIMIT 10000" in sql

    def test_limit_pydantic_rejects_over_10000(self):
        """Pydantic 모델이 10000 초과 limit을 거부한다."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PivotQuery(
                cubeName="Sales",
                rows=[],
                measures=[],
                limit=20000,
            )

    def test_custom_limit_respected(self):
        """사용자가 지정한 limit 값이 반영된다."""
        query = PivotQuery(
            cubeName="Sales",
            rows=[PivotField(dimension="Time", level="year")],
            measures=[PivotMeasure(name="revenue")],
            limit=50,
        )
        sql, _ = generate_pivot_sql(query)
        assert "LIMIT 50" in sql


# ──────────────────────────────────────────────
# 한글 차원 이름 통합 테스트
# ──────────────────────────────────────────────


class TestKoreanDimensions:
    """한글 차원/레벨 이름이 올바르게 이스케이프된다."""

    def test_korean_dimension_in_select(self):
        """한글 차원 이름 → 큰따옴표로 감싸서 SELECT에 포함."""
        query = PivotQuery(
            cubeName="매출분석",
            rows=[PivotField(dimension="시간", level="연도")],
            measures=[PivotMeasure(name="매출액")],
        )
        sql, _ = generate_pivot_sql(query)

        assert 'dw."시간"."연도"' in sql
        assert 'SUM("매출액") AS "매출액"' in sql

    def test_korean_filter_dimension(self):
        """한글 필터 차원도 올바르게 이스케이프된다."""
        query = PivotQuery(
            cubeName="매출분석",
            rows=[PivotField(dimension="시간", level="연도")],
            measures=[PivotMeasure(name="매출액")],
            filters=[FilterCondition(dimension="지역", level="도시", operator="=", value="서울")],
        )
        sql, params = generate_pivot_sql(query)

        assert 'dw."지역"."도시" = $1' in sql
        assert params == ["서울"]


# ──────────────────────────────────────────────
# 행/열 없이 측정값만 있는 경우 (전체 집계)
# ──────────────────────────────────────────────


class TestNoGroupBy:
    """행/열 없이 측정값만 → GROUP BY 없는 전체 집계."""

    def test_measures_only_no_group_by(self):
        """차원 없이 측정값만 → GROUP BY, ORDER BY 없음."""
        query = PivotQuery(
            cubeName="Sales",
            measures=[PivotMeasure(name="total_revenue", aggregator="SUM")],
        )
        sql, _ = generate_pivot_sql(query)

        assert "SUM(total_revenue) AS total_revenue" in sql
        assert "GROUP BY" not in sql
        assert "ORDER BY" not in sql
        assert "LIMIT 1000" in sql
