"""요청 컨텍스트 및 RBAC 단위 테스트.

context.py의 get_request_context와 require_capability를 검증한다.
FastAPI의 Request 객체를 간단한 mock으로 대체하여 순수 로직만 테스트한다.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import HTTPException

from app.core.context import RequestContext, get_request_context, require_capability


# ──────────────────────────────────────────────
# 테스트용 Request 모의 객체
# ──────────────────────────────────────────────


class FakeState:
    """Request.state를 모방하는 간단한 객체."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeRequest:
    """FastAPI Request를 모방하는 최소 객체."""

    def __init__(self, state=None):
        self.state = state


# ──────────────────────────────────────────────
# get_request_context 테스트
# ──────────────────────────────────────────────


class TestGetRequestContext:
    """get_request_context 함수의 정상/에러 경로를 검증한다."""

    def test_valid_state_returns_correct_context(self):
        """유효한 state → RequestContext 생성 성공."""
        state = FakeState(
            user_id="user-001",
            user_name="홍길동",
            tenant_id="tenant-abc",
            project_id="proj-xyz",
            roles=["analyst", "viewer"],
            trace_id="trace-123",
        )
        request = FakeRequest(state=state)
        ctx = get_request_context(request)

        assert ctx.user_id == "user-001"
        assert ctx.user_name == "홍길동"
        assert ctx.tenant_id == "tenant-abc"
        assert ctx.project_id == "proj-xyz"
        assert ctx.roles == ["analyst", "viewer"]
        assert ctx.trace_id == "trace-123"

    def test_missing_state_raises_401(self):
        """state가 없는 Request → 401 에러."""
        request = FakeRequest(state=None)
        with pytest.raises(HTTPException) as exc_info:
            get_request_context(request)
        assert exc_info.value.status_code == 401
        assert "인증 컨텍스트 없음" in exc_info.value.detail

    def test_missing_tenant_id_raises_401(self):
        """tenant_id가 빈 문자열 → 401 에러."""
        state = FakeState(
            user_id="user-001",
            user_name="테스트",
            tenant_id="",
            project_id="proj-1",
            roles=["viewer"],
        )
        request = FakeRequest(state=state)
        with pytest.raises(HTTPException) as exc_info:
            get_request_context(request)
        assert exc_info.value.status_code == 401
        assert "tenant_id 누락" in exc_info.value.detail

    def test_no_tenant_id_attr_raises_401(self):
        """state에 tenant_id 속성 자체가 없는 경우 → 401 에러."""
        state = FakeState(
            user_id="user-001",
            user_name="테스트",
            project_id="proj-1",
        )
        request = FakeRequest(state=state)
        with pytest.raises(HTTPException) as exc_info:
            get_request_context(request)
        assert exc_info.value.status_code == 401

    def test_optional_fields_default_to_empty(self):
        """선택적 필드 누락 → 빈 문자열/리스트 기본값."""
        state = FakeState(
            tenant_id="tenant-abc",
        )
        request = FakeRequest(state=state)
        ctx = get_request_context(request)

        assert ctx.user_id == ""
        assert ctx.user_name == ""
        assert ctx.tenant_id == "tenant-abc"
        assert ctx.project_id == ""
        assert ctx.roles == []
        assert ctx.trace_id == ""

    def test_none_roles_defaults_to_empty_list(self):
        """roles가 None → 빈 리스트."""
        state = FakeState(
            tenant_id="tenant-abc",
            roles=None,
        )
        request = FakeRequest(state=state)
        ctx = get_request_context(request)
        assert ctx.roles == []


# ──────────────────────────────────────────────
# require_capability — 관리자 (admin)
# ──────────────────────────────────────────────


