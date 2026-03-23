"""G33b: SSDD API — 드리프트 탐지 + 조회 + 해결 엔드포인트.

프론트엔드 Drift 목록/인시던트 화면과 연동.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import AuthService, CurrentUser
from app.services.drift_detector import (
    DriftDetector,
    DriftReport,
    DriftSeverity,
    ResolutionStatus,
    SchemaDrift,
    drift_detector,
)
from app.services.adapters.normalization import StandardMetadata

logger = logging.getLogger("axiom.weaver.api.drift")

router = APIRouter(prefix="/api/v3/weaver/drift", tags=["드리프트 탐지"])

_auth = AuthService()
_ALLOWED_ROLES = {"admin", "analyst", "engineer", "manager"}


async def _get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    return _auth.verify_token(authorization)


# ── 모델 ── #

class DriftDetectRequest(BaseModel):
    """드리프트 탐지 요청 — 새 메타데이터와 LKG 비교"""
    datasource_name: str
    metadata: dict[str, Any]      # StandardMetadata JSON


class DriftResolveRequest(BaseModel):
    """드리프트 해결 요청"""
    resolution_status: ResolutionStatus = ResolutionStatus.RESOLVED
    comment: str = ""


# ── 엔드포인트 ── #

@router.post("/detect")
async def detect_drift(
    request: DriftDetectRequest,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """드리프트 탐지 — 새 메타데이터 vs LKG 스냅샷 비교"""
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    try:
        metadata = StandardMetadata(**request.metadata)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"메타데이터 형식 오류: {str(e)[:200]}") from e

    report = await drift_detector.detect(
        request.datasource_name, metadata, tenant_id=user.tenant_id,
    )
    return {
        "success": True,
        "data": report.model_dump(mode="json"),
    }


@router.get("/list")
async def list_drifts(
    datasource_name: str,
    severity: DriftSeverity | None = None,
    status: ResolutionStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """드리프트 이력 조회 (테넌트 격리)"""
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    drifts = drift_detector.get_drifts(
        datasource_name, tenant_id=user.tenant_id,
        severity=severity, status=status, limit=limit,
    )
    return {
        "success": True,
        "data": [d.model_dump(mode="json") for d in drifts],
        "total": len(drifts),
    }


@router.post("/resolve/{drift_id}")
async def resolve_drift(
    drift_id: str,
    request: DriftResolveRequest,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """드리프트 해결 처리 — 서킷 브레이커 자동 해제"""
    if user.role not in {"admin", "manager"}:
        raise HTTPException(status_code=403, detail="admin/manager만 드리프트 해결 가능")

    drift = drift_detector.resolve_drift(
        drift_id=drift_id,
        tenant_id=user.tenant_id,
        resolved_by=user.user_id,
        resolution_status=request.resolution_status,
        comment=request.comment,
    )
    if not drift:
        raise HTTPException(status_code=404, detail=f"드리프트를 찾을 수 없습니다: {drift_id}")

    return {"success": True, "data": drift.model_dump(mode="json")}
