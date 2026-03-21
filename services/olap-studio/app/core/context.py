"""요청 컨텍스트 — Gateway가 주입한 헤더에서 사용자/테넌트/프로젝트 정보를 추출한다."""
from __future__ import annotations

from dataclasses import dataclass, field
from fastapi import Request, HTTPException


@dataclass(frozen=True)
class RequestContext:
    """Gateway에서 전달된 요청 컨텍스트."""
    user_id: str
    user_name: str
    tenant_id: str
    project_id: str
    roles: list[str] = field(default_factory=list)
    trace_id: str = ""


def get_request_context(request: Request) -> RequestContext:
    """Request.state에서 컨텍스트를 꺼낸다. 미들웨어가 이미 파싱한 상태여야 한다."""
    state = getattr(request, "state", None)
    if not state:
        raise HTTPException(status_code=401, detail="인증 컨텍스트 없음")

    tenant_id = getattr(state, "tenant_id", None) or ""
    if not tenant_id:
        raise HTTPException(status_code=401, detail="tenant_id 누락")

    return RequestContext(
        user_id=getattr(state, "user_id", "") or "",
        user_name=getattr(state, "user_name", "") or "",
        tenant_id=tenant_id,
        project_id=getattr(state, "project_id", "") or "",
        roles=getattr(state, "roles", []) or [],
        trace_id=getattr(state, "trace_id", "") or "",
    )


def require_capability(ctx: RequestContext, capability: str) -> None:
    """역할 기반 capability 검사 — 권한이 없으면 403."""
    # admin은 모든 capability 보유
    if "admin" in ctx.roles:
        return

    # 역할 → capability 매핑 (간략화)
    ROLE_CAPABILITIES: dict[str, set[str]] = {
        "admin": {"*"},
        "manager": {"datasource:read", "datasource:write", "etl:run", "etl:edit",
                     "cube:publish", "pivot:save", "lineage:read", "ai:use"},
        "engineer": {"datasource:read", "datasource:write", "etl:run", "etl:edit",
                      "cube:publish", "pivot:save", "lineage:read", "ai:use"},
        "analyst": {"datasource:read", "etl:read", "cube:read", "pivot:save",
                     "lineage:read", "nl2sql:use"},
        "viewer": {"datasource:read", "cube:read", "pivot:read", "lineage:read"},
    }

    user_caps: set[str] = set()
    for role in ctx.roles:
        user_caps |= ROLE_CAPABILITIES.get(role, set())

    if "*" in user_caps or capability in user_caps:
        return

    raise HTTPException(status_code=403, detail=f"권한 부족: {capability}")
