"""비즈니스 캘린더 + 시나리오 저장소 API.

시계열 데이터의 비영업일 필터링과
Redis 기반 시나리오 영속화 엔드포인트를 제공한다.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.services.business_calendar import (
    aggregate_to_business_days,
    filter_business_days,
    get_business_days_in_range,
    is_business_day,
)
from app.services.scenario_store import (
    delete_scenario,
    list_scenarios,
    load_scenario,
    save_scenario,
)

# ── 비즈니스 캘린더 라우터 ── #
router = APIRouter(prefix="/api/v1/vision/calendar", tags=["비즈니스 캘린더"])

# ── 시나리오 저장소 라우터 ── #
scenario_router = APIRouter(prefix="/api/v1/vision/scenarios", tags=["시나리오 저장소"])


# ---------------------------------------------------------------------------
# 요청/응답 모델
# ---------------------------------------------------------------------------

class FilterRequest(BaseModel):
    """비영업일 필터 요청."""
    dates: list[str] = Field(..., min_length=1, description="ISO 날짜 문자열 목록")
    values: list[float] = Field(..., min_length=1, description="각 날짜에 대응하는 값")
    include_saturday: bool = Field(default=False, description="토요일 포함 여부")


class RangeRequest(BaseModel):
    """기간 내 영업일 조회 요청."""
    start: str = Field(..., description="시작일 (ISO date)")
    end: str = Field(..., description="종료일 (ISO date)")
    include_saturday: bool = False


class AggregateRequest(BaseModel):
    """비영업일 데이터 집계 요청."""
    dates: list[str] = Field(..., min_length=1)
    values: list[float] = Field(..., min_length=1)
    method: str = Field(default="mean", pattern="^(mean|sum|last|first|max|min)$")


class ScenarioSaveRequest(BaseModel):
    """시나리오 저장 요청."""
    id: str | None = None
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    interventions: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 비즈니스 캘린더 엔드포인트
# ---------------------------------------------------------------------------

@router.post("/filter")
async def api_filter_business_days(body: FilterRequest):
    """시계열 데이터에서 비영업일 제거."""
    dates, values = filter_business_days(
        body.dates, body.values, include_saturday=body.include_saturday,
    )
    return {
        "success": True,
        "data": {
            "dates": [d.isoformat() for d in dates],
            "values": values,
            "removed_count": len(body.dates) - len(dates),
        },
    }


@router.post("/business-days")
async def api_business_days_range(body: RangeRequest):
    """기간 내 영업일 목록 조회."""
    try:
        start = date.fromisoformat(body.start)
        end = date.fromisoformat(body.end)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"날짜 형식 오류: {e}")

    days = get_business_days_in_range(start, end, include_saturday=body.include_saturday)
    return {
        "success": True,
        "data": {
            "dates": [d.isoformat() for d in days],
            "count": len(days),
        },
    }


@router.post("/aggregate")
async def api_aggregate(body: AggregateRequest):
    """비영업일 데이터를 영업일로 집계."""
    dates, values = aggregate_to_business_days(body.dates, body.values, body.method)
    return {
        "success": True,
        "data": {
            "dates": [d.isoformat() for d in dates],
            "values": values,
        },
    }


@router.get("/is-business-day/{date_str}")
async def api_is_business_day(date_str: str):
    """특정 날짜가 영업일인지 확인."""
    try:
        d = date.fromisoformat(date_str)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"날짜 형식 오류: {e}")

    result = is_business_day(d)
    return {"success": True, "data": {"date": date_str, "is_business_day": result}}


# ---------------------------------------------------------------------------
# 시나리오 저장소 엔드포인트
# ---------------------------------------------------------------------------

def _get_redis(request: Request):
    """Request.app.state에서 Redis 클라이언트를 꺼낸다. 없으면 None."""
    return getattr(getattr(request, "app", None), "state", None) and getattr(
        request.app.state, "redis", None
    )


def _get_tenant(request: Request) -> str:
    """TenantMiddleware가 설정한 tenant_id를 추출한다. 없으면 401."""
    tid = getattr(getattr(request, "state", None), "tenant_id", "")
    if not tid:
        raise HTTPException(status_code=401, detail="tenant_id 누락")
    return tid


@scenario_router.post("")
async def api_save_scenario(
    body: ScenarioSaveRequest,
    request: Request,
):
    """시나리오를 Redis에 저장한다."""
    tenant_id = _get_tenant(request)
    redis = _get_redis(request)
    scenario_id = await save_scenario(
        redis_client=redis,
        tenant_id=tenant_id,
        scenario=body.model_dump(),
    )
    return {"success": True, "data": {"scenario_id": scenario_id}}


@scenario_router.get("")
async def api_list_scenarios(
    request: Request,
):
    """테넌트의 시나리오 목록을 조회한다."""
    tenant_id = _get_tenant(request)
    redis = _get_redis(request)
    items = await list_scenarios(redis_client=redis, tenant_id=tenant_id)
    return {"success": True, "data": items, "total": len(items)}


@scenario_router.get("/{scenario_id}")
async def api_get_scenario(
    scenario_id: str,
    request: Request,
):
    """시나리오 1건을 조회한다."""
    tenant_id = _get_tenant(request)
    redis = _get_redis(request)
    scenario = await load_scenario(redis_client=redis, tenant_id=tenant_id, scenario_id=scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="시나리오를 찾을 수 없습니다")
    return {"success": True, "data": scenario}


@scenario_router.delete("/{scenario_id}")
async def api_delete_scenario(
    scenario_id: str,
    request: Request,
):
    """시나리오를 삭제한다."""
    tenant_id = _get_tenant(request)
    redis = _get_redis(request)
    ok = await delete_scenario(redis_client=redis, tenant_id=tenant_id, scenario_id=scenario_id)
    if not ok:
        raise HTTPException(status_code=404, detail="시나리오를 찾을 수 없습니다")
    return {"success": True, "data": {"deleted": True, "scenario_id": scenario_id}}
