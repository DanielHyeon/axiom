from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, auth_service
from app.services.vision_runtime import vision_runtime

router = APIRouter(prefix="/api/v3/cases/{case_id}/what-if", tags=["What-If"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_current_user(authorization: str = Header("mock_token", alias="Authorization")) -> CurrentUser:
    return auth_service.verify_token(authorization)


class ScenarioCreateRequest(BaseModel):
    scenario_name: str = Field(..., min_length=1, max_length=200)
    scenario_type: str = Field(..., pattern="^(BASELINE|OPTIMISTIC|PESSIMISTIC|STRESS|CUSTOM)$")
    base_scenario_id: str | None = None
    description: str | None = Field(default=None, max_length=1000)
    parameters: dict[str, Any] = Field(default_factory=dict)
    constraints: list[dict[str, Any]] = Field(default_factory=list)


class ScenarioUpdateRequest(BaseModel):
    scenario_name: str | None = Field(default=None, min_length=1, max_length=200)
    scenario_type: str | None = Field(default=None, pattern="^(BASELINE|OPTIMISTIC|PESSIMISTIC|STRESS|CUSTOM)$")
    description: str | None = Field(default=None, max_length=1000)
    parameters: dict[str, Any] | None = None
    constraints: list[dict[str, Any]] | None = None


class ComputeRequest(BaseModel):
    force_recompute: bool = False


class ProcessSimulationRequest(BaseModel):
    log_id: str
    baseline_throughput_per_day: float = 10.0
    bottleneck_shift_pct: float = 0.0
    period_days: int = Field(default=30, ge=1, le=3650)


def _ensure_auth(user: CurrentUser) -> None:
    auth_service.requires_role(user, ["admin", "staff"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_scenario(case_id: str, payload: ScenarioCreateRequest, user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    item = vision_runtime.create_scenario(case_id, payload.model_dump(), created_by=str(user.user_id))
    return item


@router.get("")
async def list_scenarios(case_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    items = vision_runtime.list_scenarios(case_id)
    return {"data": items, "total": len(items)}


def _compare_impl(case_id: str, scenario_ids: str) -> dict[str, Any]:
    ids = [x.strip() for x in scenario_ids.split(",") if x.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=422, detail="at least two scenario_ids are required")
    rows = []
    for sid in ids:
        item = vision_runtime.get_scenario(case_id, sid)
        if item and item.get("result"):
            rows.append(
                {
                    "scenario_id": sid,
                    "scenario_name": item["scenario_name"],
                    "npv_at_wacc": item["result"]["summary"]["npv_at_wacc"],
                    "feasibility_score": item["result"]["feasibility_score"],
                }
            )
    return {"case_id": case_id, "items": rows, "total": len(rows)}


@router.get("/compare")
async def compare_scenarios(
    case_id: str,
    scenario_ids: str = Query(..., min_length=1),
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_auth(user)
    return _compare_impl(case_id, scenario_ids)


@router.get("/{scenario_id}")
async def get_scenario(case_id: str, scenario_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    item = vision_runtime.get_scenario(case_id, scenario_id)
    if not item:
        raise HTTPException(status_code=404, detail="scenario not found")
    return item


@router.put("/{scenario_id}")
async def update_scenario(
    case_id: str,
    scenario_id: str,
    payload: ScenarioUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_auth(user)
    item = vision_runtime.get_scenario(case_id, scenario_id)
    if not item:
        raise HTTPException(status_code=404, detail="scenario not found")
    if item["status"] not in {"DRAFT", "READY", "COMPLETED"}:
        raise HTTPException(status_code=409, detail="scenario is not editable")
    changed = payload.model_dump(exclude_none=True)
    for key, value in changed.items():
        item[key] = value
    item["status"] = "DRAFT"
    item["updated_at"] = _now()
    item["started_at"] = None
    item["completed_at"] = None
    item["result"] = None
    vision_runtime.save_scenario(case_id, item)
    return item


@router.delete("/{scenario_id}")
async def delete_scenario(case_id: str, scenario_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    ok = vision_runtime.delete_scenario(case_id, scenario_id)
    if not ok:
        raise HTTPException(status_code=404, detail="scenario not found")
    return {"deleted": True, "scenario_id": scenario_id}


@router.post("/{scenario_id}/compute", status_code=status.HTTP_202_ACCEPTED)
async def compute_scenario(
    case_id: str,
    scenario_id: str,
    payload: ComputeRequest,
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_auth(user)
    item = vision_runtime.get_scenario(case_id, scenario_id)
    if not item:
        raise HTTPException(status_code=404, detail="scenario not found")
    if item["status"] == "COMPLETED" and not payload.force_recompute:
        return {"scenario_id": scenario_id, "status": "COMPLETED", "estimated_duration_seconds": 0}
    vision_runtime.compute_scenario(case_id, scenario_id)
    return {
        "scenario_id": scenario_id,
        "status": "COMPUTING",
        "estimated_duration_seconds": 1,
        "poll_url": f"/api/v3/cases/{case_id}/what-if/{scenario_id}/status",
    }


@router.get("/{scenario_id}/status")
async def scenario_status(case_id: str, scenario_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    item = vision_runtime.get_scenario(case_id, scenario_id)
    if not item:
        raise HTTPException(status_code=404, detail="scenario not found")
    status_value = item["status"]
    started_at = item.get("started_at")
    progress = 100 if status_value == "COMPLETED" else (50 if status_value == "COMPUTING" else 0)
    elapsed_seconds = 0
    if started_at:
        try:
            started_dt = datetime.fromisoformat(started_at)
            elapsed_seconds = max(0, int((datetime.now(timezone.utc) - started_dt).total_seconds()))
        except ValueError:
            elapsed_seconds = 0
    return {
        "scenario_id": scenario_id,
        "status": status_value,
        "progress_pct": progress,
        "started_at": started_at,
        "elapsed_seconds": elapsed_seconds,
    }


@router.get("/{scenario_id}/result")
async def scenario_result(case_id: str, scenario_id: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    item = vision_runtime.get_scenario(case_id, scenario_id)
    if not item:
        raise HTTPException(status_code=404, detail="scenario not found")
    if item["status"] != "COMPLETED" or not item["result"]:
        raise HTTPException(status_code=409, detail="scenario result not ready")
    return item["result"]


@router.post("/{scenario_id}/sensitivity")
async def sensitivity(case_id: str, scenario_id: str, payload: dict[str, Any], user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    item = vision_runtime.get_scenario(case_id, scenario_id)
    if not item:
        raise HTTPException(status_code=404, detail="scenario not found")
    base = item.get("parameters", {})
    target = str(payload.get("parameter") or "interest_rate")
    delta = float(payload.get("delta_pct") or 5.0)
    current = float(base.get(target, 1.0) or 1.0)
    elasticity = round(delta / max(current, 0.01), 3)
    return {"scenario_id": scenario_id, "parameter": target, "delta_pct": delta, "elasticity": elasticity}


@router.post("/{scenario_id}/breakeven")
async def breakeven(case_id: str, scenario_id: str, payload: dict[str, Any], user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    item = vision_runtime.get_scenario(case_id, scenario_id)
    if not item:
        raise HTTPException(status_code=404, detail="scenario not found")
    target_metric = str(payload.get("target_metric") or "overall_allocation_rate")
    target_value = float(payload.get("target_value") or 0.5)
    return {
        "scenario_id": scenario_id,
        "target_metric": target_metric,
        "target_value": target_value,
        "breakeven_parameter": "interest_rate",
        "breakeven_value": round(max(0.0, 8.0 - (target_value * 5.0)), 3),
    }


@router.post("/process-simulation")
async def process_simulation(case_id: str, payload: ProcessSimulationRequest, user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    shifted = payload.baseline_throughput_per_day * (1 + payload.bottleneck_shift_pct / 100.0)
    return {
        "case_id": case_id,
        "log_id": payload.log_id,
        "period_days": payload.period_days,
        "baseline_throughput_per_day": payload.baseline_throughput_per_day,
        "simulated_throughput_per_day": round(max(0.0, shifted), 3),
        "total_cases_processed": round(max(0.0, shifted) * payload.period_days, 3),
    }
