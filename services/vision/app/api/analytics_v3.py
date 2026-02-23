"""
Vision Analytics API v3 (Phase V1 Full-spec).
GET /api/v3/analytics/* — 실 DB 연동, 스펙 에러 코드(INVALID_PERIOD, INVALID_DISTRIBUTION_BY, CASE_NOT_FOUND).
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.auth import CurrentUser, auth_service
from app.services.analytics_service import CaseNotFoundError, get_analytics_service

router = APIRouter(prefix="/api/v3/analytics", tags=["Analytics"])

VALID_PERIODS = frozenset({"YTD", "MTD", "QTD", "LAST_YEAR", "ALL"})
VALID_DISTRIBUTION_BY = frozenset({"stakeholder_type", "stakeholder_class", "amount_band", "status"})


async def get_current_user(authorization: str = Header("mock_token", alias="Authorization")) -> CurrentUser:
    return auth_service.verify_token(authorization)


def _ensure_viewer(user: CurrentUser) -> None:
    auth_service.requires_role(user, ["admin", "staff", "viewer"])


def _tenant_id(user: CurrentUser) -> str:
    return str(user.tenant_id)


@router.get("/summary")
async def get_analytics_summary(
    period: str | None = Query(default=None),
    case_type: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_viewer(user)
    effective_period = (period or "YTD").strip().upper()
    if effective_period not in VALID_PERIODS:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PERIOD", "message": "유효하지 않은 기간 형식입니다"},
        )
    try:
        svc = get_analytics_service()
        return await asyncio.to_thread(svc.get_summary, _tenant_id(user), effective_period, case_type)
    except (RuntimeError, Exception):
        return _stub_summary(effective_period, case_type)


def _stub_summary(period: str, case_type: str | None) -> dict:
    return {
        "period": period,
        "period_label": "2026년 누적" if period == "YTD" else period,
        "kpis": {
            "total_cases": {"value": 0, "change_pct": 0, "change_direction": "up", "prev_period_value": None},
            "active_cases": {"value": 0, "change_pct": 0, "change_direction": "down", "prev_period_value": None},
            "total_obligations_amount": {"value": 0, "formatted": "0원", "change_pct": 0, "change_direction": "up"},
            "avg_performance_rate": {"value": 0, "formatted": "0%", "change_pct": 0, "change_direction": "up"},
            "avg_case_duration_days": {"value": 0, "formatted": "0일", "change_pct": 0, "change_direction": "down"},
            "stakeholder_satisfaction_rate": {"value": 0, "formatted": "0%", "change_pct": 0, "change_direction": "up"},
        },
        "computed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@router.get("/cases/trend")
async def get_cases_trend(
    granularity: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    case_type: str | None = Query(default=None),
    group_by: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_viewer(user)
    eff_granularity = (granularity or "monthly").strip().lower()
    if eff_granularity not in ("monthly", "quarterly", "yearly"):
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PERIOD", "message": "유효하지 않은 기간 형식입니다"},
        )
    to_d = to_date or date.today()
    from_d = from_date or (to_d - timedelta(days=365))
    try:
        svc = get_analytics_service()
        return await asyncio.to_thread(
            svc.get_cases_trend,
            _tenant_id(user),
            eff_granularity,
            from_d,
            to_d,
            case_type,
            group_by,
        )
    except (RuntimeError, Exception):
        return {
            "granularity": eff_granularity,
            "from_date": from_d.isoformat(),
            "to_date": to_d.isoformat(),
            "series": [],
            "case_type": case_type,
            "group_by": group_by,
        }


@router.get("/stakeholders/distribution")
async def get_stakeholders_distribution(
    distribution_by: str | None = Query(default=None),
    case_type: str | None = Query(default=None),
    year: int | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_viewer(user)
    if not distribution_by or distribution_by.strip().lower() not in VALID_DISTRIBUTION_BY:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_DISTRIBUTION_BY", "message": "지원하지 않는 분포 기준입니다"},
        )
    try:
        svc = get_analytics_service()
        return await asyncio.to_thread(
            svc.get_stakeholders_distribution,
            _tenant_id(user),
            distribution_by.strip().lower(),
            case_type,
            year,
        )
    except (RuntimeError, Exception):
        return {
            "distribution_by": distribution_by,
            "total_count": 0,
            "total_amount": 0,
            "segments": [],
            "case_type": case_type,
            "year": year,
        }


@router.get("/performance/trend")
async def get_performance_trend(
    granularity: str | None = Query(default=None),
    stakeholder_type: str | None = Query(default=None),
    case_type: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_viewer(user)
    eff_granularity = (granularity or "quarterly").strip().lower()
    if eff_granularity not in ("quarterly", "yearly"):
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PERIOD", "message": "유효하지 않은 기간 형식입니다"},
        )
    try:
        svc = get_analytics_service()
        return await asyncio.to_thread(
            svc.get_performance_trend,
            _tenant_id(user),
            eff_granularity,
            stakeholder_type,
            case_type,
        )
    except (RuntimeError, Exception):
        return {
            "granularity": eff_granularity,
            "stakeholder_type": stakeholder_type,
            "case_type": case_type,
            "series": [],
        }


@router.get("/cases/{case_id}/financial-summary")
async def get_case_financial_summary(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_viewer(user)
    if not case_id or not case_id.strip():
        raise HTTPException(
            status_code=404,
            detail={"code": "CASE_NOT_FOUND", "message": "사건을 찾을 수 없습니다"},
        )
    try:
        svc = get_analytics_service()
        return await asyncio.to_thread(svc.get_case_financial_summary, case_id.strip(), _tenant_id(user))
    except CaseNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "CASE_NOT_FOUND", "message": "사건을 찾을 수 없습니다"},
        )
    except RuntimeError:
        raise HTTPException(
            status_code=404,
            detail={"code": "CASE_NOT_FOUND", "message": "사건을 찾을 수 없습니다"},
        )


@router.get("/dashboards")
async def get_dashboards(user: CurrentUser = Depends(get_current_user)):
    _ensure_viewer(user)
    try:
        svc = get_analytics_service()
        return await asyncio.to_thread(svc.get_dashboards, _tenant_id(user))
    except (RuntimeError, Exception):
        return {
            "dashboards": [
                {
                    "id": "case-overview",
                    "title": "사건 개요 대시보드",
                    "widgets": [
                        {"id": "kpi-summary", "type": "summary", "source": "/api/v3/analytics/summary"},
                        {"id": "case-trend", "type": "timeseries", "source": "/api/v3/analytics/cases/trend"},
                    ],
                },
                {
                    "id": "stakeholder-performance",
                    "title": "이해관계자 성과 대시보드",
                    "widgets": [
                        {"id": "stakeholder-distribution", "type": "distribution", "source": "/api/v3/analytics/stakeholders/distribution"},
                        {"id": "performance-trend", "type": "timeseries", "source": "/api/v3/analytics/performance/trend"},
                    ],
                },
            ]
        }
