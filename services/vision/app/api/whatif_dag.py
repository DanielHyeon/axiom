"""
What-if DAG REST API
=====================

온톨로지 DAG 기반 What-if 시뮬레이션 API.

기존 /api/v3/cases/{case_id}/what-if (보험 시나리오 전용)와 **완전히 분리된** 라우터.

엔드포인트:
- POST /api/v3/cases/{case_id}/whatif-dag/simulate       — 시뮬레이션 실행
- POST /api/v3/cases/{case_id}/whatif-dag/compare         — 시나리오 비교
- GET  /api/v3/cases/{case_id}/whatif-dag/snapshot        — 베이스라인 스냅샷
- GET  /api/v3/cases/{case_id}/whatif-dag/models          — 시뮬레이션 가능 모델 목록
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api._auth import get_current_user
from app.core.auth import CurrentUser, auth_service
from app.engines.whatif_dag_engine import WhatIfDAGEngine
from app.engines.whatif_fallback import FallbackPredictor
from app.engines.whatif_models import InterventionSpec
from app.services.model_graph_fetcher import ModelGraphFetcher, ModelGraphFetchError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v3/cases/{case_id}/whatif-dag",
    tags=["What-If DAG"],
)

# ── 모듈 레벨 싱글톤 ──
_engine = WhatIfDAGEngine(fallback_predictor=FallbackPredictor())
_fetcher = ModelGraphFetcher()


def _ensure_auth(user: CurrentUser) -> None:
    auth_service.requires_role(user, ["admin", "staff"])


# ── Pydantic 요청/응답 모델 ──

class InterventionRequest(BaseModel):
    """개입 정의 (요청용)."""
    node_id: str = Field(..., alias="nodeId", description="온톨로지 노드 ID")
    field: str = Field(..., description="필드명")
    value: float = Field(..., description="개입 값")
    description: str = Field(default="", description="설명")

    model_config = {"populate_by_name": True}


class SimulateRequest(BaseModel):
    """시뮬레이션 실행 요청."""
    scenario_name: str = Field(
        default="Scenario",
        min_length=1,
        max_length=200,
        description="시나리오 이름",
    )
    interventions: list[InterventionRequest] = Field(
        ...,
        min_length=1,
        description="개입 목록 (1개 이상)",
    )
    baseline_data: dict[str, float] | None = Field(
        default=None,
        description="베이스라인 데이터 (생략 시 Synapse에서 자동 로드)",
    )
    snapshot_date: str | None = Field(
        default=None,
        description="베이스라인 시점 (미구현, 예약)",
    )


class ScenarioDefinition(BaseModel):
    """시나리오 비교용 개별 시나리오 정의."""
    name: str = Field(..., min_length=1, max_length=200)
    interventions: list[InterventionRequest] = Field(..., min_length=1)


class CompareRequest(BaseModel):
    """시나리오 비교 요청."""
    scenarios: list[ScenarioDefinition] = Field(
        ...,
        min_length=2,
        description="비교할 시나리오 목록 (2개 이상)",
    )
    baseline_data: dict[str, float] | None = Field(
        default=None,
        description="베이스라인 데이터 (생략 시 Synapse에서 자동 로드)",
    )


# ── API 엔드포인트 ──

@router.post("/simulate")
async def run_dag_simulation(
    case_id: str,
    payload: SimulateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    온톨로지 DAG 기반 What-if 시뮬레이션 실행.

    1. Synapse에서 모델 그래프(BehaviorModel + READS/PREDICTS) 로드
    2. 베이스라인 데이터 구성
    3. DAG 증분 전파 엔진으로 시뮬레이션 실행
    4. 결과 반환 (traces, timeline, deltas 등)
    """
    _ensure_auth(user)

    # 1. 모델 그래프 로드
    try:
        model_graph = await _fetcher.get_model_graph(case_id)
    except ModelGraphFetchError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "MODEL_GRAPH_FETCH_FAILED",
                "message": f"모델 그래프 로드 실패: {e}",
            },
        )

    # 2. 베이스라인 데이터 구성
    baseline_data = payload.baseline_data
    if baseline_data is None:
        try:
            baseline_data = await _fetcher.get_baseline_snapshot(case_id)
        except Exception as e:
            logger.warning("베이스라인 스냅샷 로드 실패, 빈 데이터로 진행: %s", e)
            baseline_data = {}

    # 3. 개입 변환
    interventions = [
        InterventionSpec(
            node_id=iv.node_id,
            field=iv.field,
            value=iv.value,
            description=iv.description,
        )
        for iv in payload.interventions
    ]

    # 4. 시뮬레이션 실행
    result = await _engine.simulate(
        model_graph=model_graph,
        interventions=interventions,
        baseline_data=baseline_data,
        scenario_name=payload.scenario_name,
    )

    return {"success": True, **result.to_dict()}


