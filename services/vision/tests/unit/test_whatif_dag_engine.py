"""
What-if DAG 전파 엔진 단위 / 통합 테스트
==========================================

WhatIfDAGEngine의 핵심 알고리즘을 검증한다:
- 단일 개입 전파
- 다중 개입 전파
- 연쇄 전파 (2차, 3차)
- 순환 방지 (executed_models set)
- 수렴 조건 (delta < 1e-6)
- disabled 모델 건너뛰기
- 빈 모델 그래프 처리
- 누적 lag 추적 (effective_day)
- 시나리오 비교
"""

import pytest

from app.engines.whatif_dag_engine import WhatIfDAGEngine
from app.engines.whatif_fallback import FallbackPredictor
from app.engines.whatif_models import InterventionSpec


# ── 테스트용 헬퍼 ──

def _make_simple_graph() -> dict:
    """
    간단한 모델 그래프: 노드 3개, 모델 1개.

    node_costs::cost_index --[READS_FIELD]--> model_defect
                                              --[PREDICTS_FIELD]--> node_quality::defect_rate
    """
    return {
        "models": [
            {"id": "model_defect", "name": "불량률 예측", "status": "trained"},
        ],
        "reads": [
            {
                "modelId": "model_defect",
                "sourceNodeId": "node_costs",
                "field": "cost_index",
                "lag": 0,
                "featureName": "cost_index",
            },
        ],
        "predicts": [
            {
                "modelId": "model_defect",
                "targetNodeId": "node_quality",
                "field": "defect_rate",
                "confidence": 0.85,
            },
        ],
    }


def _make_chain_graph() -> dict:
    """
    연쇄 전파 그래프: A → model_B → B → model_C → C

    node_A::metric_a --[READS]--> model_B --[PREDICTS]--> node_B::metric_b
    node_B::metric_b --[READS]--> model_C --[PREDICTS]--> node_C::metric_c
    """
    return {
        "models": [
            {"id": "model_B", "name": "B 예측", "status": "trained"},
            {"id": "model_C", "name": "C 예측", "status": "trained"},
        ],
        "reads": [
            {"modelId": "model_B", "sourceNodeId": "node_A", "field": "metric_a", "lag": 0, "featureName": "metric_a"},
            {"modelId": "model_C", "sourceNodeId": "node_B", "field": "metric_b", "lag": 3, "featureName": "metric_b"},
        ],
        "predicts": [
            {"modelId": "model_B", "targetNodeId": "node_B", "field": "metric_b", "confidence": 0.9},
            {"modelId": "model_C", "targetNodeId": "node_C", "field": "metric_c", "confidence": 0.8},
        ],
    }


def _make_multi_input_graph() -> dict:
    """
    다중 입력 모델: 2개 입력, 1개 출력.

    node_A::a + node_B::b --[READS]--> model_out --[PREDICTS]--> node_C::c
    """
    return {
        "models": [
            {"id": "model_out", "name": "종합 예측", "status": "trained"},
        ],
        "reads": [
            {"modelId": "model_out", "sourceNodeId": "node_A", "field": "a", "lag": 0, "featureName": "a"},
            {"modelId": "model_out", "sourceNodeId": "node_B", "field": "b", "lag": 2, "featureName": "b"},
        ],
        "predicts": [
            {"modelId": "model_out", "targetNodeId": "node_C", "field": "c", "confidence": 0.9},
        ],
    }


# ── 단위 테스트 ──

