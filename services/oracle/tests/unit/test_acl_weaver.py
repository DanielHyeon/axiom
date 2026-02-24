"""Oracle WeaverACL 단위 테스트.

Weaver API 응답 형식이 변경되어도 Oracle 내부 모델이 안정적으로 유지되는지 검증한다.
"""
import pytest

from app.infrastructure.acl.weaver_acl import (
    OracleWeaverACL,
    QueryExecutionResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def acl():
    return OracleWeaverACL(
        query_url="http://fake-weaver:8001/api/query",
        bearer_token="test-token",
    )


# ---------------------------------------------------------------------------
# execute_query 변환 테스트
# ---------------------------------------------------------------------------


class TestTranslateQueryResult:
    """Weaver 쿼리 실행 응답 → QueryExecutionResult 변환 검증."""

    def test_standard_response(self, acl: OracleWeaverACL):
        body = {
            "data": [[1, "Alice", 100], [2, "Bob", 200]],
            "columns": ["id", "name", "amount"],
            "row_count": 2,
            "execution_time_ms": 42,
        }
        result = acl._translate_query_result(body, fallback_elapsed_ms=100)

        assert isinstance(result, QueryExecutionResult)
        assert result.columns == ["id", "name", "amount"]
        assert len(result.rows) == 2
        assert result.row_count == 2
        assert result.truncated is False
        assert result.execution_time_ms == 42

    def test_truncated_response(self, acl: OracleWeaverACL):
        """row_count > len(data) → truncated=True."""
        body = {
            "data": [[1], [2], [3]],
            "columns": ["id"],
            "row_count": 100,
        }
        result = acl._translate_query_result(body, fallback_elapsed_ms=50)
        assert result.truncated is True
        assert result.row_count == 100
        assert len(result.rows) == 3

    def test_empty_response(self, acl: OracleWeaverACL):
        body = {}
        result = acl._translate_query_result(body, fallback_elapsed_ms=10)
        assert result.columns == []
        assert result.rows == []
        assert result.row_count == 0
        assert result.execution_time_ms == 10

    def test_fallback_elapsed_ms(self, acl: OracleWeaverACL):
        """execution_time_ms 없으면 fallback 값 사용."""
        body = {"data": [[1]], "columns": ["x"], "row_count": 1}
        result = acl._translate_query_result(body, fallback_elapsed_ms=77)
        assert result.execution_time_ms == 77

    def test_non_list_data_safety(self, acl: OracleWeaverACL):
        """data가 list가 아닌 경우 빈 리스트로 안전 처리."""
        body = {"data": "not a list", "columns": ["a"]}
        result = acl._translate_query_result(body, fallback_elapsed_ms=5)
        assert result.rows == []

    def test_is_configured_property(self):
        configured = OracleWeaverACL(bearer_token="token")
        assert configured.is_configured is True

        not_configured = OracleWeaverACL(bearer_token="")
        assert not_configured.is_configured is False
