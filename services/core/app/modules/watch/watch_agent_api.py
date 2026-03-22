"""Watch Agent API -- LLM 기반 모니터링 규칙 자동 생성 엔드포인트.

POST /api/v1/watch-agent/generate   — 자연어에서 규칙 제안 생성
POST /api/v1/watch-agent/confirm    — 제안된 규칙을 실제 WatchRule로 등록
POST /api/v1/watch-agent/analyze    — 데이터 가용성 분석
"""
from __future__ import annotations

import uuid
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger("watch_agent_api")

router = APIRouter(prefix="/watch-agent", tags=["watch-agent"])


# ── 요청/응답 모델 ──────────────────────────────────────────────────


class GenerateRequest(BaseModel):
    """규칙 생성 요청"""
    description: str = Field(..., min_length=1, description="자연어 모니터링 설명")
    datasource_id: str = Field(..., min_length=1, description="대상 데이터소스 ID")
    schema_context: dict[str, Any] | None = Field(
        None, description="사용 가능한 테이블/컬럼 스키마 정보"
    )


class ConfirmRequest(BaseModel):
    """규칙 확정 요청 — 제안된 규칙을 실제 WatchRule로 등록"""
    name: str = Field(..., description="규칙 이름")
    sql_query: str = Field(..., description="모니터링 SQL 쿼리")
    condition_type: str = Field("threshold", description="조건 유형")
    threshold: float = Field(0.0, description="임계값")
    severity: str = Field("medium", description="심각도")
    schedule_interval: str = Field("1h", description="실행 주기")
    datasource_id: str = Field("", description="데이터소스 ID")
    event_type: str = Field("watch_agent_rule", description="이벤트 타입")


class AnalyzeRequest(BaseModel):
    """데이터 가용성 분석 요청"""
    datasource_id: str = Field(..., description="데이터소스 ID")
    question: str = Field(..., min_length=1, description="모니터링 요구사항")
    schema_context: dict[str, Any] | None = None


# ── 엔드포인트 ──────────────────────────────────────────────────────


@router.post("/generate")
async def generate_rule(body: GenerateRequest, request: Request):
    """자연어 설명에서 모니터링 규칙 제안을 생성한다.

    사용자가 "매출이 전월 대비 20% 이상 감소하면 알림" 같은 텍스트를 입력하면
    LLM이 SQL + 조건 + 임계값을 자동 생성한다.
    """
    from app.modules.watch.watch_agent import WatchAgent

    agent = WatchAgent(schema_context=body.schema_context or {})

    try:
        proposal = await agent.generate_rule_from_text(
            description=body.description,
            datasource_id=body.datasource_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("규칙 생성 실패: %s", exc)
        raise HTTPException(status_code=500, detail=f"규칙 생성 실패: {exc}") from exc

    return {
        "success": True,
        "data": proposal.to_dict(),
    }


@router.post("/confirm")
async def confirm_rule(body: ConfirmRequest, request: Request):
    """제안된 규칙을 확정하여 실제 WatchRule로 등록한다.

    generate 엔드포인트의 결과를 사용자가 확인/수정한 후
    이 엔드포인트로 최종 등록한다.
    """
    from app.modules.watch.application.watch_service import WatchService

    # WatchRule 정의 구성
    rule_definition = {
        "type": body.condition_type,
        "sql_query": body.sql_query,
        "threshold": body.threshold,
        "schedule_interval": body.schedule_interval,
        "datasource_id": body.datasource_id,
        "source": "watch_agent",
    }

    try:
        service = WatchService()
        # 테넌트 ID 추출
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            raise HTTPException(status_code=401, detail="tenant_id not resolved")

        rule = await service.create_rule(
            tenant_id=tenant_id,
            name=body.name,
            event_type=body.event_type,
            definition=rule_definition,
            active=True,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("규칙 등록 실패: %s", exc)
        raise HTTPException(status_code=500, detail=f"규칙 등록 실패: {exc}") from exc

    return {
        "success": True,
        "data": {
            "rule_id": str(rule.id) if hasattr(rule, "id") else str(uuid.uuid4()),
            "name": body.name,
            "status": "active",
            "message": "모니터링 규칙이 등록되었습니다.",
        },
    }


@router.post("/analyze")
async def analyze_availability(body: AnalyzeRequest, request: Request):
    """모니터링에 필요한 데이터가 존재하는지 분석한다.

    규칙 생성 전에 필요한 테이블/컬럼이 존재하는지 사전 확인한다.
    """
    from app.modules.watch.watch_agent import WatchAgent

    agent = WatchAgent(schema_context=body.schema_context or {})

    try:
        report = await agent.analyze_data_availability(
            datasource_id=body.datasource_id,
            question=body.question,
        )
    except Exception as exc:
        logger.error("가용성 분석 실패: %s", exc)
        raise HTTPException(status_code=500, detail=f"분석 실패: {exc}") from exc

    return {
        "success": True,
        "data": report.to_dict(),
    }
