"""
Kinetic Layer API 라우터

Kinetic Layer의 ActionType(GWT 룰) 및 Policy CRUD 엔드포인트를 제공한다.
설계 문서: docs/03_implementation/businessos-kinetic-layer-design.md §12.1

엔드포인트 요약:
- POST   /actions            — ActionType(GWT 룰) 생성
- GET    /actions             — ActionType 목록 조회
- GET    /actions/{id}        — ActionType 단건 조회
- PUT    /actions/{id}        — ActionType 수정
- DELETE /actions/{id}        — ActionType 삭제
- POST   /actions/{id}/link   — ActionType ↔ 온톨로지 노드 연결
- POST   /actions/{id}/test   — GWT 룰 드라이런 테스트
- POST   /policies            — Policy 생성
- GET    /policies             — Policy 목록 조회
- PUT    /policies/{id}        — Policy 수정
- DELETE /policies/{id}        — Policy 삭제
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.neo4j_client import neo4j_client
from app.services.gwt_engine import (
    GWTAction,
    GWTCondition,
    GWTEngine,
    GWTRule,
    GWTRuleManager,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v3/synapse/kinetic",
    tags=["Kinetic"],
)

# ── 서비스 싱글턴 초기화 ─────────────────────────────────────
# GWTRuleManager는 Neo4j 클라이언트만 필요 (이벤트 발행 불필요)
rule_manager = GWTRuleManager(neo4j_client)


# ── 헬퍼 함수 ────────────────────────────────────────────────

def _tenant(request: Request) -> str:
    """테넌트 ID 추출 — 없으면 401 반환 (fail-closed)"""
    tid = getattr(request.state, "tenant_id", None)
    if not tid:
        raise HTTPException(status_code=401, detail="tenant_id not resolved")
    return tid


# ── Pydantic 요청/응답 모델 ──────────────────────────────────


class GWTConditionModel(BaseModel):
    """Given 조건 요청 모델"""
    type: str = Field(..., description="조건 타입: state | relation | expression")
    node_layer: str = Field("", description="대상 노드 계층 (state 타입용)")
    field: str = Field("", description="비교할 필드명")
    op: str = Field("==", description="비교 연산자: ==, !=, >, <, >=, <=, in, not_in, contains")
    value: Any = Field(None, description="비교 대상 값 또는 expression 문자열")
    source_layer: str = Field("", description="관계 시작 노드 계층 (relation 타입용)")
    rel_type: str = Field("", description="관계 타입 (relation 타입용)")
    target_layer: str = Field("", description="관계 끝 노드 계층 (relation 타입용)")


class GWTActionModel(BaseModel):
    """Then 액션 요청 모델"""
    op: str = Field(..., description="액션 타입: SET | EMIT | EXECUTE | CREATE_RELATION | DELETE_RELATION")
    target_node: str = Field("", description="대상 노드 ID 또는 $trigger 참조")
    field: str = Field("", description="SET: 변경할 필드명")
    value: Any = Field(None, description="SET: 새 값")
    event_type: str = Field("", description="EMIT: 발행할 이벤트 타입")
    payload: dict = Field(default_factory=dict, description="EMIT: 이벤트 페이로드")
    action_id: str = Field("", description="EXECUTE: 호출할 ActionType ID")
    params: dict = Field(default_factory=dict, description="EXECUTE: 파라미터")


class ActionTypeCreateRequest(BaseModel):
    """ActionType 생성 요청"""
    name: str = Field(..., description="룰 이름", min_length=1, max_length=200)
    case_id: str = Field(..., description="케이스 ID")
    description: str = Field("", description="룰 설명")
    enabled: bool = Field(True, description="활성화 여부")
    priority: int = Field(100, ge=0, le=10000, description="우선순위 (높을수록 먼저 실행)")
    given_conditions: list[GWTConditionModel] = Field(
        default_factory=list,
        description="Given 조건 목록 (AND 결합)",
    )
    when_event: str = Field(..., description="트리거 이벤트 타입", min_length=1)
    then_actions: list[GWTActionModel] = Field(
        default_factory=list,
        description="Then 액션 시퀀스",
    )


class ActionTypeUpdateRequest(BaseModel):
    """ActionType 수정 요청 (부분 수정)"""
    name: str | None = Field(None, description="룰 이름", min_length=1, max_length=200)
    description: str | None = Field(None, description="룰 설명")
    enabled: bool | None = Field(None, description="활성화 여부")
    priority: int | None = Field(None, ge=0, le=10000, description="우선순위")
    given_conditions: str | None = Field(None, description="Given 조건 JSON 문자열")
    when_event: str | None = Field(None, description="트리거 이벤트 타입")
    then_actions: str | None = Field(None, description="Then 액션 JSON 문자열")


class LinkRequest(BaseModel):
    """ActionType ↔ 온톨로지 노드 연결 요청"""
    node_id: str = Field(..., description="연결할 온톨로지 노드 ID 또는 ActionType ID")
    rel_type: str = Field("TRIGGERS", description="관계 타입: TRIGGERS | MODIFIES | CHAINS_TO | USES_MODEL")


class DryRunRequest(BaseModel):
    """GWT 룰 드라이런 테스트 요청"""
    event_type: str = Field(..., description="시뮬레이션할 이벤트 타입")
    aggregate_id: str = Field("", description="이벤트 대상 어그리거트 ID")
    payload: dict = Field(default_factory=dict, description="이벤트 페이로드")
    case_id: str = Field(..., description="케이스 ID")


class PolicyCreateRequest(BaseModel):
    """Policy 생성 요청"""
    name: str = Field(..., description="정책 이름", min_length=1, max_length=200)
    case_id: str = Field(..., description="케이스 ID")
    description: str = Field("", description="정책 설명")
    enabled: bool = Field(True, description="활성화 여부")
    trigger_event: str = Field(..., description="트리거 이벤트 타입")
    trigger_condition: dict = Field(
        default_factory=dict,
        description='트리거 조건: {"field": "temperature", "op": ">", "value": 85.0}',
    )
    target_service: str = Field("core", description="대상 서비스 (core, synapse, vision, weaver, oracle)")
    target_command: str = Field(..., description="발행할 커맨드 이름")
    command_payload_template: dict = Field(
        default_factory=dict,
        description="커맨드 페이로드 템플릿 ($trigger.payload.xxx 변수 사용 가능)",
    )
    cooldown_seconds: int = Field(3600, ge=0, description="동일 정책 재실행 쿨다운 (초)")
    max_executions_per_day: int = Field(10, ge=0, description="일일 최대 실행 횟수")


class PolicyUpdateRequest(BaseModel):
    """Policy 수정 요청 (부분 수정)"""
    name: str | None = Field(None, description="정책 이름")
    description: str | None = Field(None, description="정책 설명")
    enabled: bool | None = Field(None, description="활성화 여부")
    trigger_event: str | None = Field(None, description="트리거 이벤트 타입")
    trigger_condition: dict | None = Field(None, description="트리거 조건")
    target_service: str | None = Field(None, description="대상 서비스")
    target_command: str | None = Field(None, description="발행할 커맨드")
    command_payload_template: dict | None = Field(None, description="커맨드 페이로드 템플릿")
    cooldown_seconds: int | None = Field(None, ge=0, description="쿨다운 (초)")
    max_executions_per_day: int | None = Field(None, ge=0, description="일일 최대 실행 횟수")


# ══════════════════════════════════════════════════════════════
# ActionType(GWT 룰) CRUD 엔드포인트
# ══════════════════════════════════════════════════════════════


@router.post("/actions", status_code=201)
async def create_action_type(request: Request, body: ActionTypeCreateRequest):
    """ActionType(GWT 룰) 생성

    Given-When-Then 패턴의 비즈니스 룰을 Neo4j에 ActionType 노드로 저장한다.
    생성 시 고유 ID가 자동 발급된다.
    """
    tenant_id = _tenant(request)
    action_id = f"action-{uuid.uuid4().hex[:12]}"

    # Pydantic 모델 → GWTCondition/GWTAction 데이터클래스로 변환
    given = [
        GWTCondition(**cond.model_dump())
        for cond in body.given_conditions
    ]
    then = [
        GWTAction(**act.model_dump())
        for act in body.then_actions
    ]

    # 조건/액션 유효성 검증 (Cypher 인젝션 방지)
    try:
        for cond in given:
            cond.validate()
        for act in then:
            act.validate()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rule = GWTRule(
        id=action_id,
        name=body.name,
        case_id=body.case_id,
        tenant_id=tenant_id,
        given=given,
        when_event=body.when_event,
        then=then,
        enabled=body.enabled,
        priority=body.priority,
    )

    try:
        created_id = await rule_manager.create_rule(rule)
    except Exception as exc:
        logger.error("ActionType 생성 실패: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"ActionType 생성 실패: {exc}") from exc

    return {
        "success": True,
        "data": {"id": created_id, "name": body.name},
    }


@router.get("/actions")
async def list_action_types(
    request: Request,
    case_id: str = Query(..., description="케이스 ID"),
    enabled_only: bool = Query(False, description="활성화된 룰만 조회"),
):
    """ActionType 목록 조회

    case_id 필수. enabled_only=true이면 활성 룰만 반환한다.
    priority 내림차순으로 정렬된다.
    tenant_id는 항상 인증 컨텍스트에서 추출 (쿼리 파라미터 오버라이드 불가).
    """
    tid = _tenant(request)
    try:
        rules = await rule_manager.list_rules(
            case_id=case_id,
            tenant_id=tid,
            enabled_only=enabled_only,
        )
    except Exception as exc:
        logger.error("ActionType 목록 조회 실패: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"ActionType 목록 조회 실패: {exc}") from exc

    return {
        "success": True,
        "data": rules,
        "total": len(rules),
    }


@router.get("/actions/{action_id}")
async def get_action_type(action_id: str, request: Request):
    """ActionType 단건 조회

    action_id에 해당하는 ActionType 노드를 Neo4j에서 조회한다.
    tenant_id 필터로 크로스 테넌트 접근을 방지한다.
    없으면 404를 반환한다.
    """
    tenant_id = _tenant(request)
    query = """
    MATCH (a:ActionType {id: $action_id, tenant_id: $tenant_id})
    RETURN a
    """
    records = await neo4j_client.execute_read(query, {
        "action_id": action_id,
        "tenant_id": tenant_id,
    })
    if not records:
        raise HTTPException(status_code=404, detail=f"ActionType not found: {action_id}")

    return {
        "success": True,
        "data": dict(records[0]["a"]),
    }


@router.put("/actions/{action_id}")
async def update_action_type(action_id: str, request: Request, body: ActionTypeUpdateRequest):
    """ActionType 수정 (부분 수정)

    ALLOWED_UPDATE_FIELDS에 포함된 필드만 수정 가능하다.
    업데이트 시 version이 자동으로 1 증가하고 updated_at이 갱신된다.
    """
    _tenant(request)  # 인증 확인

    # None이 아닌 필드만 추출
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="수정할 필드가 없습니다")

    try:
        updated = await rule_manager.update_rule(action_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("ActionType 수정 실패: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"ActionType 수정 실패: {exc}") from exc

    if not updated:
        raise HTTPException(status_code=404, detail=f"ActionType not found: {action_id}")

    return {"success": True, "data": {"id": action_id, "updated": True}}


@router.delete("/actions/{action_id}")
async def delete_action_type(action_id: str, request: Request):
    """ActionType 삭제

    연결된 관계(TRIGGERS, MODIFIES, CHAINS_TO, USES_MODEL)도 함께 삭제된다.
    """
    _tenant(request)  # 인증 확인

    try:
        deleted = await rule_manager.delete_rule(action_id)
    except Exception as exc:
        logger.error("ActionType 삭제 실패: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"ActionType 삭제 실패: {exc}") from exc

    if not deleted:
        raise HTTPException(status_code=404, detail=f"ActionType not found: {action_id}")

    return {"success": True, "data": {"id": action_id, "deleted": True}}


@router.post("/actions/{action_id}/link")
async def link_action_to_ontology(action_id: str, request: Request, body: LinkRequest):
    """ActionType ↔ 온톨로지 노드 연결

    rel_type별로 연결 방향이 다르다:
    - TRIGGERS:   (OntologyNode)-[:TRIGGERS]->(ActionType)
    - MODIFIES:   (ActionType)-[:MODIFIES]->(OntologyNode)
    - CHAINS_TO:  (ActionType)-[:CHAINS_TO]->(ActionType)
    - USES_MODEL: (ActionType)-[:USES_MODEL]->(BehaviorModel)
    """
    _tenant(request)  # 인증 확인

    try:
        await rule_manager.link_to_ontology(
            rule_id=action_id,
            node_id=body.node_id,
            rel_type=body.rel_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("ActionType 연결 실패: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"ActionType 연결 실패: {exc}") from exc

    return {
        "success": True,
        "data": {
            "action_id": action_id,
            "node_id": body.node_id,
            "rel_type": body.rel_type,
        },
    }


@router.post("/actions/{action_id}/test")
async def test_action_dry_run(action_id: str, request: Request, body: DryRunRequest):
    """GWT 룰 드라이런 테스트

    dry_run=True로 GWTEngine을 생성하여 Neo4j 쓰기/이벤트 발행 없이
    룰 매칭 결과와 예상 상태 변경만 계산한다.
    특정 action_id의 룰만 테스트하는 것이 아니라, 해당 case의 모든 매칭 룰을 평가한다.
    """
    tenant_id = _tenant(request)

    # dry_run 모드 — Neo4j 쓰기/이벤트 발행 없음. publisher=None 허용
    engine = GWTEngine(neo4j_client, async_publisher=None, dry_run=True)

    try:
        results = await engine.handle_event(
            event_type=body.event_type,
            aggregate_id=body.aggregate_id,
            payload=body.payload,
            case_id=body.case_id,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.error("GWT 드라이런 실패: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"드라이런 실패: {exc}") from exc

    return {
        "success": True,
        "data": {
            "action_id": action_id,
            "event_type": body.event_type,
            "results": [
                {
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "matched": r.matched,
                    "state_changes": r.state_changes,
                    "emitted_events": r.emitted_events,
                    "chained_actions": r.chained_actions,
                    "error": r.error,
                }
                for r in results
            ],
            "total_matched": sum(1 for r in results if r.matched),
        },
    }


# ══════════════════════════════════════════════════════════════
# Policy CRUD 엔드포인트
# ══════════════════════════════════════════════════════════════

# Policy 업데이트 시 허용되는 필드 (Cypher 인젝션 방지)
_ALLOWED_POLICY_UPDATE_FIELDS = {
    "name", "description", "enabled",
    "trigger_event", "trigger_condition",
    "target_service", "target_command",
    "command_payload_template",
    "cooldown_seconds", "max_executions_per_day",
}


@router.post("/policies", status_code=201)
async def create_policy(request: Request, body: PolicyCreateRequest):
    """Policy 노드를 Neo4j에 생성

    이벤트 반응형 자동 오케스트레이션 정책을 정의한다.
    PolicyExecutorWorker(Core)가 이벤트 수신 시 이 정책을 조회하여 커맨드를 발행한다.
    """
    tenant_id = _tenant(request)
    policy_id = f"policy-{uuid.uuid4().hex[:12]}"

    # trigger_condition과 command_payload_template는 JSON 문자열로 저장
    query = """
    CREATE (p:Policy {
      id: $id,
      case_id: $case_id,
      tenant_id: $tenant_id,
      name: $name,
      description: $description,
      layer: "kinetic",
      enabled: $enabled,
      trigger_event: $trigger_event,
      trigger_condition: $trigger_condition,
      target_service: $target_service,
      target_command: $target_command,
      command_payload_template: $command_payload_template,
      cooldown_seconds: $cooldown_seconds,
      max_executions_per_day: $max_executions_per_day,
      created_at: datetime(),
      updated_at: datetime()
    })
    RETURN p.id AS id
    """
    try:
        records = await neo4j_client.execute_write(query, {
            "id": policy_id,
            "case_id": body.case_id,
            "tenant_id": tenant_id,
            "name": body.name,
            "description": body.description,
            "enabled": body.enabled,
            "trigger_event": body.trigger_event,
            "trigger_condition": json.dumps(body.trigger_condition, ensure_ascii=False),
            "target_service": body.target_service,
            "target_command": body.target_command,
            "command_payload_template": json.dumps(body.command_payload_template, ensure_ascii=False),
            "cooldown_seconds": body.cooldown_seconds,
            "max_executions_per_day": body.max_executions_per_day,
        })
    except Exception as exc:
        logger.error("Policy 생성 실패: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Policy 생성 실패: {exc}") from exc

    return {
        "success": True,
        "data": {"id": records[0]["id"], "name": body.name},
    }


@router.get("/policies")
async def list_policies(
    request: Request,
    case_id: str = Query(..., description="케이스 ID"),
    enabled_only: bool = Query(False, description="활성화된 정책만 조회"),
):
    """Policy 목록 조회

    case_id 필수. enabled_only=true이면 활성 정책만 반환한다.
    tenant_id는 항상 인증 컨텍스트에서 추출 (쿼리 파라미터 오버라이드 불가).
    """
    tid = _tenant(request)

    # enabled_only 조건은 정적 문자열이므로 인젝션 위험 없음
    where_clause = "AND p.enabled = true" if enabled_only else ""
    query = f"""
    MATCH (p:Policy {{case_id: $case_id, tenant_id: $tenant_id}})
    {where_clause}
    RETURN p
    ORDER BY p.name
    """
    try:
        records = await neo4j_client.execute_read(query, {
            "case_id": case_id,
            "tenant_id": tid,
        })
    except Exception as exc:
        logger.error("Policy 목록 조회 실패: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Policy 목록 조회 실패: {exc}") from exc

    policies = [dict(r["p"]) for r in records]
    return {
        "success": True,
        "data": policies,
        "total": len(policies),
    }


@router.put("/policies/{policy_id}")
async def update_policy(policy_id: str, request: Request, body: PolicyUpdateRequest):
    """Policy 수정 (부분 수정)

    _ALLOWED_POLICY_UPDATE_FIELDS에 포함된 필드만 수정 가능하다.
    dict 타입 필드(trigger_condition, command_payload_template)는 JSON 직렬화하여 저장한다.
    """
    _tenant(request)  # 인증 확인

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="수정할 필드가 없습니다")

    # 허용되지 않는 필드 차단
    invalid_keys = set(updates.keys()) - _ALLOWED_POLICY_UPDATE_FIELDS
    if invalid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"허용되지 않는 업데이트 필드: {invalid_keys}",
        )

    # dict 타입 필드는 JSON 문자열로 변환 (Neo4j에 저장)
    for key in ("trigger_condition", "command_payload_template"):
        if key in updates and isinstance(updates[key], dict):
            updates[key] = json.dumps(updates[key], ensure_ascii=False)

    # 안전한 SET 절 생성 — 모든 키가 _ALLOWED_POLICY_UPDATE_FIELDS에 속함
    set_clauses = ", ".join(f"p.{k} = ${k}" for k in updates.keys())
    query = f"""
    MATCH (p:Policy {{id: $policy_id}})
    SET {set_clauses}, p.updated_at = datetime()
    RETURN p.id AS id
    """
    try:
        records = await neo4j_client.execute_write(query, {
            "policy_id": policy_id,
            **updates,
        })
    except Exception as exc:
        logger.error("Policy 수정 실패: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Policy 수정 실패: {exc}") from exc

    if not records:
        raise HTTPException(status_code=404, detail=f"Policy not found: {policy_id}")

    return {"success": True, "data": {"id": policy_id, "updated": True}}


@router.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str, request: Request):
    """Policy 삭제

    연결된 관계(EMITS_TO, DISPATCHES_TO 등)도 함께 삭제된다.
    """
    _tenant(request)  # 인증 확인

    query = """
    MATCH (p:Policy {id: $policy_id})
    DETACH DELETE p
    RETURN count(*) AS deleted
    """
    try:
        records = await neo4j_client.execute_write(query, {"policy_id": policy_id})
    except Exception as exc:
        logger.error("Policy 삭제 실패: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Policy 삭제 실패: {exc}") from exc

    if not records or records[0]["deleted"] == 0:
        raise HTTPException(status_code=404, detail=f"Policy not found: {policy_id}")

    return {"success": True, "data": {"id": policy_id, "deleted": True}}
