"""
멀티테넌트 프로세스 그래프 — TenantContext 정의 및 ContextVar 저장소.

Phase 0 (플랫폼 하드닝): 모든 서비스 레이어에서 사용하는 요청 범위 컨텍스트.
기존 식별자(tenant_id, user_id)는 str(VARCHAR)로 유지하고,
신규 엔티티 PK만 UUID를 사용한다.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class TenantContext:
    """요청 범위 테넌트/워크스페이스 컨텍스트.

    frozen=True로 선언하여 요청 처리 중 변경을 방지한다.
    tenant_id/user_id는 기존 tenants.id, users.id 타입(VARCHAR)과 일치시킨다.
    """
    tenant_id: str
    user_id: str
    org_unit_id: UUID | None = None
    workspace_id: UUID | None = None
    role_codes: frozenset[str] = field(default_factory=frozenset)
    permission_codes: frozenset[str] = field(default_factory=frozenset)
    timezone: str = "Asia/Seoul"


# ── ContextVar 저장소 ──────────────────────────────────────

# 미들웨어가 헤더에서 추출한 workspace_id 원본 문자열 (검증 전)
_workspace_id_header: ContextVar[str] = ContextVar("workspace_id_header", default="")

# 검증 완료된 TenantContext (security.py에서 조립)
_tenant_context: ContextVar[TenantContext | None] = ContextVar("tenant_context", default=None)


def get_workspace_id_header() -> str:
    """미들웨어가 설정한 X-Axiom-Workspace-Id 헤더 원본값."""
    return _workspace_id_header.get()


def get_tenant_context() -> TenantContext | None:
    """현재 요청의 검증 완료된 TenantContext."""
    return _tenant_context.get()


def set_tenant_context(ctx: TenantContext) -> None:
    """서비스 레이어에서 TenantContext를 설정한다."""
    _tenant_context.set(ctx)


def parse_workspace_id(raw: str) -> UUID | None:
    """문자열을 UUID로 파싱한다. 실패하면 None."""
    if not raw:
        return None
    try:
        return UUID(raw)
    except (ValueError, AttributeError):
        return None
