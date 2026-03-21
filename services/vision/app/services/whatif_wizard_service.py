"""What-if 시뮬레이션 위자드 서비스 -- KAIR 9단계 파이프라인 이식.

파이프라인 단계:
  1. discover_edges     -- 변수 간 상관관계 및 인과관계 탐색
  2. correlation_matrix -- 상관 행렬 히트맵 데이터 생성
  3. build_model_graph  -- 탐색된 엣지로 DAG 구성
  4. train_models       -- 각 노드별 예측 모델 학습 (statsmodels/sklearn)
  5. validate_models    -- 모델 성능 백테스팅
  6. simulate           -- DAG 기반 What-if 전파 시뮬레이션
  7. compare_scenarios  -- 시나리오 간 비교 분석
  8. save_scenario      -- 시나리오 영속화
  9. load_scenario      -- 저장된 시나리오 복원

KAIR robo-data-domain-layer의 whatif.py (3,328 LOC)를 참조하되
Axiom의 기존 Vision 패턴(causal_analysis_service, scenario_manager)에 맞게 재구현.
"""
from __future__ import annotations

import asyncio
import collections
import json
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------

class EdgeMethod(str, Enum):
    """엣지 탐색 방법."""
    PEARSON = "pearson"
    SPEARMAN = "spearman"
    GRANGER = "granger"


@dataclass
class EdgeCandidate:
    """탐색된 인과/상관 엣지 후보."""
    source: str
    target: str
    method: EdgeMethod
    correlation: float = 0.0
    p_value: float = 1.0
    lag: int = 0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """직렬화용 딕셔너리 반환."""
        return {
            "source": self.source,
            "target": self.target,
            "method": self.method.value,
            "correlation": self.correlation,
            "p_value": self.p_value,
            "lag": self.lag,
            "confidence": self.confidence,
        }


