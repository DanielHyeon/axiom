"""Value Mapping 서비스 단위 테스트.

테스트 대상:
- _strip_korean_particles (한국어 조사 제거)
- _strip_admin_suffix (행정구역 접미사 제거)
- expand_search_terms (검색어 확장)
- _is_safe_identifier (식별자 안전성 검증)
- ValueMappingService._extract_search_terms (검색어 추출)
- ValueMappingService._extract_equality_filters (SQL 필터 추출)
- ValueMappingService.validate_sql_literals (SQL 리터럴 검증)
- ValueMappingService 캐시 동작
- ValueMapping Pydantic 모델
"""

from __future__ import annotations

import pytest

from app.core.value_mapping import (
    MappingResult,
    ResolvedValue,
    ValueMapping,
    ValueMappingService,
    _is_safe_identifier,
    _strip_admin_suffix,
    _strip_korean_particles,
    expand_search_terms,
)


# ---------------------------------------------------------------------------
# 한국어 조사 제거 테스트
# ---------------------------------------------------------------------------


class TestStripKoreanParticles:
    """한국어 조사 제거 함수 테스트."""

    def test_strip_ui(self):
        """'의' 제거: '서울의' -> '서울'"""
        assert _strip_korean_particles("서울의") == "서울"

    def test_strip_eseo(self):
        """'에서' 제거: '부산에서' -> '부산'"""
        assert _strip_korean_particles("부산에서") == "부산"

    def test_strip_eul(self):
        """'을' 제거: '매출을' -> '매출'"""
        assert _strip_korean_particles("매출을") == "매출"

    def test_strip_reul(self):
        """'를' 제거: '데이터를' -> '데이터'"""
        assert _strip_korean_particles("데이터를") == "데이터"

    def test_no_particle(self):
        """조사가 없으면 원본 반환"""
        assert _strip_korean_particles("서울") == "서울"

    def test_short_string(self):
        """길이 2 미만이면 제거하지 않음"""
        assert _strip_korean_particles("의") == "의"

    def test_empty_string(self):
        assert _strip_korean_particles("") == ""


# ---------------------------------------------------------------------------
# 행정구역 접미사 제거 테스트
# ---------------------------------------------------------------------------


class TestStripAdminSuffix:
    """행정구역 접미사 제거 테스트."""

    def test_strip_si(self):
        """'시' 제거: '부산시' -> '부산'"""
        assert _strip_admin_suffix("부산시") == "부산"

    def test_strip_do(self):
        """'도' 제거: '경기도' -> '경기'"""
        assert _strip_admin_suffix("경기도") == "경기"

    def test_strip_gu(self):
        """'구' 제거: '강남구' -> '강남'"""
        assert _strip_admin_suffix("강남구") == "강남"

    def test_no_suffix(self):
        assert _strip_admin_suffix("서울") == "서울"

    def test_too_short(self):
        """너무 짧으면 접미사 제거하지 않음"""
        assert _strip_admin_suffix("시") == "시"
        assert _strip_admin_suffix("구") == "구"


# ---------------------------------------------------------------------------
# 검색어 확장 테스트
# ---------------------------------------------------------------------------


class TestExpandSearchTerms:
    """한국어 조사/접미사 제거로 검색 범위 확장 테스트."""

    def test_basic_expansion(self):
        """조사 제거 버전이 추가됨"""
        result = expand_search_terms(["서울의"])
        assert "서울의" in result
        assert "서울" in result

    def test_admin_suffix_expansion(self):
        """행정구역 접미사 제거 버전이 추가됨"""
        result = expand_search_terms(["청주시"])
        assert "청주시" in result
        assert "청주" in result

    def test_no_duplicates(self):
        """중복 제거"""
        result = expand_search_terms(["서울", "서울의"])
        # '서울'이 한 번만 등장
        assert result.count("서울") == 1

    def test_max_20(self):
        """최대 20개까지"""
        many_terms = [f"용어{i}" for i in range(30)]
        result = expand_search_terms(many_terms)
        assert len(result) <= 20

    def test_min_length(self):
        """길이 2 미만은 제외"""
        result = expand_search_terms(["가"])
        assert len(result) == 0

    def test_combined_strip(self):
        """조사 + 행정구역 둘 다 제거"""
        result = expand_search_terms(["부산시의"])
        assert "부산시의" in result
        # "부산시의" -> 조사제거 "부산시" -> 행정구역제거 "부산"
        assert "부산시" in result
        assert "부산" in result


# ---------------------------------------------------------------------------
# 식별자 안전성 검증 테스트
# ---------------------------------------------------------------------------


