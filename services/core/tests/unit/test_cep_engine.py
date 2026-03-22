"""CEP 엔진 단위 테스트.

조건 유형별 평가, 규칙 CRUD, 이력 관리, 엣지 케이스를 검증한다.
"""
from __future__ import annotations

import math

import pytest

from app.modules.watch.cep_engine import (
    ActionType,
    CEPEngine,
    CEPResult,
    CEPRule,
    ConditionType,
    Severity,
    _MAX_HISTORY_PER_RULE,
)


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------
@pytest.fixture
def engine() -> CEPEngine:
    """매 테스트마다 새 엔진 인스턴스를 생성한다."""
    return CEPEngine()


def _make_rule(
    name: str = "test_rule",
    condition_type: ConditionType = ConditionType.GT,
    threshold: float | list[float] = 100.0,
    **kwargs,
) -> CEPRule:
    """테스트용 규칙을 간편하게 생성한다."""
    return CEPRule(
        name=name,
        condition_type=condition_type,
        threshold=threshold,
        **kwargs,
    )


# ===========================================================================
# 규칙 CRUD 테스트
# ===========================================================================
class TestRuleCRUD:
    """규칙 등록·조회·수정·삭제 동작 검증."""

    def test_add_and_get_rule(self, engine: CEPEngine):
        """규칙을 등록하고 ID로 조회할 수 있다."""
        rule = _make_rule(name="OEE 임계값")
        added = engine.add_rule(rule)
        assert added.id == rule.id
        assert engine.get_rule(rule.id) is not None
        assert engine.get_rule(rule.id).name == "OEE 임계값"

    def test_list_rules(self, engine: CEPEngine):
        """등록된 규칙 목록을 조회할 수 있다."""
        engine.add_rule(_make_rule(name="rule_a"))
        engine.add_rule(_make_rule(name="rule_b"))
        rules = engine.list_rules()
        assert len(rules) == 2
        names = {r.name for r in rules}
        assert names == {"rule_a", "rule_b"}

    def test_update_rule(self, engine: CEPEngine):
        """규칙을 부분 업데이트할 수 있다."""
        rule = _make_rule(name="original")
        engine.add_rule(rule)
        updated = engine.update_rule(rule.id, name="updated", enabled=False)
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False
        # 변경하지 않은 필드는 유지
        assert updated.condition_type == ConditionType.GT

    def test_update_nonexistent_rule_returns_none(self, engine: CEPEngine):
        """존재하지 않는 규칙을 업데이트하면 None을 반환한다."""
        result = engine.update_rule("nonexistent", name="x")
        assert result is None

    def test_delete_rule(self, engine: CEPEngine):
        """규칙을 삭제하면 조회되지 않는다."""
        rule = _make_rule()
        engine.add_rule(rule)
        assert engine.delete_rule(rule.id) is True
        assert engine.get_rule(rule.id) is None

    def test_delete_nonexistent_rule_returns_false(self, engine: CEPEngine):
        """존재하지 않는 규칙 삭제는 False를 반환한다."""
        assert engine.delete_rule("nonexistent") is False

    def test_delete_rule_clears_history(self, engine: CEPEngine):
        """규칙 삭제 시 이력도 함께 제거된다."""
        rule = _make_rule()
        engine.add_rule(rule)
        engine.evaluate_rule(rule, 200.0)
        assert len(engine.get_history_by_id(rule.id)) == 1
        engine.delete_rule(rule.id)
        assert len(engine.get_history_by_id(rule.id)) == 0

    def test_add_rule_overwrites_existing(self, engine: CEPEngine):
        """동일 ID 규칙을 다시 등록하면 덮어쓴다."""
        rule = _make_rule(name="v1")
        engine.add_rule(rule)
        rule_v2 = CEPRule(
            id=rule.id,
            name="v2",
            condition_type=ConditionType.GT,
            threshold=200.0,
        )
        engine.add_rule(rule_v2)
        assert engine.get_rule(rule.id).name == "v2"


