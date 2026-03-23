"""
프로세스 Publish Validator — §0.10 명세 구현.

DRAFT → PUBLISHED 발행 시 7개 구조 규칙을 모두 통과해야 상태 전이 허용.
참조 무결성 5규칙(CONTRACTS_SAME_TENANT 등)은 복합 FK로 DB가 강제한다.
"""
from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from app.modules.process_model.domain.models import StepDefinition, StepTransitionEdge


def validate_for_publish(
    steps: list[StepDefinition],
    transitions: list[StepTransitionEdge],
) -> list[dict]:
    """발행 검증 — 실패 규칙 목록을 반환. 빈 리스트면 통과."""
    failures: list[dict] = []

    step_ids = {s.id for s in steps}
    step_by_id = {s.id: s for s in steps}

    # step_type 별 분류
    starts = [s for s in steps if s.step_type == "START"]
    ends = [s for s in steps if s.step_type == "END"]
    decisions = [s for s in steps if s.step_type == "DECISION"]

    # transition 맵
    outgoing: dict[UUID, list[StepTransitionEdge]] = defaultdict(list)
    incoming: dict[UUID, list[StepTransitionEdge]] = defaultdict(list)
    for t in transitions:
        outgoing[t.from_step_id].append(t)
        incoming[t.to_step_id].append(t)

    # 1. EXACTLY_ONE_START
    if len(starts) != 1:
        failures.append({"rule": "EXACTLY_ONE_START", "message": f"Found {len(starts)} START steps, expected 1"})

    # 2. AT_LEAST_ONE_END
    if len(ends) < 1:
        failures.append({"rule": "AT_LEAST_ONE_END", "message": "No END step found"})

    # 3. NO_ORPHAN_STEPS — 모든 step은 최소 1개의 incoming 또는 outgoing
    for s in steps:
        has_in = s.id in incoming
        has_out = s.id in outgoing
        if not has_in and not has_out:
            failures.append({"rule": "NO_ORPHAN_STEPS", "message": f"Step '{s.code}' has no transitions"})

    # 4. NON_END_HAS_OUTGOING — END가 아닌 step은 outgoing 필수
    for s in steps:
        if s.step_type != "END" and s.id not in outgoing:
            failures.append({"rule": "NON_END_HAS_OUTGOING", "message": f"Non-END step '{s.code}' has no outgoing transition"})

    # 5. DECISION_HAS_DEFAULT — DECISION은 is_default=true 정확히 1개
    for d in decisions:
        defaults = [t for t in outgoing.get(d.id, []) if t.is_default]
        if len(defaults) != 1:
            failures.append({"rule": "DECISION_HAS_DEFAULT", "message": f"DECISION step '{d.code}' has {len(defaults)} default transitions, expected 1"})

    # 6. ALL_TRANSITIONS_SAME_VERSION — 모든 transition이 같은 version
    version_ids = {t.process_version_id for t in transitions}
    step_version_ids = {s.process_version_id for s in steps}
    all_versions = version_ids | step_version_ids
    if len(all_versions) > 1:
        failures.append({"rule": "ALL_TRANSITIONS_SAME_VERSION", "message": f"Multiple version IDs found: {all_versions}"})

    # 7. NO_UNREACHABLE_STEPS — BFS: START에서 모든 step 도달 가능
    if starts:
        reachable: set[UUID] = set()
        queue = [starts[0].id]
        while queue:
            current = queue.pop(0)
            if current in reachable:
                continue
            reachable.add(current)
            for t in outgoing.get(current, []):
                if t.to_step_id not in reachable:
                    queue.append(t.to_step_id)

        unreachable = step_ids - reachable
        if unreachable:
            codes = [step_by_id[uid].code for uid in unreachable if uid in step_by_id]
            failures.append({"rule": "NO_UNREACHABLE_STEPS", "message": f"Steps {codes} unreachable from START"})

    return failures
