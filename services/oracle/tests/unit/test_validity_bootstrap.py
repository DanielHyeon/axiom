"""Text2SQL 유효성 부트스트랩 단위 테스트 (#P4-16).

ValidityReport 데이터 모델, 테이블/컬럼 분류 로직, 설정 기본값을 검증한다.
"""

from __future__ import annotations

import pytest

from app.pipelines.validity_bootstrap import (
    ValidityReport,
    classify_empty_tables,
    classify_null_only_columns,
    get_last_report,
)


# ──────────────────────────────────────────────────────────────
# ValidityReport 데이터 모델 테스트
# ──────────────────────────────────────────────────────────────


class TestValidityReport:
    """ValidityReport 데이터클래스 기본 동작 검증."""

    def test_default_values(self):
        """기본 생성 시 모든 필드가 빈 값/0으로 초기화된다."""
        report = ValidityReport()
        assert report.invalid_tables == []
        assert report.invalid_columns == []
        assert report.scanned_tables == 0
        assert report.scanned_columns == 0
        assert report.synapse_updated == 0
        assert report.synapse_errors == 0
        assert report.elapsed_ms == 0.0

    def test_with_data(self):
        """필드 값을 지정하면 정확히 저장된다."""
        report = ValidityReport(
            invalid_tables=["public.empty1", "public.empty2"],
            invalid_columns=["public.sales.unused_col"],
            scanned_tables=10,
            scanned_columns=50,
            synapse_updated=3,
            synapse_errors=0,
            elapsed_ms=123.4,
        )
        assert len(report.invalid_tables) == 2
        assert len(report.invalid_columns) == 1
        assert report.scanned_tables == 10
        assert report.scanned_columns == 50
        assert report.synapse_updated == 3
        assert report.elapsed_ms == 123.4

    def test_mutable_lists(self):
        """각 인스턴스의 리스트는 독립적이다 (default_factory 검증)."""
        r1 = ValidityReport()
        r2 = ValidityReport()
        r1.invalid_tables.append("public.test")
        assert r2.invalid_tables == []


# ──────────────────────────────────────────────────────────────
# 테이블 분류 로직 테스트
# ──────────────────────────────────────────────────────────────


class TestClassifyEmptyTables:
    """pg_stat_user_tables 통계 기반 빈 테이블 분류 검증."""

    def test_all_empty(self):
        """모든 테이블의 행수가 0이면 전부 invalid로 분류된다."""
        stats = [
            ("public", "table_a", 0),
            ("public", "table_b", 0),
        ]
        empty, valid = classify_empty_tables(stats)
        assert empty == ["public.table_a", "public.table_b"]
        assert valid == []

    def test_all_valid(self):
        """모든 테이블에 데이터가 있으면 전부 valid로 분류된다."""
        stats = [
            ("public", "sales", 100),
            ("public", "operations", 50),
        ]
        empty, valid = classify_empty_tables(stats)
        assert empty == []
        assert valid == ["sales", "operations"]

    def test_mixed(self):
        """빈 테이블과 유효 테이블이 섞여 있으면 정확히 분류된다."""
        stats = [
            ("public", "sales", 100),
            ("public", "empty_table", 0),
            ("public", "operations", 50),
            ("public", "staging", 0),
        ]
        empty, valid = classify_empty_tables(stats)
        assert empty == ["public.empty_table", "public.staging"]
        assert valid == ["sales", "operations"]

    def test_empty_input(self):
        """입력이 비어있으면 빈 결과를 반환한다."""
        empty, valid = classify_empty_tables([])
        assert empty == []
        assert valid == []

    def test_single_row_is_valid(self):
        """행수가 1이어도 유효 테이블이다 (0만 invalid)."""
        stats = [("public", "tiny_table", 1)]
        empty, valid = classify_empty_tables(stats)
        assert empty == []
        assert valid == ["tiny_table"]


# ──────────────────────────────────────────────────────────────
# 컬럼 분류 로직 테스트
# ──────────────────────────────────────────────────────────────


