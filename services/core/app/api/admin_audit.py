"""관리자용 감사 로그 + AI 사용량 API.

EventOutbox 테이블에서 이벤트를 조회하여 감사 로그로 제공하고,
NL2SQL/LLM 호출 이력을 집계하여 AI 비용 모니터링을 지원한다.

Sprint 3: 스텁 구현 — 실제 DB 쿼리는 Sprint 4+에서 연결.
현재는 EventOutbox 기반 mock 데이터를 반환한다.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user

logger = logging.getLogger("axiom.core.api.admin_audit")

router = APIRouter(prefix="/api/v3/core/admin", tags=["관리자 감사/AI"])


# ── 요청/응답 모델 ── #


class AuditLogItem(BaseModel):
    """감사 로그 항목 — EventOutbox 기반"""
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    tenant_id: str
    status: str  # PENDING, PUBLISHED, FAILED
    created_at: datetime
    published_at: datetime | None = None
    payload_summary: str = ""  # payload에서 추출한 1줄 요약 (민감 정보 제외)


class AuditLogListResponse(BaseModel):
    """감사 로그 목록 응답"""
    success: bool = True
    data: list[AuditLogItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 50


class AIUsageItem(BaseModel):
    """AI 사용량 일별 집계 항목"""
    date: str  # YYYY-MM-DD
    nl2sql_calls: int = 0
    llm_calls: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class AIUsageResponse(BaseModel):
    """AI 사용량 집계 응답"""
    success: bool = True
    period_days: int = 30
    summary: dict[str, Any] = Field(default_factory=dict)
    daily: list[AIUsageItem] = Field(default_factory=list)


class AIUsageByCaller(BaseModel):
    """호출자별 AI 사용량"""
    user_id: str
    user_email: str
    nl2sql_calls: int = 0
    llm_calls: int = 0
    total_tokens: int = 0


class AIUsageByCallerResponse(BaseModel):
    """호출자별 AI 사용량 응답"""
    success: bool = True
    period_days: int = 30
    data: list[AIUsageByCaller] = Field(default_factory=list)


# ── 권한 검증 헬퍼 ── #


def _require_admin(user: dict) -> None:
    """admin 또는 manager 역할이 아니면 403을 던진다."""
    role = user.get("role", "viewer")
    if role not in ("admin", "manager"):
        raise HTTPException(
            status_code=403,
            detail="admin/manager 역할만 접근 가능합니다",
        )


# ── Mock 데이터 생성 (Sprint 3 스텁) ── #


def _generate_mock_audit_logs(
    tenant_id: str,
    page: int,
    size: int,
    event_type: str | None,
    since: datetime | None,
) -> tuple[list[AuditLogItem], int]:
    """EventOutbox 기반 mock 감사 로그를 생성한다.

    Sprint 4+에서 실제 DB 쿼리로 교체 예정:
    SELECT * FROM core.event_outbox
    WHERE tenant_id = :tenant_id
    ORDER BY created_at DESC
    LIMIT :size OFFSET :offset
    """
    # 데모용 이벤트 타입 목록
    _event_types = [
        "SEMANTIC_ENTITY_PUBLISHED",
        "SEMANTIC_MEASURE_PUBLISHED",
        "ONTOLOGY_CONCEPT_CREATED",
        "QUALITY_SCORE_UPDATED",
        "CONTEXT_PACK_GENERATED",
        "JOIN_CONTRACT_CREATED",
        "NL2SQL_QUERY_EXECUTED",
        "USER_LOGIN",
        "DATASOURCE_CONNECTED",
        "CASE_CREATED",
    ]

    now = datetime.now(timezone.utc)
    total = 127  # mock 전체 건수
    items: list[AuditLogItem] = []

    # since 필터 적용 시 mock 건수 줄이기
    if since and (now - since).days < 7:
        total = 23

    for i in range(size):
        idx = (page - 1) * size + i
        if idx >= total:
            break

        et = _event_types[idx % len(_event_types)]
        # event_type 필터
        if event_type and et != event_type:
            continue

        created = now - timedelta(hours=idx * 2, minutes=idx * 7)
        items.append(AuditLogItem(
            event_id=str(uuid.uuid4()),
            event_type=et,
            aggregate_type=et.split("_")[0].lower(),
            aggregate_id=str(uuid.uuid4())[:8],
            tenant_id=tenant_id,
            status="PUBLISHED" if idx % 5 != 0 else "PENDING",
            created_at=created,
            published_at=created + timedelta(seconds=2) if idx % 5 != 0 else None,
            payload_summary=f"[mock] {et} 이벤트 #{idx + 1}",
        ))

    return items, total


def _generate_mock_ai_usage(days: int) -> tuple[dict[str, Any], list[AIUsageItem]]:
    """NL2SQL/LLM 호출 mock 집계를 생성한다.

    Sprint 4+에서 실제 데이터로 교체 예정:
    - Oracle 서비스의 query_history 테이블
    - LLM 호출 로그 (Redis 또는 별도 테이블)
    """
    now = datetime.now(timezone.utc)
    daily: list[AIUsageItem] = []
    total_nl2sql = 0
    total_llm = 0
    total_tokens = 0
    total_cost = 0.0

    for d in range(min(days, 30)):
        date = (now - timedelta(days=d)).strftime("%Y-%m-%d")
        # 점진적으로 증가하는 mock 패턴 (최근일수록 많음)
        nl2sql = max(5, 30 - d * 1)
        llm = max(3, 20 - d)
        tokens = nl2sql * 850 + llm * 1200  # 평균 토큰 추정
        # GPT-4o 가격 기준 대략 추정 ($5/1M input, $15/1M output)
        cost = round(tokens * 0.00001, 4)

        daily.append(AIUsageItem(
            date=date,
            nl2sql_calls=nl2sql,
            llm_calls=llm,
            total_tokens=tokens,
            estimated_cost_usd=cost,
        ))
        total_nl2sql += nl2sql
        total_llm += llm
        total_tokens += tokens
        total_cost += cost

    summary = {
        "total_nl2sql_calls": total_nl2sql,
        "total_llm_calls": total_llm,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(total_cost, 2),
        "avg_daily_nl2sql": round(total_nl2sql / max(len(daily), 1), 1),
        "avg_daily_llm": round(total_llm / max(len(daily), 1), 1),
        "top_model": "gpt-4o",
        "period_days": days,
    }

    return summary, daily


# ── 엔드포인트 ── #


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(50, ge=1, le=200, description="페이지 크기"),
    event_type: str | None = Query(None, description="이벤트 타입 필터 (예: NL2SQL_QUERY_EXECUTED)"),
    since: datetime | None = Query(None, description="이 시각 이후 이벤트만 조회 (ISO 8601)"),
):
    """감사 로그 조회 — EventOutbox 기반.

    admin/manager 역할만 접근 가능하다.
    EventOutbox 테이블에서 이벤트를 페이지네이션으로 조회한다.

    Sprint 3: mock 데이터 반환. Sprint 4+에서 실제 DB 쿼리 연결.
    """
    _require_admin(user)
    tenant_id = user.get("tenant_id", "")

    items, total = _generate_mock_audit_logs(
        tenant_id=tenant_id,
        page=page,
        size=size,
        event_type=event_type,
        since=since,
    )

    logger.info(
        "감사 로그 조회: tenant=%s, page=%d, size=%d, total=%d",
        tenant_id, page, size, total,
    )

    return AuditLogListResponse(
        data=items,
        total=total,
        page=page,
        size=size,
    )


@router.get("/ai-usage", response_model=AIUsageResponse)
async def get_ai_usage(
    user: dict = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
):
    """AI 사용량 집계 — NL2SQL/LLM 호출 횟수, 토큰, 비용.

    admin/manager 역할만 접근 가능하다.
    일별 집계와 전체 요약을 반환한다.

    Sprint 3: mock 데이터 반환. Sprint 4+에서 실제 데이터 연결.
    실제 구현 시 데이터 소스:
    - Oracle 서비스 query_history 테이블 (NL2SQL 호출)
    - LLM 호출 로그 (토큰/비용 추적)
    """
    _require_admin(user)

    summary, daily = _generate_mock_ai_usage(days)

    logger.info(
        "AI 사용량 조회: tenant=%s, days=%d, total_calls=%d",
        user.get("tenant_id", ""),
        days,
        summary.get("total_nl2sql_calls", 0) + summary.get("total_llm_calls", 0),
    )

    return AIUsageResponse(
        period_days=days,
        summary=summary,
        daily=daily,
    )


@router.get("/ai-usage/by-caller", response_model=AIUsageByCallerResponse)
async def get_ai_usage_by_caller(
    user: dict = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
):
    """호출자별 AI 사용량 집계.

    어떤 사용자가 NL2SQL/LLM을 많이 사용하는지 확인한다.
    관리자가 비용 할당 및 사용량 모니터링에 활용한다.

    Sprint 3: mock 데이터 반환.
    """
    _require_admin(user)

    # Mock 호출자별 데이터
    mock_callers = [
        AIUsageByCaller(
            user_id="user-001",
            user_email="analyst@example.com",
            nl2sql_calls=245,
            llm_calls=89,
            total_tokens=312000,
        ),
        AIUsageByCaller(
            user_id="user-002",
            user_email="manager@example.com",
            nl2sql_calls=128,
            llm_calls=45,
            total_tokens=167000,
        ),
        AIUsageByCaller(
            user_id="user-003",
            user_email="engineer@example.com",
            nl2sql_calls=67,
            llm_calls=120,
            total_tokens=198000,
        ),
    ]

    return AIUsageByCallerResponse(
        period_days=days,
        data=mock_callers,
    )


@router.get("/audit-logs/event-types")
async def get_event_types(
    user: dict = Depends(get_current_user),
) -> dict:
    """사용 가능한 이벤트 타입 목록을 반환한다.

    프론트엔드 필터 드롭다운에서 사용한다.
    """
    _require_admin(user)

    # 현재 시스템에서 정의된 이벤트 타입 목록
    event_types = [
        {"type": "SEMANTIC_ENTITY_PUBLISHED", "category": "semantic", "description": "시멘틱 엔티티 배포"},
        {"type": "SEMANTIC_MEASURE_PUBLISHED", "category": "semantic", "description": "시멘틱 지표 배포"},
        {"type": "SEMANTIC_DIMENSION_PUBLISHED", "category": "semantic", "description": "시멘틱 차원 배포"},
        {"type": "SEMANTIC_MEASURE_DEPRECATED", "category": "semantic", "description": "시멘틱 지표 폐기"},
        {"type": "JOIN_CONTRACT_CREATED", "category": "semantic", "description": "조인 계약 생성"},
        {"type": "GRAIN_CONTRACT_CREATED", "category": "semantic", "description": "그레인 계약 생성"},
        {"type": "ONTOLOGY_CONCEPT_CREATED", "category": "ontology", "description": "온톨로지 개념 생성"},
        {"type": "ONTOLOGY_CONCEPT_UPDATED", "category": "ontology", "description": "온톨로지 개념 수정"},
        {"type": "ONTOLOGY_BINDING_VALIDATED", "category": "ontology", "description": "온톨로지 바인딩 검증"},
        {"type": "CONTEXT_PACK_GENERATED", "category": "ai", "description": "AI 컨텍스트팩 생성"},
        {"type": "SEMANTIC_RELEASE_DEPLOYED", "category": "release", "description": "시멘틱 릴리즈 배포"},
        {"type": "QUALITY_SCORE_UPDATED", "category": "quality", "description": "품질 점수 업데이트"},
        {"type": "QUALITY_THRESHOLD_BREACHED", "category": "quality", "description": "품질 임계값 초과"},
        {"type": "NL2SQL_QUERY_EXECUTED", "category": "ai", "description": "NL2SQL 쿼리 실행"},
        {"type": "USER_LOGIN", "category": "auth", "description": "사용자 로그인"},
        {"type": "DATASOURCE_CONNECTED", "category": "data", "description": "데이터소스 연결"},
        {"type": "CASE_CREATED", "category": "case", "description": "케이스 생성"},
    ]

    return {
        "success": True,
        "data": event_types,
        "total": len(event_types),
    }
