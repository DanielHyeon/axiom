"""G18: DAG 기반 알림 규칙 빌더 API.

SQL 조건 노드 + 논리 노드(AND/OR/NOT) + 액션 노드(email/webhook/slack)를
DAG로 연결하여 복합 알림 규칙을 정의한다.
프론트엔드 AlertDagBuilder.tsx (ReactFlow)와 연동.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user

logger = logging.getLogger("axiom.core.api.alert_dag")

router = APIRouter(prefix="/api/v3/core/alert-rules", tags=["알림 규칙"])


# ── 모델 ── #

class DagNodeType(str, Enum):
    SQL_CONDITION = "sql_condition"     # SQL 조건 (예: SELECT COUNT(*) > threshold)
    BOOLEAN_LOGIC = "boolean_logic"     # AND/OR/NOT
    ACTION = "action"                   # 알림 액션 (email, webhook, slack)
    WHATIF = "whatif"                    # What-if 시나리오 트리거
    THRESHOLD = "threshold"             # 임계값 비교


class ActionType(str, Enum):
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    REDIS_EVENT = "redis_event"


class DagNode(BaseModel):
    node_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    node_type: DagNodeType
    label: str = ""
    config: dict = Field(default_factory=dict)
    position: dict = Field(default_factory=lambda: {"x": 0, "y": 0})


class DagEdge(BaseModel):
    edge_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    source_node_id: str
    target_node_id: str
    label: str = ""


class AlertRule(BaseModel):
    rule_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    description: str = ""
    nodes: list[DagNode] = Field(default_factory=list)
    edges: list[DagEdge] = Field(default_factory=list)
    enabled: bool = True
    schedule_cron: str = ""           # cron 표현식 (비어있으면 수동 실행)
    tenant_id: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AlertRuleRequest(BaseModel):
    name: str
    description: str = ""
    nodes: list[DagNode] = Field(default_factory=list, max_length=50)
    edges: list[DagEdge] = Field(default_factory=list, max_length=100)
    enabled: bool = True
    schedule_cron: str = ""


# ── 저장소 (in-memory MVP) ── #

_rules: dict[str, AlertRule] = {}


# ── 엔드포인트 ── #

@router.get("")
async def list_alert_rules(user: dict = Depends(get_current_user)) -> dict:
    tenant_id = user.get("tenant_id", "")
    rules = [r for r in _rules.values() if r.tenant_id == tenant_id]
    return {"success": True, "data": [r.model_dump(mode="json") for r in rules], "total": len(rules)}


@router.post("")
async def create_alert_rule(request: AlertRuleRequest, user: dict = Depends(get_current_user)) -> dict:
    role = user.get("role", "viewer")
    if role not in ("admin", "manager", "analyst"):
        raise HTTPException(status_code=403, detail="권한 부족")

    rule = AlertRule(
        **request.model_dump(),
        tenant_id=user.get("tenant_id", ""),
        created_by=user.get("user_id", ""),
    )
    rule.rule_id = uuid.uuid4().hex
    _rules[rule.rule_id] = rule
    return {"success": True, "data": rule.model_dump(mode="json")}


@router.get("/{rule_id}")
async def get_alert_rule(rule_id: str, user: dict = Depends(get_current_user)) -> dict:
    tenant_id = user.get("tenant_id", "")
    rule = _rules.get(rule_id)
    if not rule or rule.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="규칙을 찾을 수 없습니다")
    return {"success": True, "data": rule.model_dump(mode="json")}


@router.put("/{rule_id}")
async def update_alert_rule(rule_id: str, request: AlertRuleRequest, user: dict = Depends(get_current_user)) -> dict:
    tenant_id = user.get("tenant_id", "")
    rule = _rules.get(rule_id)
    if not rule or rule.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="규칙을 찾을 수 없습니다")
    for field, value in request.model_dump().items():
        setattr(rule, field, value)
    rule.updated_at = datetime.now(timezone.utc)
    return {"success": True, "data": rule.model_dump(mode="json")}


@router.delete("/{rule_id}")
async def delete_alert_rule(rule_id: str, user: dict = Depends(get_current_user)) -> dict:
    tenant_id = user.get("tenant_id", "")
    rule = _rules.get(rule_id)
    if not rule or rule.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="규칙을 찾을 수 없습니다")
    del _rules[rule_id]
    return {"success": True, "message": f"삭제 완료: {rule_id}"}
