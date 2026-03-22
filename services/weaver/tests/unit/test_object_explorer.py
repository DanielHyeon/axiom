"""Object Explorer + Instance Fetcher 단위 테스트.

테스트 대상:
- ObjectExplorerService: 컬럼 분류 휴리스틱, 안전한 식별자 검증
- InstanceFetcherService: 타입 추론, 데이터 추출 헬퍼
"""
import pytest

from app.services.object_explorer_service import (
    _classify_column,
    _is_safe_identifier,
)
from app.services.instance_fetcher_service import (
    _infer_column_type,
    _validate_identifier,
    InstanceFetcherService,
)


# ── 컬럼 분류 테스트 ──


class TestColumnClassification:
    """컬럼 분류 휴리스틱 검증."""

    def test_id_columns(self):
        """ID 컬럼 패턴 감지."""
        assert _classify_column("id") == "id"
        assert _classify_column("user_id") == "id"
        assert _classify_column("order_code") == "id"
        assert _classify_column("emp_no") == "id"
        assert _classify_column("item_key") == "id"
        assert _classify_column("주문번호") == "id"

    def test_text_columns(self):
        """텍스트 컬럼 패턴 감지."""
        assert _classify_column("name") == "text"
        assert _classify_column("user_name") == "text"
        assert _classify_column("title") == "text"
        assert _classify_column("description") == "text"
        assert _classify_column("label") == "text"
        assert _classify_column("고객명") == "text"
        assert _classify_column("제품이름") == "text"

    def test_other_columns(self):
        """분류 불가 컬럼은 other."""
        assert _classify_column("amount") == "other"
        assert _classify_column("created_at") == "other"
        assert _classify_column("status") == "other"


# ── SQL 식별자 검증 테스트 ──


class TestIdentifierValidation:
    """SQL 식별자 안전성 검증."""

    def test_safe_identifiers(self):
        assert _is_safe_identifier("users") is True
        assert _is_safe_identifier("my_table") is True
        assert _is_safe_identifier("schema.table") is True
        assert _is_safe_identifier("_private") is True

    def test_unsafe_identifiers(self):
        assert _is_safe_identifier("1table") is False
        assert _is_safe_identifier("drop;--") is False
        assert _is_safe_identifier("has space") is False
        assert _is_safe_identifier("") is False

    def test_validate_identifier_raises(self):
        with pytest.raises(ValueError, match="유효하지 않은"):
            _validate_identifier("drop;--")


# ── 타입 추론 테스트 ──


class TestTypeInference:
    """Python 값 → 컬럼 타입 추론."""

    def test_infer_types(self):
        assert _infer_column_type(None) == "unknown"
        assert _infer_column_type(True) == "boolean"
        assert _infer_column_type(42) == "integer"
        assert _infer_column_type(3.14) == "number"
        assert _infer_column_type("hello") == "text"

    def test_infer_date(self):
        assert _infer_column_type("2024-01-15") == "date"
        assert _infer_column_type("2024-01-15T10:30:00") == "date"


# ── 데이터 추출 헬퍼 테스트 ──


class TestDataExtraction:
    """MindsDB 응답 데이터 추출 헬퍼."""

    def test_extract_count_dict(self):
        fetcher = InstanceFetcherService()
        data = {"data": [{"cnt": 42}]}
        assert fetcher._extract_count(data) == 42

    def test_extract_count_list(self):
        fetcher = InstanceFetcherService()
        data = {"data": [[100]]}
        assert fetcher._extract_count(data) == 100

    def test_extract_count_empty(self):
        fetcher = InstanceFetcherService()
        assert fetcher._extract_count({"data": []}) == 0
        assert fetcher._extract_count({}) == 0

    def test_extract_column_names_dict(self):
        fetcher = InstanceFetcherService()
        data = {"data": [{"id": 1, "name": "test"}]}
        assert fetcher._extract_column_names(data) == ["id", "name"]

    def test_extract_column_names_explicit(self):
        fetcher = InstanceFetcherService()
        data = {"column_names": ["a", "b"], "data": [[1, 2]]}
        assert fetcher._extract_column_names(data) == ["a", "b"]

    def test_extract_rows_dict(self):
        fetcher = InstanceFetcherService()
        data = {"data": [{"id": 1}, {"id": 2}]}
        rows = fetcher._extract_rows(data)
        assert len(rows) == 2
        assert rows[0]["id"] == 1

    def test_extract_rows_list(self):
        fetcher = InstanceFetcherService()
        data = {"column_names": ["id", "name"], "data": [[1, "a"], [2, "b"]]}
        rows = fetcher._extract_rows(data)
        assert len(rows) == 2
        assert rows[0] == {"id": 1, "name": "a"}
