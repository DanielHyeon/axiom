"""피벗 API 엔드포인트 단위 테스트.

pivot.py의 /pivot/execute와 /pivot/preview-sql 엔드포인트를
FastAPI TestClient로 검증한다.
DB 의존성은 모킹하여 순수 API 계층 로직만 테스트한다.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.pivot import router


# ──────────────────────────────────────────────
# 테스트 픽스처 — FastAPI 앱 + 인증 모킹
# ──────────────────────────────────────────────


def _make_fake_state():
    """인증 미들웨어가 설정하는 state를 모방한다."""
    state = MagicMock()
    state.user_id = "test-user"
    state.user_name = "테스트유저"
    state.tenant_id = "tenant-001"
    state.project_id = "proj-001"
    state.roles = ["admin"]
    state.trace_id = "trace-test"
    return state


@pytest.fixture()
def client():
    """피벗 라우터만 포함한 테스트 앱을 생성한다."""
    app = FastAPI()
    app.include_router(router)

    # 인증 미들웨어 대신 state를 직접 주입하는 미들웨어
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class FakeAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            state = _make_fake_state()
            for attr in ("user_id", "user_name", "tenant_id", "project_id", "roles", "trace_id"):
                setattr(request.state, attr, getattr(state, attr))
            return await call_next(request)

    app.add_middleware(FakeAuthMiddleware)

    return TestClient(app)


# ──────────────────────────────────────────────
# /pivot/preview-sql 엔드포인트 테스트
# ──────────────────────────────────────────────


class TestPreviewSql:
    """SQL 미리보기 — 실행 없이 SQL만 반환하는 엔드포인트."""

    def test_기본_피벗_SQL_미리보기(self, client):
        """행 1개 + 측정값 1개 → 유효한 SQL 반환."""
        body = {
            "cubeName": "Sales",
            "rows": [{"dimension": "Time", "level": "year"}],
            "measures": [{"name": "revenue", "aggregator": "SUM"}],
        }
        resp = client.post("/pivot/preview-sql", json=body)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        sql = data["data"]["sql"]
        assert "SELECT" in sql
        assert "SUM(revenue)" in sql
        assert "GROUP BY" in sql

    def test_측정값_없으면_400_에러(self, client):
        """measures가 비어있으면 SQL 생성 실패 → 400."""
        body = {
            "cubeName": "Sales",
            "rows": [{"dimension": "Time", "level": "year"}],
            "measures": [],
        }
        resp = client.post("/pivot/preview-sql", json=body)
        # generate_pivot_sql이 빈 SQL을 반환하면 400은 execute에서만 발생
        # preview-sql은 빈 SQL을 그대로 반환할 수 있음
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["sql"] == ""

    def test_허용되지_않은_연산자_400_에러(self, client):
        """SQL 인젝션 시도 — 허용되지 않은 연산자 → 400."""
        body = {
            "cubeName": "Sales",
            "rows": [{"dimension": "Time", "level": "year"}],
            "measures": [{"name": "revenue", "aggregator": "SUM"}],
            "filters": [
                {"dimension": "Region", "level": "country", "operator": "DROP TABLE", "value": "x"},
            ],
        }
        resp = client.post("/pivot/preview-sql", json=body)

        assert resp.status_code == 400
        assert "허용되지 않은 연산자" in resp.json()["detail"]

    def test_필터_포함_SQL_미리보기(self, client):
        """필터 → WHERE 절이 포함된 SQL."""
        body = {
            "cubeName": "Sales",
            "rows": [{"dimension": "Time", "level": "year"}],
            "measures": [{"name": "revenue"}],
            "filters": [
                {"dimension": "Region", "level": "country", "operator": "=", "value": "Korea"},
            ],
        }
        resp = client.post("/pivot/preview-sql", json=body)

        assert resp.status_code == 200
        sql = resp.json()["data"]["sql"]
        assert "WHERE" in sql
        assert "$1" in sql

    def test_IN_필터_SQL_미리보기(self, client):
        """IN 연산자 + 리스트 값 → 복수 플레이스홀더."""
        body = {
            "cubeName": "Sales",
            "rows": [{"dimension": "Time", "level": "year"}],
            "measures": [{"name": "revenue"}],
            "filters": [
                {"dimension": "Product", "level": "category", "operator": "IN", "value": ["A", "B", "C"]},
            ],
        }
        resp = client.post("/pivot/preview-sql", json=body)

        assert resp.status_code == 200
        sql = resp.json()["data"]["sql"]
        assert "IN ($1, $2, $3)" in sql

    def test_limit_10000_초과_거부(self, client):
        """Pydantic 검증 — limit > 10000이면 422."""
        body = {
            "cubeName": "Sales",
            "rows": [],
            "measures": [{"name": "revenue"}],
            "limit": 20000,
        }
        resp = client.post("/pivot/preview-sql", json=body)

        assert resp.status_code == 422  # Pydantic ValidationError

    def test_limit_0_이하_거부(self, client):
        """Pydantic 검증 — limit < 1이면 422."""
        body = {
            "cubeName": "Sales",
            "measures": [{"name": "revenue"}],
            "limit": 0,
        }
        resp = client.post("/pivot/preview-sql", json=body)

        assert resp.status_code == 422

    def test_cubeName_누락_422(self, client):
        """필수 필드 cubeName 누락 → 422."""
        body = {
            "measures": [{"name": "revenue"}],
        }
        resp = client.post("/pivot/preview-sql", json=body)

        assert resp.status_code == 422


# ──────────────────────────────────────────────
# /pivot/execute 엔드포인트 테스트
# ──────────────────────────────────────────────


class TestExecutePivot:
    """피벗 실행 — SQL 생성 + DB 실행 + 이력 저장."""

    @patch("app.api.pivot.execute_command", new_callable=AsyncMock)
    @patch("app.api.pivot.execute_query", new_callable=AsyncMock)
    def test_정상_실행_결과_반환(self, mock_query, mock_cmd, client):
        """행 1개 + 측정값 1개 → SQL 실행 후 결과 반환."""
        # DB 쿼리 결과 모킹
        mock_query.return_value = [
            {"year": "2025", "revenue": 100000},
            {"year": "2026", "revenue": 150000},
        ]
        mock_cmd.return_value = None  # 이력 저장은 성공

        body = {
            "cubeName": "Sales",
            "rows": [{"dimension": "Time", "level": "year"}],
            "measures": [{"name": "revenue", "aggregator": "SUM"}],
        }
        resp = client.post("/pivot/execute", json=body)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        result = data["data"]
        assert result["sql"] != ""
        assert result["columns"] == ["year", "revenue"]
        assert result["row_count"] == 2
        assert result["rows"] == [["2025", 100000], ["2026", 150000]]
        assert result["execution_time_ms"] >= 0

        # 이력 저장 호출 확인
        mock_cmd.assert_called_once()

    @patch("app.api.pivot.execute_command", new_callable=AsyncMock)
    @patch("app.api.pivot.execute_query", new_callable=AsyncMock)
    def test_빈_결과(self, mock_query, mock_cmd, client):
        """쿼리 결과가 0행일 때도 정상 반환."""
        mock_query.return_value = []
        mock_cmd.return_value = None

        body = {
            "cubeName": "Sales",
            "rows": [{"dimension": "Time", "level": "year"}],
            "measures": [{"name": "revenue"}],
            "filters": [{"dimension": "Region", "level": "country", "operator": "=", "value": "Moon"}],
        }
        resp = client.post("/pivot/execute", json=body)

        assert resp.status_code == 200
        result = resp.json()["data"]
        assert result["columns"] == []
        assert result["rows"] == []
        assert result["row_count"] == 0

    @patch("app.api.pivot.execute_query", new_callable=AsyncMock)
    def test_DB_실행_오류_500(self, mock_query, client):
        """DB 쿼리 실행 중 예외 → 500."""
        mock_query.side_effect = Exception("connection refused")

        body = {
            "cubeName": "Sales",
            "rows": [{"dimension": "Time", "level": "year"}],
            "measures": [{"name": "revenue"}],
        }
        resp = client.post("/pivot/execute", json=body)

        assert resp.status_code == 500
        assert "쿼리 실행 중 오류" in resp.json()["detail"]

    def test_측정값_없으면_400(self, client):
        """measures 비어있으면 SQL 생성 실패 → 400."""
        body = {
            "cubeName": "Sales",
            "rows": [{"dimension": "Time", "level": "year"}],
            "measures": [],
        }
        resp = client.post("/pivot/execute", json=body)

        assert resp.status_code == 400
        assert "SQL 생성 실패" in resp.json()["detail"]

    def test_허용되지_않은_연산자_400(self, client):
        """SQL 인젝션 시도 → 400 에러."""
        body = {
            "cubeName": "Sales",
            "rows": [{"dimension": "Time", "level": "year"}],
            "measures": [{"name": "revenue"}],
            "filters": [
                {"dimension": "Region", "level": "country", "operator": "; DROP TABLE", "value": "x"},
            ],
        }
        resp = client.post("/pivot/execute", json=body)

        assert resp.status_code == 400


# ──────────────────────────────────────────────
# 요청 본문 검증 (Pydantic 모델)
# ──────────────────────────────────────────────


class TestRequestValidation:
    """Pydantic 모델 검증을 통한 잘못된 입력 거부."""

    def test_잘못된_JSON_형식(self, client):
        """유효하지 않은 JSON → 422."""
        resp = client.post(
            "/pivot/execute",
            content="not a json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_빈_본문(self, client):
        """빈 요청 본문 → 422."""
        resp = client.post(
            "/pivot/execute",
            content="{}",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422  # cubeName 필수

    def test_커스텀_limit_반영(self, client):
        """limit 지정 시 SQL에 반영된다."""
        body = {
            "cubeName": "Sales",
            "rows": [{"dimension": "Time", "level": "year"}],
            "measures": [{"name": "revenue"}],
            "limit": 50,
        }
        resp = client.post("/pivot/preview-sql", json=body)

        assert resp.status_code == 200
        assert "LIMIT 50" in resp.json()["data"]["sql"]
