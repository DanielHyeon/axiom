"""DMN 규칙 엔진 단위 테스트."""
import pytest

from app.services.dmn_engine import (
    DecisionInput,
    DecisionOutput,
    DecisionRule,
    DecisionTable,
    HitPolicy,
    _evaluate_condition,
    create_table_from_dict,
    execute_decision_table,
)


# ─── _evaluate_condition 테스트 ────────────────────────────

class TestEvaluateCondition:
    """조건 평가 함수 테스트."""

    def test_wildcard_empty(self):
        """빈 문자열은 항상 True."""
        assert _evaluate_condition("", 42) is True

    def test_wildcard_dash(self):
        """대시('-')는 항상 True."""
        assert _evaluate_condition("-", "anything") is True

    def test_eq_number(self):
        assert _evaluate_condition("== 100", 100) is True
        assert _evaluate_condition("== 100", 99) is False

    def test_ne_number(self):
        assert _evaluate_condition("!= 0", 1) is True
        assert _evaluate_condition("!= 0", 0) is False

    def test_gt(self):
        assert _evaluate_condition("> 50", 51) is True
        assert _evaluate_condition("> 50", 50) is False

    def test_gte(self):
        assert _evaluate_condition(">= 50", 50) is True
        assert _evaluate_condition(">= 50", 49) is False

    def test_lt(self):
        assert _evaluate_condition("< 10", 9) is True
        assert _evaluate_condition("< 10", 10) is False

    def test_lte(self):
        assert _evaluate_condition("<= 10", 10) is True
        assert _evaluate_condition("<= 10", 11) is False

    def test_eq_string(self):
        assert _evaluate_condition("== 'VIP'", "VIP") is True
        assert _evaluate_condition("== 'VIP'", "regular") is False

    def test_float_comparison(self):
        assert _evaluate_condition("> 3.14", 4.0) is True
        assert _evaluate_condition("<= 3.14", 3.14) is True

    def test_boolean(self):
        assert _evaluate_condition("== True", True) is True
        assert _evaluate_condition("== false", False) is True

    def test_in_list(self):
        assert _evaluate_condition("in [1, 2, 3]", 2) is True
        assert _evaluate_condition("in [1, 2, 3]", 5) is False

    def test_not_in_list(self):
        assert _evaluate_condition("not in ['a', 'b']", "c") is True
        assert _evaluate_condition("not in ['a', 'b']", "a") is False

    def test_simple_value_equality(self):
        """연산자 없는 값은 문자열 등호 비교."""
        assert _evaluate_condition("hello", "hello") is True
        assert _evaluate_condition("hello", "world") is False

    def test_single_quoted_value(self):
        assert _evaluate_condition("'active'", "active") is True


# ─── execute_decision_table 테스트 ─────────────────────────

class TestExecuteDecisionTable:
    """결정 테이블 실행 테스트."""

    def _make_discount_table(self, hit_policy: str = HitPolicy.FIRST) -> DecisionTable:
        """할인율 결정 테이블 헬퍼."""
        return DecisionTable(
            name="DiscountTable",
            hit_policy=hit_policy,
            inputs=[
                DecisionInput(name="customer_type"),
                DecisionInput(name="order_total", type_ref="number"),
            ],
            output_defs=[DecisionOutput(name="discount")],
            rules=[
                DecisionRule(
                    conditions={"customer_type": "== 'VIP'", "order_total": ">= 100"},
                    outputs={"discount": 0.2},
                    priority=1,
                    description="VIP 고객 + 100 이상 주문: 20% 할인",
                ),
                DecisionRule(
                    conditions={"customer_type": "== 'VIP'", "order_total": "-"},
                    outputs={"discount": 0.1},
                    priority=2,
                    description="VIP 고객: 10% 할인",
                ),
                DecisionRule(
                    conditions={"customer_type": "-", "order_total": ">= 200"},
                    outputs={"discount": 0.05},
                    priority=3,
                    description="200 이상 주문: 5% 할인",
                ),
            ],
        )

    def test_first_hit_policy(self):
        """FIRST 정책: 첫 번째 매칭 규칙만 반환."""
        table = self._make_discount_table(HitPolicy.FIRST)
        results = execute_decision_table(
            table, {"customer_type": "VIP", "order_total": 150}
        )
        assert len(results) == 1
        assert results[0]["discount"] == 0.2

    def test_collect_hit_policy(self):
        """COLLECT 정책: 매칭되는 모든 규칙 수집."""
        table = self._make_discount_table(HitPolicy.COLLECT)
        results = execute_decision_table(
            table, {"customer_type": "VIP", "order_total": 250}
        )
        # VIP+100이상, VIP전체, 200이상 — 3개 규칙 모두 매칭
        assert len(results) == 3

    def test_priority_hit_policy(self):
        """PRIORITY 정책: 가장 높은 우선순위(낮은 숫자) 규칙 반환."""
        table = self._make_discount_table(HitPolicy.PRIORITY)
        results = execute_decision_table(
            table, {"customer_type": "VIP", "order_total": 250}
        )
        assert len(results) == 1
        assert results[0]["discount"] == 0.2  # priority=1

    def test_no_match(self):
        """매칭 규칙 없으면 빈 리스트 반환."""
        table = self._make_discount_table()
        results = execute_decision_table(
            table, {"customer_type": "regular", "order_total": 50}
        )
        assert results == []


# ─── create_table_from_dict 테스트 ─────────────────────────

class TestCreateTableFromDict:
    """딕셔너리→DecisionTable 변환 테스트."""

    def test_basic_conversion(self):
        definition = {
            "name": "TestTable",
            "hit_policy": "COLLECT",
            "inputs": [{"name": "x", "type_ref": "number"}],
            "outputs": [{"name": "y"}],
            "rules": [
                {
                    "conditions": {"x": "> 0"},
                    "outputs": {"y": "positive"},
                    "priority": 1,
                    "description": "양수",
                }
            ],
        }
        table = create_table_from_dict(definition)
        assert table.name == "TestTable"
        assert table.hit_policy == "COLLECT"
        assert len(table.inputs) == 1
        assert len(table.output_defs) == 1
        assert len(table.rules) == 1
        assert table.rules[0].description == "양수"

    def test_defaults(self):
        """필드 누락 시 기본값 적용."""
        table = create_table_from_dict({})
        assert table.name == "Unnamed"
        assert table.hit_policy == HitPolicy.FIRST
        assert table.inputs == []
        assert table.rules == []