class TestClassifyNullOnlyColumns:
    """pg_stats null_frac 기반 null-only 컬럼 분류 검증."""

    def test_all_null_only(self):
        """null_frac = 1.0인 컬럼은 전부 invalid로 분류된다."""
        stats = [
            ("public", "sales", "unused1", 1.0),
            ("public", "sales", "unused2", 1.0),
        ]
        result = classify_null_only_columns(stats)
        assert result == ["public.sales.unused1", "public.sales.unused2"]

    def test_no_null_only(self):
        """null_frac < 1.0이면 모두 유효하다."""
        stats = [
            ("public", "sales", "region", 0.0),
            ("public", "sales", "cost", 0.15),
            ("public", "operations", "status", 0.02),
        ]
        result = classify_null_only_columns(stats)
        assert result == []

    def test_mixed_null_fracs(self):
        """다양한 null_frac 값이 섞여 있으면 1.0만 invalid로 분류된다."""
        stats = [
            ("public", "sales", "region", 0.0),
            ("public", "sales", "notes", 1.0),
            ("public", "sales", "cost", 0.5),
            ("public", "operations", "completed_at", 1.0),
            ("public", "operations", "status", 0.0),
        ]
        result = classify_null_only_columns(stats)
        assert result == ["public.sales.notes", "public.operations.completed_at"]

    def test_none_null_frac(self):
        """null_frac이 None이면 (ANALYZE 미실행) 유효로 간주한다."""
        stats = [
            ("public", "sales", "region", None),
            ("public", "sales", "notes", 1.0),
        ]
        result = classify_null_only_columns(stats)
        assert result == ["public.sales.notes"]

    def test_empty_input(self):
        """입력이 비어있으면 빈 결과를 반환한다."""
        result = classify_null_only_columns([])
        assert result == []

    def test_near_one_is_valid(self):
        """null_frac = 0.99는 invalid가 아니다 (정확히 1.0만 invalid)."""
        stats = [
            ("public", "sales", "rare_col", 0.99),
        ]
        result = classify_null_only_columns(stats)
        assert result == []

    def test_exactly_one(self):
        """null_frac = 1.0 정확히 경계값에서 invalid로 분류된다."""
        stats = [
            ("public", "sales", "dead_col", 1.0),
        ]
        result = classify_null_only_columns(stats)
        assert result == ["public.sales.dead_col"]


# ──────────────────────────────────────────────────────────────
# 설정 기본값 테스트
# ──────────────────────────────────────────────────────────────


class TestConfigDefaults:
    """유효성 부트스트랩 관련 설정 기본값 검증."""

    def test_validity_bootstrap_enabled_default(self):
        """VALIDITY_BOOTSTRAP_ENABLED 기본값은 True이다."""
        from app.core.config import Settings
        s = Settings()
        assert s.VALIDITY_BOOTSTRAP_ENABLED is True

    def test_validity_bootstrap_concurrency_default(self):
        """VALIDITY_BOOTSTRAP_CONCURRENCY 기본값은 6이다."""
        from app.core.config import Settings
        s = Settings()
        assert s.VALIDITY_BOOTSTRAP_CONCURRENCY == 6

    def test_validity_bootstrap_target_schema_default(self):
        """VALIDITY_BOOTSTRAP_TARGET_SCHEMA 기본값은 'public'이다."""
        from app.core.config import Settings
        s = Settings()
        assert s.VALIDITY_BOOTSTRAP_TARGET_SCHEMA == "public"


# ──────────────────────────────────────────────────────────────
# get_last_report 테스트
# ──────────────────────────────────────────────────────────────


class TestGetLastReport:
    """마지막 보고서 조회 함수 검증."""

    def test_returns_none_initially_or_report(self):
        """get_last_report()는 None 또는 ValidityReport를 반환한다."""
        report = get_last_report()
        # 다른 테스트에서 run()을 호출했을 수 있으므로
        # 타입만 검증한다
        assert report is None or isinstance(report, ValidityReport)
