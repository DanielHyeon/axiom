"""관리자 감사 로그 + AI 사용량 API 단위 테스트.

admin_audit.py 모듈의 엔드포인트를 검증한다.

Note: passlib이 설치되지 않은 환경에서도 테스트가 동작하도록
      sys.modules 패치로 의존성을 우회한다.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# passlib이 없는 환경에서도 테스트 가능하도록 mock 모듈 주입
if "passlib" not in sys.modules:
    _passlib = ModuleType("passlib")
    _passlib_ctx = ModuleType("passlib.context")
    _passlib_ctx.CryptContext = MagicMock()  # type: ignore[attr-defined]
    sys.modules["passlib"] = _passlib
    sys.modules["passlib.context"] = _passlib_ctx

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.admin_audit import (
    router,
    _require_admin,
    _generate_mock_audit_logs,
    _generate_mock_ai_usage,
)
from app.core.security import get_current_user

# ── 테스트용 FastAPI 앱 ── #

_app = FastAPI()
_app.include_router(router)


def _make_user(role: str = "admin", tenant_id: str = "t-001") -> dict:
    """테스트용 사용자 딕셔너리 생성."""
    return {
        "user_id": "u-001",
        "email": "test@axiom.ai",
        "role": role,
        "tenant_id": tenant_id,
    }


def _override_user(user: dict):
    """FastAPI 의존성 오버라이드를 설정한다."""
    _app.dependency_overrides[get_current_user] = lambda: user


# ── 권한 검증 테스트 ── #


class TestRequireAdmin:
    """_require_admin 헬퍼 함수 검증."""

    def test_admin_통과(self):
        """admin 역할은 예외 없이 통과한다."""
        _require_admin({"role": "admin"})  # 예외 없어야 함

    def test_manager_통과(self):
        """manager 역할도 통과한다."""
        _require_admin({"role": "manager"})

    def test_viewer_차단(self):
        """viewer 역할은 403 예외를 던진다."""
        with pytest.raises(HTTPException) as exc_info:
            _require_admin({"role": "viewer"})
        assert exc_info.value.status_code == 403

    def test_analyst_차단(self):
        """analyst 역할은 403 예외를 던진다."""
        with pytest.raises(HTTPException):
            _require_admin({"role": "analyst"})

    def test_역할_없음_차단(self):
        """역할이 없는 사용자는 viewer로 취급하여 차단한다."""
        with pytest.raises(HTTPException):
            _require_admin({})


# ── Mock 데이터 생성 테스트 ── #


class TestMockAuditLogs:
    """_generate_mock_audit_logs 함수 검증."""

    def test_기본_페이지_반환(self):
        items, total = _generate_mock_audit_logs(
            tenant_id="t-001", page=1, size=10,
            event_type=None, since=None,
        )
        assert total > 0
        assert len(items) <= 10
        # 모든 항목에 tenant_id가 설정됨
        for item in items:
            assert item.tenant_id == "t-001"

    def test_페이지_크기_초과_방지(self):
        items, total = _generate_mock_audit_logs(
            tenant_id="t-001", page=100, size=50,
            event_type=None, since=None,
        )
        # 범위 밖 페이지는 빈 리스트
        assert len(items) == 0

    def test_event_type_필터(self):
        items, total = _generate_mock_audit_logs(
            tenant_id="t-001", page=1, size=50,
            event_type="NL2SQL_QUERY_EXECUTED", since=None,
        )
        for item in items:
            assert item.event_type == "NL2SQL_QUERY_EXECUTED"

    def test_since_필터_건수_감소(self):
        recent = datetime.now(timezone.utc)
        _items_recent, total_recent = _generate_mock_audit_logs(
            tenant_id="t-001", page=1, size=50,
            event_type=None, since=recent,
        )
        _items_all, total_all = _generate_mock_audit_logs(
            tenant_id="t-001", page=1, size=50,
            event_type=None, since=None,
        )
        assert total_recent <= total_all


class TestMockAIUsage:
    """_generate_mock_ai_usage 함수 검증."""

    def test_기본_30일_집계(self):
        summary, daily = _generate_mock_ai_usage(30)
        assert summary["period_days"] == 30
        assert len(daily) == 30
        assert summary["total_nl2sql_calls"] > 0
        assert summary["estimated_cost_usd"] > 0

    def test_1일_최소_집계(self):
        summary, daily = _generate_mock_ai_usage(1)
        assert len(daily) == 1

    def test_일별_항목_필드(self):
        _, daily = _generate_mock_ai_usage(7)
        for item in daily:
            assert item.date  # YYYY-MM-DD 형식
            assert item.nl2sql_calls >= 0
            assert item.total_tokens >= 0
            assert item.estimated_cost_usd >= 0


# ── API 엔드포인트 테스트 (TestClient) ── #


class TestAuditLogsEndpoint:
    """GET /api/v3/core/admin/audit-logs 엔드포인트 검증."""

    def setup_method(self):
        _override_user(_make_user(role="admin"))

    def teardown_method(self):
        _app.dependency_overrides.clear()

    def test_admin_조회_성공(self):
        client = TestClient(_app)
        resp = client.get("/api/v3/core/admin/audit-logs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["total"] > 0
        assert isinstance(body["data"], list)

    def test_페이지네이션_파라미터(self):
        client = TestClient(_app)
        resp = client.get("/api/v3/core/admin/audit-logs?page=2&size=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 2
        assert body["size"] == 5

    def test_viewer_403(self):
        _override_user(_make_user(role="viewer"))
        client = TestClient(_app)
        resp = client.get("/api/v3/core/admin/audit-logs")
        assert resp.status_code == 403

    def test_event_type_필터(self):
        client = TestClient(_app)
        resp = client.get(
            "/api/v3/core/admin/audit-logs?event_type=NL2SQL_QUERY_EXECUTED"
        )
        assert resp.status_code == 200


class TestAIUsageEndpoint:
    """GET /api/v3/core/admin/ai-usage 엔드포인트 검증."""

    def setup_method(self):
        _override_user(_make_user(role="admin"))

    def teardown_method(self):
        _app.dependency_overrides.clear()

    def test_admin_조회_성공(self):
        client = TestClient(_app)
        resp = client.get("/api/v3/core/admin/ai-usage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "summary" in body
        assert "daily" in body
        assert body["period_days"] == 30

    def test_days_파라미터(self):
        client = TestClient(_app)
        resp = client.get("/api/v3/core/admin/ai-usage?days=7")
        assert resp.status_code == 200
        body = resp.json()
        assert body["period_days"] == 7
        assert len(body["daily"]) == 7

    def test_viewer_403(self):
        _override_user(_make_user(role="viewer"))
        client = TestClient(_app)
        resp = client.get("/api/v3/core/admin/ai-usage")
        assert resp.status_code == 403

    def test_summary_필드_완전성(self):
        client = TestClient(_app)
        resp = client.get("/api/v3/core/admin/ai-usage")
        summary = resp.json()["summary"]
        assert "total_nl2sql_calls" in summary
        assert "total_llm_calls" in summary
        assert "total_tokens" in summary
        assert "estimated_cost_usd" in summary
        assert "top_model" in summary


class TestAIUsageByCallerEndpoint:
    """GET /api/v3/core/admin/ai-usage/by-caller 엔드포인트 검증."""

    def setup_method(self):
        _override_user(_make_user(role="admin"))

    def teardown_method(self):
        _app.dependency_overrides.clear()

    def test_admin_조회_성공(self):
        client = TestClient(_app)
        resp = client.get("/api/v3/core/admin/ai-usage/by-caller")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) > 0

    def test_호출자_필드_완전성(self):
        client = TestClient(_app)
        resp = client.get("/api/v3/core/admin/ai-usage/by-caller")
        for caller in resp.json()["data"]:
            assert "user_id" in caller
            assert "user_email" in caller
            assert "nl2sql_calls" in caller


class TestEventTypesEndpoint:
    """GET /api/v3/core/admin/audit-logs/event-types 엔드포인트 검증."""

    def setup_method(self):
        _override_user(_make_user(role="admin"))

    def teardown_method(self):
        _app.dependency_overrides.clear()

    def test_이벤트_타입_목록(self):
        client = TestClient(_app)
        resp = client.get("/api/v3/core/admin/audit-logs/event-types")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["total"] > 0
        # 각 항목에 type, category, description 필드가 있어야 함
        for item in body["data"]:
            assert "type" in item
            assert "category" in item
            assert "description" in item