class TestWhatIfDAGEngine:
    """WhatIfDAGEngine 핵심 알고리즘 테스트."""

    @pytest.mark.asyncio
    async def test_empty_model_graph(self):
        """모델이 없으면 빈 결과 반환."""
        engine = WhatIfDAGEngine()
        result = await engine.simulate(
            model_graph={"models": [], "reads": [], "predicts": []},
            interventions=[InterventionSpec(node_id="n", field="f", value=1.0)],
            baseline_data={},
        )
        assert result.traces == []
        assert result.propagation_waves == 0
        assert result.converged is True

    @pytest.mark.asyncio
    async def test_single_intervention_propagation(self):
        """단일 개입 → 모델 1개 실행 → trace 1개."""
        engine = WhatIfDAGEngine()
        graph = _make_simple_graph()
        baseline = {
            "node_costs::cost_index": 100.0,
            "node_quality::defect_rate": 3.2,
        }

        result = await engine.simulate(
            model_graph=graph,
            interventions=[InterventionSpec(node_id="node_costs", field="cost_index", value=150.0)],
            baseline_data=baseline,
            scenario_name="원가 인상",
        )

        assert result.scenario_name == "원가 인상"
        # 모델이 학습되지 않았으므로 FallbackPredictor는 None → baseline 유지
        # 하지만 intervention 자체가 state에 반영됨
        assert result.final_state["node_costs::cost_index"] == 150.0
        # 1 wave 실행 (모델 1개)
        assert result.propagation_waves >= 1

    @pytest.mark.asyncio
    async def test_chain_propagation(self):
        """연쇄 전파: A→B→C, 2 wave 실행."""
        engine = WhatIfDAGEngine()
        graph = _make_chain_graph()
        baseline = {
            "node_A::metric_a": 10.0,
            "node_B::metric_b": 20.0,
            "node_C::metric_c": 30.0,
        }

        result = await engine.simulate(
            model_graph=graph,
            interventions=[InterventionSpec(node_id="node_A", field="metric_a", value=15.0)],
            baseline_data=baseline,
        )

        # FallbackPredictor가 학습되지 않았으므로 baseline 유지 → delta=0 → 전파 중단
        # wave 1: model_B 실행 (delta=0 → 수렴)
        assert result.propagation_waves >= 1

    @pytest.mark.asyncio
    async def test_cumulative_lag_tracking(self):
        """누적 lag 추적: chain A(lag=0)→B(lag=3) → effective_day가 누적."""
        engine = WhatIfDAGEngine()
        graph = _make_chain_graph()

        # FallbackPredictor를 학습시켜서 실제 전파가 일어나게 함
        import numpy as np
        import pandas as pd
        fallback = FallbackPredictor()

        # model_B: metric_a → metric_b (lag=0)
        df_b = pd.DataFrame({"metric_a": np.arange(50, dtype=float), "metric_b": np.arange(50, dtype=float) * 2})
        fallback.train("model_B", df_b, "metric_b", ["metric_a"])

        # model_C: metric_b → metric_c (lag=3)
        df_c = pd.DataFrame({"metric_b": np.arange(50, dtype=float), "metric_c": np.arange(50, dtype=float) * 3})
        fallback.train("model_C", df_c, "metric_c", ["metric_b"])

        engine = WhatIfDAGEngine(fallback_predictor=fallback)

        baseline = {
            "node_A::metric_a": 10.0,
            "node_B::metric_b": 20.0,
            "node_C::metric_c": 60.0,
        }

        result = await engine.simulate(
            model_graph=graph,
            interventions=[InterventionSpec(node_id="node_A", field="metric_a", value=15.0)],
            baseline_data=baseline,
        )

        # 2 wave: model_B(wave=0, lag=0, eff_day=0) → model_C(wave=1, lag=3, eff_day=0+3=3)
        assert result.propagation_waves == 2
        assert len(result.traces) == 2

        trace_b = [t for t in result.traces if t.model_id == "model_B"][0]
        trace_c = [t for t in result.traces if t.model_id == "model_C"][0]

        assert trace_b.effective_day == 0   # lag=0, 부모=Day0
        assert trace_c.effective_day == 3   # lag=3, 부모(model_B 출력)=Day0 → 0+3=3

    @pytest.mark.asyncio
    async def test_disabled_model_skipped(self):
        """disabled 상태 모델은 건너뜀."""
        engine = WhatIfDAGEngine()
        graph = _make_simple_graph()
        graph["models"][0]["status"] = "disabled"

        baseline = {"node_costs::cost_index": 100.0, "node_quality::defect_rate": 3.2}
        result = await engine.simulate(
            model_graph=graph,
            interventions=[InterventionSpec(node_id="node_costs", field="cost_index", value=150.0)],
            baseline_data=baseline,
        )

        # disabled 모델은 건너뛰므로 trace 없음
        assert len(result.traces) == 0

    @pytest.mark.asyncio
    async def test_convergence_when_no_delta(self):
        """delta가 0이면 수렴 → 추가 전파 없음."""
        engine = WhatIfDAGEngine()
        graph = _make_simple_graph()
        baseline = {"node_costs::cost_index": 100.0, "node_quality::defect_rate": 3.2}

        result = await engine.simulate(
            model_graph=graph,
            interventions=[InterventionSpec(node_id="node_costs", field="cost_index", value=150.0)],
            baseline_data=baseline,
        )

        # FallbackPredictor 미학습 → baseline 유지 → delta=0 → 수렴
        assert result.converged is True

    @pytest.mark.asyncio
    async def test_max_waves_limit(self):
        """MAX_WAVES 제한 동작 확인."""
        engine = WhatIfDAGEngine()
        engine.MAX_WAVES = 3  # 테스트용으로 줄임

        # 계속 전파되는 그래프는 없지만 MAX_WAVES 설정 자체가 동작하는지 확인
        graph = _make_simple_graph()
        baseline = {"node_costs::cost_index": 100.0, "node_quality::defect_rate": 3.2}

        result = await engine.simulate(
            model_graph=graph,
            interventions=[InterventionSpec(node_id="node_costs", field="cost_index", value=150.0)],
            baseline_data=baseline,
        )
        assert result.propagation_waves <= 3

    @pytest.mark.asyncio
    async def test_multi_input_model(self):
        """2개 입력을 받는 모델 테스트."""
        engine = WhatIfDAGEngine()
        graph = _make_multi_input_graph()
        baseline = {
            "node_A::a": 10.0,
            "node_B::b": 20.0,
            "node_C::c": 30.0,
        }

        result = await engine.simulate(
            model_graph=graph,
            interventions=[
                InterventionSpec(node_id="node_A", field="a", value=15.0),
                InterventionSpec(node_id="node_B", field="b", value=25.0),
            ],
            baseline_data=baseline,
        )

        # 2개 입력 변경 → model_out 실행
        assert result.final_state["node_A::a"] == 15.0
        assert result.final_state["node_B::b"] == 25.0

    @pytest.mark.asyncio
    async def test_intervention_applied_to_state(self):
        """개입값이 final_state에 반영."""
        engine = WhatIfDAGEngine()
        result = await engine.simulate(
            model_graph={"models": [], "reads": [], "predicts": []},
            interventions=[InterventionSpec(node_id="n1", field="f1", value=999.0)],
            baseline_data={"n1::f1": 0.0},
        )
        assert result.final_state["n1::f1"] == 999.0

    @pytest.mark.asyncio
    async def test_deltas_only_significant(self):
        """deltas에는 변화가 의미 있는 것만 포함."""
        engine = WhatIfDAGEngine()
        result = await engine.simulate(
            model_graph={"models": [], "reads": [], "predicts": []},
            interventions=[InterventionSpec(node_id="n1", field="f1", value=100.0)],
            baseline_data={"n1::f1": 100.0, "n2::f2": 50.0},
        )
        # n1::f1 = 100 → 100 (변화 없음), n2::f2 변화 없음
        assert "n2::f2" not in result.deltas
        assert "n1::f1" not in result.deltas

    @pytest.mark.asyncio
    async def test_duplicate_reads_deduplication(self):
        """동일 field를 여러 번 읽는 READS_FIELD는 중복 제거."""
        engine = WhatIfDAGEngine()
        graph = {
            "models": [{"id": "m1", "name": "test", "status": "trained"}],
            "reads": [
                {"modelId": "m1", "sourceNodeId": "n1", "field": "f1", "lag": 0, "featureName": "f1"},
                {"modelId": "m1", "sourceNodeId": "n1", "field": "f1", "lag": 0, "featureName": "f1"},  # 중복
            ],
            "predicts": [
                {"modelId": "m1", "targetNodeId": "n2", "field": "f2", "confidence": 0.9},
            ],
        }
        baseline = {"n1::f1": 10.0, "n2::f2": 20.0}

        result = await engine.simulate(
            model_graph=graph,
            interventions=[InterventionSpec(node_id="n1", field="f1", value=15.0)],
            baseline_data=baseline,
        )

        # 중복 제거 후 정상 실행
        assert len(result.traces) == 1
        # 입력에 f1이 1번만 있어야 함
        assert len(result.traces[0].inputs) == 1


# ── 시나리오 비교 테스트 ──

class TestCompareScenarios:
    """시나리오 비교 기능 테스트."""

    @pytest.mark.asyncio
    async def test_compare_two_scenarios(self):
        """2개 시나리오 비교."""
        engine = WhatIfDAGEngine()
        graph = _make_simple_graph()
        baseline = {"node_costs::cost_index": 100.0, "node_quality::defect_rate": 3.2}

        comparison = await engine.compare_scenarios(
            model_graph=graph,
            scenarios=[
                {"name": "시나리오A", "interventions": [{"node_id": "node_costs", "field": "cost_index", "value": 120.0}]},
                {"name": "시나리오B", "interventions": [{"node_id": "node_costs", "field": "cost_index", "value": 180.0}]},
            ],
            baseline_data=baseline,
        )

        assert "scenarios" in comparison
        assert len(comparison["scenarios"]) == 2
        assert comparison["scenarios"][0]["scenario_name"] == "시나리오A"
        assert comparison["scenarios"][1]["scenario_name"] == "시나리오B"
        assert "comparison" in comparison
