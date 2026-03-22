"""온톨로지 피드백 API 라우터.

KAIR schema_generator.py의 feedback 엔드포인트를 Axiom 패턴으로 이식.
구조화된 피드백 또는 자연어 피드백을 받아 온톨로지를 수정한다.

엔드포인트:
  - POST /ontology/cases/{case_id}/feedback — 구조화된 피드백 적용
  - POST /ontology/cases/{case_id}/feedback/natural — 자연어 피드백 (LLM 해석)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import structlog

from app.api.ontology import ontology_service
from app.services.schema_refiner import SchemaRefiner

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v3/synapse/ontology", tags=["ontology-feedback"])

# SchemaRefiner 인스턴스 — OntologyService 연결
_refiner = SchemaRefiner(ontology_service=ontology_service)


# ── 요청 모델 ──

class FeedbackRequest(BaseModel):
    """구조화된 피드백 요청."""
    feedback: list[dict[str, Any]] = Field(
        ...,
        description="피드백 항목 배열 [{type, target_id?, content?}]",
        min_length=1,
    )


class NaturalFeedbackRequest(BaseModel):
    """자연어 피드백 요청."""
    feedback_text: str = Field(
        ...,
        min_length=5,
        max_length=5000,
        description="자연어 피드백 텍스트",
    )


# ── 엔드포인트 ──

@router.post("/cases/{case_id}/feedback")
async def apply_feedback(case_id: str, body: FeedbackRequest, request: Request):
    """구조화된 피드백을 온톨로지에 적용한다.

    피드백 타입:
    - add_node: { content: { id, layer, properties: { name, ... } } }
    - update_node: { target_id: "node-id", content: { properties: { name, ... } } }
    - delete_node: { target_id: "node-id" }
    - add_relation: { content: { source_id, target_id, relation_type } }
    - delete_relation: { target_id: "relation-id" }
    - move_layer: { target_id: "node-id", content: { layer: "kpi" } }
    """
    tenant_id = getattr(request.state, "tenant_id", "default")

    result = await _refiner.apply_feedback(
        case_id=case_id,
        tenant_id=tenant_id,
        feedback_items=body.feedback,
    )

    return {
        "success": True,
        "applied": result.applied,
        "rejected": result.rejected,
        "new_version": result.new_version,
        "applied_count": len(result.applied),
        "rejected_count": len(result.rejected),
    }


@router.post("/cases/{case_id}/feedback/natural")
async def apply_natural_feedback(
    case_id: str, body: NaturalFeedbackRequest, request: Request
):
    """자연어 피드백을 LLM으로 해석하여 온톨로지를 수정한다.

    사용자가 자유 형식으로 피드백을 제출하면 LLM이 구조화된
    변경사항으로 변환하여 적용한다.

    예시: "OEE KPI에 에너지 효율 지표를 추가하고, Assembly 프로세스의
    설명을 '자동화 조립 라인'으로 변경해주세요"
    """
    tenant_id = getattr(request.state, "tenant_id", "default")

    # LLM 함수 지연 로딩
    llm_fn = _get_llm_fn()
    refiner = SchemaRefiner(ontology_service=ontology_service, llm_generate_fn=llm_fn)

    result = await refiner.refine_with_llm(
        case_id=case_id,
        tenant_id=tenant_id,
        natural_feedback=body.feedback_text,
    )

    if not result.applied and result.rejected:
        raise HTTPException(
            status_code=422,
            detail=result.rejected[0].get("error", "피드백 처리 실패"),
        )

    return {
        "success": True,
        "applied": result.applied,
        "rejected": result.rejected,
        "new_version": result.new_version,
    }


def _get_llm_fn():
    """LLM 생성 함수를 지연 로딩한다."""
    from app.core.config import settings
    if not settings.OPENAI_API_KEY:
        return None
    try:
        from kair_common.llm_factory import generate_text
        return generate_text
    except ImportError:
        return None
