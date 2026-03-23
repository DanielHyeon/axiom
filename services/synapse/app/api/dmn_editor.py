"""G15: DMN 결정 테이블 에디터 API — CRUD + 테스트 실행.

프론트엔드 DmnTableEditor와 연동하여 결정 테이블의
생성·조회·수정·삭제·테스트 실행을 제공한다.

결정 테이블은 in-memory + Redis 저장 (Phase 4에서 PostgreSQL 전환).
적중 정책: FIRST, COLLECT, PRIORITY (기존 dmn_engine 활용).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.dmn_engine import execute_decision_table, create_table_from_dict

router = APIRouter(prefix="/api/v3/synapse/dmn/tables", tags=["DMN 에디터"])

logger = logging.getLogger("axiom.synapse.dmn_editor")


# ── 모델 ── #

class DmnCondition(BaseModel):
    """DMN 규칙의 조건 항목"""
    input_name: str               # 입력 변수명 (예: "temperature", "priority")
    operator: Literal["==", "!=", ">", "<", ">=", "<=", "in", "between"] = "=="  # M-2: 허용 연산자 제한
    value: Any = None             # 비교 값


class DmnAction(BaseModel):
    """DMN 규칙의 실행 항목"""
    output_name: str              # 출력 변수명
    value: Any = None             # 출력 값


class DmnRule(BaseModel):
    """DMN 규칙 행"""
    rule_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    description: str = ""
    conditions: list[DmnCondition] = Field(default_factory=list)
    actions: list[DmnAction] = Field(default_factory=list)
    priority: int = 0             # PRIORITY 정책용 우선순위


class DmnTableDefinition(BaseModel):
    """DMN 결정 테이블 정의"""
    table_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    description: str = ""
    hit_policy: Literal["FIRST", "COLLECT", "PRIORITY"] = "FIRST"
    input_columns: list[str] = Field(default_factory=list)   # 입력 변수명 목록
    output_columns: list[str] = Field(default_factory=list)  # 출력 변수명 목록
    rules: list[DmnRule] = Field(default_factory=list, max_length=500)  # M-2: 규칙 수 상한
    tenant_id: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DmnTestRequest(BaseModel):
    """DMN 테이블 테스트 실행 요청"""
    context: dict                 # 입력 변수 (예: {"temperature": 38, "priority": "high"})


class DmnTestResult(BaseModel):
    """DMN 테스트 실행 결과"""
    matched_rules: list[dict] = Field(default_factory=list)
    hit_count: int = 0
    hit_policy: str = ""
    input_context: dict = Field(default_factory=dict)


# ── 저장소 (in-memory MVP) ── #

_tables: dict[str, DmnTableDefinition] = {}


def _get_table(table_id: str, tenant_id: str = "") -> DmnTableDefinition:
    """테이블 조회 — 없거나 테넌트 불일치 시 404 (C-1 반영)"""
    table = _tables.get(table_id)
    if not table or (tenant_id and table.tenant_id != tenant_id):
        raise HTTPException(status_code=404, detail=f"결정 테이블을 찾을 수 없습니다: {table_id}")
    return table


def _get_tenant_id(req: Request) -> str:
    """TenantMiddleware에서 주입한 tenant_id 추출"""
    return getattr(req.state, "tenant_id", "")


def _to_engine_format(table: DmnTableDefinition) -> dict:
    """DmnTableDefinition → 기존 dmn_engine 호환 dict 변환"""
    engine_rules = []
    for rule in table.rules:
        conditions = {}
        for cond in rule.conditions:
            if cond.operator == "==":
                conditions[cond.input_name] = cond.value
            elif cond.operator == "in":
                conditions[cond.input_name] = cond.value  # 리스트
            else:
                # 비교 연산자 → 문자열 표현 (dmn_engine 확장 필요)
                conditions[cond.input_name] = f"{cond.operator} {cond.value}"

        actions = {a.output_name: a.value for a in rule.actions}

        engine_rules.append({
            "conditions": conditions,
            "actions": actions,
            "priority": rule.priority,
            "description": rule.description,
        })

    return {
        "name": table.name,
        "hit_policy": table.hit_policy,
        "rules": engine_rules,
    }


# ── 엔드포인트 ── #

@router.get("")
async def list_dmn_tables(
    req: Request,
) -> dict:
    """결정 테이블 목록 조회 — C-1: 테넌트 격리"""
    tenant_id = _get_tenant_id(req)
    tables = [t for t in _tables.values() if t.tenant_id == tenant_id]
    return {
        "success": True,
        "data": [t.model_dump(mode="json") for t in tables],
        "total": len(tables),
    }


@router.post("")
async def create_dmn_table(
    body: DmnTableDefinition,
    req: Request,
) -> dict:
    """결정 테이블 생성 — M-5: table_id 서버 생성 강제, C-1: 테넌트 격리"""
    if not body.name:
        raise HTTPException(status_code=400, detail="테이블 이름이 비어있습니다")

    body.table_id = uuid.uuid4().hex  # M-5: 항상 서버에서 ID 생성
    body.tenant_id = _get_tenant_id(req)
    body.created_at = datetime.now(timezone.utc)
    body.updated_at = body.created_at
    _tables[body.table_id] = body

    logger.info("DMN 테이블 생성: %s (%s, 규칙 %d개)", body.table_id, body.name, len(body.rules))
    return {"success": True, "data": body.model_dump(mode="json")}


@router.get("/{table_id}")
async def get_dmn_table(table_id: str, req: Request) -> dict:
    """결정 테이블 상세 조회 — C-1: 테넌트 격리"""
    table = _get_table(table_id, _get_tenant_id(req))
    return {"success": True, "data": table.model_dump(mode="json")}


@router.put("/{table_id}")
async def update_dmn_table(table_id: str, body: DmnTableDefinition, req: Request) -> dict:
    """결정 테이블 수정 (전체 교체) — C-1: 테넌트 격리"""
    tenant_id = _get_tenant_id(req)
    _get_table(table_id, tenant_id)  # 존재 + 테넌트 확인
    body.table_id = table_id
    body.tenant_id = tenant_id
    body.updated_at = datetime.now(timezone.utc)
    _tables[table_id] = body

    logger.info("DMN 테이블 수정: %s (%s, 규칙 %d개)", table_id, body.name, len(body.rules))
    return {"success": True, "data": body.model_dump(mode="json")}


@router.delete("/{table_id}")
async def delete_dmn_table(table_id: str, req: Request) -> dict:
    """결정 테이블 삭제 — C-1: 테넌트 격리"""
    _get_table(table_id, _get_tenant_id(req))  # 존재 + 테넌트 확인
    del _tables[table_id]
    logger.info("DMN 테이블 삭제: %s", table_id)
    return {"success": True, "message": f"삭제 완료: {table_id}"}


@router.post("/{table_id}/test")
async def test_dmn_table(table_id: str, body: DmnTestRequest, req: Request) -> dict:
    """결정 테이블 테스트 실행 — C-1: 테넌트 격리"""
    table = _get_table(table_id, _get_tenant_id(req))

    engine_dict = _to_engine_format(table)
    engine_table = create_table_from_dict(engine_dict)
    results = execute_decision_table(engine_table, body.context)

    return {
        "success": True,
        "data": DmnTestResult(
            matched_rules=results,
            hit_count=len(results),
            hit_policy=table.hit_policy,
            input_context=body.context,
        ).model_dump(),
    }


@router.post("/{table_id}/rules")
async def add_rule(table_id: str, rule: DmnRule, req: Request) -> dict:
    """결정 테이블에 규칙 추가 — C-1: 테넌트 격리"""
    table = _get_table(table_id, _get_tenant_id(req))
    table.rules.append(rule)
    table.updated_at = datetime.now(timezone.utc)

    return {"success": True, "data": rule.model_dump(mode="json"), "total_rules": len(table.rules)}


@router.delete("/{table_id}/rules/{rule_id}")
async def delete_rule(table_id: str, rule_id: str, req: Request) -> dict:
    """결정 테이블에서 규칙 삭제 — C-1: 테넌트 격리"""
    table = _get_table(table_id, _get_tenant_id(req))
    original_count = len(table.rules)
    table.rules = [r for r in table.rules if r.rule_id != rule_id]

    if len(table.rules) == original_count:
        raise HTTPException(status_code=404, detail=f"규칙을 찾을 수 없습니다: {rule_id}")

    table.updated_at = datetime.now(timezone.utc)
    return {"success": True, "message": f"규칙 삭제 완료: {rule_id}", "total_rules": len(table.rules)}