class TestRequireCapabilityAdmin:
    """admin 역할은 모든 capability에 대해 통과한다."""

    def test_admin_passes_any_capability(self):
        """admin → 어떤 capability든 통과."""
        ctx = RequestContext(
            user_id="admin-1",
            user_name="관리자",
            tenant_id="t-1",
            project_id="p-1",
            roles=["admin"],
        )
        # 예외 없이 통과해야 한다
        require_capability(ctx, "pivot:save")
        require_capability(ctx, "etl:edit")
        require_capability(ctx, "datasource:write")
        require_capability(ctx, "nonexistent:capability")

    def test_admin_with_other_roles(self):
        """admin + viewer → admin 권한이 우선하여 통과."""
        ctx = RequestContext(
            user_id="admin-2",
            user_name="관리자겸뷰어",
            tenant_id="t-1",
            project_id="p-1",
            roles=["viewer", "admin"],
        )
        require_capability(ctx, "etl:edit")


# ──────────────────────────────────────────────
# require_capability — analyst
# ──────────────────────────────────────────────


class TestRequireCapabilityAnalyst:
    """analyst 역할의 capability 검증."""

    def _make_analyst_ctx(self) -> RequestContext:
        return RequestContext(
            user_id="analyst-1",
            user_name="분석가",
            tenant_id="t-1",
            project_id="p-1",
            roles=["analyst"],
        )

    def test_analyst_can_pivot_save(self):
        """analyst는 pivot:save 권한이 있다."""
        require_capability(self._make_analyst_ctx(), "pivot:save")

    def test_analyst_can_datasource_read(self):
        """analyst는 datasource:read 권한이 있다."""
        require_capability(self._make_analyst_ctx(), "datasource:read")

    def test_analyst_can_lineage_read(self):
        """analyst는 lineage:read 권한이 있다."""
        require_capability(self._make_analyst_ctx(), "lineage:read")

    def test_analyst_can_nl2sql_use(self):
        """analyst는 nl2sql:use 권한이 있다."""
        require_capability(self._make_analyst_ctx(), "nl2sql:use")

    def test_analyst_cannot_etl_edit(self):
        """analyst는 etl:edit 권한이 없다 → 403."""
        with pytest.raises(HTTPException) as exc_info:
            require_capability(self._make_analyst_ctx(), "etl:edit")
        assert exc_info.value.status_code == 403
        assert "권한 부족" in exc_info.value.detail

    def test_analyst_cannot_cube_publish(self):
        """analyst는 cube:publish 권한이 없다 → 403."""
        with pytest.raises(HTTPException) as exc_info:
            require_capability(self._make_analyst_ctx(), "cube:publish")
        assert exc_info.value.status_code == 403


# ──────────────────────────────────────────────
# require_capability — viewer
# ──────────────────────────────────────────────


class TestRequireCapabilityViewer:
    """viewer 역할의 capability 검증."""

    def _make_viewer_ctx(self) -> RequestContext:
        return RequestContext(
            user_id="viewer-1",
            user_name="뷰어",
            tenant_id="t-1",
            project_id="p-1",
            roles=["viewer"],
        )

    def test_viewer_can_datasource_read(self):
        """viewer는 datasource:read 권한이 있다."""
        require_capability(self._make_viewer_ctx(), "datasource:read")

    def test_viewer_can_pivot_read(self):
        """viewer는 pivot:read 권한이 있다."""
        require_capability(self._make_viewer_ctx(), "pivot:read")

    def test_viewer_can_lineage_read(self):
        """viewer는 lineage:read 권한이 있다."""
        require_capability(self._make_viewer_ctx(), "lineage:read")

    def test_viewer_cannot_etl_edit(self):
        """viewer는 etl:edit 권한이 없다 → 403."""
        with pytest.raises(HTTPException) as exc_info:
            require_capability(self._make_viewer_ctx(), "etl:edit")
        assert exc_info.value.status_code == 403

    def test_viewer_cannot_pivot_save(self):
        """viewer는 pivot:save 권한이 없다 → 403."""
        with pytest.raises(HTTPException) as exc_info:
            require_capability(self._make_viewer_ctx(), "pivot:save")
        assert exc_info.value.status_code == 403

    def test_viewer_cannot_datasource_write(self):
        """viewer는 datasource:write 권한이 없다 → 403."""
        with pytest.raises(HTTPException) as exc_info:
            require_capability(self._make_viewer_ctx(), "datasource:write")
        assert exc_info.value.status_code == 403


