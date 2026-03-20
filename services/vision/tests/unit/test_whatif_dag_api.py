"""
What-if DAG API 통합 테스트
============================

FastAPI TestClient를 사용하여 /api/v3/cases/{case_id}/whatif-dag/* 엔드포인트를 검증.

Synapse API 호출은 모킹하여 외부 의존성 없이 테스트.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ── 테스트용 모킹 데이터 ──

MOCK_MODEL_GRAPH = {
    "models": [
        {"id": "model_defect", "name": "불량률 예측", "status": "trained", "modelType": "RandomForest"},
    ],
    "reads": [
        {"modelId": "model_defect", "sourceNodeId": "node_costs", "field": "cost_index", "lag": 0, "featureName": "cost_index"},
    ],
    "predicts": [
        {"modelId": "model_defect", "targetNodeId": "node_quality", "field": "defect_rate", "confidence": 0.85},
    ],
}

MOCK_BASELINE = {
    "node_costs::cost_index": 100.0,
    "node_quality::defect_rate": 3.2,
}


# ── Synapse 모킹 헬퍼 ──

def _mock_fetcher_get_model_graph():
    """ModelGraphFetcher.get_model_graph를 모킹."""
    return patch(
        "app.api.whatif_dag._fetcher.get_model_graph",
        new_callable=AsyncMock,
        return_value=MOCK_MODEL_GRAPH,
    )


def _mock_fetcher_get_baseline():
    """ModelGraphFetcher.get_baseline_snapshot를 모킹."""
    return patch(
        "app.api.whatif_dag._fetcher.get_baseline_snapshot",
        new_callable=AsyncMock,
        return_value=MOCK_BASELINE,
    )


# ── API 테스트 ──

class TestSimulateEndpoint:
    """POST /api/v3/cases/{case_id}/whatif-dag/simulate 테스트."""

    @pytest.mark.asyncio
    async def test_simulate_success(self):
        """정상 시뮬레이션 실행."""
        with _mock_fetcher_get_model_graph(), _mock_fetcher_get_baseline():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v3/cases/case1/whatif-dag/simulate",
                    json={
                        "scenario_name": "원가 인상",
                        "interventions": [
                            {"nodeId": "node_costs", "field": "cost_index", "value": 150.0, "description": "50% 인상"},
                        ],
                    },
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["scenario_name"] == "원가 인상"
        assert "traces" in data
        assert "timeline" in data
        assert "final_state" in data
        assert "deltas" in data
        assert "converged" in data

    @pytest.mark.asyncio
    async def test_simulate_with_baseline_data(self):
        """baseline_data를 직접 제공."""
        with _mock_fetcher_get_model_graph():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v3/cases/case1/whatif-dag/simulate",
                    json={
                        "scenario_name": "테스트",
                        "interventions": [
                            {"nodeId": "n1", "field": "f1", "value": 100.0},
                        ],
                        "baseline_data": {"n1::f1": 50.0},
                    },
                )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_simulate_empty_interventions(self):
        """개입이 비어있으면 422 에러."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v3/cases/case1/whatif-dag/simulate",
                json={
                    "scenario_name": "빈 개입",
                    "interventions": [],
                },
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_simulate_model_graph_fetch_failure(self):
        """Synapse 통신 실패 시 502."""
        from app.services.model_graph_fetcher import ModelGraphFetchError

        with patch(
            "app.api.whatif_dag._fetcher.get_model_graph",
            new_callable=AsyncMock,
            side_effect=ModelGraphFetchError("connection refused"),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v3/cases/case1/whatif-dag/simulate",
                    json={
                        "interventions": [{"nodeId": "n1", "field": "f1", "value": 1.0}],
                    },
                )
        assert resp.status_code == 502
        assert "MODEL_GRAPH_FETCH_FAILED" in resp.json()["detail"]["code"]


class TestCompareEndpoint:
    """POST /api/v3/cases/{case_id}/whatif-dag/compare 테스트."""

    @pytest.mark.asyncio
    async def test_compare_two_scenarios(self):
        """2개 시나리오 비교."""
        with _mock_fetcher_get_model_graph(), _mock_fetcher_get_baseline():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v3/cases/case1/whatif-dag/compare",
                    json={
                        "scenarios": [
                            {
                                "name": "시나리오A",
                                "interventions": [{"nodeId": "node_costs", "field": "cost_index", "value": 120.0}],
                            },
                            {
                                "name": "시나리오B",
                                "interventions": [{"nodeId": "node_costs", "field": "cost_index", "value": 180.0}],
                            },
                        ],
                    },
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["scenarios"]) == 2
        assert "comparison" in data

    @pytest.mark.asyncio
    async def test_compare_single_scenario_rejected(self):
        """1개 시나리오만 제공하면 422."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v3/cases/case1/whatif-dag/compare",
                json={
                    "scenarios": [
                        {"name": "하나만", "interventions": [{"nodeId": "n", "field": "f", "value": 1.0}]},
                    ],
                },
            )
        assert resp.status_code == 422


class TestSnapshotEndpoint:
    """GET /api/v3/cases/{case_id}/whatif-dag/snapshot 테스트."""

    @pytest.mark.asyncio
    async def test_snapshot_success(self):
        """스냅샷 조회."""
        with _mock_fetcher_get_baseline():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/v3/cases/case1/whatif-dag/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["variable_count"] == 2


class TestModelsEndpoint:
    """GET /api/v3/cases/{case_id}/whatif-dag/models 테스트."""

    @pytest.mark.asyncio
    async def test_list_models(self):
        """시뮬레이션 가능 모델 목록 조회."""
        with _mock_fetcher_get_model_graph():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/v3/cases/case1/whatif-dag/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total"] == 1
        assert data["models"][0]["name"] == "불량률 예측"
        assert data["models"][0]["input_count"] == 1
        assert data["models"][0]["output"]["target_field"] == "defect_rate"
