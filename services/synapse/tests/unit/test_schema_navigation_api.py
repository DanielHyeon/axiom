"""스키마 네비게이션 API 통합 테스트.

실제 HTTP 요청/응답을 검증한다. 서비스 함수는 모킹한다.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, ANY
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.related_tables_service import (
    SchemaAvailabilityResponse,
    RelatedTableResponse,
    RelatedTableItem,
)

# 서비스 토큰 인증 헤더 — TenantMiddleware가 tenant_id="system"으로 설정한다
AUTH = {"Authorization": "Bearer local-oracle-token"}
TENANT = {"X-Tenant-Id": "test-tenant"}
HEADERS = {**AUTH, **TENANT}


@pytest_asyncio.fixture
async def ac():
    """httpx AsyncClient를 생성하여 FastAPI 앱에 직접 요청한다."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


# ────────────────────────────────────────────────────────
# GET /api/v3/synapse/schema-nav/availability
# ────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.api.schema_navigation.fetch_schema_availability")
async def test_availability_success(mock_fn, ac):
    """가용성 조회가 성공하면 success=True와 올바른 데이터를 반환한다."""
    mock_fn.return_value = SchemaAvailabilityResponse(
        robo={"table_count": 0},
        text2sql={"table_count": 13},
    )
    resp = await ac.get(
        "/api/v3/synapse/schema-nav/availability",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["text2sql"]["table_count"] == 13
    assert data["data"]["robo"]["table_count"] == 0


@pytest.mark.asyncio
@patch("app.api.schema_navigation.fetch_schema_availability")
async def test_availability_with_datasource_param(mock_fn, ac):
    """datasourceName 쿼리 파라미터가 서비스 함수에 올바르게 전달된다."""
    mock_fn.return_value = SchemaAvailabilityResponse(
        robo={"table_count": 0},
        text2sql={"table_count": 5},
    )
    resp = await ac.get(
        "/api/v3/synapse/schema-nav/availability?datasourceName=erp_db",
        headers=HEADERS,
    )
    assert resp.status_code == 200
    # 서비스 함수가 datasource_name='erp_db'와 tenant_id로 호출되었는지 확인
    mock_fn.assert_called_once_with("erp_db", tenant_id=ANY)


@pytest.mark.asyncio
async def test_availability_no_tenant_401(ac):
    """인증 헤더가 없으면 401을 반환한다."""
    resp = await ac.get("/api/v3/synapse/schema-nav/availability")
    assert resp.status_code == 401


# ────────────────────────────────────────────────────────
# POST /api/v3/synapse/schema-nav/related-tables
# ────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.api.schema_navigation.fetch_related_tables_unified")
async def test_related_tables_success(mock_fn, ac):
    """유효한 요청 본문으로 관련 테이블 조회가 성공한다."""
    mock_fn.return_value = RelatedTableResponse(
        sourceTable={
            "tableId": "text2sql:erp_db:public:orders",
            "tableName": "orders",
            "schemaName": "public",
            "datasourceName": "erp_db",
        },
        relatedTables=[
            RelatedTableItem(
                tableId="text2sql:erp_db:public:line_items",
                tableName="line_items",
                schemaName="public",
                datasourceName="erp_db",
                relationType="FK_OUT",
                score=1.02,
                fkCount=1,
                hopDistance=1,
                sourceColumns=["order_id"],
                targetColumns=["id"],
            ),
        ],
        meta={
            "mode": "TEXT2SQL",
            "limitApplied": 5,
            "excludedAlreadyLoaded": 0,
            "depthUsed": 1,
        },
    )

    resp = await ac.post(
        "/api/v3/synapse/schema-nav/related-tables",
        json={
            "mode": "TEXT2SQL",
            "tableName": "orders",
            "schemaName": "public",
            "datasourceName": "erp_db",
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]["relatedTables"]) == 1
    assert data["data"]["sourceTable"]["tableName"] == "orders"
    # depthUsed가 meta에 포함되어 있는지 확인
    assert data["data"]["meta"]["depthUsed"] == 1


@pytest.mark.asyncio
@patch("app.api.schema_navigation.fetch_related_tables_unified")
async def test_related_tables_response_aliases(mock_fn, ac):
    """응답 JSON 키가 camelCase인지 확인한다 (tableId, tableName 등)."""
    mock_fn.return_value = RelatedTableResponse(
        sourceTable={
            "tableId": "robo::public:orders",
            "tableName": "orders",
            "schemaName": "public",
            "datasourceName": "",
        },
        relatedTables=[
            RelatedTableItem(
                tableId="robo::public:items",
                tableName="items",
                relationType="FK_OUT",
                score=1.0,
                fkCount=2,
                hopDistance=1,
                sourceColumns=["item_id"],
                targetColumns=["id"],
            ),
        ],
        meta={
            "mode": "ROBO",
            "limitApplied": 5,
            "excludedAlreadyLoaded": 0,
            "depthUsed": 1,
        },
    )

    resp = await ac.post(
        "/api/v3/synapse/schema-nav/related-tables",
        json={"mode": "ROBO", "tableName": "orders"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    # camelCase 키 확인 — 프론트엔드가 기대하는 형식
    item = data["relatedTables"][0]
    assert "tableId" in item
    assert "tableName" in item
    assert "schemaName" in item
    assert "datasourceName" in item
    assert "relationType" in item
    assert "fkCount" in item
    assert "sourceColumns" in item
    assert "targetColumns" in item
    assert "autoAddRecommended" in item
    assert "hopDistance" in item

    # snake_case 키가 없어야 한다
    assert "table_id" not in item
    assert "table_name" not in item
    assert "relation_type" not in item
    assert "hop_distance" not in item

    # meta에 depthUsed가 포함되어야 한다
    assert "depthUsed" in data["meta"]


@pytest.mark.asyncio
@patch("app.api.schema_navigation.fetch_related_tables_unified")
async def test_related_tables_tenant_id_passed(mock_fn, ac):
    """서비스 함수에 tenant_id가 전달되는지 확인한다."""
    mock_fn.return_value = RelatedTableResponse(
        sourceTable={
            "tableId": "robo::public:orders",
            "tableName": "orders",
            "schemaName": "public",
            "datasourceName": "",
        },
        relatedTables=[],
        meta={
            "mode": "ROBO",
            "limitApplied": 5,
            "excludedAlreadyLoaded": 0,
            "depthUsed": 1,
        },
    )

    resp = await ac.post(
        "/api/v3/synapse/schema-nav/related-tables",
        json={"mode": "ROBO", "tableName": "orders"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    # fetch_related_tables_unified가 tenant_id 키워드 인자와 함께 호출되었는지 확인
    mock_fn.assert_called_once_with(ANY, tenant_id=ANY)


@pytest.mark.asyncio
async def test_related_tables_no_tenant_401(ac):
    """인증 헤더가 없으면 401을 반환한다."""
    resp = await ac.post(
        "/api/v3/synapse/schema-nav/related-tables",
        json={"mode": "ROBO", "tableName": "orders"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_related_tables_invalid_mode_422(ac):
    """유효하지 않은 mode 값이면 422 Validation Error를 반환한다."""
    resp = await ac.post(
        "/api/v3/synapse/schema-nav/related-tables",
        json={"mode": "INVALID", "tableName": "orders"},
        headers=HEADERS,
    )
    assert resp.status_code == 422
