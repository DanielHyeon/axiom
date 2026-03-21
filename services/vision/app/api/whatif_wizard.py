"""What-if 시뮬레이션 위자드 API -- 9단계 파이프라인 엔드포인트.

KAIR의 /whatif/* API를 Axiom Vision 패턴으로 이식.
기존 whatif_dag, whatif_fork 라우터와 완전히 분리된 독립 라우터.

엔드포인트:
- POST /api/v1/vision/whatif-wizard/discover-edges       -- Step 1: 엣지 탐색
- POST /api/v1/vision/whatif-wizard/correlation-matrix    -- Step 2: 상관 행렬
- POST /api/v1/vision/whatif-wizard/build-graph           -- Step 3: DAG 구축
- POST /api/v1/vision/whatif-wizard/train                 -- Step 4: 모델 학습
- POST /api/v1/vision/whatif-wizard/validate              -- Step 5: 모델 검증
- POST /api/v1/vision/whatif-wizard/simulate              -- Step 6: 시뮬레이션
- POST /api/v1/vision/whatif-wizard/compare               -- Step 7: 시나리오 비교
- POST /api/v1/vision/whatif-wizard/scenarios             -- Step 8: 시나리오 저장
- GET  /api/v1/vision/whatif-wizard/scenarios             -- Step 9: 시나리오 목록
- GET  /api/v1/vision/whatif-wizard/scenarios/{id}        -- Step 9: 시나리오 조회
- DELETE /api/v1/vision/whatif-wizard/scenarios/{id}      -- 시나리오 삭제
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator

from app.services.whatif_wizard_service import (
    EdgeCandidate,
    EdgeMethod,
    SimulationNode,
    WhatIfScenario,
    build_model_graph,
    compare_scenarios,
    compute_correlation_matrix,
    discover_edges,
    simulate,
    train_models,
    validate_models,
    wizard_store,
)

logger = logging.getLogger(__name__)


def _get_tenant(request: Request) -> str:
    """TenantMiddleware가 설정한 tenant_id를 추출한다. 없으면 401."""
    tid = getattr(getattr(request, "state", None), "tenant_id", "")
    if not tid:
        raise HTTPException(status_code=401, detail="tenant_id 누락")
    return tid


router = APIRouter(
    prefix="/api/v1/vision/whatif-wizard",
    tags=["What-if 위자드"],
)


# ---------------------------------------------------------------------------
# 요청 모델 -- Pydantic v2
# ---------------------------------------------------------------------------

class DiscoverEdgesRequest(BaseModel):
    """Step 1: 엣지 탐색 요청."""
    data: dict[str, list[float]] = Field(
        ..., description="변수명 -> 시계열 값 리스트",
    )

    @field_validator("data")
    @classmethod
    def _limit_data_size(cls, v: dict[str, list[float]]) -> dict[str, list[float]]:
        """변수 수와 데이터 포인트 수를 제한한다 (DoS 방지)."""
        if len(v) > 50:
            raise ValueError("변수는 최대 50개까지 허용됩니다")
        for key, values in v.items():
            if len(values) > 10_000:
                raise ValueError(f"변수 '{key}'의 데이터 포인트가 10,000개를 초과합니다")
        return v
    methods: list[str] = Field(
        default_factory=lambda: ["pearson", "granger"],
        description="사용할 탐색 방법 (pearson, spearman, granger)",
    )
    threshold: float = Field(
        default=0.3, ge=0.0, le=1.0,
        description="상관계수 절대값 임계치",
    )
    max_lag: int = Field(
        default=5, ge=1, le=20,
        description="Granger 검정 최대 래그",
    )


class CorrelationMatrixRequest(BaseModel):
    """Step 2: 상관 행렬 요청."""
    data: dict[str, list[float]] = Field(
        ..., description="변수명 -> 시계열 값 리스트",
    )
    method: str = Field(
        default="pearson", description="pearson 또는 spearman",
    )


class BuildGraphRequest(BaseModel):
    """Step 3: DAG 구축 요청."""
    edges: list[dict[str, Any]] = Field(
        ..., description="엣지 후보 리스트 ({source, target, method, confidence})",
    )
    variables: list[str] = Field(
        ..., description="그래프에 포함할 변수 목록",
    )


class TrainRequest(BaseModel):
    """Step 4: 모델 학습 요청."""
    graph: dict[str, dict[str, Any]] = Field(
        ..., description="변수명 -> {parents, model_type} 매핑",
    )
    data: dict[str, list[float]] = Field(
        ..., description="변수명 -> 시계열 값 리스트",
    )
    model_type: str = Field(
        default="linear", description="회귀 모델 종류 (linear, ridge, lasso)",
    )

    @field_validator("data")
    @classmethod
    def _limit_data_size(cls, v: dict[str, list[float]]) -> dict[str, list[float]]:
        """변수 수와 데이터 포인트 수를 제한한다 (DoS 방지)."""
        if len(v) > 50:
            raise ValueError("변수는 최대 50개까지 허용됩니다")
        for key, values in v.items():
            if len(values) > 10_000:
                raise ValueError(f"변수 '{key}'의 데이터 포인트가 10,000개를 초과합니다")
        return v


class ValidateRequest(BaseModel):
    """Step 5: 모델 검증 요청."""
    graph: dict[str, dict[str, Any]] = Field(
        ..., description="학습 완료된 그래프 (coefficients, intercept 포함)",
    )
    data: dict[str, list[float]] = Field(
        ..., description="변수명 -> 시계열 값 리스트",
    )
    test_ratio: float = Field(
        default=0.2, ge=0.05, le=0.5,
        description="테스트 데이터 비율",
    )


class SimulateRequest(BaseModel):
    """Step 6: 시뮬레이션 실행 요청."""
    graph: dict[str, dict[str, Any]] = Field(
        ..., description="학습 완료된 그래프",
    )
    baseline: dict[str, float] = Field(
        ..., description="변수명 -> 기본값",
    )
    interventions: dict[str, float] = Field(
        ..., description="변수명 -> 개입 값",
    )


class CompareRequest(BaseModel):
    """Step 7: 시나리오 비교 요청."""
    scenarios: list[dict[str, Any]] = Field(
        ..., min_length=2,
        description="비교할 시나리오 목록 (id, name, results, baseline)",
    )


class SaveScenarioRequest(BaseModel):
    """Step 8: 시나리오 저장 요청."""
    name: str = Field(..., min_length=1, max_length=200, description="시나리오 이름")
    description: str = Field(default="", description="시나리오 설명")
    interventions: dict[str, float] = Field(
        default_factory=dict, description="개입 값",
    )
    results: dict[str, float] = Field(
        default_factory=dict, description="시뮬레이션 결과",
    )
    baseline: dict[str, float] = Field(
        default_factory=dict, description="기본값",
    )
    project_id: str = Field(default="", description="프로젝트 ID")


# ---------------------------------------------------------------------------
# Step 1: 엣지 탐색
# ---------------------------------------------------------------------------

@router.post("/discover-edges")
async def api_discover_edges(body: DiscoverEdgesRequest) -> dict[str, Any]:
    """Step 1: 변수 간 상관/인과 엣지 탐색.

    Pearson, Spearman, Granger 방법을 조합하여
    유의미한 상관/인과 관계를 가진 변수 쌍을 식별한다.
    """
    # 최소 데이터 검증
    if len(body.data) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INSUFFICIENT_VARIABLES", "message": "최소 2개 변수가 필요합니다"},
        )

    edges = await discover_edges(
        data=body.data,
        methods=body.methods,
        threshold=body.threshold,
        max_lag=body.max_lag,
    )
    return {
        "success": True,
        "data": {
            "edges": [e.to_dict() for e in edges],
            "count": len(edges),
        },
    }


# ---------------------------------------------------------------------------
# Step 2: 상관 행렬
# ---------------------------------------------------------------------------

@router.post("/correlation-matrix")
async def api_correlation_matrix(body: CorrelationMatrixRequest) -> dict[str, Any]:
    """Step 2: 상관 행렬 히트맵 데이터.

    모든 변수 쌍에 대한 상관계수를 행렬로 반환한다.
    프론트엔드 히트맵 컴포넌트에서 직접 사용 가능.
    """
    if len(body.data) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INSUFFICIENT_VARIABLES", "message": "최소 2개 변수가 필요합니다"},
        )

    result = await compute_correlation_matrix(data=body.data, method=body.method)
    return {"success": True, "data": result}


# ---------------------------------------------------------------------------
# Step 3: DAG 구축
# ---------------------------------------------------------------------------

@router.post("/build-graph")
async def api_build_graph(body: BuildGraphRequest) -> dict[str, Any]:
    """Step 3: 엣지에서 비순환 방향 그래프(DAG)를 구축.

    confidence 순으로 엣지를 추가하며 사이클이 생기면 건너뛴다.
    """
    if not body.variables:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "NO_VARIABLES", "message": "변수 목록이 비어있습니다"},
        )

    # dict -> EdgeCandidate 변환
    edges = []
    for e in body.edges:
        method_str = e.get("method", "pearson")
        try:
            method = EdgeMethod(method_str)
        except ValueError:
            method = EdgeMethod.PEARSON
        edges.append(EdgeCandidate(
            source=e["source"],
            target=e["target"],
            method=method,
            correlation=e.get("correlation", 0.0),
            p_value=e.get("p_value", 1.0),
            lag=e.get("lag", 0),
            confidence=e.get("confidence", 0.5),
        ))

    graph = await build_model_graph(edges, body.variables)
    return {
        "success": True,
        "data": {
            v: {"variable": v, "parents": n.parents, "model_type": n.model_type}
            for v, n in graph.items()
        },
    }


# ---------------------------------------------------------------------------
# Step 4: 모델 학습
# ---------------------------------------------------------------------------

@router.post("/train")
async def api_train(body: TrainRequest) -> dict[str, Any]:
    """Step 4: 노드별 회귀 모델 학습.

    각 노드의 부모 변수를 독립변수로 하는 회귀 모델을 학습한다.
    학습 결과로 coefficients, intercept, r_squared가 반환된다.
    """
    # dict -> SimulationNode 변환
    graph = {
        v: SimulationNode(
            variable=v,
            parents=d.get("parents", []),
            model_type=d.get("model_type", body.model_type),
        )
        for v, d in body.graph.items()
    }

    trained = await train_models(graph, body.data, model_type=body.model_type)
    return {
        "success": True,
        "data": {v: n.to_dict() for v, n in trained.items()},
    }


# ---------------------------------------------------------------------------
# Step 5: 모델 검증
# ---------------------------------------------------------------------------

@router.post("/validate")
async def api_validate(body: ValidateRequest) -> dict[str, Any]:
    """Step 5: 학습된 모델의 예측 성능 백테스팅.

    마지막 test_ratio 비율의 데이터로 RMSE, R2를 계산하여
    모델 신뢰성을 검증한다.
    """
    # dict -> SimulationNode 변환 (학습 완료 상태 포함)
    graph = {
        v: SimulationNode.from_dict({**d, "variable": v})
        for v, d in body.graph.items()
    }

    results = await validate_models(graph, body.data, test_ratio=body.test_ratio)
    return {"success": True, "data": results}


# ---------------------------------------------------------------------------
# Step 6: 시뮬레이션 실행
# ---------------------------------------------------------------------------

@router.post("/simulate")
async def api_simulate(body: SimulateRequest) -> dict[str, Any]:
    """Step 6: What-if DAG 전파 시뮬레이션.

    개입 변수를 고정(do-calculus)하고 DAG를 위상 정렬 순서로 전파하여
    모든 변수의 변화량을 계산한다.
    """
    if not body.interventions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "NO_INTERVENTIONS", "message": "최소 1개 개입이 필요합니다"},
        )

    # dict -> SimulationNode 변환
    graph = {
        v: SimulationNode.from_dict({**d, "variable": v})
        for v, d in body.graph.items()
    }

    result = await simulate(graph, body.baseline, body.interventions)

    # 변화량(delta) 계산
    deltas = {
        v: round(result.get(v, 0.0) - body.baseline.get(v, 0.0), 6)
        for v in result
    }

    return {
        "success": True,
        "data": {
            "results": result,
            "deltas": deltas,
            "interventions": body.interventions,
            "baseline": body.baseline,
        },
    }


# ---------------------------------------------------------------------------
# Step 7: 시나리오 비교
# ---------------------------------------------------------------------------

@router.post("/compare")
async def api_compare(body: CompareRequest) -> dict[str, Any]:
    """Step 7: 여러 시나리오의 결과를 비교.

    각 변수별로 시나리오 간 delta, delta_pct를 계산하고
    가장 영향이 큰 변수를 식별한다.
    """
    scenarios = [
        WhatIfScenario(
            id=s.get("id", ""),
            name=s.get("name", ""),
            results=s.get("results", {}),
            baseline=s.get("baseline", {}),
            deltas=s.get("deltas", {}),
        )
        for s in body.scenarios
    ]

    result = await compare_scenarios(scenarios)
    return {"success": True, "data": result}


# ---------------------------------------------------------------------------
# Step 8: 시나리오 저장
# ---------------------------------------------------------------------------

@router.post("/scenarios", status_code=status.HTTP_201_CREATED)
async def api_save_scenario(body: SaveScenarioRequest, request: Request) -> dict[str, Any]:
    """Step 8: 시나리오를 저장한다.

    위자드에서 실행한 시뮬레이션 결과를 영속화하여
    나중에 비교하거나 복원할 수 있도록 한다.
    """
    tenant_id = _get_tenant(request)

    # delta 계산
    deltas = {
        v: round(body.results.get(v, 0.0) - body.baseline.get(v, 0.0), 6)
        for v in body.results
    }

    scenario = WhatIfScenario(
        name=body.name,
        description=body.description,
        interventions=body.interventions,
        results=body.results,
        baseline=body.baseline,
        deltas=deltas,
        tenant_id=tenant_id,
        project_id=body.project_id,
    )

    scenario_id = wizard_store.save_scenario(scenario)

    return {
        "success": True,
        "data": {
            "scenario_id": scenario_id,
            "name": scenario.name,
            "message": f"시나리오 '{scenario.name}' 저장 완료",
        },
    }


# ---------------------------------------------------------------------------
# Step 9: 시나리오 조회/목록
# ---------------------------------------------------------------------------

@router.get("/scenarios")
async def api_list_scenarios(request: Request) -> dict[str, Any]:
    """Step 9: 저장된 시나리오 목록을 조회한다."""
    tenant_id = _get_tenant(request)
    scenarios = wizard_store.list_scenarios(tenant_id)
    return {
        "success": True,
        "data": {
            "scenarios": [s.to_dict() for s in scenarios],
            "total": len(scenarios),
        },
    }


@router.get("/scenarios/{scenario_id}")
async def api_get_scenario(scenario_id: str, request: Request) -> dict[str, Any]:
    """Step 9: 저장된 시나리오를 복원한다."""
    tenant_id = _get_tenant(request)
    scenario = wizard_store.load_scenario(tenant_id, scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SCENARIO_NOT_FOUND",
                "message": f"시나리오를 찾을 수 없음: {scenario_id}",
            },
        )

    return {"success": True, "data": scenario.to_dict()}


# ---------------------------------------------------------------------------
# 시나리오 삭제
# ---------------------------------------------------------------------------

@router.delete("/scenarios/{scenario_id}")
async def api_delete_scenario(scenario_id: str, request: Request) -> dict[str, Any]:
    """저장된 시나리오를 삭제한다."""
    tenant_id = _get_tenant(request)
    deleted = wizard_store.delete_scenario(tenant_id, scenario_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "SCENARIO_NOT_FOUND",
                "message": f"시나리오를 찾을 수 없음: {scenario_id}",
            },
        )

    return {
        "success": True,
        "message": f"시나리오 '{scenario_id}' 삭제 완료",
    }
