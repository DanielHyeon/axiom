"""
GWT(Given-When-Then) 룰 엔진

BusinessOS의 Generic Interpreter 패턴을 Axiom에 적용:
- Given: 온톨로지 상태 조건 평가 (Cypher 패턴 매칭)
- When: 이벤트 타입 매칭
- Then: 상태 변경 + 이벤트 발행 + 액션 체이닝

⚠️ 보안 원칙:
- Cypher 쿼리에 사용자 입력을 f-string으로 직접 삽입 금지
- 모든 라벨/필드명은 ALLOWED_LABELS, _ALNUM_UNDERSCORE 화이트리스트로 검증
- expression 평가는 ast.parse + safe_eval (eval() 사용 금지)
- ontology_service.py의 기존 보안 패턴을 그대로 준수
"""
from __future__ import annotations

import ast
import json
import operator
import re
import uuid
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger()

# ── 보안: ontology_service.py와 동일한 화이트리스트 패턴 ──
# 필드명·변수명에 허용되는 문자: 영문자/밑줄로 시작, 이후 영숫자/밑줄
_ALNUM_UNDERSCORE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Neo4j 노드 라벨 허용 목록 — Semantic 5계층 + Kinetic 확장 라벨
ALLOWED_LABELS = {
    "Kpi", "Measure", "Process", "Resource", "Driver", "Entity",
    "ActionType", "Policy",
}

# Kinetic Layer 관계 타입 허용 목록 (기존 온톨로지 관계 포함)
ALLOWED_REL_TYPES_KINETIC = {
    # Kinetic 전용 관계
    "TRIGGERS", "MODIFIES", "CHAINS_TO", "USES_MODEL",
    "EMITS_TO", "DISPATCHES_TO",
    # 기존 Semantic 관계
    "DERIVED_FROM", "OBSERVED_IN", "PRECEDES", "SUPPORTS", "USES",
    "CAUSES", "INFLUENCES", "RELATED_TO",
    "READS_FIELD", "PREDICTS_FIELD", "HAS_BEHAVIOR", "DEFINES",
}

# ActionType 업데이트 시 허용되는 필드 목록 (Cypher 인젝션 방지)
ALLOWED_UPDATE_FIELDS = {
    "name", "description", "enabled", "priority",
    "given_conditions", "when_event", "then_actions",
}


def _iso_now() -> str:
    """UTC ISO 타임스탬프 반환"""
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════
# 데이터 클래스 정의
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class GWTCondition:
    """Given 조건 하나를 표현

    type 종류:
    - "state": 특정 계층 노드의 필드 값 비교
    - "relation": 두 노드 간 관계 존재 여부 + 속성 비교
    - "expression": Python 표현식 기반 복합 조건
    """
    type: str                    # "state" | "relation" | "expression"
    node_layer: str = ""         # 대상 노드의 계층 (state 타입용)
    field: str = ""              # 비교할 필드명
    op: str = "=="               # 비교 연산자: ==, !=, >, <, >=, <=, in, not_in, contains
    value: Any = None            # 비교 대상 값 또는 expression 문자열
    # relation 타입 전용 필드
    source_layer: str = ""       # 관계 시작 노드의 계층
    rel_type: str = ""           # 관계 타입 (TRIGGERS, MODIFIES 등)
    target_layer: str = ""       # 관계 끝 노드의 계층

    def validate(self) -> None:
        """⚠️ Cypher 인젝션 방지 — 라벨/필드/관계 타입 화이트리스트 검증

        모든 사용자 지정 값이 허용 목록에 있는지 확인한다.
        검증 실패 시 ValueError를 발생시켜 룰 실행을 차단한다.
        """
        # 노드 계층(라벨) 검증 — capitalize()로 변환 후 확인
        if self.node_layer and self.node_layer.capitalize() not in ALLOWED_LABELS:
            raise ValueError(f"허용되지 않는 node_layer: {self.node_layer}")
        if self.source_layer and self.source_layer.capitalize() not in ALLOWED_LABELS:
            raise ValueError(f"허용되지 않는 source_layer: {self.source_layer}")
        if self.target_layer and self.target_layer.capitalize() not in ALLOWED_LABELS:
            raise ValueError(f"허용되지 않는 target_layer: {self.target_layer}")
        # 필드명 검증 — 영숫자+밑줄만 허용
        if self.field and not _ALNUM_UNDERSCORE.match(self.field):
            raise ValueError(f"허용되지 않는 field 이름: {self.field}")
        # 관계 타입 검증
        if self.rel_type and self.rel_type not in ALLOWED_REL_TYPES_KINETIC:
            raise ValueError(f"허용되지 않는 rel_type: {self.rel_type}")


@dataclass(frozen=True)
class GWTAction:
    """Then 액션 하나를 표현

    op 종류:
    - "SET": 노드 필드 값 변경
    - "EMIT": 새 이벤트 발행
    - "EXECUTE": 다른 ActionType 체이닝 호출
    - "CREATE_RELATION": 노드 간 관계 생성
    - "DELETE_RELATION": 노드 간 관계 삭제
    """
    op: str                      # "SET" | "EMIT" | "EXECUTE" | "CREATE_RELATION" | "DELETE_RELATION"
    target_node: str = ""        # 대상 노드 ID 또는 "$trigger.source_node_id"
    field: str = ""              # SET: 변경할 필드명
    value: Any = None            # SET: 새 값
    event_type: str = ""         # EMIT: 발행할 이벤트 타입
    payload: dict = dataclass_field(default_factory=dict)   # EMIT: 이벤트 페이로드
    action_id: str = ""          # EXECUTE: 호출할 ActionType ID
    params: dict = dataclass_field(default_factory=dict)    # EXECUTE: 파라미터

    def validate(self) -> None:
        """⚠️ field명 인젝션 방지 — _ALNUM_UNDERSCORE 검증"""
        if self.field and not _ALNUM_UNDERSCORE.match(self.field):
            raise ValueError(f"허용되지 않는 field 이름: {self.field}")


