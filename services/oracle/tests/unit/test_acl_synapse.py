"""Oracle SynapseACL 단위 테스트.

Synapse API 응답 형식이 변경되어도 Oracle 내부 모델이 안정적으로 유지되는지 검증한다.
"""
import pytest

from app.infrastructure.acl.synapse_acl import (
    CachedQuery,
    ColumnInfo,
    DatasourceInfo,
    OracleSynapseACL,
    SchemaSearchResult,
    SchemaUpdateResult,
    TableInfo,
    ValueMapping,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def acl():
    return OracleSynapseACL(base_url="http://fake-synapse:8003")


# ---------------------------------------------------------------------------
# search_schema_context 변환 테스트
# ---------------------------------------------------------------------------


class TestTranslateSearchResult:
    """Synapse 그래프 검색 응답 → SchemaSearchResult 변환 검증."""

    def test_standard_response(self, acl: OracleSynapseACL):
        data = {
            "tables": {
                "vector_matched": [
                    {
                        "name": "sales_records",
                        "columns": [
                            {"name": "id", "data_type": "integer", "is_key": True},
                            {"name": "amount", "data_type": "numeric"},
                        ],
                        "has_embedding": True,
                    }
                ],
                "fk_related": [
                    {
                        "name": "employees",
                        "columns": [{"name": "emp_id"}, {"name": "name"}],
                    }
                ],
            },
            "value_mappings": [
                {
                    "natural_language": "서울",
                    "db_value": "SEOUL",
                    "column": "region",
                    "table": "branches",
                }
            ],
            "similar_queries": [
                {
                    "question": "매출 합계는?",
                    "sql": "SELECT SUM(amount) FROM sales_records",
                    "confidence": 0.95,
                }
            ],
        }
        result = acl._translate_search_result(data)

        assert isinstance(result, SchemaSearchResult)
        assert len(result.tables) == 2

        # First table
        t0 = result.tables[0]
        assert isinstance(t0, TableInfo)
        assert t0.name == "sales_records"
        assert len(t0.columns) == 2
        assert t0.columns[0].is_key is True
        assert t0.has_embedding is True

        # FK related table
        t1 = result.tables[1]
        assert t1.name == "employees"
        assert len(t1.columns) == 2

        # Value mappings
        assert len(result.value_mappings) == 1
        vm = result.value_mappings[0]
        assert isinstance(vm, ValueMapping)
        assert vm.natural_language == "서울"
        assert vm.db_value == "SEOUL"

        # Cached queries
        assert len(result.cached_queries) == 1
        cq = result.cached_queries[0]
        assert isinstance(cq, CachedQuery)
        assert cq.confidence == 0.95

    def test_duplicate_table_dedup(self, acl: OracleSynapseACL):
        """같은 테이블이 vector_matched와 fk_related 양쪽에 있으면 중복 제거."""
        data = {
            "tables": {
                "vector_matched": [{"name": "orders", "columns": [{"name": "id"}]}],
                "fk_related": [{"name": "orders", "columns": [{"name": "id"}, {"name": "total"}]}],
            }
        }
        result = acl._translate_search_result(data)
        assert len(result.tables) == 1
        assert result.tables[0].name == "orders"

    def test_no_columns_default(self, acl: OracleSynapseACL):
        """컬럼 없는 테이블은 기본 [id, name] 컬럼."""
        data = {"tables": {"vector_matched": [{"name": "unknown_table"}], "fk_related": []}}
        result = acl._translate_search_result(data)
        assert len(result.tables[0].columns) == 2
        assert result.tables[0].columns[0].name == "id"

    def test_empty_response(self, acl: OracleSynapseACL):
        result = acl._translate_search_result({})
        assert result.tables == []
        assert result.value_mappings == []
        assert result.cached_queries == []


# ---------------------------------------------------------------------------
# list_tables 변환 테스트
# ---------------------------------------------------------------------------


class TestTranslateTableList:
    def test_standard_response(self, acl: OracleSynapseACL):
        response = {
            "data": {
                "tables": [
                    {"name": "creditors", "description": "채권자 목록", "row_count": 500, "has_embedding": True},
                    {"name": "debtors", "description": "채무자 정보"},
                ]
            }
        }
        result = acl._translate_table_list(response)
        assert len(result) == 2
        assert result[0].name == "creditors"
        assert result[0].row_count == 500
        assert result[0].has_embedding is True
        assert result[1].description == "채무자 정보"

    def test_empty_tables(self, acl: OracleSynapseACL):
        assert acl._translate_table_list({}) == []
        assert acl._translate_table_list({"data": {"tables": []}}) == []


# ---------------------------------------------------------------------------
# get_table_detail 변환 테스트
# ---------------------------------------------------------------------------


class TestTranslateTableDetail:
    def test_standard_response(self, acl: OracleSynapseACL):
        response = {
            "data": {
                "description": "매출 테이블",
                "columns": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "amount", "data_type": "numeric", "description": "금액"},
                ],
            }
        }
        result = acl._translate_table_detail(response, "sales")
        assert result is not None
        assert result.name == "sales"
        assert len(result.columns) == 2
        assert result.columns[1].description == "금액"

    def test_no_columns_returns_none(self, acl: OracleSynapseACL):
        response = {"data": {"columns": []}}
        assert acl._translate_table_detail(response, "empty") is None


# ---------------------------------------------------------------------------
# list_datasources 변환 테스트
# ---------------------------------------------------------------------------


class TestListDatasources:
    def test_default_datasource(self):
        """JSON 파싱 실패 시 기본 데이터소스 반환."""
        acl = OracleSynapseACL.__new__(OracleSynapseACL)
        acl._datasources_json = "invalid json"
        result = acl.list_datasources()
        assert len(result) == 1
        assert isinstance(result[0], DatasourceInfo)
        assert result[0].id == "ds_business_main"

    def test_custom_datasources(self):
        acl = OracleSynapseACL.__new__(OracleSynapseACL)
        acl._datasources_json = '[{"id":"ds1","name":"Test","type":"postgres","database":"testdb"}]'
        result = acl.list_datasources()
        assert len(result) == 1
        assert result[0].id == "ds1"
        assert result[0].database == "testdb"
