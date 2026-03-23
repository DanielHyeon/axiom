"""
멀티테넌트 프로세스 그래프 — Permission Catalog.

Phase 0 (플랫폼 하드닝): 프로세스 그래프/트윈/시나리오 도메인의 권한 19종 정의.
기존 security.py의 ROLE_PERMISSIONS(case/agent/watch 도메인)와 분리하여 관리하고,
Phase 1에서 통합 권한 체크로 합칠 예정.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDef:
    """권한 정의 — code, 설명, 허용 역할 목록."""
    code: str
    description: str
    allowed_roles: frozenset[str]


# ── 프로세스 그래프 도메인 권한 카탈로그 (19종) ──────────────

PROCESS_GRAPH_PERMISSIONS: dict[str, PermissionDef] = {
    # 거버넌스
    "governance:tenant:read": PermissionDef(
        code="governance:tenant:read",
        description="테넌트 정보 조회",
        allowed_roles=frozenset({"PLATFORM_ADMIN", "TENANT_ADMIN", "DOMAIN_OWNER",
                                  "PROCESS_ARCHITECT", "PROCESS_ANALYST", "TWIN_OPERATOR",
                                  "SCENARIO_ANALYST", "VIEWER"}),
    ),
    "governance:tenant:manage": PermissionDef(
        code="governance:tenant:manage",
        description="테넌트 설정 변경",
        allowed_roles=frozenset({"PLATFORM_ADMIN", "TENANT_ADMIN"}),
    ),
    "governance:workspace:create": PermissionDef(
        code="governance:workspace:create",
        description="워크스페이스 생성",
        allowed_roles=frozenset({"TENANT_ADMIN"}),
    ),
    "governance:workspace:read": PermissionDef(
        code="governance:workspace:read",
        description="워크스페이스 조회",
        allowed_roles=frozenset({"PLATFORM_ADMIN", "TENANT_ADMIN", "DOMAIN_OWNER",
                                  "PROCESS_ARCHITECT", "PROCESS_ANALYST", "TWIN_OPERATOR",
                                  "SCENARIO_ANALYST", "VIEWER"}),
    ),
    "governance:membership:grant": PermissionDef(
        code="governance:membership:grant",
        description="멤버십 할당",
        allowed_roles=frozenset({"TENANT_ADMIN", "DOMAIN_OWNER"}),
    ),
    "governance:membership:revoke": PermissionDef(
        code="governance:membership:revoke",
        description="멤버십 해제",
        allowed_roles=frozenset({"TENANT_ADMIN"}),
    ),

    # 프로세스 모델
    "process:definition:read": PermissionDef(
        code="process:definition:read",
        description="프로세스 정의 조회",
        allowed_roles=frozenset({"PROCESS_ARCHITECT", "PROCESS_ANALYST", "VIEWER"}),
    ),
    "process:definition:write": PermissionDef(
        code="process:definition:write",
        description="프로세스 정의 생성/수정",
        allowed_roles=frozenset({"PROCESS_ARCHITECT"}),
    ),
    "process:version:publish": PermissionDef(
        code="process:version:publish",
        description="프로세스 버전 발행",
        allowed_roles=frozenset({"PROCESS_ARCHITECT", "DOMAIN_OWNER"}),
    ),
    "process:relation:create": PermissionDef(
        code="process:relation:create",
        description="프로세스 관계 엣지 생성",
        allowed_roles=frozenset({"PROCESS_ARCHITECT"}),
    ),
    "process:clone": PermissionDef(
        code="process:clone",
        description="프로세스 복제",
        allowed_roles=frozenset({"PROCESS_ARCHITECT"}),
    ),

    # 그래프
    "graph:read": PermissionDef(
        code="graph:read",
        description="그래프 탐색/영향도 조회",
        allowed_roles=frozenset({"PROCESS_ANALYST", "PROCESS_ARCHITECT"}),
    ),
    "graph:admin": PermissionDef(
        code="graph:admin",
        description="그래프 재구축",
        allowed_roles=frozenset({"PLATFORM_ADMIN"}),
    ),

    # 디지털 트윈
    "twin:read": PermissionDef(
        code="twin:read",
        description="트윈 상태/대시보드 조회",
        allowed_roles=frozenset({"TWIN_OPERATOR", "PROCESS_ANALYST"}),
    ),
    "twin:event:write": PermissionDef(
        code="twin:event:write",
        description="트윈 이벤트 발행",
        allowed_roles=frozenset({"TWIN_OPERATOR", "SYSTEM"}),
    ),
    "twin:snapshot:capture": PermissionDef(
        code="twin:snapshot:capture",
        description="수동 스냅샷 캡처",
        allowed_roles=frozenset({"TWIN_OPERATOR"}),
    ),

    # 시나리오
    "scenario:read": PermissionDef(
        code="scenario:read",
        description="시나리오 조회",
        allowed_roles=frozenset({"PROCESS_ANALYST", "SCENARIO_ANALYST"}),
    ),
    "scenario:run": PermissionDef(
        code="scenario:run",
        description="시나리오 실행",
        allowed_roles=frozenset({"SCENARIO_ANALYST"}),
    ),
    "scenario:manage": PermissionDef(
        code="scenario:manage",
        description="시나리오 생성/삭제",
        allowed_roles=frozenset({"SCENARIO_ANALYST", "PROCESS_ARCHITECT"}),
    ),
}


def has_process_graph_permission(role_codes: set[str] | frozenset[str], required: str) -> bool:
    """주어진 역할 집합이 프로세스 그래프 권한을 보유하는지 확인한다.

    PLATFORM_ADMIN은 모든 권한을 통과한다.
    """
    # 기존 admin(소문자) + 신규 PLATFORM_ADMIN 모두 superuser
    if "PLATFORM_ADMIN" in role_codes or "admin" in role_codes:
        return True
    perm_def = PROCESS_GRAPH_PERMISSIONS.get(required)
    if perm_def is None:
        return False
    return bool(role_codes & perm_def.allowed_roles)
