"""G19: 감사 로그 집계 API — 기존 AuditLogViewer.tsx 연동.

날짜/액션/사용자 필터, 페이지네이션, 상세 조회를 제공한다.
in-memory MVP — Phase 5에서 PostgreSQL audit 테이블 연동.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user

logger = logging.getLogger("axiom.core.api.audit")

router = APIRouter(prefix="/api/v3/core/audit", tags=["감사 로그"])


# ── 모델 ── #

class AuditAction(str, Enum):
    """감사 로그 액션 유형"""
    LOGIN = "login"
    LOGOUT = "logout"
    QUERY_EXECUTE = "query_execute"
    DATA_EXPORT = "data_export"
    SCHEMA_CHANGE = "schema_change"
    PERMISSION_CHANGE = "permission_change"
    POLICY_CHANGE = "policy_change"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    DATASOURCE_CONNECT = "datasource_connect"
    CODE_UPLOAD = "code_upload"
    ONTOLOGY_EDIT = "ontology_edit"


class AuditLogEntry(BaseModel):
    """감사 로그 항목"""
    log_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    action: AuditAction
    user_id: str = ""
    user_email: str = ""
    tenant_id: str = ""
    resource_type: str = ""               # table, column, policy, user 등
    resource_id: str = ""
    detail: str = ""                      # 액션 상세 설명
    ip_address: str = ""
    user_agent: str = ""
    success: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLogListResponse(BaseModel):
    success: bool = True
    data: list[dict] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50


# ── 저장소 (in-memory MVP) ── #

_audit_logs: list[AuditLogEntry] = []
_MAX_AUDIT_LOGS = 50000


def record_audit_log(
    action: AuditAction,
    user_id: str = "",
    tenant_id: str = "",
    resource_type: str = "",
    resource_id: str = "",
    detail: str = "",
    success: bool = True,
    **kwargs: Any,
) -> str:
    """감사 로그 기록 — 다른 모듈에서 호출"""
    entry = AuditLogEntry(
        action=action,
        user_id=user_id,
        tenant_id=tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        success=success,
        **kwargs,
    )
    _audit_logs.append(entry)

    # 메모리 제한
    if len(_audit_logs) > _MAX_AUDIT_LOGS:
        _audit_logs[:] = _audit_logs[-_MAX_AUDIT_LOGS // 2:]

    return entry.log_id


# ── 엔드포인트 ── #

@router.get("/logs")
async def list_audit_logs(
    user: dict = Depends(get_current_user),
    action: AuditAction | None = None,
    user_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> AuditLogListResponse:
    """감사 로그 조회 — admin/manager만"""
    role = user.get("role", "viewer")
    if role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="admin/manager만 감사 로그 조회 가능")

    tenant_id = user.get("tenant_id", "")

    # 필터링
    filtered = [log for log in _audit_logs if log.tenant_id == tenant_id]

    if action:
        filtered = [log for log in filtered if log.action == action]
    if user_id:
        filtered = [log for log in filtered if log.user_id == user_id]
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            filtered = [log for log in filtered if log.created_at >= dt_from]
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            filtered = [log for log in filtered if log.created_at <= dt_to]
        except ValueError:
            pass

    # 최신순 정렬
    filtered.sort(key=lambda x: x.created_at, reverse=True)

    # 페이지네이션
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_data = filtered[start:end]

    return AuditLogListResponse(
        data=[log.model_dump(mode="json") for log in page_data],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/logs/{log_id}")
async def get_audit_log_detail(
    log_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """감사 로그 상세 조회"""
    role = user.get("role", "viewer")
    if role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="admin/manager만 조회 가능")

    tenant_id = user.get("tenant_id", "")
    for log in _audit_logs:
        if log.log_id == log_id and log.tenant_id == tenant_id:
            return {"success": True, "data": log.model_dump(mode="json")}

    raise HTTPException(status_code=404, detail="감사 로그를 찾을 수 없습니다")


@router.get("/summary")
async def audit_summary(
    user: dict = Depends(get_current_user),
    days: int = Query(7, ge=1, le=90),
) -> dict:
    """감사 로그 요약 통계 — 액션별 횟수"""
    role = user.get("role", "viewer")
    if role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="admin/manager만 조회 가능")

    tenant_id = user.get("tenant_id", "")
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    filtered = [
        log for log in _audit_logs
        if log.tenant_id == tenant_id and log.created_at >= cutoff
    ]

    by_action: dict[str, int] = {}
    by_user: dict[str, int] = {}
    for log in filtered:
        by_action[log.action.value] = by_action.get(log.action.value, 0) + 1
        by_user[log.user_id] = by_user.get(log.user_id, 0) + 1

    return {
        "success": True,
        "data": {
            "total_events": len(filtered),
            "by_action": by_action,
            "by_user": dict(sorted(by_user.items(), key=lambda x: -x[1])[:10]),
            "period_days": days,
        },
    }
