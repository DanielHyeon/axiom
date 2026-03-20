"""피드백 통계 API 엔드포인트.

피드백 대시보드에서 사용하는 통계 조회 API를 제공한다.
admin, manager 역할만 접근 가능하다.
"""

from fastapi import APIRouter, Depends, Query

from app.api.text2sql import get_current_user
from app.core.auth import CurrentUser, auth_service
from app.core.feedback_analytics import feedback_analytics

router = APIRouter(prefix="/feedback/stats", tags=["Feedback Stats"])


def _require_manager(user: CurrentUser) -> CurrentUser:
    """admin 또는 manager 역할인지 확인한다."""
    auth_service.requires_role(user, ["admin", "manager"])
    return user


@router.get("/summary")
async def get_summary(
    date_from: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="시작일 (YYYY-MM-DD)"),
    date_to: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="종료일 (YYYY-MM-DD)"),
    user: CurrentUser = Depends(get_current_user),
):
    """피드백 요약 통계."""
    _require_manager(user)
    data = await feedback_analytics.get_summary(
        tenant_id=str(user.tenant_id), date_from=date_from, date_to=date_to
    )
    return {"success": True, "data": data}


@router.get("/trend")
async def get_trend(
    date_from: str = Query(...),
    date_to: str = Query(...),
    granularity: str = Query(default="day", pattern="^(day|week)$"),
    user: CurrentUser = Depends(get_current_user),
):
    """일별/주별 피드백 추이."""
    _require_manager(user)
    data = await feedback_analytics.get_trend(
        tenant_id=str(user.tenant_id),
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
    )
    return {"success": True, "data": data}


@router.get("/failures")
async def get_failures(
    date_from: str = Query(...),
    date_to: str = Query(...),
    limit: int = Query(default=20, le=100),
    user: CurrentUser = Depends(get_current_user),
):
    """실패 패턴 분석."""
    _require_manager(user)
    data = await feedback_analytics.get_failure_patterns(
        tenant_id=str(user.tenant_id),
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return {"success": True, "data": data}


@router.get("/by-datasource")
async def get_by_datasource(
    date_from: str = Query(...),
    date_to: str = Query(...),
    user: CurrentUser = Depends(get_current_user),
):
    """데이터소스별 피드백 분포."""
    _require_manager(user)
    data = await feedback_analytics.get_datasource_breakdown(
        tenant_id=str(user.tenant_id),
        date_from=date_from,
        date_to=date_to,
    )
    return {"success": True, "data": data}


@router.get("/top-failed")
async def get_top_failed(
    date_from: str = Query(...),
    date_to: str = Query(...),
    limit: int = Query(default=10, le=50),
    user: CurrentUser = Depends(get_current_user),
):
    """가장 많이 실패한 질문 TOP-N."""
    _require_manager(user)
    data = await feedback_analytics.get_top_failed_queries(
        tenant_id=str(user.tenant_id),
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return {"success": True, "data": data}
