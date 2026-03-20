"""
GWT Engine 단위 테스트 — Kinetic Layer Phase 1

테스트 대상:
  1. safe_eval: AST 기반 안전한 표현식 평가기 (~15 tests)
  2. GWTCondition.validate(): 조건 화이트리스트 검증 (~8 tests)
  3. GWTAction.validate(): 액션 필드명 검증 (~4 tests)
  4. GWTEngine: 룰 로딩/평가/실행 엔진 (~10 tests)
  5. GWTRuleManager: 룰 CRUD 관리자 (~6 tests)

모든 외부 의존성(Neo4j, Redis, EventPublisher)은 mock으로 대체한다.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.gwt_engine import (
    ALLOWED_LABELS,
    ALLOWED_REL_TYPES_KINETIC,
    ALLOWED_UPDATE_FIELDS,
    GWTAction,
    GWTCondition,
    GWTEngine,
    GWTEvalContext,
    GWTExecutionResult,
    GWTRule,
    GWTRuleManager,
    safe_eval,
)


# ═══════════════════════════════════════════════════════════════
# 1. safe_eval 테스트 (~15 tests)
# ═══════════════════════════════════════════════════════════════


class TestSafeEval:
    """AST 기반 안전한 표현식 평가기 테스트"""

    # ── 기본 비교 연산 ──

    def test_constant_equality(self):
        """상수 비교: 1 == 1 → True"""
        assert safe_eval("1 == 1", {}) is True

    def test_constant_inequality(self):
        """상수 불일치: 1 == 2 → False"""
        assert safe_eval("1 == 2", {}) is False

    def test_variable_greater_than(self):
        """변수 비교: x > 5 (x=10) → True"""
        assert safe_eval("x > 5", {"x": 10}) is True

    def test_variable_greater_than_false(self):
        """변수 비교: x > 5 (x=3) → False"""
        assert safe_eval("x > 5", {"x": 3}) is False

    def test_less_than_or_equal(self):
        """변수 비교: x <= 5 (x=5) → True"""
        assert safe_eval("x <= 5", {"x": 5}) is True

    def test_not_equal(self):
        """변수 비교: x != 0 (x=1) → True"""
        assert safe_eval("x != 0", {"x": 1}) is True

    # ── Boolean 논리 ──

    def test_boolean_and(self):
        """AND 논리: x > 0 and y < 10 → True"""
        assert safe_eval("x > 0 and y < 10", {"x": 5, "y": 3}) is True

    def test_boolean_and_false(self):
        """AND 논리 하나 실패: x > 0 and y < 10 (y=15) → False"""
        assert safe_eval("x > 0 and y < 10", {"x": 5, "y": 15}) is False

    def test_boolean_or(self):
        """OR 논리: a or b → True (a=True, b=False)"""
        assert safe_eval("a or b", {"a": True, "b": False}) is True

    def test_boolean_or_both_false(self):
        """OR 논리 둘 다 실패: a or b → False"""
        assert safe_eval("a or b", {"a": False, "b": False}) is False

    def test_not_operator(self):
        """NOT 단항 연산자: not x → True (x=False)"""
        assert safe_eval("not x", {"x": False}) is True

    # ── 속성/인덱스 접근 ──

    def test_attribute_access(self):
        """속성 접근: state.status == 'PENDING'"""
        result = safe_eval(
            "state.status == 'PENDING'",
            {"state": {"status": "PENDING"}},
        )
        assert result is True

    def test_subscript_access(self):
        """인덱스 접근: state["name"] == "test" """
        result = safe_eval(
            'state["name"] == "test"',
            {"state": {"name": "test"}},
        )
        assert result is True

    def test_list_subscript_access(self):
        """리스트 인덱스 접근: items[0] == 'a'"""
        result = safe_eval(
            "items[0] == 'a'",
            {"items": ["a", "b", "c"]},
        )
        assert result is True

    # ── 산술 연산 ──

    def test_arithmetic_addition(self):
        """산술: x + y > 10 (x=7, y=5) → True"""
        assert safe_eval("x + y > 10", {"x": 7, "y": 5}) is True

    def test_arithmetic_multiplication(self):
        """산술: price * quantity == 500"""
        result = safe_eval(
            "price * quantity == 500",
            {"price": 50, "quantity": 10},
        )
        assert result is True

    def test_arithmetic_modulo(self):
        """산술: x % 2 == 0 (짝수 검사)"""
        assert safe_eval("x % 2 == 0", {"x": 4}) is True

    def test_unary_minus(self):
        """단항 마이너스: -x < 0 (x=5)"""
        assert safe_eval("-x < 0", {"x": 5}) is True

    # ── 복합 표현식 ──

    def test_nested_attribute_and_payload(self):
        """중첩 표현식: state.count > 0 and payload.type == 'order'"""
        result = safe_eval(
            "state.count > 0 and payload.type == 'order'",
            {
                "state": {"count": 3},
                "payload": {"type": "order"},
            },
        )
        assert result is True

    def test_chained_comparison(self):
        """체인 비교: 0 < x < 10 (Python 체인 비교 지원)"""
        # ast.Compare에서 체인 비교를 처리하는지 확인
        assert safe_eval("0 < x < 10", {"x": 5}) is True
        assert safe_eval("0 < x < 10", {"x": 15}) is False

    # ── 보안: 금지된 표현식 차단 ──

    def test_security_import_blocked(self):
        """보안: __import__('os') 호출 차단 → ValueError"""
        with pytest.raises(ValueError, match="허용되지 않는 표현식 노드"):
            safe_eval("__import__('os').system('ls')", {})

    def test_security_class_introspection_blocked(self):
        """보안: ().__class__.__bases__ 체인 차단 → ValueError"""
        with pytest.raises(ValueError, match="허용되지 않는 표현식 노드"):
            safe_eval("().__class__.__bases__[0].__subclasses__()", {})

    def test_security_function_call_blocked(self):
        """보안: len([1,2,3]) 함수 호출 차단 → ValueError"""
        with pytest.raises(ValueError, match="허용되지 않는 표현식 노드"):
            safe_eval("len([1,2,3])", {})

    def test_security_eval_blocked(self):
        """보안: eval() 호출 차단 → ValueError"""
        with pytest.raises(ValueError, match="허용되지 않는 표현식 노드"):
            safe_eval("eval('1+1')", {})

    def test_security_lambda_blocked(self):
        """보안: lambda 표현식 차단 → ValueError"""
        with pytest.raises(ValueError, match="허용되지 않는 표현식 노드"):
            safe_eval("(lambda: 1)()", {})

    # ── 에지 케이스 ──

    def test_empty_string_raises(self):
        """빈 문자열 → SyntaxError (ast.parse 실패)"""
        with pytest.raises(SyntaxError):
            safe_eval("", {})

    def test_none_expression_raises(self):
        """None 입력 → TypeError (ast.parse에 None 전달 불가)"""
        with pytest.raises(TypeError):
            safe_eval(None, {})  # type: ignore

    def test_undefined_variable_raises(self):
        """정의되지 않은 변수 참조 → ValueError"""
        with pytest.raises(ValueError, match="알 수 없는 변수"):
            safe_eval("unknown_var > 0", {})

    def test_attribute_on_non_dict_raises(self):
        """dict가 아닌 객체에 속성 접근 → ValueError"""
        with pytest.raises(ValueError, match="속성 접근 불가"):
            safe_eval("x.name", {"x": 42})

    def test_in_operator(self):
        """in 연산자: 'a' in items"""
        result = safe_eval("x in items", {"x": "a", "items": ["a", "b"]})
        assert result is True

    def test_not_in_operator(self):
        """not in 연산자: 'c' not in items"""
        result = safe_eval("x not in items", {"x": "c", "items": ["a", "b"]})
        assert result is True

    def test_string_equality(self):
        """문자열 상수 비교: name == 'hello'"""
        assert safe_eval("name == 'hello'", {"name": "hello"}) is True

    def test_none_constant(self):
        """None 상수 비교: x == None"""
        assert safe_eval("x == None", {"x": None}) is True

    def test_boolean_constant(self):
        """bool 상수 비교: flag == True"""
        assert safe_eval("flag == True", {"flag": True}) is True


# ═══════════════════════════════════════════════════════════════
# 2. GWTCondition.validate() 테스트 (~8 tests)
# ═══════════════════════════════════════════════════════════════


class TestGWTConditionValidate:
    """GWTCondition 화이트리스트 검증 테스트"""

    def test_valid_state_condition(self):
        """유효한 state 조건 — node_layer='Kpi', field='status'"""
        cond = GWTCondition(type="state", node_layer="Kpi", field="status", op="==", value="ACTIVE")
        cond.validate()  # ValueError 없으면 통과

    def test_valid_state_condition_lowercase_layer(self):
        """소문자 계층도 capitalize()로 매칭 — 'kpi' → 'Kpi'"""
        cond = GWTCondition(type="state", node_layer="kpi", field="name")
        cond.validate()

    def test_invalid_node_layer_raises(self):
        """허용되지 않는 node_layer → ValueError"""
        cond = GWTCondition(type="state", node_layer="HackerNode", field="status")
        with pytest.raises(ValueError, match="허용되지 않는 node_layer"):
            cond.validate()

    def test_invalid_field_with_injection(self):
        """SQL/Cypher 인젝션 시도 필드명 → ValueError"""
        cond = GWTCondition(type="state", node_layer="Kpi", field="status} RETURN 1 //")
        with pytest.raises(ValueError, match="허용되지 않는 field 이름"):
            cond.validate()

    def test_field_with_special_chars_rejected(self):
        """특수문자 포함 필드명 → ValueError"""
        cond = GWTCondition(type="state", node_layer="Process", field="na-me")
        with pytest.raises(ValueError, match="허용되지 않는 field 이름"):
            cond.validate()

    def test_invalid_rel_type_raises(self):
        """허용되지 않는 rel_type → ValueError"""
        cond = GWTCondition(
            type="relation",
            source_layer="Kpi",
            target_layer="Measure",
            rel_type="HACK_RELATION",
            field="weight",
        )
        with pytest.raises(ValueError, match="허용되지 않는 rel_type"):
            cond.validate()

    def test_valid_relation_condition(self):
        """유효한 relation 조건 — TRIGGERS 관계"""
        cond = GWTCondition(
            type="relation",
            source_layer="Process",
            target_layer="Resource",
            rel_type="TRIGGERS",
            field="weight",
        )
        cond.validate()  # ValueError 없으면 통과

    def test_valid_relation_all_kinetic_rel_types(self):
        """Kinetic 전용 관계 타입이 모두 통과하는지 확인"""
        for rel in ["TRIGGERS", "MODIFIES", "CHAINS_TO", "USES_MODEL"]:
            cond = GWTCondition(
                type="relation",
                source_layer="Process",
                target_layer="Resource",
                rel_type=rel,
                field="status",
            )
            cond.validate()

    def test_empty_optional_fields_pass(self):
        """선택 필드가 비어있으면 검증 생략 — expression 타입"""
        cond = GWTCondition(type="expression", value="x > 0")
        cond.validate()  # node_layer, field, rel_type 모두 빈 문자열

    def test_invalid_source_layer_raises(self):
        """source_layer가 허용되지 않으면 ValueError"""
        cond = GWTCondition(
            type="relation",
            source_layer="BadLayer",
            target_layer="Kpi",
            rel_type="TRIGGERS",
        )
        with pytest.raises(ValueError, match="허용되지 않는 source_layer"):
            cond.validate()

    def test_invalid_target_layer_raises(self):
        """target_layer가 허용되지 않으면 ValueError"""
        cond = GWTCondition(
            type="relation",
            source_layer="Kpi",
            target_layer="BadLayer",
            rel_type="TRIGGERS",
        )
        with pytest.raises(ValueError, match="허용되지 않는 target_layer"):
            cond.validate()


# ═══════════════════════════════════════════════════════════════
# 3. GWTAction.validate() 테스트 (~4 tests)
# ═══════════════════════════════════════════════════════════════


class TestGWTActionValidate:
    """GWTAction 필드명 검증 테스트"""

    def test_valid_set_action(self):
        """유효한 SET 액션 — field='status'"""
        action = GWTAction(op="SET", target_node="node-1", field="status", value="COMPLETED")
        action.validate()  # ValueError 없으면 통과

    def test_valid_emit_action_no_field(self):
        """EMIT 액션은 field가 없으므로 검증 통과"""
        action = GWTAction(op="EMIT", event_type="ORDER_COMPLETED")
        action.validate()

    def test_invalid_field_raises(self):
        """인젝션 시도 field → ValueError"""
        action = GWTAction(op="SET", field="status} RETURN 1 //", value="hacked")
        with pytest.raises(ValueError, match="허용되지 않는 field 이름"):
            action.validate()

    def test_field_with_dot_rejected(self):
        """dot 포함 field → ValueError (nested 접근 시도 차단)"""
        action = GWTAction(op="SET", field="a.b", value="x")
        with pytest.raises(ValueError, match="허용되지 않는 field 이름"):
            action.validate()

    def test_underscore_field_accepted(self):
        """밑줄 포함 field → 통과 (예: last_updated)"""
        action = GWTAction(op="SET", field="last_updated", value="now")
        action.validate()


# ═══════════════════════════════════════════════════════════════
# 4. GWTEngine 테스트 (~10 tests) — mock 기반
# ═══════════════════════════════════════════════════════════════


def _make_engine(dry_run: bool = False) -> tuple[GWTEngine, AsyncMock, AsyncMock]:
    """테스트용 GWTEngine과 mock 의존성을 생성하는 헬퍼"""
    neo4j_mock = AsyncMock()
    publisher_mock = AsyncMock()
    engine = GWTEngine(neo4j_client=neo4j_mock, async_publisher=publisher_mock, dry_run=dry_run)
    return engine, neo4j_mock, publisher_mock


def _make_rule(
    rule_id: str = "rule-001",
    name: str = "테스트 룰",
    given: list[GWTCondition] | None = None,
    then: list[GWTAction] | None = None,
    when_event: str = "ORDER_PLACED",
) -> GWTRule:
    """테스트용 GWTRule 생성 헬퍼"""
    return GWTRule(
        id=rule_id,
        name=name,
        case_id="case-001",
        tenant_id="tenant-001",
        given=given or [],
        when_event=when_event,
        then=then or [],
    )


def _make_context(**overrides) -> GWTEvalContext:
    """테스트용 GWTEvalContext 생성 헬퍼"""
    defaults = {
        "event_type": "ORDER_PLACED",
        "aggregate_id": "agg-001",
        "source_node_id": "node-001",
        "payload": {"order_id": "ord-123", "source_node_id": "node-001"},
        "case_id": "case-001",
        "tenant_id": "tenant-001",
    }
    defaults.update(overrides)
    return GWTEvalContext(**defaults)


class TestGWTEngine:
    """GWT 룰 엔진 테스트"""

    @pytest.mark.asyncio
    async def test_load_rules_parses_neo4j_records(self):
        """load_rules: Neo4j에서 ActionType 노드를 조회하여 GWTRule로 파싱"""
        engine, neo4j_mock, _ = _make_engine()

        # Neo4j가 반환할 mock 레코드
        neo4j_mock.execute_read.return_value = [
            {
                "a": {
                    "id": "rule-001",
                    "name": "자동 승인 룰",
                    "case_id": "case-001",
                    "tenant_id": "tenant-001",
                    "when_event": "ORDER_PLACED",
                    "given_conditions": json.dumps([
                        {"type": "state", "node_layer": "Process", "field": "status", "op": "==", "value": "PENDING"}
                    ]),
                    "then_actions": json.dumps([
                        {"op": "SET", "target_node": "$trigger.source_node_id", "field": "status", "value": "APPROVED"}
                    ]),
                    "enabled": True,
                    "priority": 100,
                    "version": 1,
                },
            },
        ]

        rules = await engine.load_rules("case-001", "tenant-001", "ORDER_PLACED")

        assert len(rules) == 1
        assert rules[0].id == "rule-001"
        assert rules[0].name == "자동 승인 룰"
        assert len(rules[0].given) == 1
        assert rules[0].given[0].type == "state"
        assert len(rules[0].then) == 1
        assert rules[0].then[0].op == "SET"

    @pytest.mark.asyncio
    async def test_evaluate_given_all_true(self):
        """evaluate_given: 모든 조건이 True이면 True 반환"""
        engine, neo4j_mock, _ = _make_engine()

        # _eval_state_condition이 True를 반환하도록 Neo4j mock 설정
        neo4j_mock.execute_read.return_value = [{"val": "PENDING"}]

        rule = _make_rule(
            given=[
                GWTCondition(type="state", node_layer="Process", field="status", op="==", value="PENDING"),
            ],
        )
        ctx = _make_context()

        result = await engine.evaluate_given(rule, ctx)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_given_one_false(self):
        """evaluate_given: 하나라도 False이면 False 반환 (AND 결합)"""
        engine, neo4j_mock, _ = _make_engine()

        # 첫 번째 조건: status가 PENDING이 아님 → False
        neo4j_mock.execute_read.return_value = [{"val": "COMPLETED"}]

        rule = _make_rule(
            given=[
                GWTCondition(type="state", node_layer="Process", field="status", op="==", value="PENDING"),
                GWTCondition(type="state", node_layer="Process", field="priority", op=">", value=5),
            ],
        )
        ctx = _make_context()

        result = await engine.evaluate_given(rule, ctx)
        assert result is False

    @pytest.mark.asyncio
    async def test_evaluate_given_expression_type(self):
        """evaluate_given: expression 타입 조건 평가"""
        engine, _, _ = _make_engine()

        rule = _make_rule(
            given=[
                GWTCondition(type="expression", value="payload.order_id == 'ord-123'"),
            ],
        )
        ctx = _make_context(payload={"order_id": "ord-123"})

        result = await engine.evaluate_given(rule, ctx)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_given_empty_conditions(self):
        """evaluate_given: 조건이 없으면 True 반환 (vacuous truth)"""
        engine, _, _ = _make_engine()
        rule = _make_rule(given=[])
        ctx = _make_context()

        result = await engine.evaluate_given(rule, ctx)
        assert result is True

    @pytest.mark.asyncio
    async def test_execute_then_builds_state_changes(self):
        """execute_then (normal mode): SET 액션이 Neo4j 쓰기를 수행하고 결과 기록"""
        engine, neo4j_mock, _ = _make_engine(dry_run=False)

        # _execute_set이 반환할 결과 mock
        neo4j_mock.execute_write.return_value = [{"updated_id": "node-001"}]

        rule = _make_rule(
            then=[
                GWTAction(op="SET", target_node="$trigger.source_node_id", field="status", value="APPROVED"),
            ],
        )
        ctx = _make_context()

        result = await engine.execute_then(rule, ctx)

        assert result.matched is True
        assert len(result.state_changes) == 1
        assert result.state_changes[0]["field"] == "status"
        assert result.state_changes[0]["new_value"] == "APPROVED"
        # Neo4j execute_write가 호출되었는지 확인
        neo4j_mock.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_then_dry_run_skips_neo4j_write(self):
        """execute_then (dry_run mode): Neo4j 쓰기 없이 예상 결과만 계산"""
        engine, neo4j_mock, _ = _make_engine(dry_run=True)

        rule = _make_rule(
            then=[
                GWTAction(op="SET", target_node="$trigger.source_node_id", field="status", value="APPROVED"),
            ],
        )
        ctx = _make_context()
        ctx.node_states["node-001"] = {"status": "PENDING"}

        result = await engine.execute_then(rule, ctx)

        assert result.matched is True
        assert len(result.state_changes) == 1
        assert result.state_changes[0]["old_value"] == "PENDING"
        assert result.state_changes[0]["new_value"] == "APPROVED"
        # dry_run에서는 Neo4j 쓰기가 호출되지 않아야 한다
        neo4j_mock.execute_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_then_emit_action(self):
        """execute_then: EMIT 액션이 이벤트를 emitted_events에 기록"""
        engine, _, _ = _make_engine()

        rule = _make_rule(
            then=[
                GWTAction(
                    op="EMIT",
                    event_type="ORDER_APPROVED",
                    payload={"order_id": "$payload.order_id"},
                ),
            ],
        )
        ctx = _make_context(payload={"order_id": "ord-123"})

        result = await engine.execute_then(rule, ctx)

        assert len(result.emitted_events) == 1
        assert result.emitted_events[0]["event_type"] == "ORDER_APPROVED"
        # $payload.order_id가 해석되었는지 확인
        assert result.emitted_events[0]["payload"]["order_id"] == "ord-123"

    @pytest.mark.asyncio
    async def test_execute_then_max_chain_depth_exceeded(self):
        """execute_then: MAX_CHAIN_DEPTH 초과 시 에러 반환 (무한 루프 방지)"""
        engine, _, _ = _make_engine()

        rule = _make_rule(
            then=[GWTAction(op="EXECUTE", action_id="rule-002")],
        )
        ctx = _make_context()

        # depth를 MAX_CHAIN_DEPTH로 설정하여 초과 트리거
        result = await engine.execute_then(rule, ctx, depth=GWTEngine.MAX_CHAIN_DEPTH)

        assert result.error is not None
        assert "최대 체이닝 깊이" in result.error

    @pytest.mark.asyncio
    async def test_handle_event_publishes_in_normal_mode(self):
        """handle_event (normal mode): 매칭된 룰의 EMIT 이벤트를 publisher로 발행"""
        engine, neo4j_mock, publisher_mock = _make_engine(dry_run=False)

        # load_rules mock — 하나의 룰 반환
        neo4j_mock.execute_read.return_value = [
            {
                "a": {
                    "id": "rule-001",
                    "name": "승인 룰",
                    "case_id": "case-001",
                    "tenant_id": "tenant-001",
                    "when_event": "ORDER_PLACED",
                    "given_conditions": "[]",  # 조건 없음 → 항상 매칭
                    "then_actions": json.dumps([
                        {"op": "EMIT", "event_type": "ORDER_APPROVED", "payload": {"status": "ok"}},
                    ]),
                    "enabled": True,
                    "priority": 100,
                    "version": 1,
                },
            },
        ]

        results = await engine.handle_event(
            event_type="ORDER_PLACED",
            aggregate_id="agg-001",
            payload={"source_node_id": "node-001"},
            case_id="case-001",
            tenant_id="tenant-001",
        )

        assert len(results) == 1
        assert results[0].matched is True
        # publisher.publish가 호출되었는지 확인
        publisher_mock.publish.assert_called_once()
        call_kwargs = publisher_mock.publish.call_args
        assert call_kwargs.kwargs["event_type"] == "ORDER_APPROVED"

    @pytest.mark.asyncio
    async def test_handle_event_skips_publish_in_dry_run(self):
        """handle_event (dry_run mode): 이벤트 발행을 건너뜀"""
        engine, neo4j_mock, publisher_mock = _make_engine(dry_run=True)

        neo4j_mock.execute_read.return_value = [
            {
                "a": {
                    "id": "rule-001",
                    "name": "테스트 룰",
                    "case_id": "case-001",
                    "tenant_id": "tenant-001",
                    "when_event": "ORDER_PLACED",
                    "given_conditions": "[]",
                    "then_actions": json.dumps([
                        {"op": "EMIT", "event_type": "ORDER_APPROVED", "payload": {}},
                    ]),
                    "enabled": True,
                    "priority": 100,
                    "version": 1,
                },
            },
        ]

        results = await engine.handle_event(
            event_type="ORDER_PLACED",
            aggregate_id="agg-001",
            payload={"source_node_id": "node-001"},
            case_id="case-001",
            tenant_id="tenant-001",
        )

        assert len(results) == 1
        # dry_run에서는 publisher가 호출되지 않아야 한다
        publisher_mock.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_event_no_rules_returns_empty(self):
        """handle_event: 매칭 룰이 없으면 빈 리스트 반환"""
        engine, neo4j_mock, _ = _make_engine()
        neo4j_mock.execute_read.return_value = []

        results = await engine.handle_event(
            event_type="UNKNOWN_EVENT",
            aggregate_id="agg-001",
            payload={},
            case_id="case-001",
            tenant_id="tenant-001",
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_handle_event_skips_invalid_rule(self):
        """handle_event: 검증 실패한 룰은 건너뛰고 나머지 룰 실행"""
        engine, neo4j_mock, _ = _make_engine()

        neo4j_mock.execute_read.return_value = [
            {
                "a": {
                    "id": "bad-rule",
                    "name": "잘못된 룰",
                    "case_id": "case-001",
                    "tenant_id": "tenant-001",
                    "when_event": "ORDER_PLACED",
                    # 인젝션 시도 필드명 → validate()에서 ValueError
                    "given_conditions": json.dumps([
                        {"type": "state", "node_layer": "Kpi", "field": "a}//inject", "op": "==", "value": "x"}
                    ]),
                    "then_actions": "[]",
                    "enabled": True,
                    "priority": 200,
                    "version": 1,
                },
            },
            {
                "a": {
                    "id": "good-rule",
                    "name": "정상 룰",
                    "case_id": "case-001",
                    "tenant_id": "tenant-001",
                    "when_event": "ORDER_PLACED",
                    "given_conditions": "[]",
                    "then_actions": json.dumps([
                        {"op": "EMIT", "event_type": "OK", "payload": {}},
                    ]),
                    "enabled": True,
                    "priority": 100,
                    "version": 1,
                },
            },
        ]

        results = await engine.handle_event(
            event_type="ORDER_PLACED",
            aggregate_id="agg-001",
            payload={"source_node_id": "node-001"},
            case_id="case-001",
            tenant_id="tenant-001",
        )

        # bad-rule은 validate 실패로 건너뛰고, good-rule만 실행됨
        assert len(results) == 1
        assert results[0].rule_id == "good-rule"


class TestGWTEngineCompare:
    """GWTEngine._compare 정적 메서드 테스트"""

    def test_compare_eq(self):
        assert GWTEngine._compare("ACTIVE", "==", "ACTIVE") is True

    def test_compare_neq(self):
        assert GWTEngine._compare("ACTIVE", "!=", "PENDING") is True

    def test_compare_gt(self):
        assert GWTEngine._compare(10, ">", 5) is True

    def test_compare_lt(self):
        assert GWTEngine._compare(3, "<", 5) is True

    def test_compare_gte(self):
        assert GWTEngine._compare(5, ">=", 5) is True

    def test_compare_lte(self):
        assert GWTEngine._compare(5, "<=", 5) is True

    def test_compare_in(self):
        assert GWTEngine._compare("a", "in", ["a", "b", "c"]) is True

    def test_compare_not_in(self):
        assert GWTEngine._compare("d", "not_in", ["a", "b", "c"]) is True

    def test_compare_contains(self):
        assert GWTEngine._compare("hello world", "contains", "world") is True

    def test_compare_unknown_op_returns_false(self):
        assert GWTEngine._compare(1, "INVALID_OP", 1) is False


class TestGWTEngineResolveRef:
    """GWTEngine._resolve_ref 변수 참조 해석 테스트"""

    def test_resolve_trigger_source_node_id(self):
        engine, _, _ = _make_engine()
        ctx = _make_context(source_node_id="src-node-001")

        result = engine._resolve_ref("$trigger.source_node_id", ctx)
        assert result == "src-node-001"

    def test_resolve_trigger_aggregate_id(self):
        engine, _, _ = _make_engine()
        ctx = _make_context(aggregate_id="agg-999")

        result = engine._resolve_ref("$trigger.aggregate_id", ctx)
        assert result == "agg-999"

    def test_resolve_payload_field(self):
        engine, _, _ = _make_engine()
        ctx = _make_context(payload={"order_id": "ord-555"})

        result = engine._resolve_ref("$payload.order_id", ctx)
        assert result == "ord-555"

    def test_resolve_non_ref_returns_original(self):
        engine, _, _ = _make_engine()
        ctx = _make_context()

        result = engine._resolve_ref("plain-string", ctx)
        assert result == "plain-string"

    def test_resolve_empty_string_returns_empty(self):
        engine, _, _ = _make_engine()
        ctx = _make_context()

        result = engine._resolve_ref("", ctx)
        assert result == ""


# ═══════════════════════════════════════════════════════════════
# 5. GWTRuleManager 테스트 (~6 tests)
# ═══════════════════════════════════════════════════════════════


class TestGWTRuleManager:
    """GWT 룰 CRUD 관리자 테스트"""

    @pytest.mark.asyncio
    async def test_create_rule_calls_execute_write(self):
        """create_rule: Neo4j execute_write를 올바른 파라미터로 호출"""
        neo4j_mock = AsyncMock()
        neo4j_mock.execute_write.return_value = [{"id": "rule-001"}]
        manager = GWTRuleManager(neo4j_client=neo4j_mock)

        rule = _make_rule(
            rule_id="rule-001",
            name="자동 승인",
            given=[GWTCondition(type="state", node_layer="Process", field="status", op="==", value="PENDING")],
            then=[GWTAction(op="SET", field="status", value="APPROVED")],
        )

        result_id = await manager.create_rule(rule)

        assert result_id == "rule-001"
        neo4j_mock.execute_write.assert_called_once()

        # 호출 인자에서 given_conditions, then_actions가 JSON 문자열인지 확인
        call_args = neo4j_mock.execute_write.call_args
        params = call_args.args[1]  # 두 번째 인자 = 파라미터 dict
        assert params["id"] == "rule-001"
        assert params["name"] == "자동 승인"
        assert isinstance(params["given_conditions"], str)
        assert isinstance(params["then_actions"], str)

        # JSON 파싱이 올바른지 확인
        given_parsed = json.loads(params["given_conditions"])
        assert len(given_parsed) == 1
        assert given_parsed[0]["type"] == "state"

    @pytest.mark.asyncio
    async def test_update_rule_rejects_invalid_fields(self):
        """update_rule: ALLOWED_UPDATE_FIELDS에 없는 필드 → ValueError"""
        neo4j_mock = AsyncMock()
        manager = GWTRuleManager(neo4j_client=neo4j_mock)

        with pytest.raises(ValueError, match="허용되지 않는 업데이트 필드"):
            await manager.update_rule("rule-001", {"id": "hacked", "name": "ok"})

    @pytest.mark.asyncio
    async def test_update_rule_accepts_valid_fields(self):
        """update_rule: 허용된 필드만 업데이트 → 성공"""
        neo4j_mock = AsyncMock()
        neo4j_mock.execute_write.return_value = [{"id": "rule-001"}]
        manager = GWTRuleManager(neo4j_client=neo4j_mock)

        result = await manager.update_rule(
            "rule-001",
            {"name": "새 이름", "enabled": False, "priority": 200},
        )

        assert result is True
        neo4j_mock.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_rule_empty_updates_returns_false(self):
        """update_rule: 빈 업데이트 → False 반환"""
        neo4j_mock = AsyncMock()
        manager = GWTRuleManager(neo4j_client=neo4j_mock)

        result = await manager.update_rule("rule-001", {})

        assert result is False
        neo4j_mock.execute_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_link_to_ontology_rejects_invalid_rel_type(self):
        """link_to_ontology: 허용되지 않는 관계 타입 → ValueError"""
        neo4j_mock = AsyncMock()
        manager = GWTRuleManager(neo4j_client=neo4j_mock)

        with pytest.raises(ValueError, match="허용되지 않는 link rel_type"):
            await manager.link_to_ontology("rule-001", "node-001", rel_type="HACKED")

    @pytest.mark.asyncio
    async def test_link_to_ontology_triggers_direction(self):
        """link_to_ontology: TRIGGERS 관계 → (OntologyNode)-[:TRIGGERS]->(ActionType)"""
        neo4j_mock = AsyncMock()
        manager = GWTRuleManager(neo4j_client=neo4j_mock)

        await manager.link_to_ontology("rule-001", "node-001", rel_type="TRIGGERS")

        neo4j_mock.execute_write.assert_called_once()
        call_args = neo4j_mock.execute_write.call_args
        cypher_query = call_args.args[0]
        # TRIGGERS 쿼리는 (n)-[:TRIGGERS]->(a) 방향이어야 한다
        assert "TRIGGERS" in cypher_query
        assert "n)-[:TRIGGERS]->(a)" in cypher_query.replace(" ", "").replace("\n", "")

    @pytest.mark.asyncio
    async def test_link_to_ontology_modifies_direction(self):
        """link_to_ontology: MODIFIES 관계 → (ActionType)-[:MODIFIES]->(OntologyNode)"""
        neo4j_mock = AsyncMock()
        manager = GWTRuleManager(neo4j_client=neo4j_mock)

        await manager.link_to_ontology("rule-001", "node-001", rel_type="MODIFIES")

        neo4j_mock.execute_write.assert_called_once()
        call_args = neo4j_mock.execute_write.call_args
        cypher_query = call_args.args[0]
        assert "MODIFIES" in cypher_query

    @pytest.mark.asyncio
    async def test_delete_rule_calls_detach_delete(self):
        """delete_rule: DETACH DELETE Cypher를 실행"""
        neo4j_mock = AsyncMock()
        neo4j_mock.execute_write.return_value = [{"deleted": 1}]
        manager = GWTRuleManager(neo4j_client=neo4j_mock)

        result = await manager.delete_rule("rule-001")

        assert result is True
        neo4j_mock.execute_write.assert_called_once()
        call_args = neo4j_mock.execute_write.call_args
        cypher_query = call_args.args[0]
        assert "DETACH DELETE" in cypher_query

    @pytest.mark.asyncio
    async def test_delete_rule_not_found_returns_false(self):
        """delete_rule: 삭제할 노드가 없으면 False 반환"""
        neo4j_mock = AsyncMock()
        neo4j_mock.execute_write.return_value = [{"deleted": 0}]
        manager = GWTRuleManager(neo4j_client=neo4j_mock)

        result = await manager.delete_rule("nonexistent-rule")

        assert result is False

    @pytest.mark.asyncio
    async def test_list_rules_enabled_only(self):
        """list_rules: enabled_only=True → WHERE 절에 enabled 조건 추가"""
        neo4j_mock = AsyncMock()
        neo4j_mock.execute_read.return_value = [
            {"a": {"id": "rule-001", "name": "R1", "enabled": True}},
        ]
        manager = GWTRuleManager(neo4j_client=neo4j_mock)

        result = await manager.list_rules("case-001", "tenant-001", enabled_only=True)

        assert len(result) == 1
        neo4j_mock.execute_read.assert_called_once()
        call_args = neo4j_mock.execute_read.call_args
        cypher_query = call_args.args[0]
        assert "enabled = true" in cypher_query


# ═══════════════════════════════════════════════════════════════
# 6. GraphProjectorWorker 테스트 (보너스)
# ═══════════════════════════════════════════════════════════════


class TestGraphProjectorResolveParams:
    """GraphProjectorWorker._resolve_params 파라미터 해석 테스트"""

    def _make_worker(self):
        from app.workers.graph_projector import GraphProjectorWorker

        redis_mock = AsyncMock()
        neo4j_mock = AsyncMock()
        return GraphProjectorWorker(redis_mock, neo4j_mock)

    def test_resolve_payload_field(self):
        """payload.xxx → payload에서 해당 키 추출"""
        worker = self._make_worker()
        params = worker._resolve_params(
            {"node_id": "payload.process_node_id"},
            payload={"process_node_id": "proc-001"},
            case_id="case-001",
            event_id="evt-001",
            full_payload="{}",
        )
        assert params["node_id"] == "proc-001"
        assert params["case_id"] == "case-001"

    def test_resolve_event_id(self):
        """$event_id → event_id 값 주입"""
        worker = self._make_worker()
        params = worker._resolve_params(
            {"snapshot_id": "$event_id"},
            payload={},
            case_id="case-001",
            event_id="evt-999",
            full_payload="{}",
        )
        assert params["snapshot_id"] == "evt-999"

    def test_resolve_full_payload(self):
        """$full_payload → payload JSON 문자열"""
        worker = self._make_worker()
        full = '{"key": "value"}'
        params = worker._resolve_params(
            {"data": "$full_payload"},
            payload={"key": "value"},
            case_id="case-001",
            event_id="evt-001",
            full_payload=full,
        )
        assert params["data"] == full

    def test_resolve_literal_value(self):
        """리터럴 문자열 → 그대로 사용"""
        worker = self._make_worker()
        params = worker._resolve_params(
            {"status": "ACTIVE"},
            payload={},
            case_id="case-001",
            event_id="evt-001",
            full_payload="{}",
        )
        assert params["status"] == "ACTIVE"

    def test_resolve_missing_payload_key_returns_none(self):
        """payload에 없는 키 → None 반환"""
        worker = self._make_worker()
        params = worker._resolve_params(
            {"value": "payload.nonexistent"},
            payload={"other_key": "val"},
            case_id="case-001",
            event_id="evt-001",
            full_payload="{}",
        )
        assert params["value"] is None

    def test_case_id_always_included(self):
        """case_id는 params_map에 없어도 항상 자동 포함"""
        worker = self._make_worker()
        params = worker._resolve_params(
            {},
            payload={},
            case_id="case-XYZ",
            event_id="evt-001",
            full_payload="{}",
        )
        assert params["case_id"] == "case-XYZ"


# ═══════════════════════════════════════════════════════════════
# 7. GWTConsumerWorker 테스트 (보너스)
# ═══════════════════════════════════════════════════════════════


class TestGWTConsumerWorker:
    """GWT Consumer Worker 메시지 필터링 테스트"""

    def _make_worker(self):
        from app.workers.gwt_consumer import GWTConsumerWorker

        redis_mock = AsyncMock()
        engine_mock = AsyncMock()
        worker = GWTConsumerWorker(redis_mock, engine_mock)
        return worker, redis_mock, engine_mock

    @pytest.mark.asyncio
    async def test_skip_self_source_worker(self):
        """source_worker='gwt-engine' 이벤트 → 자가 소비 방지 스킵"""
        worker, redis_mock, engine_mock = self._make_worker()

        await worker._process_message(
            "axiom:core:events",
            "msg-001",
            {"event_type": "ORDER_PLACED", "source_worker": "gwt-engine"},
        )

        assert worker._stats["skipped_self"] == 1
        engine_mock.handle_event.assert_not_called()
        redis_mock.xack.assert_called_once()

    @pytest.mark.asyncio
    async def test_skip_no_case_id(self):
        """case_id가 없는 이벤트 → GWT 대상 아니므로 스킵"""
        worker, redis_mock, engine_mock = self._make_worker()

        await worker._process_message(
            "axiom:core:events",
            "msg-002",
            {
                "event_type": "METADATA_CHANGED",
                "payload": json.dumps({"table": "users"}),
            },
        )

        assert worker._stats["skipped_no_case"] == 1
        engine_mock.handle_event.assert_not_called()
        redis_mock.xack.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_valid_event(self):
        """유효한 이벤트 → GWT Engine에 전달"""
        worker, redis_mock, engine_mock = self._make_worker()
        engine_mock.handle_event.return_value = []

        await worker._process_message(
            "axiom:core:events",
            "msg-003",
            {
                "event_type": "ORDER_PLACED",
                "aggregate_id": "agg-001",
                "tenant_id": "tenant-001",
                "payload": json.dumps({"case_id": "case-001", "order_id": "ord-1"}),
            },
        )

        assert worker._stats["processed"] == 1
        engine_mock.handle_event.assert_called_once()
        redis_mock.xack.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_failure_increments_failed_stat(self):
        """GWT Engine 처리 실패 → failed 카운트 증가, ACK 미실행"""
        worker, redis_mock, engine_mock = self._make_worker()
        engine_mock.handle_event.side_effect = RuntimeError("Neo4j 연결 실패")

        await worker._process_message(
            "axiom:core:events",
            "msg-004",
            {
                "event_type": "ORDER_PLACED",
                "aggregate_id": "agg-001",
                "tenant_id": "tenant-001",
                "payload": json.dumps({"case_id": "case-001"}),
            },
        )

        assert worker._stats["failed"] == 1
        # 실패 시 ACK하지 않아야 한다 (재시도 대상)
        redis_mock.xack.assert_not_called()

    @pytest.mark.asyncio
    async def test_payload_string_parsed_as_json(self):
        """payload가 문자열이면 JSON 파싱"""
        worker, redis_mock, engine_mock = self._make_worker()
        engine_mock.handle_event.return_value = []

        await worker._process_message(
            "axiom:core:events",
            "msg-005",
            {
                "event_type": "ORDER_PLACED",
                "tenant_id": "t-001",
                "payload": '{"case_id": "case-ABC", "amount": 100}',
            },
        )

        engine_mock.handle_event.assert_called_once()
        call_kwargs = engine_mock.handle_event.call_args.kwargs
        assert call_kwargs["case_id"] == "case-ABC"
        assert call_kwargs["payload"]["amount"] == 100


# ═══════════════════════════════════════════════════════════════
# 8. Projection Rules 구조 검증 테스트 (보너스)
# ═══════════════════════════════════════════════════════════════


class TestProjectionRulesStructure:
    """PROJECTION_RULES 매핑 테이블의 구조적 무결성 검증"""

    def test_all_rules_have_required_keys(self):
        """모든 규칙에 description, cypher, params_map 키가 있는지 확인"""
        from app.workers.projection_rules import PROJECTION_RULES

        for event_type, rules in PROJECTION_RULES.items():
            for i, rule in enumerate(rules):
                assert "description" in rule, f"{event_type}[{i}]: description 누락"
                assert "cypher" in rule, f"{event_type}[{i}]: cypher 누락"
                assert "params_map" in rule, f"{event_type}[{i}]: params_map 누락"

    def test_known_event_types_exist(self):
        """핵심 이벤트 타입이 매핑에 존재하는지 확인"""
        from app.workers.projection_rules import PROJECTION_RULES

        expected_events = [
            "PROCESS_INITIATED",
            "WORKITEM_COMPLETED",
            "WHATIF_SIMULATION_COMPLETED",
            "CAUSAL_RELATION_DISCOVERED",
            "INSIGHT_JOB_COMPLETED",
            "METADATA_TABLE_DISCOVERED",
        ]
        for event in expected_events:
            assert event in PROJECTION_RULES, f"{event}가 PROJECTION_RULES에 없음"

    def test_params_map_values_are_strings(self):
        """params_map의 모든 값이 문자열인지 확인"""
        from app.workers.projection_rules import PROJECTION_RULES

        for event_type, rules in PROJECTION_RULES.items():
            for i, rule in enumerate(rules):
                for key, val in rule["params_map"].items():
                    assert isinstance(val, str), (
                        f"{event_type}[{i}].params_map['{key}'] = {val} "
                        f"(type: {type(val).__name__}, 문자열이어야 함)"
                    )

    def test_cypher_queries_are_non_empty(self):
        """Cypher 쿼리가 비어있지 않은지 확인"""
        from app.workers.projection_rules import PROJECTION_RULES

        for event_type, rules in PROJECTION_RULES.items():
            for i, rule in enumerate(rules):
                cypher = rule["cypher"].strip()
                assert len(cypher) > 10, f"{event_type}[{i}]: cypher가 너무 짧거나 비어있음"