class TestIsSafeIdentifier:
    """SQL 식별자 안전성 검증 테스트."""

    def test_valid_identifiers(self):
        assert _is_safe_identifier("sales") is True
        assert _is_safe_identifier("user_name") is True
        assert _is_safe_identifier("_private") is True
        assert _is_safe_identifier("Table123") is True

    def test_invalid_identifiers(self):
        """SQL injection 가능한 문자열은 거부"""
        assert _is_safe_identifier("sales; DROP TABLE") is False
        assert _is_safe_identifier("col'name") is False
        assert _is_safe_identifier('col"name') is False
        assert _is_safe_identifier("col name") is False
        assert _is_safe_identifier("") is False
        assert _is_safe_identifier("123abc") is False  # 숫자로 시작


# ---------------------------------------------------------------------------
# ValueMappingService 내부 메서드 테스트
# ---------------------------------------------------------------------------


class TestValueMappingServiceInternal:
    """ValueMappingService 내부 메서드 테스트."""

    @pytest.fixture
    def svc(self):
        return ValueMappingService()

    def test_extract_search_terms(self, svc):
        """질문에서 검색 용어 추출"""
        terms = svc._extract_search_terms("서울 지역의 매출 합계를 보여줘")
        # "보여줘"는 불용어로 제거됨
        assert "서울" in terms
        assert "지역의" in terms
        assert "매출" in terms
        assert "보여줘" not in terms

    def test_extract_search_terms_no_numbers(self, svc):
        """순수 숫자는 제외"""
        terms = svc._extract_search_terms("2024년 매출 12345")
        assert "12345" not in terms

    def test_extract_equality_filters(self, svc):
        """SQL에서 col='value' 패턴 추출"""
        filters = svc._extract_equality_filters(
            "SELECT * FROM sales WHERE region='서울' AND status='SUCCESS'"
        )
        assert ("region", "서울") in filters
        assert ("status", "SUCCESS") in filters

    def test_extract_equality_filters_empty(self, svc):
        """필터 없는 SQL"""
        filters = svc._extract_equality_filters("SELECT * FROM sales")
        assert filters == []

    def test_validate_sql_literals_mismatch(self, svc):
        """SQL 리터럴이 허용 값에 없으면 불일치 보고"""
        sql = "SELECT * FROM sales WHERE region='세울'"  # 오타: 서울 -> 세울
        hints = {"region": {"서울", "부산", "대전"}}
        mismatches = svc.validate_sql_literals(sql, hints)
        assert len(mismatches) == 1
        assert mismatches[0]["column"] == "region"
        assert mismatches[0]["value"] == "세울"

    def test_validate_sql_literals_match(self, svc):
        """SQL 리터럴이 허용 값에 있으면 불일치 없음"""
        sql = "SELECT * FROM sales WHERE region='서울'"
        hints = {"region": {"서울", "부산"}}
        mismatches = svc.validate_sql_literals(sql, hints)
        assert len(mismatches) == 0

    def test_validate_sql_literals_no_hints(self, svc):
        """힌트가 없으면 검증 건너뜀"""
        sql = "SELECT * FROM sales WHERE region='서울'"
        mismatches = svc.validate_sql_literals(sql, {})
        assert len(mismatches) == 0


# ---------------------------------------------------------------------------
# ValueMappingService 캐시 동작 테스트
# ---------------------------------------------------------------------------


class TestValueMappingCache:
    """인메모리 캐시 동작 테스트."""

    def test_save_and_lookup(self):
        """캐시에 저장하고 조회"""
        svc = ValueMappingService()
        svc._save_to_cache(
            natural_value="서울",
            db_value="SEOUL",
            column_fqn="sales.region",
            confidence=0.95,
        )
        results = svc._lookup_cache("서울")
        assert len(results) == 1
        assert results[0].db_value == "SEOUL"
        assert results[0].confidence == 0.95

    def test_cache_case_insensitive(self):
        """캐시 조회는 대소문자 무시"""
        svc = ValueMappingService()
        svc._save_to_cache(
            natural_value="Success",
            db_value="SUCCESS",
            column_fqn="t.status",
            confidence=1.0,
        )
        results = svc._lookup_cache("success")
        assert len(results) == 1

    def test_cache_miss(self):
        """캐시에 없으면 빈 목록"""
        svc = ValueMappingService()
        results = svc._lookup_cache("없는값")
        assert len(results) == 0


# ---------------------------------------------------------------------------
# ValueMapping 모델 테스트
# ---------------------------------------------------------------------------


class TestValueMappingModel:
    """ValueMapping Pydantic 모델 테스트."""

    def test_basic_creation(self):
        vm = ValueMapping(
            natural_value="서울",
            db_value="SEOUL",
            column_fqn="sales.region",
        )
        assert vm.natural_value == "서울"
        assert vm.db_value == "SEOUL"
        assert vm.confidence == 1.0  # 기본값
        assert vm.verified is False

    def test_with_source(self):
        vm = ValueMapping(
            natural_value="성공",
            db_value="SUCCESS",
            column_fqn="t.status",
            source="db_probe",
            confidence=0.75,
            verified=True,
        )
        assert vm.source == "db_probe"
        assert vm.verified is True
