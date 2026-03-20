"""
What-if 데이터 모델 단위 테스트
================================

InterventionSpec, SimulationTrace, SimulationResult의
생성, 직렬화, NaN/inf 처리를 검증한다.
"""

import math

import pytest

from app.engines.whatif_models import InterventionSpec, SimulationResult, SimulationTrace


# ── InterventionSpec ──

class TestInterventionSpec:
    """개입 정의 테스트."""

    def test_frozen_dataclass(self):
        """frozen=True이므로 값 변경 시 에러."""
        spec = InterventionSpec(node_id="n1", field="cost", value=100.0)
        with pytest.raises(AttributeError):
            spec.value = 200.0  # type: ignore[misc]

    def test_to_dict(self):
        """to_dict()가 올바른 딕셔너리를 반환."""
        spec = InterventionSpec(node_id="n1", field="cost", value=150.0, description="원가 인상")
        d = spec.to_dict()
        assert d == {
            "node_id": "n1",
            "field": "cost",
            "value": 150.0,
            "description": "원가 인상",
        }

    def test_default_description(self):
        """description 기본값은 빈 문자열."""
        spec = InterventionSpec(node_id="n1", field="cost", value=100.0)
        assert spec.description == ""


# ── SimulationTrace ──

class TestSimulationTrace:
    """단일 모델 실행 트레이스 테스트."""

    def test_frozen_dataclass(self):
        """frozen=True이므로 값 변경 시 에러."""
        trace = SimulationTrace(
            model_id="m1", model_name="test", inputs={}, output_field="n::f",
            baseline_value=1.0, predicted_value=2.0, delta=1.0, pct_change=100.0,
        )
        with pytest.raises(AttributeError):
            trace.delta = 0.5  # type: ignore[misc]

    def test_to_dict_rounding(self):
        """to_dict()가 4자리 반올림을 적용."""
        trace = SimulationTrace(
            model_id="m1", model_name="불량률 예측",
            inputs={"cost_index": 150.123456},
            output_field="node_quality::defect_rate",
            baseline_value=3.123456, predicted_value=4.876543,
            delta=1.753087, pct_change=56.14285714,
            wave=0, effective_day=3,
            triggered_by=("node_costs::cost_index",),
        )
        d = trace.to_dict()
        assert d["baseline_value"] == 3.1235
        assert d["predicted_value"] == 4.8765
        assert d["delta"] == 1.7531
        assert d["pct_change"] == 56.14
        assert d["triggered_by"] == ["node_costs::cost_index"]

    def test_to_dict_nan_handling(self):
        """NaN 값은 None으로 변환."""
        trace = SimulationTrace(
            model_id="m1", model_name="test", inputs={"x": float("nan")},
            output_field="n::f",
            baseline_value=float("nan"), predicted_value=float("inf"),
            delta=float("-inf"), pct_change=float("nan"),
        )
        d = trace.to_dict()
        assert d["baseline_value"] is None
        assert d["predicted_value"] is None
        assert d["delta"] is None
        assert d["pct_change"] is None
        assert d["inputs"]["x"] is None

    def test_triggered_by_tuple(self):
        """triggered_by는 tuple로 저장되고, to_dict에서 list로 변환."""
        trace = SimulationTrace(
            model_id="m1", model_name="test", inputs={},
            output_field="n::f", baseline_value=0, predicted_value=0,
            delta=0, pct_change=0,
            triggered_by=("a::b", "c::d"),
        )
        assert isinstance(trace.triggered_by, tuple)
        assert isinstance(trace.to_dict()["triggered_by"], list)


# ── SimulationResult ──

class TestSimulationResult:
    """시뮬레이션 전체 결과 테스트."""

    def test_empty_result(self):
        """빈 결과 생성."""
        result = SimulationResult(
            scenario_name="테스트",
            interventions=[],
        )
        assert result.propagation_waves == 0
        assert result.traces == []
        assert result.converged is False

    def test_to_dict_structure(self):
        """to_dict()가 올바른 키 구조를 반환."""
        intervention = InterventionSpec(node_id="n1", field="f1", value=100.0)
        result = SimulationResult(
            scenario_name="시나리오A",
            interventions=[intervention],
            final_state={"n1::f1": 100.0},
            baseline_state={"n1::f1": 50.0},
            deltas={"n1::f1": 50.0},
            propagation_waves=2,
            converged=True,
        )
        d = result.to_dict()
        assert d["scenario_name"] == "시나리오A"
        assert len(d["interventions"]) == 1
        assert d["propagation_waves"] == 2
        assert d["converged"] is True
        assert "executed_at" in d

    def test_to_dict_timeline_sorted(self):
        """timeline은 day 기준 정렬."""
        result = SimulationResult(
            scenario_name="test",
            interventions=[],
            timeline={5: [{"x": 1}], 0: [{"x": 2}], 3: [{"x": 3}]},
        )
        d = result.to_dict()
        keys = list(d["timeline"].keys())
        assert keys == ["0", "3", "5"]

    def test_to_dict_nan_in_state(self):
        """final_state/baseline_state의 NaN/inf는 None으로 변환."""
        result = SimulationResult(
            scenario_name="test",
            interventions=[],
            final_state={"a::b": float("nan"), "c::d": float("inf")},
            baseline_state={"a::b": 1.0},
            deltas={"a::b": float("-inf")},
        )
        d = result.to_dict()
        assert d["final_state"]["a::b"] is None
        assert d["final_state"]["c::d"] is None
        assert d["deltas"]["a::b"] is None