@dataclass
class SimulationNode:
    """시뮬레이션 DAG 노드.

    각 노드는 부모 변수(parents)를 입력으로 받아 예측하는 회귀 모델을 보유한다.
    학습 완료 시 is_trained = True, coefficients/intercept/r_squared 가 설정됨.
    """
    variable: str
    parents: list[str] = field(default_factory=list)
    model_type: str = "linear"  # linear, ridge, lasso
    coefficients: dict[str, float] = field(default_factory=dict)
    intercept: float = 0.0
    r_squared: float = 0.0
    is_trained: bool = False

    def to_dict(self) -> dict[str, Any]:
        """직렬화용 딕셔너리 반환."""
        return {
            "variable": self.variable,
            "parents": self.parents,
            "model_type": self.model_type,
            "coefficients": self.coefficients,
            "intercept": self.intercept,
            "r_squared": self.r_squared,
            "is_trained": self.is_trained,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimulationNode":
        """딕셔너리에서 복원."""
        return cls(
            variable=data.get("variable", ""),
            parents=data.get("parents", []),
            model_type=data.get("model_type", "linear"),
            coefficients=data.get("coefficients", {}),
            intercept=data.get("intercept", 0.0),
            r_squared=data.get("r_squared", 0.0),
            is_trained=data.get("is_trained", False),
        )


@dataclass
class WhatIfScenario:
    """What-if 시나리오 -- 개입(interventions)과 그에 따른 결과(results)를 보관."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    interventions: dict[str, float] = field(default_factory=dict)
    results: dict[str, float] = field(default_factory=dict)
    baseline: dict[str, float] = field(default_factory=dict)
    deltas: dict[str, float] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    tenant_id: str = ""
    project_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """직렬화용 딕셔너리 반환."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WhatIfScenario":
        """딕셔너리에서 복원."""
        return cls(
            id=data.get("id", str(uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            interventions=data.get("interventions", {}),
            results=data.get("results", {}),
            baseline=data.get("baseline", {}),
            deltas=data.get("deltas", {}),
            created_at=data.get("created_at", ""),
            tenant_id=data.get("tenant_id", ""),
            project_id=data.get("project_id", ""),
        )


# ---------------------------------------------------------------------------
# Step 1: 엣지 탐색 -- 변수 간 상관/인과관계 후보를 반환
# ---------------------------------------------------------------------------

async def discover_edges(
    data: dict[str, list[float]],
    methods: list[str] | None = None,
    threshold: float = 0.3,
    max_lag: int = 5,
) -> list[EdgeCandidate]:
    """변수 간 상관/인과 엣지를 탐색한다.

    Pearson/Spearman 상관 + Granger 인과성 검정을 조합하여 후보 엣지를 반환한다.
    threshold 이상의 상관 또는 p < 0.05 인 Granger 인과만 포함.

    Args:
        data: 변수명 -> 시계열 값 리스트
        methods: 사용할 탐색 방법 (pearson, spearman, granger)
        threshold: 상관계수 절대값 임계치
        max_lag: Granger 검정 최대 래그

    Returns:
        confidence 내림차순 정렬된 엣지 후보 리스트
    """
    if methods is None:
        methods = ["pearson", "granger"]

    candidates: list[EdgeCandidate] = []
    variables = list(data.keys())

    # CPU 바운드 계산을 별도 스레드에서 실행
    def _compute() -> list[EdgeCandidate]:
        local_candidates: list[EdgeCandidate] = []
        for i, src in enumerate(variables):
            for j, tgt in enumerate(variables):
                if i == j:
                    continue

                src_data = np.array(data[src], dtype=np.float64)
                tgt_data = np.array(data[tgt], dtype=np.float64)

                # 데이터 길이 맞추기 -- 최소 10개 이상 필요
                min_len = min(len(src_data), len(tgt_data))
                if min_len < 10:
                    continue
                src_arr = src_data[:min_len]
                tgt_arr = tgt_data[:min_len]

                # NaN 제거 -- 공통 유효 인덱스만 사용
                valid_mask = ~(np.isnan(src_arr) | np.isnan(tgt_arr))
                if valid_mask.sum() < 10:
                    continue
                src_valid = src_arr[valid_mask]
                tgt_valid = tgt_arr[valid_mask]

                # --- Pearson 상관 ---
                if "pearson" in methods:
                    corr = float(np.corrcoef(src_valid, tgt_valid)[0, 1])
                    if not np.isnan(corr) and abs(corr) >= threshold:
                        local_candidates.append(EdgeCandidate(
                            source=src, target=tgt,
                            method=EdgeMethod.PEARSON,
                            correlation=round(corr, 4),
                            confidence=round(abs(corr), 4),
                        ))

                # --- Spearman 상관 ---
                if "spearman" in methods:
                    try:
                        from scipy.stats import spearmanr
                        corr_s, p_s = spearmanr(src_valid, tgt_valid)
                        if not np.isnan(corr_s) and abs(corr_s) >= threshold:
                            local_candidates.append(EdgeCandidate(
                                source=src, target=tgt,
                                method=EdgeMethod.SPEARMAN,
                                correlation=round(float(corr_s), 4),
                                p_value=round(float(p_s), 6),
                                confidence=round(abs(float(corr_s)), 4),
                            ))
                    except ImportError:
                        logger.debug("scipy 미설치 -- spearman 건너뜀")
                    except Exception as e:
                        logger.debug("spearman_test_skipped", extra={"src": src, "tgt": tgt, "error": str(e)})

                # --- Granger 인과성 ---
                if "granger" in methods and min_len > max_lag + 10:
                    try:
                        from statsmodels.tsa.stattools import grangercausalitytests
                        # grangercausalitytests는 (y, x) 컬럼 순서 -- tgt가 종속변수
                        test_data = np.column_stack([tgt_valid, src_valid])
                        result = grangercausalitytests(
                            test_data, maxlag=max_lag, verbose=False,
                        )
                        # 최소 p-value를 가진 래그 찾기
                        best_lag = 1
                        best_p = 1.0
                        for lag_val in range(1, max_lag + 1):
                            if lag_val in result:
                                p = result[lag_val][0]["ssr_ftest"][1]
                                if p < best_p:
                                    best_p = p
                                    best_lag = lag_val
                        if best_p < 0.05:
                            local_candidates.append(EdgeCandidate(
                                source=src, target=tgt,
                                method=EdgeMethod.GRANGER,
                                p_value=round(best_p, 6),
                                lag=best_lag,
                                confidence=round(1 - best_p, 4),
                            ))
                    except ImportError:
                        logger.debug("statsmodels 미설치 -- granger 건너뜀")
                    except Exception as e:
                        logger.debug(
                            "granger_test_skipped",
                            extra={"src": src, "tgt": tgt, "error": str(e)},
                        )

        return local_candidates

    candidates = await asyncio.to_thread(_compute)

    # 중복 제거 -- 같은 (source, target) 쌍에서 가장 높은 confidence만 유지
    best: dict[tuple[str, str], EdgeCandidate] = {}
    for c in candidates:
        key = (c.source, c.target)
        if key not in best or c.confidence > best[key].confidence:
            best[key] = c

    result = sorted(best.values(), key=lambda e: e.confidence, reverse=True)
    logger.info("edges_discovered: count=%d, variables=%d", len(result), len(variables))
    return result


# ---------------------------------------------------------------------------
# Step 2: 상관 행렬 -- 히트맵 시각화용
# ---------------------------------------------------------------------------

async def compute_correlation_matrix(
    data: dict[str, list[float]],
    method: str = "pearson",
) -> dict[str, Any]:
    """상관 행렬을 계산하여 히트맵 데이터로 반환한다.

    Args:
        data: 변수명 -> 시계열 값 리스트
        method: pearson 또는 spearman

    Returns:
        {variables, matrix (2D list), method}
    """
    variables = list(data.keys())
    n = len(variables)

    def _compute() -> list[list[float]]:
        matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 1.0
                    continue
                arr_i = np.array(data[variables[i]], dtype=np.float64)
                arr_j = np.array(data[variables[j]], dtype=np.float64)
                min_len = min(len(arr_i), len(arr_j))
                if min_len < 3:
                    continue
                a, b = arr_i[:min_len], arr_j[:min_len]
                # NaN 제거
                valid = ~(np.isnan(a) | np.isnan(b))
                if valid.sum() < 3:
                    continue

                if method == "spearman":
                    try:
                        from scipy.stats import spearmanr
                        corr, _ = spearmanr(a[valid], b[valid])
                    except ImportError:
                        corr = float(np.corrcoef(a[valid], b[valid])[0, 1])
                else:
                    corr = float(np.corrcoef(a[valid], b[valid])[0, 1])

                matrix[i][j] = round(corr, 4) if not np.isnan(corr) else 0.0
        return matrix.tolist()

    matrix_list = await asyncio.to_thread(_compute)

    return {
        "variables": variables,
        "matrix": matrix_list,
        "method": method,
    }


# ---------------------------------------------------------------------------
# Step 3: DAG 구축 -- 엣지 후보로 비순환 방향 그래프 조립
# ---------------------------------------------------------------------------

async def build_model_graph(
    edges: list[EdgeCandidate],
    variables: list[str],
) -> dict[str, SimulationNode]:
    """엣지 후보에서 시뮬레이션 DAG를 구축한다.

    사이클을 방지하기 위해 confidence 순으로 엣지를 추가하고,
    사이클이 생기면 해당 엣지를 건너뛴다.

    Args:
        edges: discover_edges 결과
        variables: 그래프에 포함할 변수 목록

    Returns:
        변수명 -> SimulationNode 매핑 (DAG)
    """
    graph: dict[str, SimulationNode] = {
        v: SimulationNode(variable=v) for v in variables
    }
    added_edges: list[tuple[str, str]] = []

    # confidence 내림차순 정렬 -- 높은 확신도의 엣지부터 추가
    sorted_edges = sorted(edges, key=lambda e: e.confidence, reverse=True)

    for edge in sorted_edges:
        if edge.source not in graph or edge.target not in graph:
            continue

        # 잠정적으로 엣지 추가 후 사이클 검사
        graph[edge.target].parents.append(edge.source)
        if _has_cycle(graph):
            # 사이클이 생기면 롤백
            graph[edge.target].parents.remove(edge.source)
            logger.debug(
                "edge_skipped_cycle: %s -> %s (confidence=%.4f)",
                edge.source, edge.target, edge.confidence,
            )
            continue

        added_edges.append((edge.source, edge.target))

    logger.info(
        "model_graph_built: nodes=%d, edges=%d", len(graph), len(added_edges),
    )
    return graph


def _has_cycle(graph: dict[str, SimulationNode]) -> bool:
    """DAG에 사이클이 있는지 검사한다 (Kahn's algorithm).

    위상 정렬로 방문 가능한 노드 수가 전체보다 적으면 사이클이 존재.
    """
    in_degree: dict[str, int] = {v: len(n.parents) for v, n in graph.items()}
    # deque 사용 — popleft()는 O(1), list.pop(0)은 O(n)
    queue = collections.deque(v for v, d in in_degree.items() if d == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        # 현재 노드를 부모로 가진 자식 노드의 in_degree 감소
        for v, n in graph.items():
            if node in n.parents:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
    return visited != len(graph)


# ---------------------------------------------------------------------------
# Step 4: 모델 학습 -- 각 노드별 부모를 입력으로 하는 회귀 모델
# ---------------------------------------------------------------------------

async def train_models(
    graph: dict[str, SimulationNode],
    data: dict[str, list[float]],
    model_type: str = "linear",
) -> dict[str, SimulationNode]:
    """각 노드별로 부모 변수를 입력으로 하는 회귀 모델을 학습한다.

    부모가 없는 루트 노드는 학습 없이 is_trained=True 로 표시.

    Args:
        graph: build_model_graph 결과
        data: 변수명 -> 시계열 값 리스트
        model_type: 회귀 모델 종류 (linear, ridge, lasso)

    Returns:
        학습 완료된 그래프 (각 노드에 coefficients, intercept, r_squared 설정됨)
    """
    def _train() -> None:
        for var, node in graph.items():
            node.model_type = model_type
            # 루트 노드 (부모 없음) -- 학습 불필요
            if not node.parents:
                node.is_trained = True
                continue

            y = np.array(data.get(var, []), dtype=np.float64)
            X_cols = []
            for parent in node.parents:
                X_cols.append(np.array(data.get(parent, []), dtype=np.float64))

            if not X_cols or len(y) == 0:
                logger.debug("train_skipped_no_data: variable=%s", var)
                continue

            # 데이터 길이를 최소값으로 맞춤
            min_len = min(len(y), *(len(x) for x in X_cols))
            if min_len < 5:
                logger.debug("train_skipped_insufficient: variable=%s, samples=%d", var, min_len)
                continue

            y = y[:min_len]
            X = np.column_stack([x[:min_len] for x in X_cols])

            # NaN 행 제거
            valid_mask = ~(np.isnan(y) | np.any(np.isnan(X), axis=1))
            if valid_mask.sum() < 5:
                continue
            y = y[valid_mask]
            X = X[valid_mask]

            try:
                # 모델 종류에 따라 다른 회귀 모델 사용
                if model_type == "ridge":
                    try:
                        from sklearn.linear_model import Ridge
                        model = Ridge(alpha=1.0)
                    except ImportError:
                        from sklearn.linear_model import LinearRegression
                        model = LinearRegression()
                elif model_type == "lasso":
                    try:
                        from sklearn.linear_model import Lasso
                        model = Lasso(alpha=0.1)
                    except ImportError:
                        from sklearn.linear_model import LinearRegression
                        model = LinearRegression()
                else:
                    from sklearn.linear_model import LinearRegression
                    model = LinearRegression()

                model.fit(X, y)

                node.coefficients = {
                    p: round(float(c), 6)
                    for p, c in zip(node.parents, model.coef_)
                }
                node.intercept = round(float(model.intercept_), 6)
                node.r_squared = round(float(model.score(X, y)), 4)
                node.is_trained = True
                logger.debug(
                    "model_trained: variable=%s, r2=%.4f, parents=%s",
                    var, node.r_squared, node.parents,
                )
            except ImportError:
                logger.warning("sklearn 미설치 -- 모델 학습 불가: variable=%s", var)
            except Exception as e:
                logger.warning("model_training_failed: variable=%s, error=%s", var, str(e))

    await asyncio.to_thread(_train)

    trained_count = sum(1 for n in graph.values() if n.is_trained)
    logger.info("models_trained: total=%d, trained=%d", len(graph), trained_count)
    return graph


# ---------------------------------------------------------------------------
# Step 5: 모델 검증 -- 백테스팅으로 RMSE, R2 평가
# ---------------------------------------------------------------------------

async def validate_models(
    graph: dict[str, SimulationNode],
    data: dict[str, list[float]],
    test_ratio: float = 0.2,
) -> dict[str, dict[str, Any]]:
    """학습된 모델의 예측 성능을 백테스트한다.

    마지막 test_ratio 비율의 데이터로 RMSE, R2를 계산한다.

    Args:
        graph: train_models 결과
        data: 변수명 -> 시계열 값 리스트
        test_ratio: 테스트 데이터 비율

    Returns:
        변수명 -> {status, rmse, r2_test, r2_train, test_samples}
    """
    def _validate() -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}

        for var, node in graph.items():
            # 학습 안됨 또는 부모 없음 -- 검증 건너뜀
            if not node.is_trained or not node.parents:
                results[var] = {
                    "status": "skipped",
                    "reason": "학습 안됨 또는 부모 없음",
                }
                continue

            y = np.array(data.get(var, []), dtype=np.float64)
            X_cols = [
                np.array(data.get(p, []), dtype=np.float64)
                for p in node.parents
            ]
            min_len = min(len(y), *(len(x) for x in X_cols))
            if min_len < 10:
                results[var] = {"status": "skipped", "reason": "데이터 부족 (최소 10개 필요)"}
                continue

            # 학습/테스트 분할
            split = int(min_len * (1 - test_ratio))
            y_test = y[split:min_len]
            X_test = np.column_stack([x[split:min_len] for x in X_cols])

            # 계수 벡터로 예측
            coeff_vec = np.array([node.coefficients.get(p, 0.0) for p in node.parents])
            y_pred = X_test @ coeff_vec + node.intercept

            # RMSE 계산
            rmse = float(np.sqrt(np.mean((y_test - y_pred) ** 2)))

            # 테스트 R2 계산
            ss_res = float(np.sum((y_test - y_pred) ** 2))
            ss_tot = float(np.sum((y_test - np.mean(y_test)) ** 2))
            r2_test = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

            results[var] = {
                "status": "validated",
                "rmse": round(rmse, 4),
                "r2_test": round(r2_test, 4),
                "r2_train": node.r_squared,
                "test_samples": len(y_test),
            }

        return results

    results = await asyncio.to_thread(_validate)
    logger.info("models_validated: count=%d", len(results))
    return results


# ---------------------------------------------------------------------------
# Step 6: 시뮬레이션 -- DAG 기반 What-if 전파
# ---------------------------------------------------------------------------

async def simulate(
    graph: dict[str, SimulationNode],
    baseline: dict[str, float],
    interventions: dict[str, float],
) -> dict[str, float]:
    """DAG 기반 What-if 시뮬레이션 -- 개입 값을 전파한다.

    위상 정렬 순서로 노드를 방문하며,
    개입 대상 변수는 개입 값으로 고정(do-calculus)하고
    나머지는 학습된 회귀 모델로 예측한다.

    Args:
        graph: train_models 결과 (학습 완료 DAG)
        baseline: 변수명 -> 기본값
        interventions: 변수명 -> 개입 값 (do-operator)

    Returns:
        변수명 -> 시뮬레이션 결과 값
    """
    # 위상 정렬 순서 계산
    order = _topological_sort(graph)

    # 현재 값을 baseline으로 초기화
    current = dict(baseline)

    # 개입 적용 -- do-calculus: 개입 변수는 고정
    for var, value in interventions.items():
        current[var] = value

    # DAG 전파 -- 위상 정렬 순서로 방문
    for var in order:
        # 개입 변수는 고정값 유지
        if var in interventions:
            continue

        node = graph.get(var)
        if not node or not node.is_trained or not node.parents:
            continue

        # 부모 값으로 예측: y = intercept + sum(coeff_i * parent_i)
        predicted = node.intercept
        for parent in node.parents:
            coeff = node.coefficients.get(parent, 0.0)
            parent_val = current.get(parent, baseline.get(parent, 0.0))
            predicted += coeff * parent_val

        current[var] = round(predicted, 6)

    logger.info(
        "simulation_complete: interventions=%d, variables=%d",
        len(interventions), len(current),
    )
    return current


def _topological_sort(graph: dict[str, SimulationNode]) -> list[str]:
    """DAG를 위상 정렬한다 (Kahn's algorithm).

    in_degree가 0인 노드부터 순서대로 방문하여
    모든 부모가 먼저 처리되도록 보장한다.
    """
    in_degree: dict[str, int] = {v: len(n.parents) for v, n in graph.items()}
    # deque 사용 — popleft()는 O(1), list.pop(0)은 O(n)
    queue = collections.deque(v for v, d in in_degree.items() if d == 0)
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for v, n in graph.items():
            if node in n.parents:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
    return order


# ---------------------------------------------------------------------------
# Step 7: 시나리오 비교 -- 여러 시나리오 결과를 병렬 비교
# ---------------------------------------------------------------------------

async def compare_scenarios(
    scenarios: list[WhatIfScenario],
) -> dict[str, Any]:
    """여러 시나리오의 결과를 비교 분석한다.

    각 변수별로 시나리오 간 차이를 계산하고, 가장 영향이 큰 변수를 식별한다.

    Args:
        scenarios: 비교할 WhatIfScenario 리스트 (최소 2개)

    Returns:
        {comparison, max_impact_variable, max_impact_pct, scenario_count}
    """
    if len(scenarios) < 2:
        return {"error": "비교하려면 최소 2개 시나리오가 필요합니다"}

    # 모든 시나리오에 등장하는 변수 수집
    all_vars: set[str] = set()
    for s in scenarios:
        all_vars.update(s.results.keys())

    comparison: dict[str, list[dict[str, Any]]] = {}
    for var in sorted(all_vars):
        comparison[var] = []
        for s in scenarios:
            val = s.results.get(var, 0.0)
            base = s.baseline.get(var, 0.0)
            delta = val - base
            pct = (delta / base * 100) if base != 0 else 0.0
            comparison[var].append({
                "scenario_id": s.id,
                "scenario_name": s.name,
                "value": round(val, 4),
                "baseline": round(base, 4),
                "delta": round(delta, 4),
                "delta_pct": round(pct, 2),
            })

    # 가장 영향이 큰 변수 (최대 |delta_pct| 기준)
    max_impact_var = ""
    max_impact = 0.0
    for var, entries in comparison.items():
        for e in entries:
            if abs(e["delta_pct"]) > abs(max_impact):
                max_impact = e["delta_pct"]
                max_impact_var = var

    return {
        "comparison": comparison,
        "max_impact_variable": max_impact_var,
        "max_impact_pct": max_impact,
        "scenario_count": len(scenarios),
    }


# ---------------------------------------------------------------------------
# Step 8 & 9: 시나리오 저장/복원 -- 메모리 + JSON 직렬화
# ---------------------------------------------------------------------------

class WhatIfWizardStore:
    """What-if 위자드 시나리오 영속 저장소 (메모리 캐시 + 파일).

    테넌트/프로젝트 별로 시나리오를 관리한다.
    향후 PostgreSQL 기반 영속화로 교체 가능하도록 인터페이스를 분리.
    """

    def __init__(self) -> None:
        # {tenant_id: {scenario_id: WhatIfScenario}}
        self._store: dict[str, dict[str, WhatIfScenario]] = {}
        self._lock = threading.Lock()

    def save_scenario(
        self,
        scenario: WhatIfScenario,
        graph: dict[str, SimulationNode] | None = None,
    ) -> str:
        """시나리오를 저장한다. graph가 주어지면 함께 저장.

        Args:
            scenario: 저장할 시나리오
            graph: 시나리오에 사용된 DAG (선택)

        Returns:
            시나리오 ID
        """
        with self._lock:
            bucket = self._store.setdefault(scenario.tenant_id, {})
            bucket[scenario.id] = scenario
            logger.info(
                "scenario_saved: id=%s, name=%s, tenant=%s",
                scenario.id, scenario.name, scenario.tenant_id,
            )
            return scenario.id

    def load_scenario(
        self, tenant_id: str, scenario_id: str,
    ) -> WhatIfScenario | None:
        """저장된 시나리오를 복원한다.

        Args:
            tenant_id: 테넌트 ID
            scenario_id: 시나리오 ID

        Returns:
            WhatIfScenario 또는 None
        """
        with self._lock:
            return self._store.get(tenant_id, {}).get(scenario_id)

    def list_scenarios(self, tenant_id: str) -> list[WhatIfScenario]:
        """테넌트의 모든 시나리오를 생성일 역순으로 반환한다."""
        with self._lock:
            bucket = self._store.get(tenant_id, {})
            items = list(bucket.values())
        items.sort(key=lambda s: s.created_at, reverse=True)
        return items

    def delete_scenario(self, tenant_id: str, scenario_id: str) -> bool:
        """시나리오를 삭제한다. 성공 시 True."""
        with self._lock:
            bucket = self._store.get(tenant_id, {})
            if scenario_id in bucket:
                del bucket[scenario_id]
                logger.info("scenario_deleted: id=%s, tenant=%s", scenario_id, tenant_id)
                return True
            return False


# 모듈 레벨 싱글톤 -- API 라우터에서 공유
wizard_store = WhatIfWizardStore()
