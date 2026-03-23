"""G17 + G28: 온톨로지 히스토리(Undo/Redo) + 컨텍스트 메뉴 액션 API.

G17: 온톨로지 그래프 편집 이력을 서버에 저장하여 Undo/Redo를 지원한다.
     프론트엔드 Zustand history 스택과 동기화.
G28: 우클릭 컨텍스트 메뉴의 서버 액션 (복제, 삭제, 관계 추가 등).

설계:
- 편집 액션을 EventLog로 기록 → 역방향 실행으로 Undo
- 최대 50단계 히스토리 유지 (in-memory MVP)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v3/synapse/ontology/history", tags=["온톨로지 히스토리"])

logger = logging.getLogger("axiom.synapse.ontology_history")


# ── 모델 ── #

class EditActionType(str, Enum):
    """편집 액션 유형"""
    NODE_CREATE = "node_create"
    NODE_UPDATE = "node_update"
    NODE_DELETE = "node_delete"
    EDGE_CREATE = "edge_create"
    EDGE_UPDATE = "edge_update"
    EDGE_DELETE = "edge_delete"
    NODE_MOVE = "node_move"       # 위치 변경 (Cytoscape)
    BATCH = "batch"               # 복수 액션 그룹


class EditAction(BaseModel):
    """단일 편집 액션 — Undo/Redo 단위"""
    action_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    action_type: EditActionType
    case_id: str
    target_id: str = ""           # 노드/엣지 ID
    before_state: dict = Field(default_factory=dict)  # Undo용: 변경 전 상태
    after_state: dict = Field(default_factory=dict)    # Redo용: 변경 후 상태
    description: str = ""         # 사람이 읽을 수 있는 설명
    user_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EditHistory(BaseModel):
    """케이스별 편집 히스토리"""
    case_id: str
    undo_stack: list[EditAction] = Field(default_factory=list)
    redo_stack: list[EditAction] = Field(default_factory=list)
    max_size: int = 50


# ── 저장소 (in-memory MVP) ── #

# C2: tenant_id:case_id 복합 키로 테넌트 격리
_histories: dict[str, EditHistory] = {}
_MAX_HISTORY_SIZE = 50
_MAX_TRACKED_CASES = 1000  # M: 메모리 제한


def _history_key(tenant_id: str, case_id: str) -> str:
    """테넌트 격리 키"""
    return f"{tenant_id}:{case_id}"


def _get_history(tenant_id: str, case_id: str) -> EditHistory:
    """케이스별 히스토리 조회 — 없으면 생성. M: 최대 케이스 수 제한."""
    key = _history_key(tenant_id, case_id)
    if key not in _histories:
        # M: LRU 간이 구현 — 가장 오래된 엔트리 제거
        if len(_histories) >= _MAX_TRACKED_CASES:
            oldest_key = next(iter(_histories))
            del _histories[oldest_key]
        _histories[key] = EditHistory(case_id=case_id)
    return _histories[key]


# ── 엔드포인트 ── #

@router.post("/push")
async def push_action(
    action: EditAction,
    req: Request,
) -> dict:
    """편집 액션 기록 — Undo 스택에 추가, Redo 스택 초기화.

    프론트엔드에서 편집 완료 시 호출.
    """
    # C1: TenantMiddleware에서 주입한 tenant_id 사용
    tenant_id = getattr(req.state, "tenant_id", "")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="인증되지 않은 요청")
    action.user_id = getattr(req.state, "user_id", action.user_id)

    history = _get_history(tenant_id, action.case_id)

    # Undo 스택에 추가
    history.undo_stack.append(action)
    if len(history.undo_stack) > _MAX_HISTORY_SIZE:
        history.undo_stack = history.undo_stack[-_MAX_HISTORY_SIZE:]

    # 새 액션이 추가되면 Redo 스택 초기화
    history.redo_stack.clear()

    logger.info(
        "편집 기록: case=%s, action=%s, target=%s",
        action.case_id, action.action_type.value, action.target_id,
    )

    return {
        "success": True,
        "data": {
            "action_id": action.action_id,
            "undo_count": len(history.undo_stack),
            "redo_count": 0,
        },
    }


@router.post("/undo/{case_id}")
async def undo_action(case_id: str, req: Request) -> dict:
    """Undo — 마지막 액션의 before_state 반환.

    프론트엔드는 before_state를 적용하여 그래프를 복원한다.
    """
    tenant_id = getattr(req.state, "tenant_id", "")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="인증되지 않은 요청")
    history = _get_history(tenant_id, case_id)

    if not history.undo_stack:
        raise HTTPException(status_code=404, detail="되돌릴 액션이 없습니다")

    action = history.undo_stack.pop()
    history.redo_stack.append(action)

    logger.info("Undo: case=%s, action=%s", case_id, action.action_type.value)

    return {
        "success": True,
        "data": {
            "action_id": action.action_id,
            "action_type": action.action_type.value,
            "restore_state": action.before_state,
            "description": action.description,
            "undo_count": len(history.undo_stack),
            "redo_count": len(history.redo_stack),
        },
    }


@router.post("/redo/{case_id}")
async def redo_action(case_id: str, req: Request) -> dict:
    """Redo — 마지막 Undo된 액션의 after_state 반환."""
    tenant_id = getattr(req.state, "tenant_id", "")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="인증되지 않은 요청")
    history = _get_history(tenant_id, case_id)

    if not history.redo_stack:
        raise HTTPException(status_code=404, detail="다시 실행할 액션이 없습니다")

    action = history.redo_stack.pop()
    history.undo_stack.append(action)

    logger.info("Redo: case=%s, action=%s", case_id, action.action_type.value)

    return {
        "success": True,
        "data": {
            "action_id": action.action_id,
            "action_type": action.action_type.value,
            "restore_state": action.after_state,
            "description": action.description,
            "undo_count": len(history.undo_stack),
            "redo_count": len(history.redo_stack),
        },
    }


@router.get("/status/{case_id}")
async def get_history_status(case_id: str, req: Request) -> dict:
    """히스토리 상태 조회 — Undo/Redo 가능 여부 + 최근 액션"""
    tenant_id = getattr(req.state, "tenant_id", "")
    history = _get_history(tenant_id or "anonymous", case_id)

    recent = []
    for a in reversed(history.undo_stack[-5:]):
        recent.append({
            "action_id": a.action_id,
            "action_type": a.action_type.value,
            "description": a.description,
            "created_at": a.created_at.isoformat(),
        })

    return {
        "success": True,
        "data": {
            "can_undo": len(history.undo_stack) > 0,
            "can_redo": len(history.redo_stack) > 0,
            "undo_count": len(history.undo_stack),
            "redo_count": len(history.redo_stack),
            "recent_actions": recent,
        },
    }


# ── G28: 컨텍스트 메뉴 액션 ── #

class ContextMenuAction(BaseModel):
    """컨텍스트 메뉴 액션 요청"""
    case_id: str
    node_id: str = ""
    edge_id: str = ""
    action: Literal[
        "duplicate_node",     # 노드 복제
        "delete_node",        # 노드 삭제
        "add_relation",       # 관계 추가
        "view_detail",        # 상세 보기 (프론트엔드 라우팅)
        "copy_name",          # 이름 복사 (프론트엔드 클립보드)
        "isolate_subgraph",   # 서브그래프 격리 보기
    ] = "view_detail"
    params: dict = Field(default_factory=dict)


@router.post("/context-action")
async def execute_context_action(
    body: ContextMenuAction,
    req: Request,
) -> dict:
    """온톨로지 우클릭 컨텍스트 메뉴 액션 실행.

    서버 측 처리가 필요한 액션만 여기서 실행.
    view_detail, copy_name 등은 프론트엔드에서 직접 처리.
    """
    tenant_id = getattr(req.state, "tenant_id", "")

    if body.action == "duplicate_node":
        # 노드 복제 — 기존 노드 속성을 복사하여 새 노드 생성
        # TODO: Neo4j에서 노드 읽기 → 복제 → 새 ID 발급
        new_id = uuid.uuid4().hex[:12]
        return {
            "success": True,
            "data": {
                "action": "duplicate_node",
                "original_id": body.node_id,
                "new_id": new_id,
                "status": "pending_neo4j",
            },
        }

    elif body.action == "delete_node":
        # 노드 삭제 — 연결된 엣지도 함께 삭제
        # TODO: Neo4j에서 노드 + 관계 삭제
        return {
            "success": True,
            "data": {
                "action": "delete_node",
                "node_id": body.node_id,
                "status": "pending_neo4j",
            },
        }

    elif body.action == "add_relation":
        # 관계 추가 — params에서 target_id, relation_type 읽기
        target_id = body.params.get("target_id", "")
        relation_type = body.params.get("relation_type", "RELATED_TO")
        return {
            "success": True,
            "data": {
                "action": "add_relation",
                "source_id": body.node_id,
                "target_id": target_id,
                "relation_type": relation_type,
                "status": "pending_neo4j",
            },
        }

    elif body.action == "isolate_subgraph":
        # 서브그래프 격리 — 해당 노드의 1-hop 이웃만 반환
        # TODO: Neo4j 쿼리로 서브그래프 조회
        return {
            "success": True,
            "data": {
                "action": "isolate_subgraph",
                "center_node_id": body.node_id,
                "status": "pending_neo4j",
            },
        }

    # view_detail, copy_name → 프론트엔드 처리
    return {
        "success": True,
        "data": {
            "action": body.action,
            "handled_by": "frontend",
        },
    }