@dataclass
class GWTRule:
    """GWT 룰 전체 정의 — Neo4j의 ActionType 노드 하나에 대응"""
    id: str
    name: str
    case_id: str
    tenant_id: str
    given: list[GWTCondition]    # Given 조건 목록 (AND 결합)
    when_event: str              # When 트리거 이벤트 타입
    then: list[GWTAction]        # Then 액션 시퀀스
    enabled: bool = True         # 활성화 여부
    priority: int = 100          # 우선순위 (높을수록 먼저 실행)
    version: int = 1             # 룰 버전


@dataclass
class GWTEvalContext:
    """룰 평가 시 사용되는 컨텍스트

    이벤트 정보와 온톨로지 상태 스냅샷을 담는다.
    handle_event()에서 생성되어 evaluate_given()/execute_then()에 전달된다.
    """
    event_type: str              # 수신된 이벤트 타입
    aggregate_id: str            # 이벤트 대상 어그리거트 ID
    source_node_id: str          # 이벤트 발생 노드 ID
    payload: dict                # 이벤트 페이로드
    case_id: str                 # 케이스 ID
    tenant_id: str               # 테넌트 ID
    # _load_context_states()에서 채워지는 온톨로지 상태 스냅샷
    node_states: dict[str, dict[str, Any]] = dataclass_field(default_factory=dict)
    # 관계 상태 (향후 확장용)
    relation_states: dict[str, list[dict]] = dataclass_field(default_factory=dict)


@dataclass
class GWTExecutionResult:
    """룰 실행 결과 — 상태 변경, 발행된 이벤트, 체이닝된 액션 기록"""
    rule_id: str
    rule_name: str
    matched: bool                # Given 조건 매칭 여부
    state_changes: list[dict] = dataclass_field(default_factory=list)
    emitted_events: list[dict] = dataclass_field(default_factory=list)
    chained_actions: list[str] = dataclass_field(default_factory=list)
    error: str | None = None


# ═══════════════════════════════════════════════════════════════
# 안전한 표현식 평가기 (eval() 완전 대체)
# ═══════════════════════════════════════════════════════════════

# 비교 연산자 매핑 — ast 노드 → operator 함수
_SAFE_COMPARE_OPS: dict[type, Any] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.Gt: operator.gt,
    ast.LtE: operator.le,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

# 이항 연산자 매핑 — ast 노드 → operator 함수
_SAFE_BIN_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}


def safe_eval(expression: str, variables: dict[str, Any]) -> Any:
    """AST 기반 안전한 표현식 평가기 — eval() 완전 대체

    허용 노드:
    - Constant (숫자, 문자열, bool, None)
    - Name (변수 참조: state, payload, trigger)
    - Compare (==, !=, >, <, >=, <=, in, not in)
    - BoolOp (and, or)
    - UnaryOp (not, 단항 마이너스)
    - BinOp (+, -, *, /, %)
    - Attribute (state.xxx → dict key 접근으로 변환)
    - Subscript (state["xxx"])

    ❌ 금지: Call, Import, Lambda, FunctionDef, ClassDef, Exec 등
    → ValueError 발생으로 실행 차단
    """
    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree.body, variables)


def _eval_node(node: ast.AST, variables: dict) -> Any:
    """AST 노드 재귀 평가 — 허용된 노드 타입만 처리

    각 노드 타입별로 안전한 연산만 수행한다.
    허용되지 않는 노드(Call, Import 등)는 ValueError로 차단한다.
    """
    # 상수 리터럴: 숫자, 문자열, bool, None
    if isinstance(node, ast.Constant):
        return node.value

    # 변수 참조: state, payload, trigger 등
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError(f"알 수 없는 변수: {node.id}")
        return variables[node.id]

    # 속성 접근: state.status → state["status"]로 변환
    if isinstance(node, ast.Attribute):
        obj = _eval_node(node.value, variables)
        if isinstance(obj, dict):
            return obj.get(node.attr)
        raise ValueError(f"속성 접근 불가: {node.attr}")

    # 인덱스/키 접근: state["status"], items[0]
    if isinstance(node, ast.Subscript):
        obj = _eval_node(node.value, variables)
        key = _eval_node(node.slice, variables)
        if isinstance(obj, dict):
            return obj.get(key)
        if isinstance(obj, (list, tuple)):
            return obj[key]
        raise ValueError(f"인덱스 접근 불가: {type(obj)}")

    # 비교 연산: ==, !=, >, <, >=, <=, in, not in
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        for op_node, comparator in zip(node.ops, node.comparators):
            op_func = _SAFE_COMPARE_OPS.get(type(op_node))
            if op_func is None:
                raise ValueError(
                    f"허용되지 않는 비교 연산자: {type(op_node).__name__}"
                )
            right = _eval_node(comparator, variables)
            if not op_func(left, right):
                return False
            left = right
        return True

    # 논리 연산: and, or (단락 평가 지원)
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval_node(v, variables) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_eval_node(v, variables) for v in node.values)

    # 단항 연산: not, 단항 마이너스(-)
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not _eval_node(node.operand, variables)
        if isinstance(node.op, ast.USub):
            return -_eval_node(node.operand, variables)

    # 이항 연산: +, -, *, /, %
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_BIN_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(
                f"허용되지 않는 이항 연산자: {type(node.op).__name__}"
            )
        return op_func(
            _eval_node(node.left, variables),
            _eval_node(node.right, variables),
        )

    # 허용되지 않는 노드 — Call, Import, Lambda 등 차단
    raise ValueError(f"허용되지 않는 표현식 노드: {type(node).__name__}")


