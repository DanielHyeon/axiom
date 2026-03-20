"""
인과 분석 API 통합 테스트.

FastAPI TestClient를 사용하여 엔드포인트를 검증한다:
- POST /api/v3/cases/{case_id}/causal — 분석 실행 (202)
- GET /api/v3/cases/{case_id}/causal/{id}/status — 상태 조회
- GET /api/v3/cases/{case_id}/causal/{id}/edges — 엣지 목록
- GET /api/v3/cases/{case_id}/causal/{id}/graph — 그래프 데이터
- GET /api/v3/cases/{case_id}/causal/latest — 최신 결과
- GET /api/v3/cases/{case_id}/causal — 이력 목록
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.vision_runtime import vision_runtime


CASE_ID = "test-case-001"
BASE_URL = f"/api/v3/cases/{CASE_ID}/causal"
AUTH_HEADER = {"Authorization": "admin_token"}
VIEWER_HEADER = {"Authorization": "viewer_token"}


@pytest.fixture(autouse=True)
def clear_runtime():
    """테스트마다 런타임 상태 초기화."""
    vision_runtime.causal_results_by_case.clear()
    yield
    vision_runtime.causal_results_by_case.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _seed_completed_analysis(case_id: str = CASE_ID) -> str:
    """완료된 인과 분석 결과를 직접 삽입 (API 테스트용)."""
    analysis_id = "causal-test-001"
    vision_runtime.causal_results_by_case.setdefault(case_id, {})[analysis_id] = {
        "analysis_id": analysis_id,
        "case_id": case_id,
        "target_node_id": "kpi-oee",
        "target_field": "value",
        "status": "COMPLETED",
        "started_at": "2026-03-20T09:00:00+00:00",
        "completed_at": "2026-03-20T09:00:30+00:00",
        "requested_by": "test-user",
        "edges": [
            {
                "source": "msr-availability",
                "target": "kpi-oee",
                "method": "decomposition",
                "strength": 0.45,
                "p_value": 0.0,
                "lag": 0,
                "direction": "positive",
            },
            {
                "source": "msr-performance",
                "target": "kpi-oee",
                "method": "decomposition",
                "strength": 0.35,
                "p_value": 0.0,
                "lag": 0,
                "direction": "positive",
            },
        ],
        "impact_scores": {"msr-availability": 1.0, "msr-performance": 0.7778},
        "metadata": {},
        "error": None,
    }
    return analysis_id


def _seed_running_analysis(case_id: str = CASE_ID) -> str:
    """실행 중인 인과 분석 결과를 직접 삽입."""
    analysis_id = "causal-running-001"
    vision_runtime.causal_results_by_case.setdefault(case_id, {})[analysis_id] = {
        "analysis_id": analysis_id,
        "case_id": case_id,
        "target_node_id": "kpi-oee",
        "target_field": "value",
        "status": "RUNNING",
        "started_at": "2026-03-20T09:00:00+00:00",
        "completed_at": None,
        "requested_by": "test-user",
        "edges": [],
        "impact_scores": {},
        "metadata": {},
        "error": None,
    }
    return analysis_id


class TestRunCausalAnalysis:
    """POST /api/v3/cases/{case_id}/causal 테스트."""

    def test_returns_202(self, client: TestClient) -> None:
        """분석 요청이 202를 반환하는지 확인."""
        # run_causal_analysis가 백그라운드 태스크를 스케줄하므로 모킹
        async def mock_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "analysis_id": "causal-mock-001",
                "status": "RUNNING",
            }

        with patch.object(vision_runtime, "run_causal_analysis", side_effect=mock_run):
            resp = client.post(
                BASE_URL,
                json={"target_node_id": "kpi-oee", "target_field": "value"},
                headers=AUTH_HEADER,
            )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "RUNNING"
        assert "analysis_id" in data
        assert "poll_url" in data

    def test_with_optional_params(self, client: TestClient) -> None:
        """선택 파라미터 (max_lag, significance_level) 전달."""
        async def mock_run(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {"analysis_id": "causal-mock-002", "status": "RUNNING"}

        with patch.object(vision_runtime, "run_causal_analysis", side_effect=mock_run):
            resp = client.post(
                BASE_URL,
                json={
                    "target_node_id": "kpi-oee",
                    "target_field": "value",
                    "max_lag": 3,
                    "significance_level": 0.01,
                },
                headers=AUTH_HEADER,
            )
        assert resp.status_code == 202

    def test_viewer_forbidden(self, client: TestClient) -> None:
        """viewer 역할은 분석 실행 불가."""
        resp = client.post(
            BASE_URL,
            json={"target_node_id": "kpi-oee", "target_field": "value"},
            headers=VIEWER_HEADER,
        )
        assert resp.status_code == 403

    def test_missing_target_node_id(self, client: TestClient) -> None:
        """필수 필드 누락 시 422."""
        resp = client.post(
            BASE_URL,
            json={"target_field": "value"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 422


class TestGetCausalStatus:
    """GET /api/v3/cases/{case_id}/causal/{id}/status 테스트."""

    def test_completed_status(self, client: TestClient) -> None:
        """완료된 분석의 상태 조회."""
        analysis_id = _seed_completed_analysis()
        resp = client.get(f"{BASE_URL}/{analysis_id}/status", headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["completed_at"] is not None

    def test_running_status(self, client: TestClient) -> None:
        """실행 중인 분석의 상태 조회."""
        analysis_id = _seed_running_analysis()
        resp = client.get(f"{BASE_URL}/{analysis_id}/status", headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "RUNNING"

    def test_not_found(self, client: TestClient) -> None:
        """존재하지 않는 분석 조회 시 404."""
        resp = client.get(f"{BASE_URL}/nonexistent/status", headers=AUTH_HEADER)
        assert resp.status_code == 404


class TestGetCausalEdges:
    """GET /api/v3/cases/{case_id}/causal/{id}/edges 테스트."""

    def test_completed_edges(self, client: TestClient) -> None:
        """완료된 분석의 엣지 목록 조회."""
        analysis_id = _seed_completed_analysis()
        resp = client.get(f"{BASE_URL}/{analysis_id}/edges", headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_edges"] == 2
        assert len(data["edges"]) == 2
        assert "msr-availability" in data["impact_scores"]

    def test_running_edges_409(self, client: TestClient) -> None:
        """실행 중인 분석의 엣지 조회 시 409."""
        analysis_id = _seed_running_analysis()
        resp = client.get(f"{BASE_URL}/{analysis_id}/edges", headers=AUTH_HEADER)
        assert resp.status_code == 409

    def test_viewer_can_read(self, client: TestClient) -> None:
        """viewer 역할도 엣지 조회 가능."""
        analysis_id = _seed_completed_analysis()
        resp = client.get(f"{BASE_URL}/{analysis_id}/edges", headers=VIEWER_HEADER)
        assert resp.status_code == 200


class TestGetCausalGraph:
    """GET /api/v3/cases/{case_id}/causal/{id}/graph 테스트."""

    def test_completed_graph(self, client: TestClient) -> None:
        """완료된 분석의 그래프 데이터 조회."""
        analysis_id = _seed_completed_analysis()
        resp = client.get(f"{BASE_URL}/{analysis_id}/graph", headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()
        assert "edges" in data
        assert "impact_scores" in data
        assert "metadata" in data


class TestGetLatestCausalAnalysis:
    """GET /api/v3/cases/{case_id}/causal/latest 테스트."""

    def test_latest_found(self, client: TestClient) -> None:
        """최신 완료 분석 조회."""
        _seed_completed_analysis()
        resp = client.get(f"{BASE_URL}/latest", headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "COMPLETED"

    def test_no_completed_404(self, client: TestClient) -> None:
        """완료된 분석이 없으면 404."""
        _seed_running_analysis()
        resp = client.get(f"{BASE_URL}/latest", headers=AUTH_HEADER)
        assert resp.status_code == 404


class TestListCausalAnalyses:
    """GET /api/v3/cases/{case_id}/causal 테스트."""

    def test_empty_list(self, client: TestClient) -> None:
        """빈 이력 목록."""
        resp = client.get(BASE_URL, headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["data"] == []

    def test_list_with_analyses(self, client: TestClient) -> None:
        """분석이 있는 이력 목록."""
        _seed_completed_analysis()
        _seed_running_analysis()
        resp = client.get(BASE_URL, headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
