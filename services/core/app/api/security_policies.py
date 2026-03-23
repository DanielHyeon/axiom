"""G06 + G20: 보안 정책 백엔드 API — 테이블/컬럼 권한 + 정책 CRUD.

기존 프론트엔드 컴포넌트와 연동:
- TablePermissions.tsx (264 LOC) — 역할 × 테이블 매트릭스
- SecurityPolicies.tsx (256 LOC) — 5가지 정책 타입

Sprint 12: G06 (테이블/컬럼 권한), Sprint 13: G20 (보안 정책)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user

logger = logging.getLogger("axiom.core.api.security_policies")

router = APIRouter(prefix="/api/v3/core/security", tags=["보안 정책"])


# ── 모델 — G06: 테이블/컬럼 권한 ── #

class PermissionLevel(str, Enum):
    NONE = "none"
    READ = "read"
    WRITE = "write"


class MaskType(str, Enum):
    HASH = "hash"
    REDACT = "redact"
    PARTIAL = "partial"
    NONE = "none"


class TablePermission(BaseModel):
    """역할별 테이블 접근 권한"""
    permission_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    role: str                             # admin, analyst, viewer 등
    table_name: str
    schema_name: str = "public"
    permission: PermissionLevel = PermissionLevel.READ
    row_filter: str = ""                  # 행 수준 필터 (WHERE 절)
    tenant_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ColumnMask(BaseModel):
    """컬럼 마스킹 규칙"""
    mask_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    role: str
    table_name: str
    column_name: str
    mask_type: MaskType = MaskType.REDACT
    tenant_id: str = ""


class TablePermissionRequest(BaseModel):
    role: str
    table_name: str
    schema_name: str = "public"
    permission: PermissionLevel = PermissionLevel.READ
    # M1: row_filter는 Phase 5 DB 연동 시 반드시 AST 검증 필요
    row_filter: str = Field(default="", max_length=500)


class ColumnMaskRequest(BaseModel):
    role: str
    table_name: str
    column_name: str
    mask_type: MaskType = MaskType.REDACT


# ── 모델 — G20: 보안 정책 ── #

class SecurityPolicyType(str, Enum):
    MASKING = "masking"
    ENCRYPTION = "encryption"
    ANONYMIZATION = "anonymization"
    RETENTION = "retention"
    ACCESS_CONTROL = "access_control"


class SecurityPolicy(BaseModel):
    """보안 정책 정의"""
    policy_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    policy_type: SecurityPolicyType
    description: str = ""
    target_scope: str = ""                # 적용 범위 (table:*, column:email, role:viewer)
    rules: dict = Field(default_factory=dict)  # 정책별 규칙 상세
    enabled: bool = True
    tenant_id: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SecurityPolicyRequest(BaseModel):
    name: str
    policy_type: SecurityPolicyType
    description: str = ""
    target_scope: str = ""
    rules: dict = Field(default_factory=dict)
    enabled: bool = True


# ── 저장소 (in-memory MVP) ── #

_permissions: dict[str, TablePermission] = {}
_masks: dict[str, ColumnMask] = {}
_policies: dict[str, SecurityPolicy] = {}


# ── G06: 테이블/컬럼 권한 엔드포인트 ── #

@router.get("/table-permissions")
async def list_table_permissions(
    user: dict = Depends(get_current_user),
) -> dict:
    """역할별 테이블 접근 권한 매트릭스 조회"""
    tenant_id = user.get("tenant_id", "")
    perms = [p for p in _permissions.values() if p.tenant_id == tenant_id]
    return {
        "success": True,
        "data": [p.model_dump(mode="json") for p in perms],
        "total": len(perms),
    }


@router.post("/table-permissions")
async def set_table_permission(
    request: TablePermissionRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """테이블 레벨 접근 권한 설정 — admin만"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin 역할만 권한 설정 가능")

    tenant_id = user.get("tenant_id", "")
    perm = TablePermission(
        role=request.role,
        table_name=request.table_name,
        schema_name=request.schema_name,
        permission=request.permission,
        row_filter=request.row_filter,
        tenant_id=tenant_id,
    )
    _permissions[perm.permission_id] = perm

    logger.info("테이블 권한 설정: %s → %s.%s (%s)",
                request.role, request.schema_name, request.table_name, request.permission.value)
    return {"success": True, "data": perm.model_dump(mode="json")}