# ===========================================================================
# 조건 유형별 평가 테스트
# ===========================================================================
class TestConditionGT:
    """GT (greater than) 조건 평가 검증."""

    def test_triggered_when_above(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.GT, threshold=100.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 150.0)
        assert result.triggered is True

    def test_not_triggered_when_equal(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.GT, threshold=100.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 100.0)
        assert result.triggered is False

    def test_not_triggered_when_below(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.GT, threshold=100.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 50.0)
        assert result.triggered is False


class TestConditionLT:
    """LT (less than) 조건 평가 검증."""

    def test_triggered_when_below(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.LT, threshold=50.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 30.0)
        assert result.triggered is True

    def test_not_triggered_when_equal(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.LT, threshold=50.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 50.0)
        assert result.triggered is False

    def test_not_triggered_when_above(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.LT, threshold=50.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 100.0)
        assert result.triggered is False


class TestConditionEQ:
    """EQ (equal) 조건 평가 검증."""

    def test_triggered_when_equal(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.EQ, threshold=42.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 42.0)
        assert result.triggered is True

    def test_not_triggered_when_different(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.EQ, threshold=42.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 43.0)
        assert result.triggered is False

    def test_floating_point_close(self, engine: CEPEngine):
        """부동소수점 근사 비교가 동작한다."""
        rule = _make_rule(condition_type=ConditionType.EQ, threshold=0.1 + 0.2)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 0.3)
        assert result.triggered is True


class TestConditionNE:
    """NE (not equal) 조건 평가 검증."""

    def test_triggered_when_different(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.NE, threshold=0.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 1.0)
        assert result.triggered is True

    def test_not_triggered_when_equal(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.NE, threshold=0.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 0.0)
        assert result.triggered is False


class TestConditionBetween:
    """BETWEEN (범위) 조건 평가 검증."""

    def test_triggered_within_range(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.BETWEEN, threshold=[10.0, 90.0])
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 50.0)
        assert result.triggered is True

    def test_triggered_at_boundary_lo(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.BETWEEN, threshold=[10.0, 90.0])
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 10.0)
        assert result.triggered is True

    def test_triggered_at_boundary_hi(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.BETWEEN, threshold=[10.0, 90.0])
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 90.0)
        assert result.triggered is True

    def test_not_triggered_outside_range(self, engine: CEPEngine):
        rule = _make_rule(condition_type=ConditionType.BETWEEN, threshold=[10.0, 90.0])
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 5.0)
        assert result.triggered is False

    def test_invalid_threshold_raises_error(self):
        """between 조건에 단일 값 임계값을 주면 검증 오류가 발생한다."""
        rule = CEPRule(
            name="bad_between",
            condition_type=ConditionType.BETWEEN,
            threshold=100.0,
        )
        with pytest.raises(ValueError, match="2개 요소"):
            rule.validate_for_condition()

    def test_inverted_range_raises_error(self):
        """lo > hi 범위를 주면 검증 오류가 발생한다."""
        rule = CEPRule(
            name="bad_range",
            condition_type=ConditionType.BETWEEN,
            threshold=[90.0, 10.0],
        )
        with pytest.raises(ValueError, match="작거나 같아야"):
            rule.validate_for_condition()


