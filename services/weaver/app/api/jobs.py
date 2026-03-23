"""G35: Job API — 작업 관리 REST 엔드포인트.

프론트엔드 JobProgressPanel과 연동하여 작업 상태 조회, 취소, 목록을 제공한다.
인증 및 테넌트 격리는 기존 Weaver 패턴(CurrentUser + auth_service)을 따른다.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel

from app.core.auth import AuthService, CurrentUser
from app.jobs.job_service import job_service
from app.models.job import JobRun, JobStatus, JobType

logger = logging.getLogger("axiom.weaver.api.jobs")

router = APIRouter(prefix="/api/v3/weaver/jobs", tags=["jobs"])

# 인증 서비스 인스턴스
_auth = AuthService()


# ── 인증 의존성 (기존 Weaver 패턴) ── #

async def _get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    """JWT 토큰에서 현재 사용자 추출 — 모든 엔드포인트에 적용"""
    return _auth.verify_token(authorization)


# ── 응답 스키마 ── #

class JobListResponse(BaseModel):
    success: bool = True
    data: list[dict]
    total: int


class JobDetailResponse(BaseModel):
    success: bool = True
    data: dict


# ── 엔드포인트 ── #

@router.get("")
async def list_jobs(
    user: CurrentUser = Depends(_get_current_user),
    job_type: JobType | None = None,
    status: JobStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> JobListResponse:
    """테넌트별 작업 목록 조회 — tenant_id는 인증된 사용자에서 추출"""
    jobs = job_service.list_by_tenant(user.tenant_id, job_type, status, limit)
    return JobListResponse(
        data=[j.model_dump(mode="json") for j in jobs],
        total=len(jobs),
    )


@router.get("/{run_id}")
async def get_job(
    run_id: str,
    user: CurrentUser = Depends(_get_current_user),
) -> JobDetailResponse:
    """작업 상세 조회"""
    job = job_service.get(run_id)
    if not job or job.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {run_id}")
    return JobDetailResponse(data=job.model_dump(mode="json"))


@router.post("/{run_id}/cancel")
async def cancel_job(
    run_id: str,
    user: CurrentUser = Depends(_get_current_user),
) -> JobDetailResponse:
    """작업 취소 — 본인 테넌트 작업만 취소 가능"""
    job = job_service.get(run_id)
    if not job or job.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail=f"취소할 수 없는 작업: {run_id}")
    cancelled = job_service.cancel(run_id)
    if not cancelled:
        raise HTTPException(status_code=409, detail=f"취소 불가 상태: {job.status}")
    return JobDetailResponse(data=cancelled.model_dump(mode="json"))


@router.post("/{run_id}/heartbeat")
async def heartbeat(
    run_id: str,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """워커 heartbeat 갱신"""
    ok = job_service.heartbeat(run_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"heartbeat 대상 작업 없음: {run_id}")
    return {"success": True}
