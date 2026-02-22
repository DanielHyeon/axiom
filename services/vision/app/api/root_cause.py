from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, auth_service
from app.services.vision_runtime import vision_runtime

router = APIRouter(prefix="/api/v3/cases/{case_id}", tags=["Root-Cause"])


async def get_current_user(authorization: str = Header("mock_token", alias="Authorization")) -> CurrentUser:
    return auth_service.verify_token(authorization)


class RootCauseAnalysisRequest(BaseModel):
    analysis_depth: str = Field(default="full", pattern="^(quick|full)$")
    max_root_causes: int = Field(default=5, ge=1, le=10)
    include_counterfactuals: bool = True
    include_explanation: bool = True
    language: str = Field(default="ko", pattern="^(ko|en)$")


class CounterfactualRequest(BaseModel):
    variable: str = Field(..., min_length=1, max_length=120)
    actual_value: float
    counterfactual_value: float
    question: str | None = Field(default=None, max_length=500)


def _elapsed_seconds(started_at: str | None) -> int:
    if not started_at:
        return 0
    try:
        started_dt = datetime.fromisoformat(started_at)
    except ValueError:
        return 0
    return max(0, int((datetime.now(timezone.utc) - started_dt).total_seconds()))


def _ensure_run_permission(user: CurrentUser) -> None:
    auth_service.requires_role(user, ["admin", "staff"])


def _ensure_read_permission(user: CurrentUser) -> None:
    auth_service.requires_role(user, ["admin", "staff", "viewer"])


@router.post("/root-cause-analysis", status_code=status.HTTP_202_ACCEPTED)
async def run_root_cause_analysis(
    case_id: str,
    payload: RootCauseAnalysisRequest,
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_run_permission(user)
    analysis = vision_runtime.create_root_cause_analysis(case_id, payload.model_dump(), requested_by=str(user.user_id))
    return {
        "analysis_id": analysis["analysis_id"],
        "case_id": case_id,
        "status": analysis["status"],
        "estimated_duration_seconds": 90,
        "poll_url": f"/api/v3/cases/{case_id}/root-cause-analysis/status",
    }


@router.get("/root-cause-analysis/status")
async def get_root_cause_status(case_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_read_permission(user)
    analysis = vision_runtime.get_root_cause_status(case_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="analysis not found")
    return {
        "analysis_id": analysis["analysis_id"],
        "status": analysis["status"],
        "progress": analysis["progress"],
        "started_at": analysis["started_at"],
        "elapsed_seconds": _elapsed_seconds(analysis["started_at"]),
    }


@router.get("/root-causes")
async def list_root_causes(case_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_read_permission(user)
    data = vision_runtime.get_root_causes(case_id)
    if not data:
        analysis = vision_runtime.get_root_cause_analysis(case_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="analysis not found")
        raise HTTPException(status_code=409, detail="analysis not completed")
    return data


@router.post("/counterfactual")
async def run_counterfactual(
    case_id: str,
    payload: CounterfactualRequest,
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_run_permission(user)
    try:
        return vision_runtime.run_counterfactual(case_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/causal-timeline")
async def get_causal_timeline(case_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_read_permission(user)
    try:
        return vision_runtime.get_causal_timeline(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/root-cause-impact")
async def get_root_cause_impact(case_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_read_permission(user)
    try:
        return vision_runtime.get_root_cause_impact(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/causal-graph")
async def get_causal_graph(case_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_read_permission(user)
    try:
        return vision_runtime.get_causal_graph(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/root-cause/process-bottleneck")
async def get_process_bottleneck_root_cause(
    case_id: str,
    process_id: str,
    bottleneck_activity: str | None = None,
    max_causes: int = 5,
    include_explanation: bool = True,
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_read_permission(user)
    try:
        return vision_runtime.get_process_bottleneck_root_cause(
            case_id=case_id,
            process_id=process_id,
            bottleneck_activity=bottleneck_activity,
            max_causes=max_causes,
            include_explanation=include_explanation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        if str(exc) == "SYNAPSE_UNAVAILABLE":
            raise HTTPException(
                status_code=502,
                detail={"code": "SYNAPSE_UNAVAILABLE", "message": "process mining service unavailable"},
            ) from exc
        raise HTTPException(status_code=500, detail="internal error") from exc
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
