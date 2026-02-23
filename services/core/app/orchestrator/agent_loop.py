"""
에이전트 지식 학습 루프 (bpm-engine.md §4.3, agent-orchestration.md).
오케스트레이터 1회 실행 후 결과 반환. HITL 시 needs_human_review로 대기.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.langgraph_flow import build_orchestrator_graph


async def run_agent_loop(
    tenant_id: str,
    workitem_id: str,
    payload: dict[str, Any],
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """
    오케스트레이터 그래프 1회 실행.
    payload: user_message, activity(직렬화), agent_mode 등.
    db: 전달 시 노드 내부에서 ProcessService 등 DB 연동 사용.
    """
    graph = build_orchestrator_graph()
    if graph is None:
        return {
            "tenant_id": tenant_id,
            "workitem_id": workitem_id,
            "status": "ERROR",
            "message": "Orchestrator graph not available.",
        }

    initial: dict[str, Any] = {
        "user_message": payload.get("user_message") or payload.get("instruction") or "",
        "workitem_id": workitem_id,
        "activity": payload.get("activity") or {},
        "tenant_id": tenant_id,
        "agent_mode": payload.get("agent_mode") or "MANUAL",
    }
    if db is not None:
        initial["db"] = db

    result_state = await graph.ainvoke(initial)

    return {
        "tenant_id": tenant_id,
        "workitem_id": workitem_id,
        "status": "SUBMITTED" if result_state.get("needs_human_review") else "DONE",
        "result": result_state.get("result", {}),
        "confidence": result_state.get("confidence", 0.0),
        "needs_human_review": result_state.get("needs_human_review", False),
        "error": result_state.get("error"),
    }
