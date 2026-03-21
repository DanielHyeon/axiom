"""DMN 규칙 엔진 + 관계 추론 API.

엔드포인트:
  POST /api/v3/synapse/dmn/execute           — 결정 테이블 실행
  POST /api/v3/synapse/dmn/infer-relation    — 두 엔티티 간 관계 추론
  POST /api/v3/synapse/dmn/infer-relations-batch — 엔티티 목록 관계 일괄 추론
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.core.rate_limiter import check_rate_limit, INFERENCE_LIMIT
from app.services.dmn_engine import execute_decision_table, create_table_from_dict
from app.services.relation_inference import infer_relation, infer_relations_batch

router = APIRouter(prefix="/api/v3/synapse/dmn", tags=["DMN 규칙 엔진"])


# ─── 요청/응답 모델 ────────────────────────────────────────

class ExecuteDecisionRequest(BaseModel):
    """DMN 결정 테이블 실행 요청."""
    table: dict  # DecisionTable JSON 정의
    context: dict  # 입력 변수


class InferRelationRequest(BaseModel):
    """두 엔티티 간 관계 추론 요청."""
    source: dict  # {"name": str, "layer": str, "description": str}
    target: dict


class BatchInferRequest(BaseModel):
    """엔티티 목록 간 관계 일괄 추론 요청."""
    entities: list[dict] = Field(..., max_length=20, description="엔티티 목록 (최대 20개)")
    min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="최소 신뢰도 — 이 값 미만의 관계는 결과에서 제외",
    )


# ─── 엔드포인트 ────────────────────────────────────────────

@router.post("/execute")
async def api_execute_decision(body: ExecuteDecisionRequest):
    """DMN 결정 테이블을 실행하고 매칭 결과를 반환한다."""
    table = create_table_from_dict(body.table)
    results = execute_decision_table(table, body.context)
    return {
        "success": True,
        "data": {
            "results": results,
            "hit_count": len(results),
        },
    }


@router.post("/infer-relation")
async def api_infer_relation(body: InferRelationRequest, request: Request):
    """두 엔티티 간 관계를 추론한다 (LLM 또는 규칙 기반 폴백)."""
    # 레이트 리밋 검사 -- 관계 추론(LLM)은 분당 15회 제한
    await check_rate_limit(request, INFERENCE_LIMIT)
    result = await infer_relation(body.source, body.target)
    return {"success": True, "data": result}


@router.post("/infer-relations-batch")
async def api_batch_infer(body: BatchInferRequest, request: Request):
    """엔티티 목록 간 관계를 일괄 추론한다."""
    # 레이트 리밋 검사 -- 일괄 추론(LLM)은 분당 15회 제한
    await check_rate_limit(request, INFERENCE_LIMIT)
    results = await infer_relations_batch(body.entities, body.min_confidence)
    return {
        "success": True,
        "data": {
            "relations": results,
            "count": len(results),
        },
    }
