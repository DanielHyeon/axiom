"""DMN 규칙 엔진 — 비헤이비어 기반 의사결정 로직 실행.

KAIR의 dmn_engine.py를 참조하여 Axiom 패턴으로 이식.
ObjectType의 Behavior(Rule 타입)를 DMN 결정 테이블로 실행한다.

지원 기능:
  - 결정 테이블 평가 (조건 매칭 → 결과 반환)
  - 다중 규칙 결합 (First, Collect, Priority)
  - 변수 바인딩 및 표현식 평가
"""
from __future__ import annotations

import ast
import operator
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ─── 데이터 모델 ──────────────────────────────────────────

class HitPolicy:
    """결정 테이블 적중 정책."""
    FIRST = "FIRST"        # 첫 번째 매칭 규칙만 반환
    COLLECT = "COLLECT"    # 모든 매칭 규칙 수집
    PRIORITY = "PRIORITY"  # 우선순위 기반 정렬 후 첫 번째 반환


@dataclass
class DecisionInput:
    """결정 테이블 입력 컬럼."""
    name: str
    expression: str = ""    # 입력 표현식 (예: "age", "order.total")
    type_ref: str = "string"  # string, number, boolean, date


@dataclass
class DecisionOutput:
    """결정 테이블 출력 컬럼."""
    name: str
    type_ref: str = "string"


@dataclass
class DecisionRule:
    """결정 테이블 규칙 행."""
    conditions: dict[str, str]    # 입력명 → 조건식 (예: "> 100", "== 'VIP'", "in [1,2,3]")
    outputs: dict[str, Any]       # 출력명 → 결과값
    priority: int = 0
    description: str = ""


@dataclass
class DecisionTable:
    """DMN 결정 테이블."""
    name: str
    hit_policy: str = HitPolicy.FIRST
    inputs: list[DecisionInput] = field(default_factory=list)
    output_defs: list[DecisionOutput] = field(default_factory=list)
    rules: list[DecisionRule] = field(default_factory=list)


# ─── 조건 평가 ─────────────────────────────────────────────

# 비교 연산자 매핑 — 긴 연산자를 먼저 검사하여 ">=" 가 ">" 보다 우선
_OPS: list[tuple[str, Any]] = [
    (">=", operator.ge),
    ("<=", operator.le),
    ("!=", operator.ne),
    ("==", operator.eq),
    (">", operator.gt),
    ("<", operator.lt),
]


def _parse_rhs(rhs: str) -> Any:
    """오른쪽 피연산자를 적절한 파이썬 타입으로 변환한다."""
    # 문자열 리터럴
    if (rhs.startswith("'") and rhs.endswith("'")) or (
        rhs.startswith('"') and rhs.endswith('"')
    ):
        return rhs[1:-1]
    # 불리언
    if rhs in ("True", "true"):
        return True
    if rhs in ("False", "false"):
        return False
    # 숫자 — 소수점 유무로 float / int 결정
    if "." in rhs:
        return float(rhs)
    return int(rhs)


def _evaluate_condition(condition: str, value: Any) -> bool:
    """단일 조건을 평가한다.

    지원 형식:
      - "> 100"         → value > 100
      - "== 'VIP'"      → value == 'VIP'
      - "in [1, 2, 3]"  → value in [1, 2, 3]
      - "-" 또는 ""     → 항상 True (와일드카드)
      - "not in [...]"  → value not in [...]
    """
    condition = condition.strip()

    # 와일드카드 — 빈 문자열 또는 대시
    if not condition or condition == "-":
        return True

    # in 연산자
    if condition.startswith("in "):
        try:
            list_str = condition[3:].strip()
            # 안전성: ast.literal_eval로 리터럴만 파싱 (코드 실행 방지)
            check_list = ast.literal_eval(list_str)
            return value in check_list
        except Exception:
            return False

    # not in 연산자
    if condition.startswith("not in "):
        try:
            list_str = condition[7:].strip()
            # 안전성: ast.literal_eval로 리터럴만 파싱 (코드 실행 방지)
            check_list = ast.literal_eval(list_str)
            return value not in check_list
        except Exception:
            return False

    # 비교 연산자 — 긴 접두사부터 순서대로 매칭
    for op_str, op_func in _OPS:
        if condition.startswith(op_str):
            rhs_raw = condition[len(op_str):].strip()
            try:
                rhs_val = _parse_rhs(rhs_raw)
                return op_func(value, rhs_val)
            except (ValueError, TypeError):
                return False

    # 연산자 없는 단순 값 — 등호 비교
    try:
        if condition.startswith("'") and condition.endswith("'"):
            return value == condition[1:-1]
        return str(value) == condition
    except Exception:
        return False


