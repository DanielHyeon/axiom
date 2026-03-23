"""
거버넌스 API — /api/v1/governance/* 라우터.

Phase 1: OrgUnit/Workspace/Membership CRUD 9개 엔드포인트.
모든 엔드포인트는 tenant_id를 JWT에서 추출하고, 응답은 표준 래퍼를 사용한다.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.core.permissions import has_process_graph_permission
from app.modules.governance.application.governance_service import GovernanceService
from app.modules.governance.domain.errors import GovernanceError


def _check_permission(user: dict, permission: str) -> None:
    """권한 검사 — 미보유 시 403."""
    role_codes = set(user.get("roles", [user.get("role", "viewer")]))
    if not has_process_graph_permission(role_codes, permission):
        raise HTTPException(status_code=403, detail=f"Permission '{permission}' required")
from app.modules.governance.domain.schemas import (
    MembershipCreate, MembershipResponse,
    OrgUnitCreate, OrgUnitResponse, OrgUnitTreeNode, OrgUnitUpdate,
    WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate,
)

router = APIRouter(prefix="/governance", tags=["governance"])


def _build_tree(units: list) -> list[dict]:
    """플랫 OrgUnit 목록을 재귀 트리로 조립한다."""
    by_id = {}
    roots = []
    for u in units:
        node = {
            "id": u.id, "code": u.code, "name": u.name,
            "org_type": u.org_type, "children": [],
        }
        by_id[u.id] = node
    for u in units:
        node = by_id[u.id]
        if u.parent_org_unit_id and u.parent_org_unit_id in by_id:
            by_id[u.parent_org_unit_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


# ── OrgUnit ────────────────────────────────────────────────

@router.post("/org-units", response_model=OrgUnitResponse, status_code=201)
async def create_org_unit(
    body: OrgUnitCreate,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """조직 단위 생성."""
    _check_permission(user, "governance:tenant:manage")
    svc = GovernanceService(session)
    try:
        org_unit = await svc.create_org_unit(user["tenant_id"], body)
        await session.commit()
        return org_unit
    except GovernanceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/org-units/tree")
async def get_org_unit_tree(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """조직 계층 트리 조회."""
    svc = GovernanceService(session)
    units = await svc.get_org_unit_tree(user["tenant_id"])
    return {"success": True, "data": _build_tree(units)}


@router.patch("/org-units/{org_unit_id}", response_model=OrgUnitResponse)
async def update_org_unit(
    org_unit_id: UUID,
    body: OrgUnitUpdate,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """조직 단위 수정."""
    _check_permission(user, "governance:tenant:manage")
    svc = GovernanceService(session)
    try:
        org_unit = await svc.update_org_unit(user["tenant_id"], org_unit_id, body)
        await session.commit()
        return org_unit
    except GovernanceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ── Workspace ──────────────────────────────────────────────

@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """워크스페이스 생성."""
    _check_permission(user, "governance:workspace:create")
    svc = GovernanceService(session)
    try:
        workspace = await svc.create_workspace(user["tenant_id"], body)
        await session.commit()
        return workspace
    except GovernanceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/workspaces")
async def list_workspaces(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """접근 가능 워크스페이스 목록."""
    svc = GovernanceService(session)
    items, total = await svc.get_workspaces(user["tenant_id"], user["user_id"], page, page_size)
    return {
        "success": True,
        "data": {
            "items": [WorkspaceResponse.model_validate(w) for w in items],
            "total": total, "page": page, "page_size": page_size,
        },
    }


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """워크스페이스 상세."""
    svc = GovernanceService(session)
    try:
        return await svc.get_workspace(user["tenant_id"], workspace_id)
    except GovernanceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    body: WorkspaceUpdate,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """워크스페이스 수정."""
    svc = GovernanceService(session)
    try:
        workspace = await svc.update_workspace(user["tenant_id"], workspace_id, body)
        await session.commit()
        return workspace
    except GovernanceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ── Membership ─────────────────────────────────────────────

@router.post("/memberships", response_model=MembershipResponse, status_code=201)
async def create_membership(
    body: MembershipCreate,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """멤버십 할당."""
    _check_permission(user, "governance:membership:grant")
    svc = GovernanceService(session)
    try:
        membership = await svc.create_membership(user["tenant_id"], body)
        await session.commit()
        return membership
    except GovernanceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/workspaces/{workspace_id}/members")
async def get_workspace_members(
    workspace_id: UUID,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """워크스페이스 멤버 목록."""
    svc = GovernanceService(session)
    members = await svc.get_workspace_members(user["tenant_id"], workspace_id)
    return {
        "success": True,
        "data": [MembershipResponse.model_validate(m) for m in members],
    }