@router.post("/compare")
async def compare_dag_scenarios(
    case_id: str,
    payload: CompareRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    여러 시나리오를 동시 실행하고 delta 비교.

    각 시나리오별로 시뮬레이션을 실행한 뒤,
    모든 변수에 대해 시나리오별 변화량(delta)을 비교 테이블로 반환.
    """
    _ensure_auth(user)

    # 1. 모델 그래프 로드
    try:
        model_graph = await _fetcher.get_model_graph(case_id)
    except ModelGraphFetchError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "MODEL_GRAPH_FETCH_FAILED",
                "message": f"모델 그래프 로드 실패: {e}",
            },
        )

    # 2. 베이스라인 데이터
    baseline_data = payload.baseline_data
    if baseline_data is None:
        try:
            baseline_data = await _fetcher.get_baseline_snapshot(case_id)
        except Exception:
            baseline_data = {}

    # 3. 시나리오 목록 변환
    scenarios = [
        {
            "name": s.name,
            "interventions": [
                {
                    "node_id": iv.node_id,
                    "field": iv.field,
                    "value": iv.value,
                    "description": iv.description,
                }
                for iv in s.interventions
            ],
        }
        for s in payload.scenarios
    ]

    # 4. 비교 실행
    comparison_result = await _engine.compare_scenarios(
        model_graph=model_graph,
        scenarios=scenarios,
        baseline_data=baseline_data,
    )

    return {"success": True, **comparison_result}


@router.get("/snapshot")
async def get_baseline_snapshot(
    case_id: str,
    date: str | None = Query(default=None, description="스냅샷 시점 (미구현)"),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    현재 또는 특정 시점의 모든 온톨로지 변수 값 조회.

    시뮬레이션의 베이스라인으로 사용되는 데이터.
    """
    _ensure_auth(user)

    try:
        snapshot = await _fetcher.get_baseline_snapshot(case_id)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "SNAPSHOT_FETCH_FAILED",
                "message": f"스냅샷 로드 실패: {e}",
            },
        )

    return {
        "success": True,
        "case_id": case_id,
        "snapshot_date": date,
        "data": snapshot,
        "variable_count": len(snapshot),
    }


@router.get("/models")
async def list_simulation_models(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    시뮬레이션에 사용 가능한 모델 목록 + 상태.

    모델별 입력(READS_FIELD) 수, 출력(PREDICTS_FIELD) 대상,
    학습 상태(status) 등을 반환.
    """
    _ensure_auth(user)

    try:
        model_graph = await _fetcher.get_model_graph(case_id)
    except ModelGraphFetchError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "MODEL_GRAPH_FETCH_FAILED",
                "message": f"모델 그래프 로드 실패: {e}",
            },
        )

    models = model_graph.get("models", [])
    reads = model_graph.get("reads", [])
    predicts = model_graph.get("predicts", [])

    # 모델별 입력/출력 수 계산
    reads_count: dict[str, int] = {}
    for r in reads:
        mid = r.get("modelId", "")
        reads_count[mid] = reads_count.get(mid, 0) + 1

    predicts_info: dict[str, dict[str, Any]] = {}
    for p in predicts:
        mid = p.get("modelId", "")
        if mid not in predicts_info:
            predicts_info[mid] = {
                "target_node_id": p.get("targetNodeId"),
                "target_field": p.get("field"),
                "confidence": p.get("confidence"),
            }

    enriched_models = []
    for m in models:
        mid = m.get("id", "")
        enriched_models.append({
            **m,
            "input_count": reads_count.get(mid, 0),
            "output": predicts_info.get(mid),
        })

    return {
        "success": True,
        "case_id": case_id,
        "models": enriched_models,
        "total": len(enriched_models),
    }
