"""P0-3 Insight 온톨로지 API 유닛 테스트.

테스트 대상:
  - GET  /api/insight/ontology/kpis
  - GET  /api/insight/ontology/drivers
  - GET  /api/insight/nodes/{node_id}
  - POST /api/insight/logs:auto-ingest
  - GET  /api/insight/schema-coverage/datasource

모든 외부 의존성(Synapse, DB, Redis)을 모킹하여 순수 로직만 검증한다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── JWT 헬퍼 — 테스트용 토큰 생성 ────────────────────────────

def _make_jwt(tenant_id: str = "t1", user_id: str = "u1", role: str = "admin") -> str:
    """테스트용 JWT 토큰을 생성한다."""
    import jwt as pyjwt
    payload = {"sub": user_id, "tenant_id": tenant_id, "role": role}
    return pyjwt.encode(payload, "axiom-dev-secret-key-do-not-use-in-production", algorithm="HS256")


def _auth_headers(tenant_id: str = "t1") -> dict[str, str]:
    """인증 헤더를 반환한다."""
    token = _make_jwt(tenant_id=tenant_id)
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}


# ── 테스트 앱 fixture ─────────────────────────────────────────

@pytest.fixture
def client():
    """TestClient를 생성한다. startup 이벤트를 건너뛰기 위해 직접 임포트."""
    from app.api.insight_ontology import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ═══════════════════════════════════════════════════════════════
# 1. GET /api/insight/ontology/kpis
# ═══════════════════════════════════════════════════════════════


class TestOntologyKpis:
    """온톨로지 KPI 목록 조회 테스트."""

    @patch("app.api.insight_ontology.synapse_ontology_client")
    def test_returns_kpi_list_from_synapse(self, mock_client, client):
        """Synapse에서 KPI 노드를 정상적으로 가져오면 변환된 목록을 반환한다."""
        mock_client.fetch_kpi_nodes = AsyncMock(return_value=[
            {
                "id": "kpi-oee",
                "name": "OEE",
                "label": "OEE",
                "properties": {
                    "description": "Overall Equipment Effectiveness",
                    "unit": "%",
                    "current_value": 85.2,
                },
            },
            {
                "id": "kpi-throughput",
                "name": "Throughput Rate",
                "properties": {
                    "description": "시간당 처리량",
                    "unit": "units/hr",
                },
            },
        ])

        resp = client.get(
            "/api/insight/ontology/kpis?case_id=case-1",
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["source"] == "ontology"
        assert len(data["kpis"]) == 2

        # 첫 번째 KPI 검증
        kpi0 = data["kpis"][0]
        assert kpi0["id"] == "kpi-oee"
        assert kpi0["name"] == "OEE"
        assert kpi0["description"] == "Overall Equipment Effectiveness"
        assert kpi0["unit"] == "%"
        assert kpi0["current_value"] == 85.2
        assert kpi0["source"] == "ontology"
        assert kpi0["primary"] is True

    @patch("app.api.insight_ontology.synapse_ontology_client")
    def test_returns_empty_when_synapse_fails(self, mock_client, client):
        """Synapse 연결 실패 시 빈 목록을 반환한다 (graceful degradation)."""
        mock_client.fetch_kpi_nodes = AsyncMock(return_value=[])

        resp = client.get(
            "/api/insight/ontology/kpis?case_id=case-1",
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["kpis"] == []

    def test_requires_case_id(self, client):
        """case_id 파라미터가 없으면 422를 반환한다."""
        resp = client.get(
            "/api/insight/ontology/kpis",
            headers=_auth_headers(),
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════
# 2. GET /api/insight/ontology/drivers
# ═══════════════════════════════════════════════════════════════


class TestOntologyDrivers:
    """온톨로지 Driver(원인) 노드 목록 조회 테스트."""

    @patch("app.api.insight_ontology.synapse_ontology_client")
    def test_returns_causal_drivers(self, mock_client, client):
        """인과 관계(CAUSES, INFLUENCES)로 연결된 이웃만 반환한다."""
        mock_client.fetch_node_neighbors_full = AsyncMock(return_value={
            "nodes": [
                {"id": "measure-avail", "name": "Availability", "layer": "measure"},
                {"id": "measure-perf", "name": "Performance", "layer": "measure"},
                {"id": "unrelated-node", "name": "SomeProcess", "layer": "process"},
            ],
            "relations": [
                {"source": "kpi-oee", "target": "measure-avail", "type": "CAUSES", "weight": 0.8},
                {"source": "kpi-oee", "target": "measure-perf", "type": "INFLUENCES", "weight": 0.6},
                {"source": "kpi-oee", "target": "unrelated-node", "type": "PRECEDES"},
            ],
        })

        resp = client.get(
            "/api/insight/ontology/drivers?kpi_id=kpi-oee",
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        data = resp.json()
        # PRECEDES는 인과 관계가 아니므로 필터됨
        assert data["total"] == 2
        assert data["drivers"][0]["id"] == "measure-avail"  # weight 0.8이 더 높으므로 먼저
        assert data["drivers"][0]["weight"] == 0.8
        assert data["drivers"][1]["id"] == "measure-perf"

    @patch("app.api.insight_ontology.synapse_ontology_client")
    def test_includes_all_when_no_relation_type(self, mock_client, client):
        """관계 타입이 없으면 모든 이웃을 포함한다."""
        mock_client.fetch_node_neighbors_full = AsyncMock(return_value={
            "nodes": [
                {"id": "n1", "name": "Node1", "layer": "measure"},
            ],
            "relations": [],
        })

        resp = client.get(
            "/api/insight/ontology/drivers?kpi_id=kpi-1",
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_requires_kpi_id(self, client):
        """kpi_id 파라미터가 없으면 422를 반환한다."""
        resp = client.get(
            "/api/insight/ontology/drivers",
            headers=_auth_headers(),
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════
# 3. GET /api/insight/nodes/{node_id}
# ═══════════════════════════════════════════════════════════════


class TestNodeDetail:
    """노드 상세 정보 조회 테스트."""

    @patch("app.api.insight_ontology.synapse_ontology_client")
    def test_returns_node_with_neighbors(self, mock_client, client):
        """노드 상세 + 이웃 + 관계를 정상적으로 반환한다."""
        mock_client.fetch_node_detail = AsyncMock(return_value={
            "id": "kpi-oee",
            "name": "OEE",
            "layer": "kpi",
            "properties": {"unit": "%", "description": "Overall Equipment Effectiveness"},
        })
        mock_client.fetch_node_neighbors_full = AsyncMock(return_value={
            "nodes": [
                {"id": "m1", "name": "Availability", "layer": "measure"},
            ],
            "relations": [
                {"source": "kpi-oee", "target": "m1", "type": "DERIVED_FROM", "weight": 0.9},
            ],
        })

        resp = client.get(
            "/api/insight/nodes/kpi-oee",
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["node"]["id"] == "kpi-oee"
        assert data["node"]["name"] == "OEE"
        assert data["node"]["layer"] == "kpi"
        assert len(data["neighbors"]) == 1
        assert data["neighbors"][0]["id"] == "m1"
        assert len(data["relations"]) == 1
        assert data["relations"][0]["type"] == "DERIVED_FROM"
        assert data["relations"][0]["weight"] == 0.9

    @patch("app.api.insight_ontology.synapse_ontology_client")
    def test_returns_404_when_node_not_found(self, mock_client, client):
        """노드가 존재하지 않으면 404를 반환한다."""
        mock_client.fetch_node_detail = AsyncMock(return_value=None)

        resp = client.get(
            "/api/insight/nodes/nonexistent",
            headers=_auth_headers(),
        )

        assert resp.status_code == 404

    @patch("app.api.insight_ontology.synapse_ontology_client")
    def test_empty_neighbors(self, mock_client, client):
        """이웃이 없는 노드도 정상 반환한다."""
        mock_client.fetch_node_detail = AsyncMock(return_value={
            "id": "isolated-node",
            "name": "Isolated",
            "layer": "resource",
            "properties": {},
        })
        mock_client.fetch_node_neighbors_full = AsyncMock(return_value={
            "nodes": [],
            "relations": [],
        })

        resp = client.get(
            "/api/insight/nodes/isolated-node",
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["node"]["id"] == "isolated-node"
        assert data["neighbors"] == []
        assert data["relations"] == []


# ═══════════════════════════════════════════════════════════════
# 4. POST /api/insight/logs:auto-ingest
# ═══════════════════════════════════════════════════════════════


class TestAutoIngest:
    """Oracle 자동 수집 엔드포인트 테스트."""

    @patch("app.api.insight_ontology.get_effective_tenant_id", return_value="t1")
    def test_requires_sql_field(self, mock_tenant, client):
        """sql 필드가 없으면 422를 반환한다."""
        resp = client.post(
            "/api/insight/logs:auto-ingest",
            json={"datasource_id": "ds1"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    @patch("app.api.insight_ontology.get_effective_tenant_id", return_value="t1")
    def test_requires_datasource_id(self, mock_tenant, client):
        """datasource_id 필드가 없으면 422를 반환한다."""
        resp = client.post(
            "/api/insight/logs:auto-ingest",
            json={"sql": "SELECT 1"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════
# 5. GET /api/insight/schema-coverage/datasource
# ═══════════════════════════════════════════════════════════════


class TestSchemaCoverageDatasource:
    """데이터소스 기반 스키마 커버리지 테스트."""

    @patch("app.api.insight_ontology.synapse_ontology_client")
    @patch("app.services.weaver_runtime.weaver_runtime")
    def test_coverage_with_catalog(self, mock_runtime, mock_synapse, client):
        """카탈로그가 있고 온톨로지 매핑이 일부 있을 때 커버리지를 정확히 계산한다."""
        # weaver_runtime.catalogs 모킹
        mock_catalog = {
            "public": {
                "orders": [{"name": "id"}, {"name": "amount"}],
                "customers": [{"name": "id"}, {"name": "name"}],
                "products": [{"name": "id"}],
            }
        }
        mock_runtime.catalogs = {"ds-test": mock_catalog}

        mock_synapse._get = AsyncMock(return_value={
            "data": {
                "nodes": [
                    {"id": "n1", "type": "TABLE", "name": "orders", "properties": {"table_name": "orders"}},
                    {"id": "n2", "type": "TABLE", "name": "customers", "properties": {"table_name": "customers"}},
                    {"id": "n3", "type": "COLUMN", "name": "amount", "layer": "column", "properties": {}},
                ],
            },
        })

        resp = client.get(
            "/api/insight/schema-coverage/datasource?datasource_id=ds-test&case_id=case-1",
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["datasource_id"] == "ds-test"
        assert data["total_tables"] == 3
        assert data["mapped_tables"] == 2  # orders, customers
        # 2/3 = 66.7%
        assert data["coverage_pct"] == 66.7
        assert len(data["unmapped_tables"]) == 1
        assert data["unmapped_tables"][0]["table_name"] == "products"

    @patch("app.api.insight_ontology.synapse_ontology_client")
    @patch("app.services.weaver_runtime.weaver_runtime")
    def test_zero_coverage_without_case_id(self, mock_runtime, mock_synapse, client):
        """case_id가 없으면 온톨로지 매핑 없이 0% 커버리지를 반환한다."""
        mock_catalog = {
            "public": {
                "orders": [{"name": "id"}],
            }
        }
        mock_runtime.catalogs = {"ds-test": mock_catalog}

        resp = client.get(
            "/api/insight/schema-coverage/datasource?datasource_id=ds-test",
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["coverage_pct"] == 0.0
        assert data["total_tables"] == 1
        assert data["mapped_tables"] == 0

    def test_requires_datasource_id(self, client):
        """datasource_id 파라미터가 없으면 422를 반환한다."""
        resp = client.get(
            "/api/insight/schema-coverage/datasource",
            headers=_auth_headers(),
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════
# 6. SynapseOntologyClient 단위 테스트
# ═══════════════════════════════════════════════════════════════


class TestSynapseOntologyClient:
    """SynapseOntologyClient HTTP 호출 로직 테스트."""

    @pytest.mark.asyncio
    async def test_fetch_kpi_nodes_graceful_on_failure(self):
        """Synapse 연결 실패 시 빈 목록을 반환한다."""
        from app.services.synapse_ontology_client import SynapseOntologyClient

        client = SynapseOntologyClient()
        # 존재하지 않는 URL로 설정 → 연결 실패
        client._base_url = "http://127.0.0.1:1"

        result = await client.fetch_kpi_nodes(case_id="test", tenant_id="t1")
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_node_detail_graceful_on_failure(self):
        """Synapse 연결 실패 시 None을 반환한다."""
        from app.services.synapse_ontology_client import SynapseOntologyClient

        client = SynapseOntologyClient()
        client._base_url = "http://127.0.0.1:1"

        result = await client.fetch_node_detail(node_id="test", tenant_id="t1")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_node_neighbors_full_graceful_on_failure(self):
        """Synapse 연결 실패 시 빈 dict를 반환한다."""
        from app.services.synapse_ontology_client import SynapseOntologyClient

        client = SynapseOntologyClient()
        client._base_url = "http://127.0.0.1:1"

        result = await client.fetch_node_neighbors_full(node_id="test", tenant_id="t1")
        assert result == {"nodes": [], "relations": []}


# ═══════════════════════════════════════════════════════════════
# 7. _safe_float 헬퍼 테스트
# ═══════════════════════════════════════════════════════════════


class TestSafeFloat:
    """_safe_float 헬퍼 함수 테스트."""

    def test_none_returns_none(self):
        from app.api.insight_ontology import _safe_float
        assert _safe_float(None) is None

    def test_valid_float(self):
        from app.api.insight_ontology import _safe_float
        assert _safe_float(3.14) == 3.14

    def test_int_to_float(self):
        from app.api.insight_ontology import _safe_float
        assert _safe_float(42) == 42.0

    def test_string_float(self):
        from app.api.insight_ontology import _safe_float
        assert _safe_float("0.75") == 0.75

    def test_invalid_string_returns_none(self):
        from app.api.insight_ontology import _safe_float
        assert _safe_float("not-a-number") is None

    def test_empty_string_returns_none(self):
        from app.api.insight_ontology import _safe_float
        assert _safe_float("") is None
