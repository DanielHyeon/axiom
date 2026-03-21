"""What-if 위자드 API 엔드포인트 단위 테스트.

대상 모듈: app.api.whatif_wizard
FastAPI TestClient로 라우터 엔드포인트를 검증한다.
인증 미들웨어를 모킹하여 외부 의존성 없이 실행 가능.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.api.whatif_wizard import router


# ──────────────────────────────────────────────
# 테스트 픽스처
# ──────────────────────────────────────────────

def _make_fake_state():
    """인증 미들웨어가 설정하는 request.state를 모방한다."""
    state = MagicMock()
    state.tenant_id = "test-tenant-001"
    state.user_id = "test-user"
    state.project_id = "proj-001"
    state.roles = ["admin"]
    return state


class FakeAuthMiddleware(BaseHTTPMiddleware):
    """인증 미들웨어 대리 -- request.state에 tenant_id를 주입한다."""

    async def dispatch(self, request: Request, call_next):
        state = _make_fake_state()
        for attr in ("tenant_id", "user_id", "project_id", "roles"):
            setattr(request.state, attr, getattr(state, attr))
        return await call_next(request)


@pytest.fixture()
def client():
    """whatif_wizard 라우터만 포함한 테스트 앱을 생성한다."""
    app = FastAPI()
    app.include_router(router)
    app.add_middleware(FakeAuthMiddleware)
    return TestClient(app)


# ──────────────────────────────────────────────
# 헬퍼: 테스트용 데이터 생성
# ──────────────────────────────────────────────

def _make_correlated_data(n: int = 50, seed: int = 42) -> dict[str, list[float]]:
    """A와 B가 높은 상관관계를 갖는 시계열 데이터를 생성한다."""
    rng = np.random.default_rng(seed)
    a = np.linspace(0, 10, n) + rng.normal(0, 0.1, n)
    b = 2.0 * a + 3.0 + rng.normal(0, 0.1, n)
    c = rng.normal(0, 1, n)
    return {
        "A": a.tolist(),
        "B": b.tolist(),
        "C": c.tolist(),
    }


# ──────────────────────────────────────────────
# Step 1: 엣지 탐색 (/discover-edges)
# ──────────────────────────────────────────────

PREFIX = "/api/v1/vision/whatif-wizard"


class TestDiscoverEdgesAPI:
    """POST /discover-edges 엔드포인트를 검증한다."""

    def test_엣지_탐색_기본(self, client: TestClient):
        """상관관계가 높은 데이터로 엣지가 반환되어야 한다."""
        data = _make_correlated_data(n=50)
        resp = client.post(f"{PREFIX}/discover-edges", json={
            "data": data,
            "methods": ["pearson"],
            "threshold": 0.3,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["count"] > 0
        # A-B 또는 B-A 엣지가 존재해야 함
        edge_pairs = {(e["source"], e["target"]) for e in body["data"]["edges"]}
        assert ("A", "B") in edge_pairs or ("B", "A") in edge_pairs

    def test_엣지_탐색_데이터_부족(self, client: TestClient):
        """데이터 포인트가 10개 미만이면 엣지가 발견되지 않아야 한다."""
        short_data = {
            "A": [1.0, 2.0, 3.0],
            "B": [4.0, 5.0, 6.0],
        }
        resp = client.post(f"{PREFIX}/discover-edges", json={
            "data": short_data,
            "methods": ["pearson"],
            "threshold": 0.3,
        })
        assert resp.status_code == 200
        body = resp.json()
        # 데이터가 부족하면 엣지가 0개
        assert body["data"]["count"] == 0

    def test_엣지_탐색_빈_데이터(self, client: TestClient):
        """빈 데이터(변수 1개 미만)로 요청하면 422 에러를 반환해야 한다."""
        resp = client.post(f"{PREFIX}/discover-edges", json={
            "data": {"A": [1.0, 2.0]},
            "methods": ["pearson"],
        })
        assert resp.status_code == 422

    def test_변수_50개_초과_422(self, client: TestClient):
        """변수가 50개를 초과하면 Pydantic 유효성 검사에서 422를 반환해야 한다."""
        # 51개 변수 생성
        data = {f"var_{i}": [1.0, 2.0, 3.0] for i in range(51)}
        resp = client.post(f"{PREFIX}/discover-edges", json={
            "data": data,
            "methods": ["pearson"],
        })
        assert resp.status_code == 422

    def test_데이터_10000개_초과_422(self, client: TestClient):
        """데이터 포인트가 10,000개를 초과하면 422를 반환해야 한다."""
        data = {
            "A": list(range(10_001)),
            "B": list(range(10_001)),
        }
        resp = client.post(f"{PREFIX}/discover-edges", json={
            "data": data,
            "methods": ["pearson"],
        })
        assert resp.status_code == 422


# ──────────────────────────────────────────────
# Step 2: 상관 행렬 (/correlation-matrix)
# ──────────────────────────────────────────────

class TestCorrelationMatrixAPI:
    """POST /correlation-matrix 엔드포인트를 검증한다."""

    def test_상관행렬_기본(self, client: TestClient):
        """정상 데이터로 행렬이 올바른 차원으로 반환되어야 한다."""
        data = _make_correlated_data(n=30)
        resp = client.post(f"{PREFIX}/correlation-matrix", json={
            "data": data,
            "method": "pearson",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        matrix = body["data"]["matrix"]
        variables = body["data"]["variables"]
        # 변수 3개 -> 3x3 행렬
        assert len(variables) == 3
        assert len(matrix) == 3
        assert all(len(row) == 3 for row in matrix)

    def test_상관행렬_대각선_1(self, client: TestClient):
        """상관 행렬의 대각선 값은 1.0이어야 한다."""
        data = _make_correlated_data(n=30)
        resp = client.post(f"{PREFIX}/correlation-matrix", json={
            "data": data,
            "method": "pearson",
        })
        body = resp.json()
        matrix = body["data"]["matrix"]
        for i in range(len(matrix)):
            assert matrix[i][i] == pytest.approx(1.0, abs=1e-6)


# ──────────────────────────────────────────────
# Step 3: DAG 구축 (/build-graph)
# ──────────────────────────────────────────────

class TestBuildGraphAPI:
    """POST /build-graph 엔드포인트를 검증한다."""

    def test_DAG_구축_기본(self, client: TestClient):
        """엣지와 변수 목록으로 그래프가 구축되어야 한다."""
        edges = [
            {"source": "A", "target": "B", "method": "pearson", "confidence": 0.9},
            {"source": "B", "target": "C", "method": "pearson", "confidence": 0.7},
        ]
        variables = ["A", "B", "C"]
        resp = client.post(f"{PREFIX}/build-graph", json={
            "edges": edges,
            "variables": variables,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        graph = body["data"]
        # 모든 변수가 그래프에 포함되어야 함
        assert set(graph.keys()) == {"A", "B", "C"}
        # A는 부모 없음 (루트), B의 부모는 A, C의 부모는 B
        assert graph["A"]["parents"] == []
        assert "A" in graph["B"]["parents"]
        assert "B" in graph["C"]["parents"]


# ──────────────────────────────────────────────
# Step 6: 시뮬레이션 (/simulate)
# ──────────────────────────────────────────────

class TestSimulateAPI:
    """POST /simulate 엔드포인트를 검증한다."""

    def test_시뮬레이션_개입_전파(self, client: TestClient):
        """개입 변수의 값이 결과에 보존되어야 한다."""
        # A -> B 단순 그래프 (B = 2*A + 1)
        graph = {
            "A": {"parents": [], "is_trained": True, "coefficients": {}, "intercept": 0.0},
            "B": {
                "parents": ["A"],
                "is_trained": True,
                "coefficients": {"A": 2.0},
                "intercept": 1.0,
            },
        }
        baseline = {"A": 5.0, "B": 11.0}
        interventions = {"A": 10.0}

        resp = client.post(f"{PREFIX}/simulate", json={
            "graph": graph,
            "baseline": baseline,
            "interventions": interventions,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        results = body["data"]["results"]
        # 개입 변수 A의 값이 보존됨
        assert results["A"] == 10.0
        # B = 2*10 + 1 = 21.0
        assert results["B"] == pytest.approx(21.0, abs=1e-4)
        # deltas 확인
        assert body["data"]["deltas"]["A"] == pytest.approx(5.0, abs=1e-4)

    def test_빈_측정값_시뮬레이션(self, client: TestClient):
        """빈 그래프에 개입하면 결과도 빈 상태여야 한다 (에러 없이)."""
        # 그래프가 비어있지만 interventions는 존재
        graph = {}
        baseline = {}
        interventions = {"X": 1.0}

        resp = client.post(f"{PREFIX}/simulate", json={
            "graph": graph,
            "baseline": baseline,
            "interventions": interventions,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        # X에 대한 개입값만 결과에 포함
        assert body["data"]["results"]["X"] == 1.0


# ──────────────────────────────────────────────
# Step 7: 시나리오 비교 (/compare)
# ──────────────────────────────────────────────

class TestCompareAPI:
    """POST /compare 엔드포인트를 검증한다."""

    def test_시나리오_비교_기본(self, client: TestClient):
        """2개 시나리오를 비교하면 delta 정보가 반환되어야 한다."""
        scenarios = [
            {
                "id": "s1", "name": "시나리오1",
                "results": {"A": 10.0, "B": 20.0},
                "baseline": {"A": 5.0, "B": 15.0},
            },
            {
                "id": "s2", "name": "시나리오2",
                "results": {"A": 8.0, "B": 25.0},
                "baseline": {"A": 5.0, "B": 15.0},
            },
        ]
        resp = client.post(f"{PREFIX}/compare", json={"scenarios": scenarios})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["scenario_count"] == 2
        # comparison에 A, B 변수가 포함됨
        assert "A" in data["comparison"]
        assert "B" in data["comparison"]
        # max_impact_variable이 설정되어야 함
        assert data["max_impact_variable"] != ""

    def test_시나리오_비교_1개_에러(self, client: TestClient):
        """시나리오가 1개만 전달되면 422 유효성 검사 에러를 반환해야 한다."""
        scenarios = [
            {
                "id": "s1", "name": "시나리오1",
                "results": {"A": 10.0},
                "baseline": {"A": 5.0},
            },
        ]
        resp = client.post(f"{PREFIX}/compare", json={"scenarios": scenarios})
        # CompareRequest.scenarios의 min_length=2 제약에 의해 422
        assert resp.status_code == 422
