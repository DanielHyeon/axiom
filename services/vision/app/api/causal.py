"""
인과 분석 API 엔드포인트.

VAR/Granger + 분해형 하이브리드 인과 분석을 실행하고 결과를 조회한다.
비동기 실행 패턴: POST 202 -> GET 폴링 -> 완료 시 엣지/그래프 조회.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api._auth import get_current_user
from app.core.auth import CurrentUser, auth_service
from app.services.vision_runtime import vision_runtime

router = APIRouter(
    prefix="/api/v3/cases/{case_id}/causal",
    tags=["Causal Analysis"],
)


# ── 요청/응답 스키마 ── #

class CausalAnalysisRequest(BaseModel):
    """인과 분석 실행 요청 스키마."""
    target_node_id: str = Field(..., min_length=1, description="타겟 노드 ID (예: 'kpi-oee')")
    target_field: str = Field(..., min_length=1, description="타겟 필드명 (예: 'value')")
    max_lag: int | None = Field(default=None, ge=1, le=10, description="VAR 최대 시차")
    # 리뷰 #6: significance_level을 요청에서 받으면 엔진에 전달
    significance_level: float | None = Field(
        default=None, ge=0.001, le=0.1,
        description="Granger 검정 유의수준 (미지정 시 엔진 기본값 0.05 사용)",
    )


class CausalEdgeResponse(BaseModel):
    """인과 엣지 응답 스키마."""
    source: str
    target: str
    method: str
    strength: float
    p_value: float
    lag: int
    direction: str


# ── 엔드포인트 ── #

@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def run_causal_analysis(
    case_id: str,
    payload: CausalAnalysisRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    인과 분석 실행 (비동기).

    타겟 노드/필드에 대해 VAR + Granger + 분해형 하이브리드 인과 분석을 실행한다.
    202 반환 후 백그라운드에서 실행, poll_url로 상태 확인.
    """
    auth_service.requires_role(user, ["admin", "staff"])
    result = await vision_runtime.run_causal_analysis(
        case_id=case_id,
        target_node_id=payload.target_node_id,
        target_field=payload.target_field,
        tenant_id=str(user.tenant_id),
        requested_by=str(user.user_id),
        max_lag=payload.max_lag,
        significance_level=payload.significance_level,
    )
    return {
        "analysis_id": result["analysis_id"],
        "case_id": case_id,
        "status": result["status"],
        "estimated_duration_seconds": 30,
        "poll_url": f"/api/v3/cases/{case_id}/causal/{result['analysis_id']}/status",
    }


@router.get("/{analysis_id}/status")
async def get_causal_status(
    case_id: str,
    analysis_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """인과 분석 진행 상태 조회."""
    auth_service.requires_role(user, ["admin", "staff", "viewer"])
    result = vision_runtime.get_causal_analysis(case_id, analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="analysis not found")
    return {
        "analysis_id": analysis_id,
        "status": result["status"],
        "started_at": result.get("started_at"),
        "completed_at": result.get("completed_at"),
        "error": result.get("error"),
    }


@router.get("/{analysis_id}/edges")
async def get_causal_edges(
    case_id: str,
    analysis_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """인과 분석 결과 엣지 목록 조회."""
    auth_service.requires_role(user, ["admin", "staff", "viewer"])
    result = vision_runtime.get_causal_analysis(case_id, analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="analysis not found")
    if result["status"] == "FAILED":
        raise HTTPException(status_code=409, detail=f"analysis failed: {result.get('error', 'unknown')}")
    if result["status"] != "COMPLETED":
        raise HTTPException(status_code=409, detail="analysis not completed")
    return {
        "case_id": case_id,
        "analysis_id": analysis_id,
        "edges": result["edges"],
        "impact_scores": result["impact_scores"],
        "total_edges": len(result["edges"]),
    }


@router.get("/{analysis_id}/graph")
async def get_causal_graph(
    case_id: str,
    analysis_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """인과 그래프 시각화용 데이터 (노드 + 엣지 + 메타데이터)."""
    auth_service.requires_role(user, ["admin", "staff", "viewer"])
    result = vision_runtime.get_causal_analysis(case_id, analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="analysis not found")
    if result["status"] != "COMPLETED":
        raise HTTPException(status_code=409, detail="analysis not completed")
    return {
        "case_id": case_id,
        "analysis_id": analysis_id,
        "edges": result["edges"],
        "impact_scores": result["impact_scores"],
        "metadata": result.get("metadata", {}),
        "completed_at": result.get("completed_at"),
    }


@router.get("/latest")
async def get_latest_causal_analysis(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """최신 완료된 인과 분석 결과 조회."""
    auth_service.requires_role(user, ["admin", "staff", "viewer"])
    analyses = vision_runtime.list_causal_analyses(case_id)
    completed = [a for a in analyses if a["status"] == "COMPLETED"]
    if not completed:
        raise HTTPException(status_code=404, detail="no completed analysis found")
    latest = max(completed, key=lambda a: a.get("completed_at", ""))
    return latest


@router.get("")
async def list_causal_analyses(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """인과 분석 이력 목록 조회."""
    auth_service.requires_role(user, ["admin", "staff", "viewer"])
    analyses = vision_runtime.list_causal_analyses(case_id)
    return {"data": analyses, "total": len(analyses)}
