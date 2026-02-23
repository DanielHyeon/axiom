"""
LangGraph 기반 오케스트레이터 (agent-orchestration.md §2).
10노드 StateGraph 설계. 노드 내부에서 ProcessService·Oracle·Synapse 연동(전달 시).
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger("axiom.orchestrator")


def _route_intent(activity: dict, user_message: str) -> str:
    """
    의도 분류(Node: route_intent).

    - process: 서비스/스크립트 태스크 또는 명시적 프로세스 지시
    - document: 문서/파일 관련 요청
    - query: 데이터 조회/질문
    - mining: 프로세스 마이닝/병목/적합성 분석
    """
    activity_type = (activity or {}).get("type", "humanTask")
    msg = (user_message or "").lower()

    mining_keywords = [
        "프로세스 마이닝",
        "process mining",
        "병목",
        "bottleneck",
        "적합성",
        "conformance",
        "프로세스 발견",
        "이벤트 로그",
    ]
    if any(kw in msg for kw in mining_keywords):
        return "mining"

    if activity_type in ("serviceTask", "scriptTask"):
        return "process"

    if "document" in msg or "파일" in msg or "첨부" in msg:
        return "document"

    # 기본은 query로 처리
    return "query"


async def _node_process_exec(state: dict[str, Any]) -> dict[str, Any]:
    """
    Node: process_exec.
    state에 db·workitem_id가 있으면 WorkItem 조회 후 실데이터 반환.
    """
    message = state.get("user_message", "")
    activity = state.get("activity") or {}
    db = state.get("db")
    workitem_id = state.get("workitem_id")
    if db and workitem_id:
        try:
            from sqlalchemy import select
            from app.models.base_models import WorkItem
            r = await db.execute(select(WorkItem).where(WorkItem.id == workitem_id))
            if (wi := r.scalar_one_or_none()):
                return {
                    "kind": "process",
                    "activity_id": wi.activity_name,
                    "activity_name": wi.activity_name,
                    "workitem_id": wi.id,
                    "status": wi.status,
                    "summary": f"워크아이템 {wi.activity_name} (상태: {wi.status})",
                }
        except Exception as e:
            logger.warning("process_exec WorkItem 조회 실패: %s", e)
    return {
        "kind": "process",
        "activity_id": activity.get("id"),
        "activity_name": activity.get("name"),
        "summary": f"프로세스 액티비티 실행 요청: {message}",
    }


async def _node_document_proc(state: dict[str, Any]) -> dict[str, Any]:
    """
    Node: document_proc.
    문서 파이프라인 연동은 추후; 현재는 요청 요약 반환.
    """
    message = state.get("user_message", "")
    return {
        "kind": "document",
        "summary": f"문서 처리 요청: {message}",
    }


async def _node_query_data(state: dict[str, Any]) -> dict[str, Any]:
    """
    Node: query_data.
    ORACLE_BASE_URL 설정 시 Oracle POST /text2sql/ask 호출 (실제 구현 경로·계약).
    """
    message = (state.get("user_message") or "").strip()
    base = getattr(settings, "ORACLE_BASE_URL", None) or ""
    datasource_id = state.get("datasource_id") or getattr(settings, "ORACLE_DEFAULT_DATASOURCE_ID", "default")
    if base and message:
        try:
            import httpx
            url = f"{base.rstrip('/')}/text2sql/ask"
            body = {
                "question": message,
                "datasource_id": datasource_id,
                "options": {"include_viz": False, "use_cache": True},
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=body)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "kind": "query",
                        "summary": (data.get("data") or {}).get("summary") or "Oracle 조회 완료",
                        "oracle_response": data,
                    }
        except Exception as e:
            logger.warning("query_data Oracle 호출 실패: %s", e)
    return {
        "kind": "query",
        "summary": f"데이터 질의: {message}" if message else "데이터 질의 요청",
    }


async def _node_mining(state: dict[str, Any]) -> dict[str, Any]:
    """
    Node: process_mining_analysis.
    SYNAPSE_BASE_URL 설정·state에 case_id·log_id 있을 때 Synapse POST /process-mining/discover 호출(실제 구현).
    /analyze 엔드포인트는 없음. discover/conformance/bottlenecks/performance 사용.
    """
    message = state.get("user_message", "")
    base = getattr(settings, "SYNAPSE_BASE_URL", None) or ""
    case_id = (state.get("case_id") or "").strip()
    log_id = (state.get("log_id") or "").strip()
    if base and case_id and log_id:
        try:
            import httpx
            url = f"{base.rstrip('/')}/api/v3/synapse/process-mining/discover"
            payload = {"case_id": case_id, "log_id": log_id, "algorithm": "inductive"}
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 202:
                    data = resp.json()
                    return {
                        "kind": "mining",
                        "summary": "프로세스 발견 태스크 제출 완료",
                        "task_id": (data.get("data") or {}).get("task_id"),
                        "synapse_response": data,
                    }
        except Exception as e:
            logger.warning("mining Synapse 호출 실패: %s", e)
    return {
        "kind": "mining",
        "summary": f"프로세스 마이닝 분석 요청: {message}" if message else "프로세스 마이닝(case_id·log_id 필요)",
    }


async def _execute_intent_node(intent: str, state: dict[str, Any]) -> dict[str, Any]:
    """
    intent별 노드 실행(서비스 연동).
    """
    if intent == "process":
        result = await _node_process_exec(state)
    elif intent == "document":
        result = await _node_document_proc(state)
    elif intent == "mining":
        result = await _node_mining(state)
    else:
        result = await _node_query_data(state)
    return {
        "result": result,
        "confidence": 0.85,
        "needs_human_review": state.get("agent_mode") == "SUPERVISED",
    }


def _hitl_check(state: dict[str, Any]) -> dict[str, Any]:
    """
    Node: hitl_check.

    - SUPERVISED 모드이거나 신뢰도 낮을 때 HITL 플래그를 세팅.
    - 현재는 agent_mode만 사용.
    """
    needs_human = state.get("agent_mode") == "SUPERVISED"
    state["needs_human_review"] = needs_human
    return state


def _finalize(state: dict[str, Any], node_output: dict[str, Any]) -> dict[str, Any]:
    """
    Node: complete.

    최종 결과를 OrchestratorState 형태로 머지.
    """
    return {
        **state,
        "result": node_output.get("result", {}),
        "confidence": node_output.get("confidence", 0.0),
        "needs_human_review": node_output.get("needs_human_review", False),
        "error": None,
    }


class _CompiledOrchestrator:
    """설계 §2.2와 동일한 ainvoke 인터페이스. LangGraph 미도입 시 내부 단순 플로우."""

    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        # 1) route_intent 노드: 의도 결정
        activity = state.get("activity") or {}
        user_message = state.get("user_message") or ""
        intent = _route_intent(activity, user_message)
        next_state: dict[str, Any] = {
            **state,
            "intent": intent,
            "last_node": "route_intent",
        }

        # 2) intent별 노드 실행 (process_exec / document_proc / query_data / process_mining_analysis)
        node_output = await _execute_intent_node(intent, next_state)
        next_state["last_node"] = f"{intent}_handler"

        # 3) hitl_check 노드
        next_state = _hitl_check(next_state)
        next_state["last_node"] = "hitl_check"

        # 4) complete 노드
        completed = _finalize(next_state, node_output)
        completed["last_node"] = "complete"
        return completed


def build_orchestrator_graph() -> _CompiledOrchestrator:
    """
    오케스트레이터 그래프 빌드.
    LangGraph StateGraph 미도입 시 단순 러너 반환. .ainvoke(state)로 1회 실행 가능.
    """
    return _CompiledOrchestrator()
