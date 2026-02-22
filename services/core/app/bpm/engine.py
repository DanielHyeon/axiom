"""
BPM 실행 엔진 (bpm-engine.md §3).
정의(definition)와 완료된 액티비티를 기준으로 다음 액티비티를 결정.
DB/이벤트는 process_service에서 처리하고, 여기서는 순수 흐름 계산만.
"""
from __future__ import annotations

from typing import Any, Optional

from app.bpm.models import (
    ActivityType,
    AgentMode,
    ProcessActivityModel,
    ProcessDefinitionModel,
)


# 현재 서비스와 동일한 기본 동작 유지
DEFAULT_INITIAL_ACTIVITY = "Initial Review"
DEFAULT_NEXT_AFTER_INITIAL = "데이터 수치 검증"


def _parse_definition(definition: Optional[dict[str, Any]]) -> Optional[ProcessDefinitionModel]:
    if not definition or not isinstance(definition, dict):
        return None
    try:
        return ProcessDefinitionModel.model_validate(definition)
    except Exception:
        return None


def get_initial_activity(definition: Optional[dict[str, Any]]) -> dict[str, Any]:
    """
    프로세스 시작 시 첫 액티비티 스펙 반환.
    Returns: {"activity_name": str, "activity_type": str, "agent_mode": str}
    """
    spec = {
        "activity_name": DEFAULT_INITIAL_ACTIVITY,
        "activity_type": ActivityType.HUMAN_TASK.value,
        "agent_mode": AgentMode.MANUAL.value,
    }
    model = _parse_definition(definition)
    if not model or not model.activities:
        return spec
    first = model.activities[0]
    spec["activity_name"] = first.name
    spec["activity_type"] = first.type.value
    spec["agent_mode"] = first.agent_mode.value
    return spec


def get_next_activities_after(
    definition: Optional[dict[str, Any]],
    completed_activity_name: str,
) -> list[dict[str, Any]]:
    """
    완료된 액티비티 이후에 진행할 액티비티 스펙 목록 반환.
    정의에 transitions가 있으면 그에 따라 결정하고, 없으면
    현재 서비스와 동일하게 단일 다음 액티비티(데이터 수치 검증) 반환.
    Returns: [{"activity_name", "activity_type", "agent_mode"}, ...]
    """
    model = _parse_definition(definition)
    if not model or not model.transitions:
        # 기존 하드코딩과 동일: 첫 단계 완료 후 "데이터 수치 검증"
        if completed_activity_name == DEFAULT_INITIAL_ACTIVITY:
            return [
                {
                    "activity_name": DEFAULT_NEXT_AFTER_INITIAL,
                    "activity_type": ActivityType.SERVICE_TASK.value,
                    "agent_mode": AgentMode.SUPERVISED.value,
                }
            ]
        return []

    # transitions에서 completed_activity_name을 source로 하는 target 조회
    activity_by_id: dict[str, ProcessActivityModel] = {a.id: a for a in model.activities}
    activity_by_name: dict[str, ProcessActivityModel] = {a.name: a for a in model.activities}
    completed = activity_by_name.get(completed_activity_name)
    if not completed:
        return []

    next_specs: list[dict[str, Any]] = []
    for t in model.transitions:
        if t.source != completed.id:
            continue
        target = activity_by_id.get(t.target) or activity_by_name.get(t.target)
        if target:
            next_specs.append({
                "activity_name": target.name,
                "activity_type": target.type.value,
                "agent_mode": target.agent_mode.value,
            })
        # Gateway target은 단순화: 여기서는 Activity만 반환

    if not next_specs and completed_activity_name == DEFAULT_INITIAL_ACTIVITY:
        return [
            {
                "activity_name": DEFAULT_NEXT_AFTER_INITIAL,
                "activity_type": ActivityType.SERVICE_TASK.value,
                "agent_mode": AgentMode.SUPERVISED.value,
            }
        ]
    return next_specs
