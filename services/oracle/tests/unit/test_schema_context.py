"""서브스키마 컨텍스트 테스트 (#7 P1-1).

build_sub_schema_ddl()이 올바른 DDL 문자열을 생성하는지 검증한다.
"""

import pytest
from app.core.schema_context import (
    SubSchemaContext,
    RelevantTable,
    RelevantColumn,
    build_sub_schema_ddl,
)


def _make_sales_table() -> RelevantTable:
    """테스트용 sales 테이블 생성."""
    return RelevantTable(
        name="sales",
        schema="public",
        description="매출 데이터",
        columns=[
            RelevantColumn(name="id", data_type="SERIAL", is_key=True),
            RelevantColumn(name="company_name", data_type="VARCHAR(100)", description="회사명"),
            RelevantColumn(name="revenue", data_type="NUMERIC(15,2)"),
            RelevantColumn(name="region", data_type="VARCHAR(50)"),
        ],
        score=0.95,
    )


def _make_operations_table() -> RelevantTable:
    """테스트용 operations 테이블 생성."""
    return RelevantTable(
        name="operations",
        columns=[
            RelevantColumn(name="id", data_type="SERIAL", is_key=True),
            RelevantColumn(name="status", data_type="VARCHAR(20)"),
        ],
    )


# ──────────────────────────────────────────────────────────────
# DDL 생성 테스트
# ──────────────────────────────────────────────────────────────

def test_basic_ddl_generation():
    """기본 DDL 문자열이 올바르게 생성된다."""
    ctx = SubSchemaContext(tables=[_make_sales_table()])
    ddl = build_sub_schema_ddl(ctx)

    assert "CREATE TABLE public.sales" in ddl
    assert "id SERIAL PRIMARY KEY" in ddl
    assert "company_name VARCHAR(100)" in ddl
    assert "revenue NUMERIC(15,2)" in ddl
    assert "-- 회사명" in ddl
    assert "-- 매출 데이터" in ddl


def test_multiple_tables():
    """여러 테이블의 DDL이 모두 포함된다."""
    ctx = SubSchemaContext(
        tables=[_make_sales_table(), _make_operations_table()]
    )
    ddl = build_sub_schema_ddl(ctx)

    assert "CREATE TABLE public.sales" in ddl
    assert "CREATE TABLE operations" in ddl  # 스키마 없으면 이름만
    assert "status VARCHAR(20)" in ddl


def test_table_without_schema_prefix():
    """스키마가 없는 테이블은 이름만 사용한다."""
    ctx = SubSchemaContext(tables=[_make_operations_table()])
    ddl = build_sub_schema_ddl(ctx)

    # "public.operations"가 아닌 "operations"
    assert "CREATE TABLE operations" in ddl
    assert "public.operations" not in ddl


def test_empty_context():
    """빈 컨텍스트는 빈 문자열을 반환한다."""
    ctx = SubSchemaContext()
    ddl = build_sub_schema_ddl(ctx)
    assert ddl == ""


def test_table_with_no_columns():
    """컬럼이 없는 테이블도 DDL에 포함된다."""
    ctx = SubSchemaContext(tables=[RelevantTable(name="empty_table")])
    ddl = build_sub_schema_ddl(ctx)
    assert "CREATE TABLE empty_table" in ddl


# ──────────────────────────────────────────────────────────────
# FK 관계 포함 테스트
# ──────────────────────────────────────────────────────────────

def test_fk_relationships_included():
    """FK 관계가 DDL에 포함된다."""
    ctx = SubSchemaContext(
        tables=[_make_sales_table()],
        fk_relationships=[
            {"from_table": "sales", "from_column": "company_id",
             "to_table": "companies", "to_column": "id"},
        ],
    )
    ddl = build_sub_schema_ddl(ctx)

    assert "Foreign Key Relationships" in ddl
    assert "sales.company_id -> companies.id" in ddl


def test_fk_limited_to_20():
    """FK 관계는 최대 20개만 포함된다."""
    fks = [
        {"from_table": f"t{i}", "from_column": "fk",
         "to_table": f"t{i+1}", "to_column": "id"}
        for i in range(25)
    ]
    ctx = SubSchemaContext(tables=[_make_sales_table()], fk_relationships=fks)
    ddl = build_sub_schema_ddl(ctx)

    # 마지막 FK (t24 -> t25)는 포함되지 않아야 함
    assert "t19" in ddl
    assert "t24" not in ddl


