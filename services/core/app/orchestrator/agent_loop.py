"""
에이전트 지식 학습 루프 (process-gpt-agent-feedback-main 이식 예정).
HITL 피드백·MCP 결과 반영 루프. 실제 연동은 agent_service와 수행 예정.
"""
from __future__ import annotations

from typing import Any


async def run_agent_loop(
    tenant_id: str,
    workitem_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    지식 학습 루프 1회 실행.
    현재: 스텁. agent_service 연동 후 구현 예정.
    """
    return {
        "tenant_id": tenant_id,
        "workitem_id": workitem_id,
        "status": "STUB",
        "message": "Agent loop not yet implemented.",
    }