def _evaluate_rule(rule: DecisionRule, context: dict[str, Any]) -> bool:
    """규칙의 모든 조건이 충족되는지 평가한다."""
    for input_name, condition in rule.conditions.items():
        value = context.get(input_name)
        if not _evaluate_condition(condition, value):
            return False
    return True


# ─── 결정 테이블 실행 ──────────────────────────────────────

def execute_decision_table(
    table: DecisionTable,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    """결정 테이블을 평가하고 결과를 반환한다.

    Args:
        table: DMN 결정 테이블 정의
        context: 입력 변수 딕셔너리

    Returns:
        매칭된 규칙의 출력값 리스트 (hit_policy에 따라 1개 또는 다수)
    """
    matched: list[tuple[int, dict[str, Any]]] = []

    for rule in table.rules:
        if _evaluate_rule(rule, context):
            matched.append((rule.priority, rule.outputs))

    if not matched:
        logger.debug("dmn_no_match", table=table.name, context_keys=list(context.keys()))
        return []

    if table.hit_policy == HitPolicy.FIRST:
        # 첫 번째 매칭 규칙만 반환
        return [matched[0][1]]
    elif table.hit_policy == HitPolicy.PRIORITY:
        # 우선순위(낮은 값 = 높은 우선순위) 정렬 후 첫 번째 반환
        matched.sort(key=lambda x: x[0])
        return [matched[0][1]]
    else:
        # COLLECT — 모든 매칭 규칙 수집
        return [m[1] for m in matched]


# ─── 편의 함수 ─────────────────────────────────────────────

def create_table_from_dict(definition: dict) -> DecisionTable:
    """딕셔너리에서 DecisionTable을 생성한다.

    프론트엔드나 API에서 JSON으로 전달된 규칙 정의를 파싱한다.

    Args:
        definition: {
            "name": str,
            "hit_policy": "FIRST" | "COLLECT" | "PRIORITY",
            "inputs": [{"name": str, "expression": str, "type_ref": str}],
            "outputs": [{"name": str, "type_ref": str}],
            "rules": [{
                "conditions": {"input_name": "condition_expr"},
                "outputs": {"output_name": value},
                "priority": int,
                "description": str,
            }],
        }
    """
    inputs = [
        DecisionInput(
            name=i["name"],
            expression=i.get("expression", ""),
            type_ref=i.get("type_ref", "string"),
        )
        for i in definition.get("inputs", [])
    ]

    output_defs = [
        DecisionOutput(
            name=o["name"],
            type_ref=o.get("type_ref", "string"),
        )
        for o in definition.get("outputs", [])
    ]

    rules = [
        DecisionRule(
            conditions=r.get("conditions", {}),
            outputs=r.get("outputs", {}),
            priority=r.get("priority", 0),
            description=r.get("description", ""),
        )
        for r in definition.get("rules", [])
    ]

    return DecisionTable(
        name=definition.get("name", "Unnamed"),
        hit_policy=definition.get("hit_policy", HitPolicy.FIRST),
        inputs=inputs,
        output_defs=output_defs,
        rules=rules,
    )