# ──────────────────────────────────────────────────────────────
# Enum 힌트 포함 테스트
# ──────────────────────────────────────────────────────────────

def test_enum_hints_included():
    """enum 힌트가 DDL에 포함된다."""
    ctx = SubSchemaContext(
        tables=[_make_sales_table()],
        enum_hints=[
            {"table": "sales", "column": "region",
             "values": ["서울", "부산", "대전"], "cardinality": 3},
        ],
    )
    ddl = build_sub_schema_ddl(ctx)

    assert "Known Column Values" in ddl
    assert "sales.region" in ddl
    assert "'서울'" in ddl
    assert "'부산'" in ddl


def test_enum_values_limited_to_10():
    """enum 값은 컬럼당 최대 10개만 표시된다."""
    values = [f"val_{i}" for i in range(20)]
    ctx = SubSchemaContext(
        tables=[_make_sales_table()],
        enum_hints=[
            {"table": "sales", "column": "region", "values": values},
        ],
    )
    ddl = build_sub_schema_ddl(ctx)

    assert "'val_9'" in ddl
    assert "'val_10'" not in ddl


# ──────────────────────────────────────────────────────────────
# 값 매핑 포함 테스트
# ──────────────────────────────────────────────────────────────

def test_value_mappings_included():
    """값 매핑이 DDL에 포함된다."""
    ctx = SubSchemaContext(
        tables=[_make_sales_table()],
        value_mappings=[
            {"natural_language": "서울전자", "db_value": "서울전자",
             "table": "sales", "column": "company_name"},
        ],
    )
    ddl = build_sub_schema_ddl(ctx)

    assert "Value Mappings" in ddl
    assert "'서울전자'" in ddl


def test_value_mappings_limited_to_10():
    """값 매핑은 최대 10개만 포함된다."""
    vms = [
        {"natural_language": f"term_{i}", "db_value": f"val_{i}",
         "table": "t", "column": "c"}
        for i in range(15)
    ]
    ctx = SubSchemaContext(tables=[_make_sales_table()], value_mappings=vms)
    ddl = build_sub_schema_ddl(ctx)

    assert "term_9" in ddl
    assert "term_10" not in ddl


# ──────────────────────────────────────────────────────────────
# 유사 쿼리 포함 테스트
# ──────────────────────────────────────────────────────────────

def test_similar_queries_included():
    """유사 쿼리가 DDL에 포함된다."""
    ctx = SubSchemaContext(
        tables=[_make_sales_table()],
        similar_queries=[
            {"question": "서울전자 매출", "sql": "SELECT SUM(revenue) FROM sales"},
        ],
    )
    ddl = build_sub_schema_ddl(ctx)

    assert "Similar Cached Queries" in ddl
    assert "서울전자 매출" in ddl
    assert "SELECT SUM(revenue)" in ddl


def test_similar_queries_limited_to_3():
    """유사 쿼리는 최대 3개만 포함된다."""
    queries = [
        {"question": f"query_{i}", "sql": f"SELECT {i}"}
        for i in range(5)
    ]
    ctx = SubSchemaContext(tables=[_make_sales_table()], similar_queries=queries)
    ddl = build_sub_schema_ddl(ctx)

    assert "query_2" in ddl
    assert "query_3" not in ddl


# ──────────────────────────────────────────────────────────────
# 전체 조합 테스트
# ──────────────────────────────────────────────────────────────

def test_full_context_all_sections():
    """모든 섹션이 포함된 전체 컨텍스트 DDL."""
    ctx = SubSchemaContext(
        tables=[_make_sales_table()],
        fk_relationships=[
            {"from_table": "sales", "from_column": "company_id",
             "to_table": "companies", "to_column": "id"},
        ],
        enum_hints=[
            {"table": "sales", "column": "region", "values": ["서울"]},
        ],
        value_mappings=[
            {"natural_language": "서울전자", "db_value": "서울전자",
             "table": "sales", "column": "company_name"},
        ],
        similar_queries=[
            {"question": "매출 합계", "sql": "SELECT SUM(revenue) FROM sales"},
        ],
    )
    ddl = build_sub_schema_ddl(ctx)

    # 모든 섹션이 존재하는지 확인
    assert "CREATE TABLE" in ddl
    assert "Foreign Key Relationships" in ddl
    assert "Known Column Values" in ddl
    assert "Value Mappings" in ddl
    assert "Similar Cached Queries" in ddl