# ═══════════════════════════════════════════════════════════════
# GWT 룰 엔진
# ═══════════════════════════════════════════════════════════════


class GWTEngine:
    """GWT 룰 엔진 — BusinessOS의 Generic Interpreter를 Axiom에 구현

    동작 플로우:
    1. Redis Stream에서 이벤트 수신 (GWTConsumerWorker가 호출)
    2. Neo4j에서 해당 case_id의 활성 ActionType 노드 조회
    3. when_event가 매칭되는 룰 필터링
    4. 각 룰의 given 조건을 Cypher로 평가
    5. 매칭된 룰의 then 액션 실행 (priority 순)
    6. 결과 이벤트를 EventOutbox에 기록

    dry_run=True: 시뮬레이션 모드 — Neo4j 쓰기/이벤트 발행 없이 결과만 계산
    (Event Fork Engine에서 호출 시 사용)
    """

    # 무한 루프 방지 — EXECUTE 체이닝 최대 깊이
    MAX_CHAIN_DEPTH = 10

    def __init__(
        self,
        neo4j_client: Any,
        async_publisher: Any,
        dry_run: bool = False,
    ):
        """
        Args:
            neo4j_client: Neo4jClient (execute_read/execute_write 메서드 보유)
            async_publisher: AsyncEventPublisher (publish 메서드 보유)
            dry_run: True이면 Neo4j 쓰기/이벤트 발행 건너뜀 (시뮬레이션 모드)
        """
        self._neo4j = neo4j_client
        self._publisher = async_publisher
        self._dry_run = dry_run

    # ── 룰 로딩 ──────────────────────────────────────────────

    async def load_rules(
        self,
        case_id: str,
        tenant_id: str,
        event_type: str,
    ) -> list[GWTRule]:
        """Neo4j에서 해당 case+tenant의 활성 ActionType 중 event_type 매칭 룰 조회

        tenant_id 필터로 크로스 테넌트 룰 실행을 방지한다.
        priority 내림차순으로 정렬하여 우선순위 높은 룰이 먼저 실행된다.
        """
        query = """
        MATCH (a:ActionType {case_id: $case_id, tenant_id: $tenant_id, enabled: true})
        WHERE a.when_event = $event_type
        RETURN a
        ORDER BY a.priority DESC
        """
        records = await self._neo4j.execute_read(query, {
            "case_id": case_id,
            "tenant_id": tenant_id,
            "event_type": event_type,
        })
        return [self._parse_rule(r["a"]) for r in records]

    # ── Given 조건 평가 ──────────────────────────────────────

    async def evaluate_given(
        self,
        rule: GWTRule,
        ctx: GWTEvalContext,
    ) -> bool:
        """Given 조건 전체를 평가 (AND 결합)

        모든 조건이 True여야 룰이 매칭된다.
        조건 타입별로 적절한 평가 메서드를 호출한다.
        """
        for cond in rule.given:
            if cond.type == "state":
                if not await self._eval_state_condition(cond, ctx):
                    return False
            elif cond.type == "relation":
                if not await self._eval_relation_condition(cond, ctx):
                    return False
            elif cond.type == "expression":
                if not self._eval_expression(cond, ctx):
                    return False
        return True

    # ── Then 액션 실행 ───────────────────────────────────────

    async def execute_then(
        self,
        rule: GWTRule,
        ctx: GWTEvalContext,
        depth: int = 0,
        executed_rule_ids: set[str] | None = None,
    ) -> GWTExecutionResult:
        """Then 액션 시퀀스 실행

        depth 파라미터로 체이닝 깊이를 추적하여 무한 루프를 방지한다.
        executed_rule_ids로 이미 실행된 룰을 추적하여 순환 참조를 방지한다.
        dry_run 모드에서는 Neo4j 쓰기와 이벤트 발행을 건너뛴다.
        """
        # 순환 방지용 실행 이력 집합 — 최초 호출 시 생성
        if executed_rule_ids is None:
            executed_rule_ids = set()

        result = GWTExecutionResult(
            rule_id=rule.id,
            rule_name=rule.name,
            matched=True,
        )

        # 무한 루프 방지: 최대 체이닝 깊이 초과 시 중단
        if depth >= self.MAX_CHAIN_DEPTH:
            result.error = f"최대 체이닝 깊이({self.MAX_CHAIN_DEPTH}) 초과"
            logger.warning(
                "gwt_max_chain_depth_exceeded",
                rule_id=rule.id,
                depth=depth,
            )
            return result

        # 현재 룰을 실행 이력에 등록
        executed_rule_ids.add(rule.id)

        for action in rule.then:
            try:
                if action.op == "SET":
                    change = await self._handle_set_action(action, ctx)
                    result.state_changes.append(change)

                elif action.op == "EMIT":
                    event = self._build_event(action, ctx)
                    result.emitted_events.append(event)

                elif action.op == "EXECUTE":
                    # 체이닝 대상 ActionType ID를 기록
                    result.chained_actions.append(action.action_id)

                    # 순환 참조 방지: 이미 실행된 룰이면 건너뜀
                    if action.action_id in executed_rule_ids:
                        logger.warning(
                            "gwt_cycle_detected",
                            rule_id=rule.id,
                            chained_action_id=action.action_id,
                            depth=depth,
                        )
                        continue

                    # 체이닝 대상 ActionType을 Neo4j에서 로드하여 재귀 실행
                    chained_rule = await self._load_chained_rule(
                        action.action_id, ctx.case_id, ctx.tenant_id,
                    )
                    if chained_rule is None:
                        logger.warning(
                            "gwt_chained_rule_not_found",
                            rule_id=rule.id,
                            chained_action_id=action.action_id,
                        )
                        continue

                    # 재귀적으로 체이닝된 룰 실행 (depth+1)
                    chained_result = await self.execute_then(
                        chained_rule, ctx,
                        depth=depth + 1,
                        executed_rule_ids=executed_rule_ids,
                    )

                    # 체이닝 결과를 현재 결과에 병합
                    result.state_changes.extend(chained_result.state_changes)
                    result.emitted_events.extend(chained_result.emitted_events)
                    result.chained_actions.extend(chained_result.chained_actions)

                    # 체이닝된 룰에서 에러 발생 시 전파
                    if chained_result.error:
                        result.error = (
                            f"체이닝된 룰 {action.action_id} 에러: "
                            f"{chained_result.error}"
                        )
                        break

                elif action.op == "CREATE_RELATION":
                    if not self._dry_run:
                        await self._execute_create_relation(action, ctx)

                elif action.op == "DELETE_RELATION":
                    if not self._dry_run:
                        await self._execute_delete_relation(action, ctx)

            except Exception as exc:
                result.error = f"액션 {action.op} 실행 실패: {exc}"
                logger.error(
                    "gwt_action_execution_failed",
                    rule_id=rule.id,
                    action_op=action.op,
                    error=str(exc),
                    exc_info=True,
                )
                break  # 액션 시퀀스 중단

        return result

    async def _load_chained_rule(
        self,
        action_id: str,
        case_id: str,
        tenant_id: str,
    ) -> GWTRule | None:
        """EXECUTE 체이닝 대상 ActionType을 Neo4j에서 로드하여 GWTRule로 변환.

        action_id로 조회하며, 비활성 룰도 체이닝 대상에서 제외한다.
        tenant_id 필터로 크로스 테넌트 접근을 방지한다.
        """
        query = """
        MATCH (a:ActionType {id: $action_id, tenant_id: $tenant_id, enabled: true})
        RETURN a
        """
        try:
            records = await self._neo4j.execute_read(query, {
                "action_id": action_id,
                "tenant_id": tenant_id,
            })
            if not records:
                return None
            return self._parse_rule(records[0]["a"])
        except Exception as exc:
            logger.error(
                "gwt_chained_rule_load_failed",
                action_id=action_id,
                error=str(exc),
            )
            return None

    # ── 메인 진입점 ──────────────────────────────────────────

    async def handle_event(
        self,
        event_type: str,
        aggregate_id: str,
        payload: dict,
        case_id: str,
        tenant_id: str,
    ) -> list[GWTExecutionResult]:
        """이벤트 하나를 처리하는 메인 진입점

        처리 흐름:
        1. 매칭 룰 로드 (Neo4j에서 case+tenant+event_type으로 조회)
        2. 컨텍스트 구성 (관련 노드 상태를 Neo4j에서 일괄 조회)
        3. 각 룰의 화이트리스트 검증 → Given 평가 → Then 실행
        4. 발행된 이벤트를 EventOutbox에 저장 (dry_run이 아닌 경우)
        """
        rules = await self.load_rules(case_id, tenant_id, event_type)
        if not rules:
            return []

        # 평가 컨텍스트 구성
        ctx = GWTEvalContext(
            event_type=event_type,
            aggregate_id=aggregate_id,
            source_node_id=payload.get("source_node_id", ""),
            payload=payload,
            case_id=case_id,
            tenant_id=tenant_id,
        )

        # 관련 노드 상태를 Neo4j에서 한 번에 일괄 조회
        await self._load_context_states(ctx, rules)

        results: list[GWTExecutionResult] = []
        for rule in rules:
            # 모든 조건/액션의 화이트리스트 검증 (Cypher 인젝션 방지)
            try:
                for cond in rule.given:
                    cond.validate()
                for action in rule.then:
                    action.validate()
            except ValueError as exc:
                logger.error(
                    "gwt_rule_validation_failed",
                    rule_id=rule.id,
                    error=str(exc),
                )
                continue  # 검증 실패한 룰은 건너뜀

            # Given 조건 평가 → 매칭되면 Then 실행
            if await self.evaluate_given(rule, ctx):
                exec_result = await self.execute_then(rule, ctx)
                results.append(exec_result)

                # dry_run 모드에서는 이벤트 발행 건너뜀
                if self._dry_run:
                    continue

                # 발행된 이벤트를 Synapse EventOutbox에 저장
                for event in exec_result.emitted_events:
                    await self._publisher.publish(
                        event_type=event["event_type"],
                        aggregate_type="ActionType",
                        aggregate_id=rule.id,
                        payload=event["payload"],
                        tenant_id=tenant_id,
                    )

        return results

    # ── 내부 메서드: 조건 평가 ────────────────────────────────

    async def _eval_state_condition(
        self,
        cond: GWTCondition,
        ctx: GWTEvalContext,
    ) -> bool:
        """노드 상태 조건 평가 — Cypher 조회 결과를 비교

        cond.validate()가 이미 호출되어 node_layer, field가 화이트리스트 검증됨.
        라벨은 ALLOWED_LABELS, 필드명은 _ALNUM_UNDERSCORE로 검증 완료.
        파라미터화된 Cypher 사용 ($case_id, $node_id).
        """
        # 검증된 값만 Cypher 문자열에 삽입 (validate()에서 이미 확인됨)
        label = cond.node_layer.capitalize()
        field_name = cond.field

        query = f"""
        MATCH (n:{label} {{case_id: $case_id}})
        WHERE n.node_id = $node_id
        RETURN n.{field_name} AS val
        """

        # $trigger.xxx 형태의 동적 참조 해석
        node_id = self._resolve_ref(
            cond.value if isinstance(cond.value, str) and cond.value.startswith("$") else "",
            ctx,
        ) or ctx.source_node_id

        records = await self._neo4j.execute_read(query, {
            "case_id": ctx.case_id,
            "node_id": node_id,
        })
        if not records:
            return False

        actual = records[0]["val"]
        # cond.value가 $참조인 경우 실제 값으로 해석한 뒤 비교
        expected = (
            self._resolve_ref(cond.value, ctx)
            if isinstance(cond.value, str) and cond.value.startswith("$")
            else cond.value
        )
        return self._compare(actual, cond.op, expected)

    async def _eval_relation_condition(
        self,
        cond: GWTCondition,
        ctx: GWTEvalContext,
    ) -> bool:
        """관계 조건 평가 — 관계의 존재 여부 + 속성 비교

        라벨/관계/필드 모두 validate()로 화이트리스트 검증 완료 상태.
        """
        src_label = cond.source_layer.capitalize()
        tgt_label = cond.target_layer.capitalize()
        rel_type = cond.rel_type
        field_name = cond.field

        query = f"""
        MATCH (a:{src_label} {{case_id: $case_id}})
              -[r:{rel_type}]->
              (b:{tgt_label} {{case_id: $case_id}})
        WHERE a.node_id = $source_id
        RETURN b.{field_name} AS val
        """

        records = await self._neo4j.execute_read(query, {
            "case_id": ctx.case_id,
            "source_id": ctx.source_node_id,
        })
        if not records:
            return False

        actual = records[0]["val"]
        return self._compare(actual, cond.op, cond.value)

    def _eval_expression(
        self,
        cond: GWTCondition,
        ctx: GWTEvalContext,
    ) -> bool:
        """AST 기반 안전한 표현식 평가 — eval() 사용 금지

        허용 변수: state(노드 상태), payload(이벤트 페이로드), trigger(트리거 정보)
        허용 연산: 비교, 논리, 산술, 속성/인덱스 접근
        금지: 함수 호출, import, lambda 등 모든 위험 구문
        """
        variables = {
            "state": ctx.node_states,
            "payload": ctx.payload,
            "trigger": {
                "event_type": ctx.event_type,
                "aggregate_id": ctx.aggregate_id,
                "source_node_id": ctx.source_node_id,
            },
        }
        try:
            return bool(safe_eval(cond.value, variables))
        except Exception as exc:
            logger.warning(
                "gwt_expression_eval_failed",
                expression=cond.value,
                error=str(exc),
            )
            return False

    # ── 내부 메서드: 액션 실행 ────────────────────────────────

    async def _handle_set_action(
        self,
        action: GWTAction,
        ctx: GWTEvalContext,
    ) -> dict:
        """SET 액션 처리 — dry_run 분기 포함

        dry_run 모드에서는 Neo4j 쓰기 없이 예상 변경 결과만 계산한다.
        """
        if self._dry_run:
            # 시뮬레이션: Neo4j 쓰기 없이 결과만 계산
            resolved_id = self._resolve_ref(action.target_node, ctx)
            return {
                "node_id": resolved_id,
                "field": action.field,
                "old_value": ctx.node_states.get(resolved_id, {}).get(action.field),
                "new_value": action.value,
            }
        return await self._execute_set(action, ctx)

    async def _execute_set(
        self,
        action: GWTAction,
        ctx: GWTEvalContext,
    ) -> dict:
        """노드 상태 변경 — Neo4j SET

        field명은 action.validate()로 _ALNUM_UNDERSCORE 검증 완료 상태.
        Neo4j 동적 속성 SET은 n[$field] 파라미터 패턴 사용 (인젝션 안전).
        """
        target_id = self._resolve_ref(action.target_node, ctx)

        query = """
        MATCH (n {case_id: $case_id})
        WHERE n.node_id = $node_id OR n.id = $node_id
        SET n[$field] = $value, n.updated_at = datetime()
        RETURN n.node_id AS updated_id
        """
        await self._neo4j.execute_write(query, {
            "case_id": ctx.case_id,
            "node_id": target_id,
            "field": action.field,
            "value": action.value,
        })

        return {
            "node_id": target_id,
            "field": action.field,
            "old_value": ctx.node_states.get(target_id, {}).get(action.field),
            "new_value": action.value,
        }

    async def _execute_create_relation(
        self,
        action: GWTAction,
        ctx: GWTEvalContext,
    ) -> None:
        """관계 생성 액션 — params에서 source/target/type 추출

        params 구조:
        {
            "source_node_id": "node-001",
            "target_node_id": "node-002",
            "rel_type": "TRIGGERS",
            "properties": {"weight": 0.8}
        }
        """
        params = action.params
        rel_type = params.get("rel_type", "RELATED_TO")
        # 관계 타입 화이트리스트 검증
        if rel_type not in ALLOWED_REL_TYPES_KINETIC:
            raise ValueError(f"허용되지 않는 rel_type: {rel_type}")

        source_id = self._resolve_ref(
            params.get("source_node_id", ""), ctx,
        )
        target_id = self._resolve_ref(
            params.get("target_node_id", ""), ctx,
        )
        properties = params.get("properties", {})
        rel_id = f"rel-gwt-{uuid.uuid4().hex[:8]}"

        query = f"""
        MATCH (a {{case_id: $case_id}})
        WHERE a.node_id = $source_id OR a.id = $source_id
        MATCH (b {{case_id: $case_id}})
        WHERE b.node_id = $target_id OR b.id = $target_id
        MERGE (a)-[r:{rel_type} {{id: $rel_id}}]->(b)
        SET r += $properties
        """
        await self._neo4j.execute_write(query, {
            "case_id": ctx.case_id,
            "source_id": source_id,
            "target_id": target_id,
            "rel_id": rel_id,
            "properties": properties,
        })

    async def _execute_delete_relation(
        self,
        action: GWTAction,
        ctx: GWTEvalContext,
    ) -> None:
        """관계 삭제 액션 — params에서 relation_id 추출"""
        rel_id = action.params.get("relation_id", "")
        if not rel_id:
            raise ValueError("DELETE_RELATION에 relation_id가 필요합니다")

        query = """
        MATCH ()-[r {id: $rel_id}]-()
        DELETE r
        """
        await self._neo4j.execute_write(query, {"rel_id": rel_id})

    # ── 내부 메서드: 유틸리티 ────────────────────────────────

    def _build_event(
        self,
        action: GWTAction,
        ctx: GWTEvalContext,
    ) -> dict:
        """이벤트 페이로드 구성 — $trigger.xxx, $payload.xxx 등의 변수 치환 포함"""
        resolved_payload: dict[str, Any] = {}
        for k, v in action.payload.items():
            if isinstance(v, str) and v.startswith("$"):
                resolved_payload[k] = self._resolve_ref(v, ctx)
            else:
                resolved_payload[k] = v

        return {
            "event_type": action.event_type,
            "payload": {
                **resolved_payload,
                "case_id": ctx.case_id,
                "tenant_id": ctx.tenant_id,
                "triggered_by_rule": ctx.event_type,
                "source_worker": "gwt-engine",
            },
        }

    # $trigger.xxx 참조 시 허용되는 속성 화이트리스트 (임의 속성 접근 방지)
    _ALLOWED_TRIGGER_ATTRS = {"source_node_id", "aggregate_id", "event_type", "case_id", "tenant_id"}

    def _resolve_ref(self, ref: str, ctx: GWTEvalContext) -> Any:
        """$trigger.xxx, $payload.xxx 등의 변수 참조를 실제 값으로 해석

        지원 패턴:
        - $trigger.source_node_id → ctx.source_node_id
        - $trigger.aggregate_id → ctx.aggregate_id
        - $payload.order_id → ctx.payload["order_id"]
        - 그 외: 원본 문자열 반환

        ⚠️ 보안: $trigger 참조는 _ALLOWED_TRIGGER_ATTRS 화이트리스트로 제한
        """
        if not ref or not ref.startswith("$"):
            return ref

        parts = ref[1:].split(".")

        if parts[0] == "trigger":
            if len(parts) > 1:
                if parts[1] not in self._ALLOWED_TRIGGER_ATTRS:
                    raise ValueError(
                        f"허용되지 않는 trigger 속성: {parts[1]}. "
                        f"허용: {self._ALLOWED_TRIGGER_ATTRS}"
                    )
                return getattr(ctx, parts[1], ref)
            return ctx.aggregate_id

        if parts[0] == "payload":
            if len(parts) > 1:
                return ctx.payload.get(parts[1], ref)
            return ctx.payload

        return ref

    @staticmethod
    def _compare(actual: Any, op: str, expected: Any) -> bool:
        """비교 연산자 평가 — 온톨로지 필드 값과 룰 조건 값 비교

        지원 연산자: ==, !=, >, <, >=, <=, in, not_in, contains
        """
        if op == "==":
            return actual == expected
        if op == "!=":
            return actual != expected
        if op == ">":
            return actual > expected
        if op == "<":
            return actual < expected
        if op == ">=":
            return actual >= expected
        if op == "<=":
            return actual <= expected
        if op == "in":
            return actual in expected
        if op == "not_in":
            return actual not in expected
        if op == "contains":
            return expected in str(actual)
        return False

    def _parse_rule(self, node: dict) -> GWTRule:
        """Neo4j ActionType 노드 → GWTRule 데이터클래스 변환

        given_conditions, then_actions는 JSON 문자열로 저장되므로
        파싱하여 GWTCondition/GWTAction 인스턴스 목록으로 변환한다.
        """
        return GWTRule(
            id=node["id"],
            name=node["name"],
            case_id=node["case_id"],
            tenant_id=node["tenant_id"],
            given=[
                GWTCondition(**c)
                for c in json.loads(node.get("given_conditions", "[]"))
            ],
            when_event=node["when_event"],
            then=[
                GWTAction(**a)
                for a in json.loads(node.get("then_actions", "[]"))
            ],
            enabled=node.get("enabled", True),
            priority=node.get("priority", 100),
            version=node.get("version", 1),
        )

    async def _load_context_states(
        self,
        ctx: GWTEvalContext,
        rules: list[GWTRule],
    ) -> None:
        """룰에서 참조하는 노드의 현재 상태를 선택적으로 조회 (성능 최적화)

        이전 구현은 각 계층의 모든 노드를 로드했으나, 이제는 룰 조건에서
        참조되는 node_id만 수집하여 WHERE n.node_id IN $node_ids 필터로
        필요한 노드만 조회한다. 대규모 온톨로지에서 쿼리 성능이 크게 향상된다.

        참조 node_id 수집 소스:
        - ctx.source_node_id: 이벤트 발생 노드
        - $trigger.source_node_id 등 조건 값의 $trigger 참조
        - 조건의 value 필드 중 문자열로 된 노드 ID 후보
        """
        # 레이어별로 참조되는 node_id를 수집
        layer_node_ids: dict[str, set[str]] = {}  # {layer: {node_id, ...}}

        for rule in rules:
            for cond in rule.given:
                # 대상 레이어 수집
                target_layers: list[str] = []
                if cond.node_layer:
                    target_layers.append(cond.node_layer)
                if cond.source_layer:
                    target_layers.append(cond.source_layer)
                if cond.target_layer:
                    target_layers.append(cond.target_layer)

                # 조건에서 참조하는 node_id 수집
                referenced_ids: set[str] = set()

                # 이벤트 발생 노드는 항상 포함
                if ctx.source_node_id:
                    referenced_ids.add(ctx.source_node_id)

                # $trigger.* 참조에서 실제 값 추출
                if isinstance(cond.value, str) and cond.value.startswith("$trigger."):
                    resolved = self._resolve_ref(cond.value, ctx)
                    if isinstance(resolved, str) and resolved:
                        referenced_ids.add(resolved)

                # then 액션의 target_node에서도 node_id 수집
                for action in rule.then:
                    if action.target_node:
                        if action.target_node.startswith("$trigger."):
                            resolved = self._resolve_ref(action.target_node, ctx)
                            if isinstance(resolved, str) and resolved:
                                referenced_ids.add(resolved)
                        elif action.target_node.startswith("$"):
                            pass  # 다른 변수 참조는 무시
                        else:
                            referenced_ids.add(action.target_node)

                # 수집된 node_id를 각 레이어에 등록
                for layer in target_layers:
                    if layer not in layer_node_ids:
                        layer_node_ids[layer] = set()
                    layer_node_ids[layer].update(referenced_ids)

        # 각 레이어별로 필요한 노드만 조회
        for layer, node_ids in layer_node_ids.items():
            label = layer.capitalize()
            # 라벨 화이트리스트 검증 후에만 f-string 삽입
            if label not in ALLOWED_LABELS:
                logger.warning(
                    "gwt_invalid_layer_ignored",
                    layer=layer,
                )
                continue

            if node_ids:
                # 참조된 node_id만 선택적으로 조회 (성능 최적화)
                query = f"""
                MATCH (n:{label} {{case_id: $case_id}})
                WHERE n.node_id IN $node_ids
                RETURN n.node_id AS id, properties(n) AS props
                """
                records = await self._neo4j.execute_read(query, {
                    "case_id": ctx.case_id,
                    "node_ids": list(node_ids),
                })
            else:
                # node_id를 특정할 수 없는 경우 전체 조회 (폴백)
                query = f"""
                MATCH (n:{label} {{case_id: $case_id}})
                RETURN n.node_id AS id, properties(n) AS props
                """
                records = await self._neo4j.execute_read(query, {
                    "case_id": ctx.case_id,
                })

            for rec in records:
                if rec.get("id"):
                    ctx.node_states[rec["id"]] = rec["props"]