@router.post("/column-masks")
async def set_column_mask(
    request: ColumnMaskRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """컬럼 레벨 마스킹 규칙 설정 — admin만"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin 역할만 마스킹 설정 가능")

    tenant_id = user.get("tenant_id", "")
    mask = ColumnMask(
        role=request.role,
        table_name=request.table_name,
        column_name=request.column_name,
        mask_type=request.mask_type,
        tenant_id=tenant_id,
    )
    _masks[mask.mask_id] = mask

    logger.info("컬럼 마스킹 설정: %s → %s.%s (%s)",
                request.role, request.table_name, request.column_name, request.mask_type.value)
    return {"success": True, "data": mask.model_dump(mode="json")}


@router.get("/column-masks")
async def list_column_masks(
    user: dict = Depends(get_current_user),
) -> dict:
    """컬럼 마스킹 규칙 목록 조회"""
    tenant_id = user.get("tenant_id", "")
    masks = [m for m in _masks.values() if m.tenant_id == tenant_id]
    return {
        "success": True,
        "data": [m.model_dump(mode="json") for m in masks],
        "total": len(masks),
    }


# ── G20: 보안 정책 엔드포인트 ── #

@router.get("/policies")
async def list_security_policies(
    user: dict = Depends(get_current_user),
) -> dict:
    """보안 정책 목록 조회"""
    tenant_id = user.get("tenant_id", "")
    policies = [p for p in _policies.values() if p.tenant_id == tenant_id]
    return {
        "success": True,
        "data": [p.model_dump(mode="json") for p in policies],
        "total": len(policies),
    }


@router.post("/policies")
async def create_security_policy(
    request: SecurityPolicyRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """보안 정책 생성 — admin/manager만"""
    role = user.get("role", "viewer")
    if role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="admin/manager만 정책 생성 가능")

    tenant_id = user.get("tenant_id", "")
    policy = SecurityPolicy(
        name=request.name,
        policy_type=request.policy_type,
        description=request.description,
        target_scope=request.target_scope,
        rules=request.rules,
        enabled=request.enabled,
        tenant_id=tenant_id,
        created_by=user.get("user_id", ""),
    )
    _policies[policy.policy_id] = policy

    logger.info("보안 정책 생성: %s (%s)", request.name, request.policy_type.value)
    return {"success": True, "data": policy.model_dump(mode="json")}


@router.put("/policies/{policy_id}")
async def update_security_policy(
    policy_id: str,
    request: SecurityPolicyRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """보안 정책 수정"""
    role = user.get("role", "viewer")
    if role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="admin/manager만 정책 수정 가능")

    tenant_id = user.get("tenant_id", "")
    policy = _policies.get(policy_id)
    if not policy or policy.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="정책을 찾을 수 없습니다")

    policy.name = request.name
    policy.policy_type = request.policy_type
    policy.description = request.description
    policy.target_scope = request.target_scope
    policy.rules = request.rules
    policy.enabled = request.enabled
    policy.updated_at = datetime.now(timezone.utc)

    return {"success": True, "data": policy.model_dump(mode="json")}


@router.delete("/policies/{policy_id}")
async def delete_security_policy(
    policy_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """보안 정책 삭제"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin만 정책 삭제 가능")

    tenant_id = user.get("tenant_id", "")
    policy = _policies.get(policy_id)
    if not policy or policy.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="정책을 찾을 수 없습니다")

    del _policies[policy_id]
    return {"success": True, "message": f"정책 삭제 완료: {policy_id}"}
