from __future__ import annotations

from datetime import datetime, timezone
import time

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, auth_service
from app.services.vision_runtime import VisionRuntimeError, vision_runtime

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
    started = time.perf_counter()
    success = False
    _ensure_run_permission(user)
    try:
        analysis = vision_runtime.create_root_cause_analysis(case_id, payload.model_dump(), requested_by=str(user.user_id))
        success = True
        return {
            "analysis_id": analysis["analysis_id"],
            "case_id": case_id,
            "status": analysis["status"],
            "estimated_duration_seconds": 90,
            "poll_url": f"/api/v3/cases/{case_id}/root-cause-analysis/status",
        }
    finally:
        vision_runtime.record_root_cause_call("run_analysis", success, (time.perf_counter() - started) * 1000.0)


@router.get("/root-cause-analysis/status")
async def get_root_cause_status(case_id: str, user: CurrentUser = Depends(get_current_user)):
    started = time.perf_counter()
    success = False
    _ensure_read_permission(user)
    try:
        analysis = vision_runtime.get_root_cause_status(case_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="analysis not found")
        success = True
        return {
            "analysis_id": analysis["analysis_id"],
            "status": analysis["status"],
            "progress": analysis["progress"],
            "started_at": analysis["started_at"],
            "elapsed_seconds": _elapsed_seconds(analysis["started_at"]),
        }
    finally:
        vision_runtime.record_root_cause_call("get_status", success, (time.perf_counter() - started) * 1000.0)


@router.get("/root-causes")
async def list_root_causes(case_id: str, user: CurrentUser = Depends(get_current_user)):
    started = time.perf_counter()
    success = False
    _ensure_read_permission(user)
    try:
        data = vision_runtime.get_root_causes(case_id)
        if not data:
            analysis = vision_runtime.get_root_cause_analysis(case_id)
            if not analysis:
                raise HTTPException(status_code=404, detail="analysis not found")
            raise HTTPException(status_code=409, detail="analysis not completed")
        success = True
        return data
    finally:
        vision_runtime.record_root_cause_call("list_root_causes", success, (time.perf_counter() - started) * 1000.0)


@router.post("/counterfactual")
async def run_counterfactual(
    case_id: str,
    payload: CounterfactualRequest,
    user: CurrentUser = Depends(get_current_user),
):
    started = time.perf_counter()
    success = False
    _ensure_run_permission(user)
    try:
        result = vision_runtime.run_counterfactual(case_id, payload.model_dump())
        success = True
        return result
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        vision_runtime.record_root_cause_call("run_counterfactual", success, (time.perf_counter() - started) * 1000.0)


@router.get("/causal-timeline")
async def get_causal_timeline(case_id: str, user: CurrentUser = Depends(get_current_user)):
    started = time.perf_counter()
    success = False
    _ensure_read_permission(user)
    try:
        result = vision_runtime.get_causal_timeline(case_id)
        success = True
        return result
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        vision_runtime.record_root_cause_call("get_causal_timeline", success, (time.perf_counter() - started) * 1000.0)


@router.get("/root-cause-impact")
async def get_root_cause_impact(case_id: str, user: CurrentUser = Depends(get_current_user)):
    started = time.perf_counter()
    success = False
    _ensure_read_permission(user)
    try:
        result = vision_runtime.get_root_cause_impact(case_id)
        success = True
        return result
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        vision_runtime.record_root_cause_call("get_root_cause_impact", success, (time.perf_counter() - started) * 1000.0)


@router.get("/causal-graph")
async def get_causal_graph(case_id: str, user: CurrentUser = Depends(get_current_user)):
    started = time.perf_counter()
    success = False
    _ensure_read_permission(user)
    try:
        result = vision_runtime.get_causal_graph(case_id)
        success = True
        return result
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        vision_runtime.record_root_cause_call("get_causal_graph", success, (time.perf_counter() - started) * 1000.0)


@router.get("/root-cause/process-bottleneck")
async def get_process_bottleneck_root_cause(
    case_id: str,
    process_id: str,
    bottleneck_activity: str | None = None,
    max_causes: int = 5,
    include_explanation: bool = True,
    user: CurrentUser = Depends(get_current_user),
):
    started = time.perf_counter()
    success = False
    _ensure_read_permission(user)
    try:
        result = vision_runtime.get_process_bottleneck_root_cause(
            case_id=case_id,
            process_id=process_id,
            bottleneck_activity=bottleneck_activity,
            max_causes=max_causes,
            include_explanation=include_explanation,
        )
        success = True
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VisionRuntimeError as exc:
        if exc.code == "SYNAPSE_UNAVAILABLE":
            raise HTTPException(status_code=502, detail={"code": exc.code, "message": exc.message}) from exc
        if exc.code == "PROCESS_MODEL_NOT_FOUND":
            raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc
        if exc.code == "INSUFFICIENT_PROCESS_DATA":
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from exc
        raise HTTPException(status_code=500, detail={"code": "RUNTIME_ERROR", "message": exc.message}) from exc
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        vision_runtime.record_root_cause_call("get_process_bottleneck", success, (time.perf_counter() - started) * 1000.0)
