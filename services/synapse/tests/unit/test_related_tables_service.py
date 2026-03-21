"""스키마 네비게이션 서비스 단위 테스트.

Neo4j 클라이언트를 모킹하여 순수 로직만 검증한다.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.related_tables_service import (
    build_node_key,
    SchemaMode,
    RelatedTableRequest,
    RelatedTableItem,
    fetch_schema_availability,
    fetch_related_tables_unified,
)


# ────────────────────────────────────────────────────────
# build_node_key 테스트
# ────────────────────────────────────────────────────────


def test_build_node_key_lowercase():
    """mode가 대문자여도 소문자로 변환되어야 한다."""
    result = build_node_key("ROBO", "erp_db", "public", "orders")
    assert result.startswith("robo:")
    assert result == "robo:erp_db:public:orders"


def test_build_node_key_defaults():
    """datasource=None, schema=None일 때 빈문자열과 'public' 기본값을 사용한다."""
    result = build_node_key("text2sql", None, None, "users")
    assert result == "text2sql::public:users"


def test_build_node_key_full():
    """모든 값이 주어졌을 때 정확한 형식을 반환한다."""
    result = build_node_key("text2sql", "erp_db", "sales", "invoices")
    assert result == "text2sql:erp_db:sales:invoices"


def test_build_node_key_roundtrip():
    """프론트엔드 nodeKey 형식과 일치하는지 확인한다."""
    # 프론트엔드에서 생성하는 키: text2sql:erp_db:public:orders
    expected = "text2sql:erp_db:public:orders"
    result = build_node_key("TEXT2SQL", "erp_db", "public", "orders")
    assert result == expected


# ────────────────────────────────────────────────────────
# RelatedTableRequest 테스트
# ────────────────────────────────────────────────────────


def test_request_get_node_key_auto():
    """nodeKey가 None이면 mode/datasource/schema/table 조합으로 자동 생성한다."""
    req = RelatedTableRequest(
        mode=SchemaMode.TEXT2SQL,
        tableName="orders",
        datasourceName="erp_db",
        schemaName="public",
    )
    assert req.get_node_key() == "text2sql:erp_db:public:orders"


def test_request_get_node_key_explicit():
    """nodeKey가 명시적으로 주어지면 그대로 반환한다."""
    req = RelatedTableRequest(
        mode=SchemaMode.ROBO,
        tableName="orders",
        nodeKey="custom:key:here:orders",
    )
    assert req.get_node_key() == "custom:key:here:orders"


def test_request_alias_parsing():
    """camelCase JSON 필드(tableName → table_name)가 올바르게 파싱되는지 확인한다."""
    req = RelatedTableRequest.model_validate({
        "mode": "TEXT2SQL",
        "tableName": "invoices",
        "schemaName": "sales",
        "datasourceName": "erp_db",
        "alreadyLoadedTableIds": ["text2sql:erp_db:sales:orders"],
        "limit": 10,
    })
    assert req.table_name == "invoices"
    assert req.schema_name == "sales"
    assert req.datasource_name == "erp_db"
    assert req.already_loaded_table_ids == ["text2sql:erp_db:sales:orders"]
    assert req.limit == 10


# ────────────────────────────────────────────────────────
# fetch_schema_availability 테스트 (Neo4j 모킹)
# ────────────────────────────────────────────────────────


@pytest.fixture
def mock_neo4j():
    """neo4j_client를 모킹하여 DB 접근 없이 테스트한다."""
    with patch("app.services.related_tables_service.neo4j_client") as mock:
        mock.execute_read = AsyncMock(return_value=[])
        yield mock


@pytest.mark.asyncio
async def test_availability_no_filter(mock_neo4j):
    """datasource_name=None일 때 전체 카운트를 조회한다."""
    # 첫 번째 호출: ROBO 카운트, 두 번째 호출: TEXT2SQL 카운트
    mock_neo4j.execute_read = AsyncMock(side_effect=[
        [{"cnt": 5}],   # ROBO: datasource_name 없는 Table
        [{"cnt": 13}],  # TEXT2SQL: datasource_name 있는 Table
    ])
    result = await fetch_schema_availability(datasource_name=None, tenant_id="")
    assert result.robo["table_count"] == 5
    assert result.text2sql["table_count"] == 13
    # 파라미터 바인딩 없이 호출 (전체 카운트)
    assert mock_neo4j.execute_read.call_count == 2


@pytest.mark.asyncio
async def test_availability_with_filter(mock_neo4j):
    """datasource_name='erp_db'일 때 해당 데이터소스만 필터하여 센다."""
    mock_neo4j.execute_read = AsyncMock(side_effect=[
        [{"cnt": 0}],   # ROBO 카운트
        [{"cnt": 8}],   # TEXT2SQL 필터된 카운트
    ])
    result = await fetch_schema_availability(datasource_name="erp_db", tenant_id="")
    assert result.robo["table_count"] == 0
    assert result.text2sql["table_count"] == 8
    # 두 번째 호출에 datasource 파라미터가 전달되어야 한다
    second_call_args = mock_neo4j.execute_read.call_args_list[1]
    assert second_call_args[0][1]["ds"] == "erp_db"


@pytest.mark.asyncio
async def test_availability_empty(mock_neo4j):
    """모든 카운트가 0일 때 빈 결과를 반환한다."""
    mock_neo4j.execute_read = AsyncMock(side_effect=[
        [{"cnt": 0}],  # ROBO
        [{"cnt": 0}],  # TEXT2SQL
    ])
    result = await fetch_schema_availability(tenant_id="")
    assert result.robo["table_count"] == 0
    assert result.text2sql["table_count"] == 0


# ────────────────────────────────────────────────────────
# fetch_related_tables_unified 테스트 (Neo4j 모킹)
# ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unified_robo_mode(mock_neo4j):
    """ROBO 모드에서 FK_OUT/FK_IN 결과를 올바르게 반환한다."""
    mock_neo4j.execute_read = AsyncMock(side_effect=[
        # _resolve_robo: 나가는 FK (FK_OUT)
        [{"related_table": "line_items", "related_schema": "public", "fk_count": 2}],
        # _resolve_robo: 들어오는 FK (FK_IN)
        [{"related_table": "customers", "related_schema": "public", "fk_count": 1}],
        # _detect_hub_tables: 허브 없음
        [],
    ])

    req = RelatedTableRequest(
        mode=SchemaMode.ROBO,
        tableName="orders",
        schemaName="public",
    )
    result = await fetch_related_tables_unified(req, tenant_id="")

    assert len(result.related_tables) == 2
    # FK_OUT 항목 확인
    fk_out = [r for r in result.related_tables if r.relation_type == "FK_OUT"]
    assert len(fk_out) == 1
    assert fk_out[0].table_name == "line_items"
    # FK_IN 항목 확인
    fk_in = [r for r in result.related_tables if r.relation_type == "FK_IN"]
    assert len(fk_in) == 1
    assert fk_in[0].table_name == "customers"


@pytest.mark.asyncio
async def test_unified_text2sql_table_level(mock_neo4j):
    """TEXT2SQL 모드에서 테이블 레벨 FK가 있으면 그것만 사용한다."""
    mock_neo4j.execute_read = AsyncMock(side_effect=[
        # _resolve_text2sql_table_level: 나가는 FK
        [{"related_table": "products", "related_schema": "public",
          "related_ds": "erp_db", "fk_count": 1}],
        # _resolve_text2sql_table_level: 들어오는 FK
        [],
        # _detect_hub_tables: 허브 없음
        [],
    ])

    req = RelatedTableRequest(
        mode=SchemaMode.TEXT2SQL,
        tableName="orders",
        datasourceName="erp_db",
    )
    result = await fetch_related_tables_unified(req, tenant_id="")

    # 테이블 레벨 결과가 있으므로 컬럼 레벨은 호출되지 않는다
    # 나가는 FK(1) + 들어오는 FK(1) + 허브 감지(1) = 3회 호출
    assert mock_neo4j.execute_read.call_count == 3
    assert len(result.related_tables) == 1
    assert result.related_tables[0].table_name == "products"


@pytest.mark.asyncio
async def test_unified_text2sql_column_fallback(mock_neo4j):
    """TEXT2SQL 테이블 레벨 결과가 없으면 컬럼 레벨로 폴백한다."""
    mock_neo4j.execute_read = AsyncMock(side_effect=[
        # _resolve_text2sql_table_level: 나가는 FK → 빈 결과
        [],
        # _resolve_text2sql_table_level: 들어오는 FK → 빈 결과
        [],
        # _resolve_text2sql_column_level: 참조하는 쪽
        [{"related_table": "accounts", "related_schema": "public",
          "related_ds": "erp_db", "fk_count": 1,
          "source_cols": ["account_id"], "target_cols": ["id"]}],
        # _resolve_text2sql_column_level: 참조받는 쪽
        [],
        # _detect_hub_tables: 허브 없음
        [],
    ])

    req = RelatedTableRequest(
        mode=SchemaMode.TEXT2SQL,
        tableName="transactions",
        datasourceName="erp_db",
    )
    result = await fetch_related_tables_unified(req, tenant_id="")

    # 테이블 레벨 2회 + 컬럼 레벨 2회 + 허브 감지 1회 = 총 5회 호출
    assert mock_neo4j.execute_read.call_count == 5
    assert len(result.related_tables) == 1
    assert result.related_tables[0].table_name == "accounts"
    assert result.related_tables[0].source_columns == ["account_id"]
    assert result.related_tables[0].target_columns == ["id"]


@pytest.mark.asyncio
async def test_unified_already_loaded_filter(mock_neo4j):
    """alreadyLoadedTableIds에 포함된 테이블은 결과에서 제외된다."""
    mock_neo4j.execute_read = AsyncMock(side_effect=[
        # ROBO 나가는 FK
        [
            {"related_table": "line_items", "related_schema": "public", "fk_count": 1},
            {"related_table": "payments", "related_schema": "public", "fk_count": 1},
        ],
        # ROBO 들어오는 FK
        [],
        # _detect_hub_tables: 허브 없음
        [],
    ])

    # line_items는 이미 로드된 상태
    already_loaded_key = build_node_key("ROBO", "", "public", "line_items")
    req = RelatedTableRequest(
        mode=SchemaMode.ROBO,
        tableName="orders",
        alreadyLoadedTableIds=[already_loaded_key],
    )
    result = await fetch_related_tables_unified(req, tenant_id="")

    # line_items는 제외되고 payments만 남아야 한다
    assert len(result.related_tables) == 1
    assert result.related_tables[0].table_name == "payments"
    assert result.meta["excludedAlreadyLoaded"] == 1


@pytest.mark.asyncio
async def test_unified_limit_applied(mock_neo4j):
    """limit=2일 때 최대 2개만 반환한다."""
    mock_neo4j.execute_read = AsyncMock(side_effect=[
        # ROBO 나가는 FK — 4개 후보
        [
            {"related_table": "t1", "related_schema": "public", "fk_count": 1},
            {"related_table": "t2", "related_schema": "public", "fk_count": 2},
            {"related_table": "t3", "related_schema": "public", "fk_count": 3},
            {"related_table": "t4", "related_schema": "public", "fk_count": 1},
        ],
        # ROBO 들어오는 FK
        [],
        # _detect_hub_tables: 허브 없음
        [],
    ])

    req = RelatedTableRequest(
        mode=SchemaMode.ROBO,
        tableName="orders",
        limit=2,
    )
    result = await fetch_related_tables_unified(req, tenant_id="")

    assert len(result.related_tables) == 2
    assert result.meta["limitApplied"] == 2


@pytest.mark.asyncio
async def test_unified_score_sorting(mock_neo4j):
    """결과가 점수 내림차순으로 정렬되는지 확인한다."""
    mock_neo4j.execute_read = AsyncMock(side_effect=[
        # ROBO 나가는 FK — fk_count가 다른 항목들 (점수에 반영됨)
        [
            {"related_table": "low_score", "related_schema": "public", "fk_count": 0},
            {"related_table": "high_score", "related_schema": "public", "fk_count": 4},
            {"related_table": "mid_score", "related_schema": "public", "fk_count": 2},
        ],
        # ROBO 들어오는 FK
        [],
        # _detect_hub_tables: 허브 없음
        [],
    ])

    req = RelatedTableRequest(
        mode=SchemaMode.ROBO,
        tableName="orders",
        limit=10,
    )
    result = await fetch_related_tables_unified(req, tenant_id="")

    scores = [item.score for item in result.related_tables]
    # 점수가 내림차순이어야 한다
    assert scores == sorted(scores, reverse=True)
    # 첫 번째가 가장 높은 점수 (fk_count=4 → base 1.0 + 4*0.02=0.08 → 1.08)
    assert result.related_tables[0].table_name == "high_score"
    assert result.related_tables[-1].table_name == "low_score"


# ────────────────────────────────────────────────────────
# _compute_score 테스트 (Step 4-1: 가중치 기반 스코어링)
# ────────────────────────────────────────────────────────


@pytest.mark.parametrize("base,fk,hop,expected", [
    (1.0, 1, 1, 1.02),    # 기본 + FK 보너스, 1홉
    (1.0, 5, 1, 1.09),    # FK 보너스 최대 캡 (5*0.02=0.10 → min(0.10,0.09)=0.09)
    (1.0, 10, 1, 1.09),   # 10개여도 0.09 캡
    (1.0, 1, 2, 0.87),    # 2홉 페널티 -0.15
    (0.9, 2, 3, 0.64),    # 3홉 페널티 -0.30
    (0.9, 0, 1, 0.9),     # FK 0개 = 보너스 없음
])
def test_compute_score(base, fk, hop, expected):
    """_compute_score가 FK 보너스와 홉 페널티를 올바르게 적용하는지 확인한다."""
    from app.services.related_tables_service import _compute_score
    assert _compute_score(base, fk, hop) == expected


# ────────────────────────────────────────────────────────
# _detect_hub_tables 테스트 (Step 4-2: 허브 테이블 감지)
# ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_hub_tables(mock_neo4j):
    """FK가 10개 이상인 테이블은 허브로 감지되어야 한다."""
    mock_neo4j.execute_read = AsyncMock(return_value=[
        {"name": "users"},      # FK 10개 이상
    ])
    from app.services.related_tables_service import _detect_hub_tables
    result = await _detect_hub_tables(["users", "orders"], tenant_id="t1")
    assert "users" in result
    # 쿼리에 threshold 파라미터가 전달되었는지 확인
    call_args = mock_neo4j.execute_read.call_args
    assert call_args[0][1]["threshold"] == 10


@pytest.mark.asyncio
async def test_detect_hub_tables_empty(mock_neo4j):
    """허브 테이블이 없으면 빈 set을 반환한다."""
    mock_neo4j.execute_read = AsyncMock(return_value=[])
    from app.services.related_tables_service import _detect_hub_tables
    result = await _detect_hub_tables(["orders"], tenant_id="t1")
    assert len(result) == 0


# ────────────────────────────────────────────────────────
# 허브 테이블 → autoAddRecommended=false 통합 테스트
# ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unified_hub_table_not_auto_recommended(mock_neo4j):
    """허브 테이블은 결과에 포함되지만 autoAddRecommended=false여야 한다."""
    # 첫 번째 호출: outgoing FK → users 테이블 반환
    # 두 번째 호출: incoming FK → 빈 결과
    # 세 번째 호출: 허브 감지 → users가 허브
    mock_neo4j.execute_read = AsyncMock(side_effect=[
        [{"related_table": "users", "related_schema": "public", "fk_count": 1, "hop_distance": 1}],
        [],
        [{"name": "users"}],  # 허브 감지 결과
    ])
    request = RelatedTableRequest(
        mode=SchemaMode.ROBO, tableName="orders", schemaName="public",
    )
    result = await fetch_related_tables_unified(request, tenant_id="t1")
    users_item = next(r for r in result.related_tables if r.table_name == "users")
    assert users_item.auto_add_recommended is False


# ────────────────────────────────────────────────────────
# Multi-hop 테스트 (Step 4-3: depth 파라미터)
# ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unified_multihop_depth2(mock_neo4j):
    """depth=2일 때 2홉 경로로 연결된 테이블도 반환한다."""
    mock_neo4j.execute_read = AsyncMock(side_effect=[
        # multi-hop 쿼리 결과
        [
            {"related_table": "orders", "related_schema": "public", "hop_distance": 1},
            {"related_table": "products", "related_schema": "public", "hop_distance": 2},
        ],
        # _detect_hub_tables: 허브 없음
        [],
    ])
    request = RelatedTableRequest(
        mode=SchemaMode.ROBO, tableName="customers", schemaName="public",
        depth=2,
    )
    result = await fetch_related_tables_unified(request, tenant_id="t1")
    assert len(result.related_tables) == 2
    # 1홉 테이블이 2홉보다 점수가 높아야 함
    orders = next(r for r in result.related_tables if r.table_name == "orders")
    products = next(r for r in result.related_tables if r.table_name == "products")
    assert orders.score > products.score
    assert orders.hop_distance == 1
    assert products.hop_distance == 2


# ────────────────────────────────────────────────────────
# tenant_id 필터 테스트
# ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_availability_with_tenant_id(mock_neo4j):
    """tenant_id가 전달되면 Cypher 쿼리에 tenant_id 조건이 포함된다."""
    mock_neo4j.execute_read = AsyncMock(side_effect=[
        [{"cnt": 5}],
        [{"cnt": 10}],
    ])
    result = await fetch_schema_availability(tenant_id="tenant-123")
    # 두 쿼리 모두 tenant_id 파라미터가 전달되었는지 확인
    for call in mock_neo4j.execute_read.call_args_list:
        assert call[0][1]["tid"] == "tenant-123"
