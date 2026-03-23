"""G22 + G23: DQ Rule CRUD + Test Execution API.

품질 규칙(not_null, unique, range, regex, custom_sql, referential)을 정의하고
실제 데이터에 대해 테스트 실행하여 검증 결과를 반환한다.

기존 Weaver 품질 엔진(quality.py)의 9차원 수집과 별개로,
사용자 정의 품질 규칙의 CRUD + 실행을 담당한다.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import AuthService, CurrentUser
from app.services.query_engine import QueryCaller, query_engine

logger = logging.getLogger("axiom.weaver.api.quality_rules")

router = APIRouter(prefix="/api/v3/weaver/quality/rules", tags=["품질 규칙"])

_auth = AuthService()
_ALLOWED_ROLES = {"admin", "analyst", "engineer", "manager"}

# 식별자 검증
_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,254}$")


async def _get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    return _auth.verify_token(authorization)


# ── 모델 ── #

class RuleType(str, Enum):
    """품질 규칙 유형"""
    NOT_NULL = "not_null"             # NULL 없어야 함
    UNIQUE = "unique"                 # 중복 없어야 함
    RANGE = "range"                   # min/max 범위 내
    REGEX = "regex"                   # 패턴 매칭
    CUSTOM_SQL = "custom_sql"         # 사용자 정의 SQL (결과 0행이면 통과)
    REFERENTIAL = "referential"       # 참조 무결성


class QualityRule(BaseModel):
    """품질 규칙 정의"""
    rule_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    rule_type: RuleType
    datasource_name: str = ""
    schema_name: str = "public"
    table_name: str
    column_name: str = ""             # 컬럼 대상 (CUSTOM_SQL은 비워도 됨)
    # 규칙 파라미터
    min_value: float | None = None    # RANGE용
    max_value: float | None = None
    pattern: str = ""                 # REGEX용 (max 200자)
    custom_sql: str = ""              # CUSTOM_SQL용 (SELECT, 결과 0행=통과)
    ref_table: str = ""               # REFERENTIAL용 (참조 대상 테이블)
    ref_column: str = ""              # REFERENTIAL용 (참조 대상 컬럼)
    # 메타
    severity: Literal["error", "warning", "info"] = "error"
    enabled: bool = True
    tenant_id: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QualityRuleRequest(BaseModel):
    """규칙 생성/수정 요청"""
    name: str
    rule_type: RuleType
    datasource_name: str = ""
    schema_name: str = "public"
    table_name: str
    column_name: str = ""
    min_value: float | None = None
    max_value: float | None = None
    pattern: str = Field(default="", max_length=200)
    custom_sql: str = Field(default="", max_length=2000)
    ref_table: str = ""
    ref_column: str = ""
    severity: Literal["error", "warning", "info"] = "error"
    enabled: bool = True


class TestExecutionRequest(BaseModel):
    """테스트 실행 요청 — 연결 정보"""
    engine: str
    connection: dict[str, Any]
    sample_size: int = Field(default=10000, ge=100, le=1000000)


class TestResult(BaseModel):
    """테스트 실행 결과"""
    rule_id: str
    rule_name: str
    rule_type: str
    passed: bool
    total_rows: int = 0
    violation_count: int = 0
    violation_rate: float = 0.0       # 0.0 ~ 1.0
    sample_violations: list[dict] = Field(default_factory=list, max_length=10)
    execution_time_ms: float = 0.0
    error: str | None = None


# ── 저장소 (in-memory MVP) ── #

_rules: dict[str, QualityRule] = {}


def _get_rule(rule_id: str, tenant_id: str) -> QualityRule:
    rule = _rules.get(rule_id)
    if not rule or rule.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail=f"규칙을 찾을 수 없습니다: {rule_id}")
    return rule


# ── CRUD 엔드포인트 ── #

@router.get("")
async def list_quality_rules(
    user: CurrentUser = Depends(_get_current_user),
    table_name: str | None = None,
    rule_type: RuleType | None = None,
) -> dict:
    """품질 규칙 목록 조회"""
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    rules = [r for r in _rules.values() if r.tenant_id == user.tenant_id]
    if table_name:
        rules = [r for r in rules if r.table_name == table_name]
    if rule_type:
        rules = [r for r in rules if r.rule_type == rule_type]

    return {
        "success": True,
        "data": [r.model_dump(mode="json") for r in rules],
        "total": len(rules),
    }


@router.post("")
async def create_quality_rule(
    request: QualityRuleRequest,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """품질 규칙 생성"""
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    rule = QualityRule(
        **request.model_dump(),
        tenant_id=user.tenant_id,
        created_by=user.user_id,
    )
    rule.rule_id = uuid.uuid4().hex[:12]  # 서버 생성 강제
    _rules[rule.rule_id] = rule

    logger.info("품질 규칙 생성: %s (%s.%s, type=%s)",
                rule.rule_id, rule.table_name, rule.column_name, rule.rule_type.value)
    return {"success": True, "data": rule.model_dump(mode="json")}


@router.get("/{rule_id}")
async def get_quality_rule(
    rule_id: str,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")
    rule = _get_rule(rule_id, user.tenant_id)
    return {"success": True, "data": rule.model_dump(mode="json")}


@router.put("/{rule_id}")
async def update_quality_rule(
    rule_id: str,
    request: QualityRuleRequest,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    rule = _get_rule(rule_id, user.tenant_id)
    for field, value in request.model_dump().items():
        setattr(rule, field, value)
    return {"success": True, "data": rule.model_dump(mode="json")}


@router.delete("/{rule_id}")
async def delete_quality_rule(
    rule_id: str,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    _get_rule(rule_id, user.tenant_id)
    del _rules[rule_id]
    return {"success": True, "message": f"규칙 삭제 완료: {rule_id}"}


# ── G23: 테스트 실행 ── #

@router.post("/{rule_id}/test")
async def execute_quality_test(
    rule_id: str,
    request: TestExecutionRequest,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """품질 규칙 테스트 실행 — 실제 데이터에 대해 검증.

    규칙 유형별 SQL 생성 → QueryPolicyEngine 경유 실행 → 결과 반환.
    """
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    rule = _get_rule(rule_id, user.tenant_id)

    # 식별자 검증
    for name in [rule.schema_name, rule.table_name]:
        if not _SAFE_IDENT.match(name):
            raise HTTPException(status_code=400, detail=f"유효하지 않은 식별자: {name}")
    if rule.column_name and not _SAFE_IDENT.match(rule.column_name):
        raise HTTPException(status_code=400, detail=f"유효하지 않은 컬럼명: {rule.column_name}")

    try:
        sql = _build_test_sql(rule, request.sample_size)
        result = await query_engine.execute_safe(
            datasource_name=rule.datasource_name,
            sql=sql,
            caller=QueryCaller.PROFILING,
            user_id=user.user_id,
            user_role=user.role,
            tenant_id=user.tenant_id,
            connection=request.connection,
            engine=request.engine,
            limit=request.sample_size,
        )

        violations = result.rows
        total = request.sample_size  # 근사치 (정확한 총 행 수는 별도 쿼리 필요)
        violation_count = len(violations)
        passed = violation_count == 0

        return {
            "success": True,
            "data": TestResult(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                rule_type=rule.rule_type.value,
                passed=passed,
                total_rows=total,
                violation_count=violation_count,
                violation_rate=round(violation_count / max(total, 1), 4),
                sample_violations=violations[:10],
                execution_time_ms=result.execution_time_ms,
            ).model_dump(mode="json"),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("품질 테스트 실행 실패: %s", e)
        raise HTTPException(status_code=500, detail="품질 테스트 실행 중 내부 오류") from e


def _build_test_sql(rule: QualityRule, sample_size: int) -> str:
    """규칙 유형별 테스트 SQL 생성 — 위반 행을 반환하는 SELECT"""
    s = rule.schema_name
    t = rule.table_name
    c = rule.column_name
    fqt = f'"{s}"."{t}"'

    if rule.rule_type == RuleType.NOT_NULL:
        return f'SELECT * FROM (SELECT * FROM {fqt} LIMIT {int(sample_size)}) AS _s WHERE "{c}" IS NULL'

    elif rule.rule_type == RuleType.UNIQUE:
        return (
            f'SELECT "{c}", COUNT(*) AS dup_count '
            f'FROM (SELECT "{c}" FROM {fqt} LIMIT {int(sample_size)}) AS _s '
            f'GROUP BY "{c}" HAVING COUNT(*) > 1'
        )

    elif rule.rule_type == RuleType.RANGE:
        conditions = []
        if rule.min_value is not None:
            conditions.append(f'"{c}" < {float(rule.min_value)}')
        if rule.max_value is not None:
            conditions.append(f'"{c}" > {float(rule.max_value)}')
        where = " OR ".join(conditions) if conditions else "FALSE"
        return f'SELECT * FROM (SELECT * FROM {fqt} LIMIT {int(sample_size)}) AS _s WHERE {where}'

    elif rule.rule_type == RuleType.REGEX:
        # 패턴 안전성 — 정규식 자체는 SQL 파라미터로 전달하기 어려우므로 길이 제한으로 방어
        pattern = rule.pattern[:200].replace("'", "''")
        return (
            f"SELECT * FROM (SELECT * FROM {fqt} LIMIT {int(sample_size)}) AS _s "
            f"WHERE \"{c}\"::text !~ '{pattern}'"
        )

    elif rule.rule_type == RuleType.CUSTOM_SQL:
        # C1: CUSTOM_SQL을 서브쿼리로 래핑 + LIMIT 강제 (크로스 테넌트 방지는 Phase 5 스키마 ACL)
        custom = rule.custom_sql.strip()
        if not custom:
            raise ValueError("custom_sql이 비어있습니다")
        return f"SELECT * FROM ({custom}) AS _custom LIMIT {int(sample_size)}"

    elif rule.rule_type == RuleType.REFERENTIAL:
        ref_t = rule.ref_table
        ref_c = rule.ref_column
        if not _SAFE_IDENT.match(ref_t) or not _SAFE_IDENT.match(ref_c):
            raise ValueError(f"유효하지 않은 참조 식별자: {ref_t}.{ref_c}")
        return (
            f'SELECT a.* FROM (SELECT * FROM {fqt} LIMIT {int(sample_size)}) AS a '
            f'LEFT JOIN "{s}"."{ref_t}" AS b ON a."{c}" = b."{ref_c}" '
            f'WHERE b."{ref_c}" IS NULL AND a."{c}" IS NOT NULL'
        )

    raise ValueError(f"미지원 규칙 유형: {rule.rule_type}")