# ═══════════════════════════════════════════════════════════════
# GWT 룰 CRUD 관리자
# ═══════════════════════════════════════════════════════════════


class GWTRuleManager:
    """GWT 룰 CRUD 관리자 — ActionType 노드의 생성/수정/삭제/조회

    프론트엔드의 도메인 모델러에서 호출된다.
    모든 쿼리는 파라미터화되어 Cypher 인젝션을 방지한다.
    """

    # link_to_ontology에서 허용되는 관계 타입
    ALLOWED_LINK_REL_TYPES = {"TRIGGERS", "MODIFIES", "CHAINS_TO", "USES_MODEL"}

    def __init__(self, neo4j_client: Any):
        """
        Args:
            neo4j_client: Neo4jClient (execute_read/execute_write 메서드 보유)
        """
        self._neo4j = neo4j_client

    async def create_rule(self, rule: GWTRule) -> str:
        """새 ActionType 노드를 Neo4j에 생성

        GWTRule의 given/then은 JSON 문자열로 직렬화되어 저장된다.
        생성된 노드의 ID를 반환한다.
        """
        query = """
        CREATE (a:ActionType {
          id: $id,
          case_id: $case_id,
          tenant_id: $tenant_id,
          name: $name,
          description: $description,
          layer: "kinetic",
          enabled: $enabled,
          priority: $priority,
          version: $version,
          given_conditions: $given_conditions,
          when_event: $when_event,
          then_actions: $then_actions,
          created_at: datetime(),
          updated_at: datetime()
        })
        RETURN a.id AS id
        """

        # GWTCondition/GWTAction를 JSON 직렬화
        given_json = json.dumps(
            [
                {k: v for k, v in c.__dict__.items() if v is not None and v != "" and v != {}}
                for c in rule.given
            ],
            ensure_ascii=False,
        )
        then_json = json.dumps(
            [
                {k: v for k, v in a.__dict__.items() if v is not None and v != "" and v != {}}
                for a in rule.then
            ],
            ensure_ascii=False,
        )

        records = await self._neo4j.execute_write(query, {
            "id": rule.id,
            "case_id": rule.case_id,
            "tenant_id": rule.tenant_id,
            "name": rule.name,
            "description": "",
            "enabled": rule.enabled,
            "priority": rule.priority,
            "version": rule.version,
            "given_conditions": given_json,
            "when_event": rule.when_event,
            "then_actions": then_json,
        })
        return records[0]["id"]

    async def list_rules(
        self,
        case_id: str,
        tenant_id: str,
        enabled_only: bool = False,
    ) -> list[dict]:
        """해당 case의 모든 ActionType 노드 조회

        enabled_only=True이면 활성화된 룰만 반환한다.
        priority 내림차순, name 오름차순으로 정렬된다.
        """
        # enabled_only 조건은 정적 문자열이므로 인젝션 위험 없음
        where_clause = "AND a.enabled = true" if enabled_only else ""
        query = f"""
        MATCH (a:ActionType {{case_id: $case_id, tenant_id: $tenant_id}})
        {where_clause}
        RETURN a
        ORDER BY a.priority DESC, a.name
        """
        records = await self._neo4j.execute_read(query, {
            "case_id": case_id,
            "tenant_id": tenant_id,
        })
        return [dict(r["a"]) for r in records]

    async def update_rule(self, rule_id: str, updates: dict) -> bool:
        """ActionType 업데이트 (부분 수정)

        ALLOWED_UPDATE_FIELDS 화이트리스트로 허용된 필드만 수정 가능.
        허용되지 않는 필드가 포함되면 ValueError 발생.
        업데이트 시 version이 자동으로 1 증가하고 updated_at이 갱신된다.
        """
        # 허용되지 않는 필드 차단
        invalid_keys = set(updates.keys()) - ALLOWED_UPDATE_FIELDS
        if invalid_keys:
            raise ValueError(f"허용되지 않는 업데이트 필드: {invalid_keys}")

        if not updates:
            return False

        # 모든 키가 ALLOWED_UPDATE_FIELDS에 속하므로 f-string 삽입 안전
        set_clauses = ", ".join(f"a.{k} = ${k}" for k in updates.keys())
        query = f"""
        MATCH (a:ActionType {{id: $rule_id}})
        SET {set_clauses}, a.updated_at = datetime(), a.version = a.version + 1
        RETURN a.id AS id
        """
        records = await self._neo4j.execute_write(query, {
            "rule_id": rule_id,
            **updates,
        })
        return len(records) > 0

    async def delete_rule(self, rule_id: str) -> bool:
        """ActionType 삭제 (연결된 관계 포함 DETACH DELETE)"""
        query = """
        MATCH (a:ActionType {id: $rule_id})
        DETACH DELETE a
        RETURN count(*) AS deleted
        """
        records = await self._neo4j.execute_write(query, {"rule_id": rule_id})
        return records[0]["deleted"] > 0

    async def link_to_ontology(
        self,
        rule_id: str,
        node_id: str,
        rel_type: str = "TRIGGERS",
    ) -> None:
        """ActionType과 온톨로지 노드 간 관계 생성

        rel_type별로 방향이 다르다:
        - TRIGGERS: (OntologyNode)-[:TRIGGERS]->(ActionType) — 노드가 액션을 트리거
        - MODIFIES: (ActionType)-[:MODIFIES]->(OntologyNode) — 액션이 노드를 수정
        - CHAINS_TO: (ActionType)-[:CHAINS_TO]->(ActionType) — 액션 간 체이닝
        - USES_MODEL: (ActionType)-[:USES_MODEL]->(BehaviorModel) — ML 모델 연결

        라벨 제한 쿼리로 전체 노드 스캔을 방지한다.
        """
        if rel_type not in self.ALLOWED_LINK_REL_TYPES:
            raise ValueError(
                f"허용되지 않는 link rel_type: {rel_type}. "
                f"허용: {self.ALLOWED_LINK_REL_TYPES}"
            )

        # 관계 타입별로 방향과 대상 노드 라벨이 다르므로 분기 처리
        if rel_type == "TRIGGERS":
            # 온톨로지 노드 → ActionType (노드가 액션을 트리거)
            query = """
            MATCH (n)
            WHERE n.node_id = $node_id
              AND (n:Kpi OR n:Driver OR n:Measure OR n:Process OR n:Resource)
            MATCH (a:ActionType {id: $rule_id})
            MERGE (n)-[:TRIGGERS]->(a)
            """
        elif rel_type == "MODIFIES":
            # ActionType → 온톨로지 노드 (액션이 노드를 수정)
            query = """
            MATCH (a:ActionType {id: $rule_id})
            MATCH (n)
            WHERE n.node_id = $node_id
              AND (n:Kpi OR n:Driver OR n:Measure OR n:Process OR n:Resource)
            MERGE (a)-[:MODIFIES]->(n)
            """
        elif rel_type == "CHAINS_TO":
            # ActionType → ActionType (액션 간 체이닝)
            query = """
            MATCH (a:ActionType {id: $rule_id})
            MATCH (b:ActionType {id: $node_id})
            MERGE (a)-[:CHAINS_TO]->(b)
            """
        elif rel_type == "USES_MODEL":
            # ActionType → BehaviorModel (ML 모델 연결)
            query = """
            MATCH (a:ActionType {id: $rule_id})
            MATCH (m:OntologyBehavior {model_id: $node_id})
            MERGE (a)-[:USES_MODEL]->(m)
            """
        else:
            # ALLOWED_LINK_REL_TYPES 검증을 통과했지만 분기에 없는 경우 (방어적)
            raise ValueError(f"처리되지 않는 rel_type: {rel_type}")

        await self._neo4j.execute_write(query, {
            "rule_id": rule_id,
            "node_id": node_id,
        })
