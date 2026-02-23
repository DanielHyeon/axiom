from __future__ import annotations

from collections import defaultdict
from pydantic import BaseModel
from typing import Any


class Deviation(BaseModel):
    """API 명세: process-mining-api §3.2 case_diagnostics.deviations."""
    position: int
    expected: str
    actual: str
    type: str  # "skipped_activity" | "unexpected_activity"
    description: str


class CaseDiagnostic(BaseModel):
    """API 명세: trace·deviations 포함."""
    instance_case_id: str
    is_fit: bool
    trace_fitness: float
    trace: list[str]
    deviations: list[Deviation]
    # 하위 호환용 (선택 노출 시 사용)
    missing_tokens: int = 0
    remaining_tokens: int = 0
    consumed_tokens: int = 0
    produced_tokens: int = 0

class ConformanceResult(BaseModel):
    fitness: float
    precision: float
    generalization: float
    simplicity: float
    total_cases: int
    conformant_cases: int
    case_diagnostics: list[CaseDiagnostic]
    deviation_statistics: dict[str, dict[str, int]]

def check_conformance(
    events: list[dict[str, Any]],
    designed_activities: list[str],
    include_case_diagnostics: bool = True,
    max_diagnostics_cases: int = 100,
) -> ConformanceResult:
    """
    Lightweight token-style conformance scoring.
    - reference net 대신 설계 활동 시퀀스를 기준으로 적합도 계산
    - case 단위 trace 비교로 fitness/diagnostics 생성
    """
    if not events:
        raise ValueError("events is empty")
    if not designed_activities:
        raise ValueError("designed_activities is empty")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[str(event["case_id"])].append(event)
    for case_id in grouped:
        grouped[case_id].sort(key=lambda item: item["timestamp"])

    total_cases = len(grouped)
    conformant_cases = 0
    diagnostics: list[CaseDiagnostic] = []
    skipped_stats: dict[str, int] = defaultdict(int)
    unexpected_stats: dict[str, int] = defaultdict(int)
    fitness_sum = 0.0

    for case_id, trace_events in grouped.items():
        trace = [item["activity"] for item in trace_events]
        missing = [a for a in designed_activities if a not in trace]
        extra_set = {a for a in trace if a not in designed_activities}
        extra_list = [a for a in trace if a not in designed_activities]
        missing_tokens = len(missing)
        remaining_tokens = len(extra_list)
        consumed_tokens = len(trace)
        produced_tokens = len(designed_activities)
        denom = max(1, consumed_tokens + produced_tokens)
        trace_fitness = max(0.0, 1.0 - ((missing_tokens + remaining_tokens) / denom))
        is_fit = (missing_tokens == 0) and (remaining_tokens == 0)
        if is_fit:
            conformant_cases += 1
        for activity in missing:
            skipped_stats[activity] += 1
        for activity in extra_list:
            unexpected_stats[activity] += 1
        fitness_sum += trace_fitness

        deviations: list[Deviation] = []
        for idx, activity in enumerate(designed_activities):
            if activity not in trace:
                deviations.append(
                    Deviation(
                        position=idx,
                        expected=activity,
                        actual="(누락)",
                        type="skipped_activity",
                        description=f"'{activity}' 활동이 누락됨",
                    )
                )
        for idx, activity in enumerate(trace):
            if activity in extra_set:
                deviations.append(
                    Deviation(
                        position=idx,
                        expected="(설계에 없음)",
                        actual=activity,
                        type="unexpected_activity",
                        description=f"설계에 없는 '{activity}' 활동이 발생",
                    )
                )
        if include_case_diagnostics and len(diagnostics) < max_diagnostics_cases:
            diagnostics.append(
                CaseDiagnostic(
                    instance_case_id=case_id,
                    is_fit=is_fit,
                    trace_fitness=round(trace_fitness, 3),
                    trace=trace,
                    deviations=deviations,
                    missing_tokens=missing_tokens,
                    remaining_tokens=remaining_tokens,
                    consumed_tokens=consumed_tokens,
                    produced_tokens=produced_tokens,
                )
            )

    avg_fitness = fitness_sum / max(1, total_cases)
    precision = max(0.0, min(1.0, 1.0 - (sum(unexpected_stats.values()) / max(1, total_cases * len(designed_activities)))))
    generalization = max(0.0, min(1.0, avg_fitness - 0.03))
    simplicity = 0.75

    return ConformanceResult(
        fitness=round(avg_fitness, 3),
        precision=round(precision, 3),
        generalization=round(generalization, 3),
        simplicity=simplicity,
        total_cases=total_cases,
        conformant_cases=conformant_cases,
        case_diagnostics=diagnostics,
        deviation_statistics={
            "skipped_activities": dict(skipped_stats),
            "unexpected_activities": dict(unexpected_stats),
        },
    )
