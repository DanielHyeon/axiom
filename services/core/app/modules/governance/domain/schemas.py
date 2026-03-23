"""거버넌스 도메인 — Pydantic 요청/응답 DTO."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.governance.domain.enums import (
    MembershipScopeType, MembershipStatus, OrgType, VisibilityPolicy, WorkspaceType,
)


# ── OrgUnit ────────────────────────────────────────────────

class OrgUnitCreate(BaseModel):
    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    org_type: OrgType
    parent_org_unit_id: UUID | None = None
    owner_user_id: str | None = None

class OrgUnitUpdate(BaseModel):
    name: str | None = None
    org_type: OrgType | None = None
    owner_user_id: str | None = None

class OrgUnitResponse(BaseModel):
    id: UUID
    tenant_id: str
    parent_org_unit_id: UUID | None
    code: str
    name: str
    org_type: str
    owner_user_id: str | None
    path: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class OrgUnitTreeNode(BaseModel):
    """재귀 트리 노드."""
    id: UUID
    code: str
    name: str
    org_type: str
    children: list[OrgUnitTreeNode] = []
    model_config = {"from_attributes": True}


# ── Workspace ──────────────────────────────────────────────

class WorkspaceCreate(BaseModel):
    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    workspace_type: WorkspaceType
    org_unit_id: UUID
    visibility_policy: VisibilityPolicy = VisibilityPolicy.PRIVATE

class WorkspaceUpdate(BaseModel):
    name: str | None = None
    visibility_policy: VisibilityPolicy | None = None

class WorkspaceResponse(BaseModel):
    id: UUID
    tenant_id: str
    org_unit_id: UUID
    code: str
    name: str
    workspace_type: str
    visibility_policy: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Membership ─────────────────────────────────────────────

class MembershipCreate(BaseModel):
    user_id: str
    role_code: str = Field(..., max_length=100)
    scope_type: MembershipScopeType
    org_unit_id: UUID | None = None
    workspace_id: UUID | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None

    @model_validator(mode="after")
    def validate_scope_consistency(self):
        """scope_type과 org_unit_id/workspace_id 정합성 검증."""
        if self.scope_type == MembershipScopeType.TENANT:
            if self.org_unit_id or self.workspace_id:
                raise ValueError("TENANT scope must not have org_unit_id or workspace_id")
        elif self.scope_type == MembershipScopeType.ORG_UNIT:
            if not self.org_unit_id or self.workspace_id:
                raise ValueError("ORG_UNIT scope requires org_unit_id, no workspace_id")
        elif self.scope_type == MembershipScopeType.WORKSPACE:
            if not self.workspace_id or self.org_unit_id:
                raise ValueError("WORKSPACE scope requires workspace_id, no org_unit_id")
        return self

class MembershipResponse(BaseModel):
    id: UUID
    tenant_id: str
    user_id: str
    role_code: str
    scope_type: str
    org_unit_id: UUID | None
    workspace_id: UUID | None
    status: str
    effective_from: datetime | None
    effective_to: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── 공통 응답 래퍼 ─────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