class TestConditionChangeRate:
    """CHANGE_RATE (변화율) 조건 평가 검증."""

    def test_first_evaluation_not_triggered(self, engine: CEPEngine):
        """첫 평가는 이전 값이 없으므로 트리거되지 않는다."""
        rule = _make_rule(condition_type=ConditionType.CHANGE_RATE, threshold=10.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 100.0)
        assert result.triggered is False
        assert "첫 번째" in result.message

    def test_triggered_on_large_change(self, engine: CEPEngine):
        """임계값을 초과하는 변화율이면 트리거된다."""
        rule = _make_rule(condition_type=ConditionType.CHANGE_RATE, threshold=10.0)
        engine.add_rule(rule)
        # 첫 평가: 기준 값 설정
        engine.evaluate_rule(rule, 100.0)
        # 두 번째 평가: 20% 변화 (> 10% 임계값)
        result = engine.evaluate_rule(rule, 120.0)
        assert result.triggered is True

    def test_not_triggered_on_small_change(self, engine: CEPEngine):
        """임계값 이하 변화율이면 트리거되지 않는다."""
        rule = _make_rule(condition_type=ConditionType.CHANGE_RATE, threshold=10.0)
        engine.add_rule(rule)
        engine.evaluate_rule(rule, 100.0)
        result = engine.evaluate_rule(rule, 105.0)
        assert result.triggered is False

    def test_previous_value_zero_to_nonzero(self, engine: CEPEngine):
        """이전 값이 0에서 비0으로 변하면 무한대 변화율로 트리거된다."""
        rule = _make_rule(condition_type=ConditionType.CHANGE_RATE, threshold=10.0)
        engine.add_rule(rule)
        engine.evaluate_rule(rule, 0.0)
        result = engine.evaluate_rule(rule, 50.0)
        assert result.triggered is True

    def test_previous_value_zero_to_zero(self, engine: CEPEngine):
        """0→0 변화는 트리거되지 않는다."""
        rule = _make_rule(condition_type=ConditionType.CHANGE_RATE, threshold=10.0)
        engine.add_rule(rule)
        engine.evaluate_rule(rule, 0.0)
        result = engine.evaluate_rule(rule, 0.0)
        assert result.triggered is False

    def test_negative_change_triggers(self, engine: CEPEngine):
        """음의 변화도 절대값으로 평가한다."""
        rule = _make_rule(condition_type=ConditionType.CHANGE_RATE, threshold=5.0)
        engine.add_rule(rule)
        engine.evaluate_rule(rule, 100.0)
        result = engine.evaluate_rule(rule, 80.0)  # -20%
        assert result.triggered is True


# ===========================================================================
# 엣지 케이스
# ===========================================================================
class TestEdgeCases:
    """None 값, NaN, Inf 등 엣지 케이스 검증."""

    def test_none_value_not_triggered(self, engine: CEPEngine):
        """None 값을 평가하면 트리거되지 않는다."""
        rule = _make_rule()
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, None)
        assert result.triggered is False
        assert result.current_value is None

    def test_nan_value_not_triggered(self, engine: CEPEngine):
        """NaN 값을 평가하면 트리거되지 않는다."""
        rule = _make_rule()
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, float("nan"))
        assert result.triggered is False

    def test_inf_value_not_triggered(self, engine: CEPEngine):
        """Inf 값을 평가하면 트리거되지 않는다."""
        rule = _make_rule()
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, float("inf"))
        assert result.triggered is False

    def test_negative_inf_value_not_triggered(self, engine: CEPEngine):
        """-Inf 값을 평가하면 트리거되지 않는다."""
        rule = _make_rule()
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, float("-inf"))
        assert result.triggered is False

    def test_zero_threshold(self, engine: CEPEngine):
        """임계값이 0일 때 정상 동작한다."""
        rule = _make_rule(condition_type=ConditionType.GT, threshold=0.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 0.001)
        assert result.triggered is True

    def test_negative_threshold(self, engine: CEPEngine):
        """음수 임계값도 정상 동작한다."""
        rule = _make_rule(condition_type=ConditionType.LT, threshold=-10.0)
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, -20.0)
        assert result.triggered is True

    def test_list_threshold_for_non_between_raises(self):
        """between 외 조건에 리스트 임계값을 주면 검증 오류가 발생한다."""
        rule = CEPRule(
            name="bad",
            condition_type=ConditionType.GT,
            threshold=[1.0, 2.0],
        )
        with pytest.raises(ValueError, match="단일 숫자"):
            rule.validate_for_condition()


