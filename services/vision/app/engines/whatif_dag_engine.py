"""
What-if DAG 전파 시뮬레이션 엔진
==================================

온톨로지 DAG(방향 비순환 그래프) 기반 증분 전파 What-if 시뮬레이션 엔진.

KAIR의 WhatIfSimulationEngine을 Axiom에 이식하되, 리뷰 수정 사항을 반영:
- effective_day: wave 기반이 아닌 **누적 lag 추적** (체인 전파 정확성)
- datetime.now(timezone.utc) 사용
- 수렴 여부 필드 추가 (converged)

알고리즘 (증분 전파 루프):
  1. intervention으로 변경된 변수 수집 -> changed_vars = {"nodeId::field": value}
  2. WHILE changed_vars 존재 AND wave < MAX_WAVES:
     a. 변경된 변수를 READS_FIELD로 읽는 모델 찾기 (역인덱스: field_to_models)
     b. 이미 실행된 모델 제외 (executed_models set -> DAG 순환 방지)
     c. 각 모델 실행:
        - 입력 필드들의 lag 합산 -> effective_day = 부모의 effective_day + max_lag
        - 입력값 구성: state[key] 또는 baseline[key] 사용
        - FallbackPredictor.predict() 호출, 실패 시 baseline 유지
        - state[output_key] = predicted
        - delta = predicted - baseline -> |delta| > 1e-6 이면 다음 wave로 전파
     d. executed_models |= 이번 wave 실행 모델들
     e. changed_vars = 새로 변경된 변수들
     f. wave += 1
  3. 결과 조립: traces, timeline(day별), final_state, deltas, converged

그래프 패턴:
  OntologyType --[READS_FIELD]--> OntologyBehavior:Model --[PREDICTS_FIELD]--> OntologyType
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Any

from app.engines.whatif_fallback import FallbackPredictor
from app.engines.whatif_models import InterventionSpec, SimulationResult, SimulationTrace

logger = logging.getLogger(__name__)


class WhatIfDAGEngine:
    """
    온톨로지 DAG 기반 증분 전파 What-if 시뮬레이션 엔진.

    변경된 변수 -> 영향받는 모델만 실행 -> 출력이 다른 모델 트리거 -> 연쇄 반응.
    최대 MAX_WAVES 번 반복하고, 모든 delta가 CONVERGENCE_THRESHOLD 이하이면 수렴.
    """

    # 최대 전파 횟수 (무한 루프 방지)
    MAX_WAVES: int = int(os.getenv("WHATIF_MAX_WAVES", "20"))
    # 수렴 임계값: 모든 모델 출력의 delta가 이 값 이하이면 수렴
    CONVERGENCE_THRESHOLD: float = float(os.getenv("WHATIF_CONVERGENCE_THRESHOLD", "1e-6"))

    def __init__(self, fallback_predictor: FallbackPredictor | None = None) -> None:
        # FallbackPredictor가 없으면 빈 예측기 생성 (predict는 항상 None 반환)
        self.fallback = fallback_predictor or FallbackPredictor()

    async def simulate(
        self,
        model_graph: dict[str, Any],
        interventions: list[InterventionSpec],
        baseline_data: dict[str, float],
        scenario_name: str = "Scenario",
    ) -> SimulationResult:
        """
        시뮬레이션 실행 (핵심 메서드).

        Args:
            model_graph: 모델 그래프 구조
                {
                    "models": [{"id", "name", "status", ...}, ...],
                    "reads": [{"modelId", "sourceNodeId", "field", "lag", "featureName"}, ...],
                    "predicts": [{"modelId", "targetNodeId", "field", "confidence"}, ...]
                }
            interventions: 사용자 개입 목록
            baseline_data: 모든 변수의 기준값 {"nodeId::field": value}
            scenario_name: 시나리오 이름

        Returns:
            SimulationResult (traces, timeline, deltas 등 포함)
        """
        models = model_graph.get("models", [])
        reads = model_graph.get("reads", [])
        predicts = model_graph.get("predicts", [])

        # 모델이 없어도 개입값은 state에 반영하고 delta 계산
        if not models:
            logger.info("시뮬레이션 건너뜀: 모델 없음 (scenario=%s)", scenario_name)
            state: dict[str, float] = dict(baseline_data)
            for iv in interventions:
                key = f"{iv.node_id}::{iv.field}"
                state[key] = iv.value
            deltas = {
                k: state[k] - baseline_data.get(k, 0.0)
                for k in state
                if abs(state[k] - baseline_data.get(k, 0.0)) > self.CONVERGENCE_THRESHOLD
            }
            return SimulationResult(
                scenario_name=scenario_name,
                interventions=interventions,
                final_state=state,
                baseline_state=dict(baseline_data),
                deltas=deltas,
                converged=True,
            )

        # -- 1. 인덱스 구축 --
        model_inputs, model_output, field_to_models, model_map = self._build_indices(
            models, reads, predicts
        )

        # -- 2. 상태 초기화 + 개입값 적용 --
        state: dict[str, float] = dict(baseline_data)
        baseline_snapshot: dict[str, float] = dict(baseline_data)

        # 개입값을 state에 적용하고, 변경 변수 집합에 추가
        changed_vars: dict[str, float] = {}
        for intervention in interventions:
            key = f"{intervention.node_id}::{intervention.field}"
            state[key] = intervention.value
            changed_vars[key] = intervention.value

        # -- 3. 누적 lag 추적용 딕셔너리 --
        # 각 변수의 effective_day를 추적 (체인 전파 시 누적)
        # 개입 변수들은 Day 0에서 시작
        var_effective_day: dict[str, int] = {}
        for key in changed_vars:
            var_effective_day[key] = 0

        # -- 4. 증분 전파 루프 --
        all_traces, timeline, wave, converged = self._run_propagation_loop(
            changed_vars=changed_vars,
            model_inputs=model_inputs,
            model_output=model_output,
            field_to_models=field_to_models,
            model_map=model_map,
            state=state,
            baseline_data=baseline_data,
            var_effective_day=var_effective_day,
        )

        # -- 5. 결과 조립 --
        return self._assemble_result(
            scenario_name=scenario_name,
            interventions=interventions,
            all_traces=all_traces,
            timeline=timeline,
            state=state,
            baseline_snapshot=baseline_snapshot,
            wave=wave,
            converged=converged,
        )

    def _build_indices(
        self,
        models: list[dict[str, Any]],
        reads: list[dict[str, Any]],
        predicts: list[dict[str, Any]],
    ) -> tuple[
        dict[str, list[dict[str, Any]]],
        dict[str, dict[str, Any]],
        dict[str, set[str]],
        dict[str, dict[str, Any]],
    ]:
        """
        모델 그래프에서 빠른 조회를 위한 인덱스 구축.

        Returns:
            (model_inputs, model_output, field_to_models, model_map)
            - model_inputs: model_id -> [입력 READS_FIELD 목록] (중복 제거)
            - model_output: model_id -> 출력 PREDICTS_FIELD (첫 번째만)
            - field_to_models: "nodeId::field" -> {model_id 집합} (역인덱스)
            - model_map: model_id -> model_info dict
        """
        # model_id -> 입력 목록 (중복 field 제거)
        model_inputs: dict[str, list[dict[str, Any]]] = defaultdict(list)
        seen_inputs: dict[str, set[str]] = defaultdict(set)
        for r in reads:
            input_key = f"{r['sourceNodeId']}::{r['field']}"
            mid = r["modelId"]
            if input_key not in seen_inputs[mid]:
                seen_inputs[mid].add(input_key)
                model_inputs[mid].append(r)

        # model_id -> 출력 (첫 번째만 유지)
        model_output: dict[str, dict[str, Any]] = {}
        for p in predicts:
            if p["modelId"] not in model_output:
                model_output[p["modelId"]] = p

        # 역인덱스: field_key -> set(model_id)
        field_to_models: dict[str, set[str]] = defaultdict(set)
        for r in reads:
            key = f"{r['sourceNodeId']}::{r['field']}"
            field_to_models[key].add(r["modelId"])

        # model_id -> model_info
        model_map: dict[str, dict[str, Any]] = {m["id"]: m for m in models}

        return model_inputs, model_output, field_to_models, model_map

    def _run_propagation_loop(
        self,
        *,
        changed_vars: dict[str, float],
        model_inputs: dict[str, list[dict[str, Any]]],
        model_output: dict[str, dict[str, Any]],
        field_to_models: dict[str, set[str]],
        model_map: dict[str, dict[str, Any]],
        state: dict[str, float],
        baseline_data: dict[str, float],
        var_effective_day: dict[str, int],
    ) -> tuple[list[SimulationTrace], dict[int, list[dict[str, Any]]], int, bool]:
        """
        증분 전파 루프 실행 -- wave별 모델 실행 + 수렴 검사.

        Returns:
            (all_traces, timeline, wave, converged)
        """
        executed_models: set[str] = set()
        all_traces: list[SimulationTrace] = []
        timeline: dict[int, list[dict[str, Any]]] = defaultdict(list)
        wave = 0
        converged = False

        while changed_vars and wave < self.MAX_WAVES:
            # 변경된 변수를 읽는 모델 찾기 (이미 실행된 모델 제외)
            models_to_run: set[str] = set()
            trigger_map: dict[str, set[str]] = {}

            for var_key in changed_vars:
                for model_id in field_to_models.get(var_key, set()):
                    if model_id not in executed_models:
                        models_to_run.add(model_id)
                        if model_id not in trigger_map:
                            trigger_map[model_id] = set()
                        trigger_map[model_id].add(var_key)

            # 실행할 모델이 없으면 종료
            if not models_to_run:
                converged = True
                break

            new_changed_vars: dict[str, float] = {}
            all_deltas_small = True  # 이번 wave에서 모든 delta가 작은지 추적

            for model_id in models_to_run:
                trace = self._execute_single_model(
                    model_id=model_id,
                    model_map=model_map,
                    model_inputs=model_inputs,
                    model_output=model_output,
                    state=state,
                    baseline_data=baseline_data,
                    wave=wave,
                    trigger_map=trigger_map,
                    var_effective_day=var_effective_day,
                )
                if trace is None:
                    continue

                all_traces.append(trace)
                timeline[trace.effective_day].append(trace.to_dict())

                # 출력이 baseline과 충분히 다르면 -> 다음 wave 전파 대상
                if abs(trace.delta) > self.CONVERGENCE_THRESHOLD:
                    new_changed_vars[trace.output_field] = trace.predicted_value
                    all_deltas_small = False

            executed_models |= models_to_run
            changed_vars = new_changed_vars
            wave += 1

            # 이번 wave에서 모든 delta가 작으면 수렴
            if all_deltas_small:
                converged = True
                break

        return all_traces, dict(timeline), wave, converged

    def _assemble_result(
        self,
        *,
        scenario_name: str,
        interventions: list[InterventionSpec],
        all_traces: list[SimulationTrace],
        timeline: dict[int, list[dict[str, Any]]],
        state: dict[str, float],
        baseline_snapshot: dict[str, float],
        wave: int,
        converged: bool,
    ) -> SimulationResult:
        """시뮬레이션 결과 조립."""
        deltas: dict[str, float] = {}
        for key in state:
            if key in baseline_snapshot:
                d = state[key] - baseline_snapshot[key]
                if abs(d) > self.CONVERGENCE_THRESHOLD:
                    deltas[key] = d

        return SimulationResult(
            scenario_name=scenario_name,
            interventions=interventions,
            traces=all_traces,
            timeline=timeline,
            final_state=state,
            baseline_state=baseline_snapshot,
            deltas=deltas,
            propagation_waves=wave,
            converged=converged,
        )

    def _execute_single_model(
        self,
        model_id: str,
        model_map: dict[str, dict[str, Any]],
        model_inputs: dict[str, list[dict[str, Any]]],
        model_output: dict[str, dict[str, Any]],
        state: dict[str, float],
        baseline_data: dict[str, float],
        wave: int,
        trigger_map: dict[str, set[str]],
        var_effective_day: dict[str, int],
    ) -> SimulationTrace | None:
        """
        단일 모델 실행.

        1. disabled 모델 건너뜀
        2. 입력값 구성 (state 또는 baseline에서)
        3. effective_day 계산: 트리거 변수들의 effective_day 최대값 + 이 모델의 max_lag
        4. FallbackPredictor.predict() 호출
        5. 실패 시 baseline 유지
        6. SimulationTrace 반환
        """
        model_info = model_map.get(model_id)
        if not model_info:
            return None

        # disabled 모델은 건너뜀
        if model_info.get("status") == "disabled":
            logger.info("모델 건너뜀 (disabled): %s", model_info.get("name", model_id))
            return None

        model_name = model_info.get("name", model_id)
        inputs_spec = model_inputs.get(model_id, [])
        output_spec = model_output.get(model_id)

        if not inputs_spec or not output_spec:
            return None

        # -- effective_day 계산 (누적 lag 추적) --
        # 이 모델의 최대 lag
        max_lag = max((inp.get("lag", 0) or 0) for inp in inputs_spec)

        # 트리거 변수들의 effective_day 최대값 (체인 전파 시 누적)
        trigger_vars = trigger_map.get(model_id, set())
        parent_max_day = 0
        for tv in trigger_vars:
            parent_max_day = max(parent_max_day, var_effective_day.get(tv, 0))

        # 이 모델의 effective_day = 부모 effective_day + 이 모델의 max_lag
        effective_day = parent_max_day + max_lag

        # -- 입력값 구성 --
        input_values: dict[str, float] = {}
        for inp in inputs_spec:
            key = f"{inp['sourceNodeId']}::{inp['field']}"
            val = state.get(key, baseline_data.get(key, 0.0))
            feature_name = inp.get("featureName", inp["field"])
            input_values[feature_name] = float(val) if val is not None else 0.0

        # -- 출력 필드 키 --
        output_key = f"{output_spec['targetNodeId']}::{output_spec['field']}"
        baseline_value = baseline_data.get(output_key, 0.0)

        # -- 예측 실행 --
        predicted: float | None = None

        # FallbackPredictor로 예측
        if self.fallback:
            predicted = self.fallback.predict(model_id, input_values)

        # 예측 실패 시 baseline 유지
        if predicted is None:
            predicted = baseline_value

        # -- state 업데이트 --
        state[output_key] = predicted

        # -- 출력 변수의 effective_day 기록 (다음 모델이 참조) --
        var_effective_day[output_key] = effective_day

        # -- delta 계산 --
        delta = predicted - baseline_value
        pct = (delta / baseline_value * 100.0) if baseline_value != 0 else 0.0

        # -- 트리거 변수 목록 (정렬) --
        triggered_list = tuple(sorted(trigger_vars))

        trace = SimulationTrace(
            model_id=model_id,
            model_name=model_name,
            inputs=input_values,
            output_field=output_key,
            baseline_value=baseline_value,
            predicted_value=predicted,
            delta=delta,
            pct_change=pct,
            wave=wave,
            effective_day=effective_day,
            triggered_by=triggered_list,
        )

        logger.debug(
            "모델 실행: %s | wave=%d | day=%d | delta=%.6f | %s -> %.4f",
            model_name, wave, effective_day, delta, output_key, predicted,
        )

        return trace

    async def compare_scenarios(
        self,
        model_graph: dict[str, Any],
        scenarios: list[dict[str, Any]],
        baseline_data: dict[str, float],
    ) -> dict[str, Any]:
        """
        여러 시나리오를 비교 실행.

        Args:
            model_graph: 모델 그래프 구조
            scenarios: 시나리오 목록
                [{"name": "시나리오A", "interventions": [{...}]}, ...]
            baseline_data: 기준값

        Returns:
            {
                "scenarios": [SimulationResult.to_dict(), ...],
                "comparison": {"nodeId::field": {"시나리오A": delta, "시나리오B": delta}}
            }
        """
        results: list[dict[str, Any]] = []

        for scenario in scenarios:
            name = scenario.get("name", f"Scenario_{len(results) + 1}")
            raw_interventions = scenario.get("interventions", [])
            interventions = [
                InterventionSpec(**i) if isinstance(i, dict) else i
                for i in raw_interventions
            ]
            result = await self.simulate(model_graph, interventions, baseline_data, name)
            results.append(result.to_dict())

        # 시나리오 간 비교 테이블 구성
        comparison: dict[str, dict[str, float]] = {}
        if results:
            all_keys: set[str] = set()
            for r in results:
                all_keys.update(r.get("deltas", {}).keys())
            for key in sorted(all_keys):
                comparison[key] = {
                    r["scenario_name"]: r.get("deltas", {}).get(key, 0.0)
                    for r in results
                }

        return {"scenarios": results, "comparison": comparison}
