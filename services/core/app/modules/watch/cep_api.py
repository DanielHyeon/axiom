"""CEP 규칙 관리 REST API.

CRUD + 수동 평가 + 이력 조회 엔드포인트를 제공한다.
인메모리 CEP 엔진을 사용하므로 프로세스 재시작 시 규칙이 초기화된다.
영속적 규칙 저장이 필요하면 DB 연동을 추가한다.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.watch.cep_engine import (
    ActionType,
    CEPRule,
    ConditionType,
    Severity,
    get_cep_engine,
)

router = APIRouter(prefix="/cep", tags=["cep"])


# ---------------------------------------------------------------------------
# 요청/응답 스키마
# ---------------------------------------------------------------------------
class CEPRuleCreateRequest(BaseModel):
    """규칙 생성 요청."""

    name: str = Field(..., min_length=1, max_length=200, description="규칙 이름")
    description: str = Field(default="", max_length=1000, description="규칙 설명")
    sql_query: str = Field(default="", description="모니터링 SQL 쿼리 (참고용)")
    condition_type: ConditionType = Field(..., description="평가 조건 유형")
    threshold: float | list[float] = Field(..., description="임계값")
    severity: Severity = Field(default=Severity.WARNING, description="심각도")
    action: ActionType = Field(default=ActionType.LOG, description="액션")
    enabled: bool = Field(default=True, description="활성화 여부")
    schedule_interval_seconds: int = Field(default=60, ge=1, description="실행 주기 (초)")
    tags: list[str] = Field(default_factory=list, description="태그 목록")


class CEPRuleUpdateRequest(BaseModel):
    """규칙 수정 요청. None인 필드는 변경하지 않는다."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    sql_query: str | None = None
    condition_type: ConditionType | None = None
    threshold: float | list[float] | None = None
    severity: Severity | None = None
    action: ActionType | None = None
    enabled: bool | None = None
    schedule_interval_seconds: int | None = Field(default=None, ge=1)
    tags: list[str] | None = None


class EvaluateRequest(BaseModel):
    """수동 평가 요청."""

    value: float | None = Field(..., description="평가할 현재 값")


class CEPRuleResponse(BaseModel):
    """규칙 응답."""

    id: str
    name: str
    description: str
    sql_query: str
    condition_type: str
    threshold: float | list[float]
    severity: str
    action: str
    enabled: bool
    schedule_interval_seconds: int
    tags: list[str]
    created_at: str
    updated_at: str


class CEPResultResponse(BaseModel):
    """평가 결과 응답."""

    rule_name: str
    triggered: bool
    current_value: float | None
    threshold: float | list[float]
    message: str
    timestamp: str
    severity: str
    condition_type: str


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------
def _rule_to_response(rule: CEPRule) -> dict:
    """CEPRule → 응답 딕셔너리 변환."""
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "sql_query": rule.sql_query,
        "condition_type": rule.condition_type.value,
        "threshold": rule.threshold,
        "severity": rule.severity.value,
        "action": rule.action.value,
        "enabled": rule.enabled,
        "schedule_interval_seconds": rule.schedule_interval_seconds,
        "tags": rule.tags,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------
@router.post("/rules", status_code=status.HTTP_201_CREATED)
async def create_rule(req: CEPRuleCreateRequest):
    """CEP 규칙을 생성한다."""
    engine = get_cep_engine()
    rule = CEPRule(
        name=req.name,
        description=req.description,
        sql_query=req.sql_query,
        condition_type=req.condition_type,
        threshold=req.threshold,
        severity=req.severity,
        action=req.action,
        enabled=req.enabled,
        schedule_interval_seconds=req.schedule_interval_seconds,
        tags=req.tags,
    )
    try:
        created = engine.add_rule(rule)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_RULE", "message": str(e)},
        )
    return _rule_to_response(created)


@router.get("/rules")
async def list_rules(
    enabled: bool | None = None,
    severity: str | None = None,
    tag: str | None = None,
):
    """등록된 CEP 규칙 목록을 조회한다.

    필터 파라미터로 enabled, severity, tag를 지원한다.
    """
    engine = get_cep_engine()
    rules = engine.list_rules()

    # 필터 적용
    if enabled is not None:
        rules = [r for r in rules if r.enabled == enabled]
    if severity is not None:
        rules = [r for r in rules if r.severity.value == severity]
    if tag is not None:
        rules = [r for r in rules if tag in r.tags]

    return {
        "data": [_rule_to_response(r) for r in rules],
        "total": len(rules),
    }


@router.get("/rules/{rule_id}")
async def get_rule(rule_id: str):
    """규칙 상세를 조회한다."""
    engine = get_cep_engine()
    rule = engine.get_rule(rule_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RULE_NOT_FOUND", "message": f"규칙 ID '{rule_id}'을(를) 찾을 수 없습니다"},
        )
    return _rule_to_response(rule)


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, req: CEPRuleUpdateRequest):
    """규칙을 수정한다. None인 필드는 기존 값을 유지한다."""
    engine = get_cep_engine()

    # None이 아닌 필드만 모아서 업데이트
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "NO_UPDATES", "message": "수정할 필드가 없습니다"},
        )

    try:
        updated = engine.update_rule(rule_id, **updates)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_RULE", "message": str(e)},
        )

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RULE_NOT_FOUND", "message": f"규칙 ID '{rule_id}'을(를) 찾을 수 없습니다"},
        )
    return _rule_to_response(updated)


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """규칙을 삭제한다. 평가 이력도 함께 제거된다."""
    engine = get_cep_engine()
    deleted = engine.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RULE_NOT_FOUND", "message": f"규칙 ID '{rule_id}'을(를) 찾을 수 없습니다"},
        )
    return {"deleted": True, "rule_id": rule_id}


@router.post("/rules/{rule_id}/evaluate")
async def evaluate_rule(rule_id: str, req: EvaluateRequest):
    """규칙을 수동으로 평가한다.

    실제 SQL 실행 없이 주어진 value로 조건을 판정한다.
    """
    engine = get_cep_engine()
    rule = engine.get_rule(rule_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RULE_NOT_FOUND", "message": f"규칙 ID '{rule_id}'을(를) 찾을 수 없습니다"},
        )
    if not rule.enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "RULE_DISABLED", "message": "비활성화된 규칙은 평가할 수 없습니다"},
        )

    result = engine.evaluate_rule(rule, req.value)
    return result.to_dict()


@router.get("/rules/{rule_id}/history")
async def get_rule_history(rule_id: str, limit: int = 50):
    """규칙의 평가 이력을 조회한다.

    최신 순으로 정렬하여 반환한다. limit 기본값은 50건.
    """
    engine = get_cep_engine()
    rule = engine.get_rule(rule_id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RULE_NOT_FOUND", "message": f"규칙 ID '{rule_id}'을(를) 찾을 수 없습니다"},
        )

    history = engine.get_history_by_id(rule_id)
    # 최신 순 정렬 + limit 적용
    history_sorted = list(reversed(history))[:limit]
    return {
        "rule_id": rule_id,
        "rule_name": rule.name,
        "data": [r.to_dict() for r in history_sorted],
        "total": len(history),
    }


@router.get("/stats")
async def get_stats():
    """CEP 엔진 전체 통계를 반환한다."""
    engine = get_cep_engine()
    return engine.get_stats()