# ──────────────────────────────────────────────
# require_capability — manager / engineer
# ──────────────────────────────────────────────


class TestRequireCapabilityManagerEngineer:
    """manager와 engineer 역할의 capability 검증."""

    def test_manager_can_etl_edit(self):
        """manager는 etl:edit 가능."""
        ctx = RequestContext(
            user_id="mgr-1", user_name="매니저",
            tenant_id="t-1", project_id="p-1",
            roles=["manager"],
        )
        require_capability(ctx, "etl:edit")

    def test_engineer_can_cube_publish(self):
        """engineer는 cube:publish 가능."""
        ctx = RequestContext(
            user_id="eng-1", user_name="엔지니어",
            tenant_id="t-1", project_id="p-1",
            roles=["engineer"],
        )
        require_capability(ctx, "cube:publish")

    def test_engineer_can_ai_use(self):
        """engineer는 ai:use 가능."""
        ctx = RequestContext(
            user_id="eng-1", user_name="엔지니어",
            tenant_id="t-1", project_id="p-1",
            roles=["engineer"],
        )
        require_capability(ctx, "ai:use")


# ──────────────────────────────────────────────
# require_capability — unknown / empty roles
# ──────────────────────────────────────────────


class TestRequireCapabilityUnknownRole:
    """알 수 없는 역할 또는 빈 역할 → 403."""

    def test_unknown_role_raises_403(self):
        """매핑에 없는 역할 → 모든 capability에 대해 403."""
        ctx = RequestContext(
            user_id="u-1", user_name="미지의역할",
            tenant_id="t-1", project_id="p-1",
            roles=["unknown_role"],
        )
        with pytest.raises(HTTPException) as exc_info:
            require_capability(ctx, "datasource:read")
        assert exc_info.value.status_code == 403

    def test_empty_roles_raises_403(self):
        """역할 없는 사용자 → 403."""
        ctx = RequestContext(
            user_id="u-1", user_name="무역할",
            tenant_id="t-1", project_id="p-1",
            roles=[],
        )
        with pytest.raises(HTTPException) as exc_info:
            require_capability(ctx, "pivot:read")
        assert exc_info.value.status_code == 403

    def test_multiple_roles_union_capabilities(self):
        """여러 역할 보유 시 capability가 합산(union)된다."""
        ctx = RequestContext(
            user_id="u-1", user_name="복수역할",
            tenant_id="t-1", project_id="p-1",
            roles=["viewer", "analyst"],
        )
        # viewer: pivot:read + analyst: pivot:save → 둘 다 가능
        require_capability(ctx, "pivot:read")
        require_capability(ctx, "pivot:save")
        require_capability(ctx, "nl2sql:use")  # analyst만 보유


# ──────────────────────────────────────────────
# RequestContext frozen 불변성 테스트
# ──────────────────────────────────────────────


class TestRequestContextImmutability:
    """RequestContext는 frozen=True이므로 수정 불가."""

    def test_cannot_modify_fields(self):
        """frozen 데이터클래스 → 필드 변경 시 에러."""
        ctx = RequestContext(
            user_id="u-1", user_name="테스트",
            tenant_id="t-1", project_id="p-1",
        )
        with pytest.raises(AttributeError):
            ctx.user_id = "modified"  # type: ignore

    def test_cannot_modify_tenant_id(self):
        """tenant_id도 변경 불가."""
        ctx = RequestContext(
            user_id="u-1", user_name="테스트",
            tenant_id="t-1", project_id="p-1",
        )
        with pytest.raises(AttributeError):
            ctx.tenant_id = "hacked"  # type: ignore
