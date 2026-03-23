"""
프로세스 전이 유효성 검증 — §2.5 명세 구현.

step_transition_edges 저장 전 아래 규칙을 검증한다:
1. from/to step이 같은 process_version 소속
2. START step은 from_step으로만 사용 가능
3. END step은 to_step으로만 사용 가능
4. 순환 경로는 허용하되 경고 로그
"""
from __future__ import annotations

import logging
from collections import defaultdict
from uuid import UUID

from app.modules.process_model.domain.models import StepDefinition

logger = logging.getLogger("axiom.process_model.transition")


def validate_transitions(
    steps: list[StepDefinition],
    transitions: list[dict],
    version_id: UUID,
) -> list[dict]:
    """전이 유효성 검증 — 실패 규칙 목록 반환. 빈 리스트면 통과.

    transitions는 {"from_step_id", "to_step_id", "transition_type"} dict 리스트.
    """
    failures: list[dict] = []
    step_by_id = {s.id: s for s in steps}
    step_ids = set(step_by_id.keys())

    for i, t in enumerate(transitions):
        from_id = t.get("from_step_id")
        to_id = t.get("to_step_id")

        # from/to step이 같은 version 소속인지
        if from_id not in step_ids:
            failures.append({"rule": "FROM_STEP_NOT_IN_VERSION", "index": i, "message": f"from_step_id '{from_id}' not found in version"})
            continue
        if to_id not in step_ids:
            failures.append({"rule": "TO_STEP_NOT_IN_VERSION", "index": i, "message": f"to_step_id '{to_id}' not found in version"})
            continue

        from_step = step_by_id[from_id]
        to_step = step_by_id[to_id]

        # START는 from으로만 (to로 들어오면 안 됨)
        if to_step.step_type == "START":
            failures.append({"rule": "START_AS_TARGET", "index": i, "message": f"START step '{to_step.code}' cannot be a transition target"})

        # END는 to로만 (from으로 나가면 안 됨)
        if from_step.step_type == "END":
            failures.append({"rule": "END_AS_SOURCE", "index": i, "message": f"END step '{from_step.code}' cannot be a transition source"})

    # 순환 경로 감지 (경고만, 차단하지 않음)
    outgoing: dict[UUID, list[UUID]] = defaultdict(list)
    for t in transitions:
        from_id = t.get("from_step_id")
        to_id = t.get("to_step_id")
        if from_id in step_ids and to_id in step_ids:
            outgoing[from_id].append(to_id)

    # DFS 순환 감지
    visited: set[UUID] = set()
    in_stack: set[UUID] = set()

    def _has_cycle(node: UUID) -> bool:
        visited.add(node)
        in_stack.add(node)
        for neighbor in outgoing.get(node, []):
            if neighbor in in_stack:
                return True
            if neighbor not in visited and _has_cycle(neighbor):
                return True
        in_stack.discard(node)
        return False

    for start_node in step_ids:
        if start_node not in visited:
            if _has_cycle(start_node):
                logger.warning("순환 경로 감지: version_id=%s — 허용하되 publish 시 주의", version_id)
                break

    return failures