# ===========================================================================
# 이력 관리 테스트
# ===========================================================================
class TestHistory:
    """평가 이력 관리 검증."""

    def test_history_recorded_after_evaluation(self, engine: CEPEngine):
        """평가 후 이력이 기록된다."""
        rule = _make_rule()
        engine.add_rule(rule)
        engine.evaluate_rule(rule, 150.0)
        history = engine.get_history_by_id(rule.id)
        assert len(history) == 1
        assert history[0].triggered is True

    def test_history_by_name(self, engine: CEPEngine):
        """규칙 이름으로 이력을 조회할 수 있다."""
        rule = _make_rule(name="my_rule")
        engine.add_rule(rule)
        engine.evaluate_rule(rule, 150.0)
        history = engine.get_history("my_rule")
        assert len(history) == 1

    def test_history_by_unknown_name_empty(self, engine: CEPEngine):
        """존재하지 않는 이름으로 이력 조회 시 빈 리스트를 반환한다."""
        assert engine.get_history("unknown") == []

    def test_history_max_limit(self, engine: CEPEngine):
        """이력은 규칙별 최대 건수를 초과하지 않는다."""
        rule = _make_rule()
        engine.add_rule(rule)
        for i in range(_MAX_HISTORY_PER_RULE + 20):
            engine.evaluate_rule(rule, float(i))
        history = engine.get_history_by_id(rule.id)
        assert len(history) == _MAX_HISTORY_PER_RULE

    def test_clear_history(self, engine: CEPEngine):
        """이력을 초기화할 수 있다."""
        rule = _make_rule()
        engine.add_rule(rule)
        engine.evaluate_rule(rule, 150.0)
        engine.clear_history(rule.id)
        assert len(engine.get_history_by_id(rule.id)) == 0

    def test_result_to_dict(self, engine: CEPEngine):
        """CEPResult.to_dict()가 올바른 키를 반환한다."""
        rule = _make_rule()
        engine.add_rule(rule)
        result = engine.evaluate_rule(rule, 150.0)
        d = result.to_dict()
        expected_keys = {
            "rule_name", "triggered", "current_value",
            "threshold", "message", "timestamp",
            "severity", "condition_type",
        }
        assert set(d.keys()) == expected_keys


# ===========================================================================
# 통계 테스트
# ===========================================================================
class TestStats:
    """엔진 통계 검증."""

    def test_empty_stats(self, engine: CEPEngine):
        """초기 상태의 통계."""
        stats = engine.get_stats()
        assert stats["total_rules"] == 0
        assert stats["total_evaluations"] == 0
        assert stats["trigger_rate"] == 0.0

    def test_stats_after_evaluations(self, engine: CEPEngine):
        """평가 후 통계가 정확하다."""
        rule = _make_rule(condition_type=ConditionType.GT, threshold=50.0)
        engine.add_rule(rule)
        engine.evaluate_rule(rule, 100.0)  # 트리거
        engine.evaluate_rule(rule, 30.0)   # 미트리거

        stats = engine.get_stats()
        assert stats["total_rules"] == 1
        assert stats["enabled_rules"] == 1
        assert stats["total_evaluations"] == 2
        assert stats["total_triggered"] == 1
        assert stats["trigger_rate"] == 0.5

    def test_stats_with_disabled_rule(self, engine: CEPEngine):
        """비활성 규칙도 통계에 포함된다."""
        engine.add_rule(_make_rule(name="active", enabled=True))
        engine.add_rule(_make_rule(name="inactive", enabled=False))
        stats = engine.get_stats()
        assert stats["total_rules"] == 2
        assert stats["enabled_rules"] == 1
        assert stats["disabled_rules"] == 1


# ===========================================================================
# 규칙 검증 테스트
# ===========================================================================
class TestRuleValidation:
    """CEPRule 모델 검증."""

    def test_valid_gt_rule(self):
        rule = _make_rule(condition_type=ConditionType.GT, threshold=100.0)
        rule.validate_for_condition()  # 예외 없음

    def test_valid_between_rule(self):
        rule = _make_rule(condition_type=ConditionType.BETWEEN, threshold=[0.0, 100.0])
        rule.validate_for_condition()  # 예외 없음

    def test_empty_name_rejected(self):
        """빈 이름은 거부된다."""
        with pytest.raises(Exception):
            CEPRule(name="", condition_type=ConditionType.GT, threshold=1.0)

    def test_negative_schedule_interval_rejected(self):
        """0 이하 실행 주기는 거부된다."""
        with pytest.raises(Exception):
            CEPRule(
                name="test",
                condition_type=ConditionType.GT,
                threshold=1.0,
                schedule_interval_seconds=0,
            )

    def test_default_values(self):
        """기본값이 올바르게 설정된다."""
        rule = _make_rule()
        assert rule.severity == Severity.WARNING
        assert rule.action == ActionType.LOG
        assert rule.enabled is True
        assert rule.schedule_interval_seconds == 60
        assert rule.tags == []
