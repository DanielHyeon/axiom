"""
What-if DAG 시뮬레이션 데이터 모델
====================================

온톨로지 DAG 기반 What-if 시뮬레이션에 사용되는 핵심 데이터 구조.

- InterventionSpec: 사용자가 "이 변수를 이 값으로 변경하면?" 하고 지정하는 개입 정의
- SimulationTrace: 단일 모델이 실행된 기록 (입력, 출력, 변화량 등)
- SimulationResult: 시뮬레이션 전체 결과 (모든 트레이스 + 타임라인 + 최종 상태)

frozen=True로 불변 객체를 보장한다 (SimulationResult 제외 -- 내부에서 조립 필요).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class InterventionSpec:
    """
    개입 정의 -- 사용자가 "이 변수를 이 값으로 바꾸면?" 지정.

    예: InterventionSpec(node_id="node_costs", field="cost_index", value=150.0, description="원가 50% 인상")
    -> 시뮬레이션 내부에서 "node_costs::cost_index" = 150.0 으로 세팅된다.
    """

    node_id: str       # 온톨로지 노드 ID
    field: str         # 해당 노드의 필드명
    value: float       # 개입 값 (이 값으로 변경)
    description: str = ""  # 사용자가 읽을 수 있는 설명

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "field": self.field,
            "value": self.value,
            "description": self.description,
        }


@dataclass(frozen=True)
class SimulationTrace:
    """
    단일 모델 실행 트레이스 -- 모델 하나가 실행될 때마다 기록.

    예를 들어 "불량률 예측" 모델이 실행되면:
    - inputs: {"cost_index": 150.0} (모델에 들어간 입력값)
    - output_field: "node_quality::defect_rate" (예측 대상)
    - baseline_value: 3.2 (변경 전 값)
    - predicted_value: 4.8 (모델이 예측한 값)
    - delta: 1.6 (변화량)
    - wave: 0 (첫 번째 전파 단계)
    - effective_day: 3 (lag=3일 이므로 Day+3에 반영)
    """

    model_id: str                  # 실행된 모델 ID
    model_name: str                # 모델 이름 (사람이 읽을 수 있는)
    inputs: dict[str, float]       # 모델에 들어간 입력값
    output_field: str              # 출력 필드 ("nodeId::fieldName" 형식)
    baseline_value: float          # 변경 전 기준값
    predicted_value: float         # 모델이 예측한 값
    delta: float                   # 변화량 (predicted - baseline)
    pct_change: float              # 변화율 (%)
    wave: int = 0                  # 전파 단계 (0 = 직접 영향, 1 = 1차 연쇄, ...)
    effective_day: int = 0         # 누적 lag 반영된 실제 Day
    triggered_by: tuple[str, ...] = ()  # 이 모델을 트리거한 변경 변수들

    def to_dict(self) -> dict[str, Any]:
        """JSON 직렬화용. NaN/inf는 None으로 변환."""
        def _safe(v: float) -> Any:
            if math.isnan(v) or math.isinf(v):
                return None
            return round(v, 4)

        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "inputs": {k: _safe(v) for k, v in self.inputs.items()},
            "output_field": self.output_field,
            "baseline_value": _safe(self.baseline_value),
            "predicted_value": _safe(self.predicted_value),
            "delta": _safe(self.delta),
            "pct_change": round(self.pct_change, 2) if not (math.isnan(self.pct_change) or math.isinf(self.pct_change)) else None,
            "wave": self.wave,
            "effective_day": self.effective_day,
            "triggered_by": list(self.triggered_by),
        }


@dataclass
class SimulationResult:
    """
    시뮬레이션 전체 결과.

    시뮬레이션이 끝나면 이 객체 하나에 모든 정보가 담긴다:
    - traces: 모든 모델 실행 기록
    - timeline: 날짜별로 묶은 트레이스 (Day 0, Day 3, Day 5 ...)
    - final_state: 시뮬레이션 후 모든 변수의 최종 값
    - baseline_state: 시뮬레이션 전 모든 변수의 기준값
    - deltas: 변화가 있는 변수들만의 차이값
    """

    scenario_name: str
    interventions: list[InterventionSpec]
    traces: list[SimulationTrace] = field(default_factory=list)
    timeline: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    final_state: dict[str, float] = field(default_factory=dict)
    baseline_state: dict[str, float] = field(default_factory=dict)
    deltas: dict[str, float] = field(default_factory=dict)
    executed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    propagation_waves: int = 0
    converged: bool = False  # 수렴 여부 (delta < 1e-6 조건 달성 시 True)

    def to_dict(self) -> dict[str, Any]:
        """API 응답용 JSON 직렬화."""

        def _safe_round(v: float, digits: int = 4) -> Any:
            if math.isnan(v) or math.isinf(v):
                return None
            return round(v, digits)

        return {
            "scenario_name": self.scenario_name,
            "interventions": [i.to_dict() for i in self.interventions],
            "traces": [t.to_dict() for t in self.traces],
            "timeline": {
                str(day): traces_list
                for day, traces_list in sorted(self.timeline.items())
            },
            "final_state": {
                k: _safe_round(v) for k, v in self.final_state.items()
            },
            "baseline_state": {
                k: _safe_round(v) for k, v in self.baseline_state.items()
            },
            "deltas": {
                k: _safe_round(v) for k, v in self.deltas.items()
            },
            "executed_at": self.executed_at,
            "propagation_waves": self.propagation_waves,
            "converged": self.converged,
        }
