"""CEP (Complex Event Processing) 규칙 엔진.

SQL 기반 모니터링 규칙을 정의하고 주기적으로 실행하여
임계값 위반 시 알림을 생성한다.

KAIR text2sql의 events.py/SimpleCEP를 Axiom Core 패턴으로 이식.

규칙 구조:
  - name: 규칙 이름
  - sql_query: 모니터링 SQL (SELECT 결과를 평가)
  - condition_type: 조건 (gt, lt, eq, ne, between, change_rate)
  - threshold: 임계값 (단일 값 또는 [lo, hi] 범위)
  - schedule_interval_seconds: 실행 주기 (초 단위)
  - severity: 심각도 (info, warning, critical)
  - action: 알림 액션 (log, webhook, email)
"""
from __future__ import annotations

import math
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 조건 타입 열거형
# ---------------------------------------------------------------------------
class ConditionType(str, Enum):
    """평가 조건 유형.

    gt: 현재 값이 임계값보다 큰지
    lt: 현재 값이 임계값보다 작은지
    eq: 현재 값이 임계값과 같은지
    ne: 현재 값이 임계값과 다른지
    between: 현재 값이 [lo, hi] 범위 안에 있는지
    change_rate: 이전 값 대비 변화율(%)이 임계값을 초과하는지
    """

    GT = "gt"
    LT = "lt"
    EQ = "eq"
    NE = "ne"
    BETWEEN = "between"
    CHANGE_RATE = "change_rate"


# ---------------------------------------------------------------------------
# 심각도 열거형
# ---------------------------------------------------------------------------
class Severity(str, Enum):
    """알림 심각도 수준."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# 액션 열거형
# ---------------------------------------------------------------------------
class ActionType(str, Enum):
    """규칙 트리거 시 실행할 액션."""

    LOG = "log"
    WEBHOOK = "webhook"
    EMAIL = "email"


# ---------------------------------------------------------------------------
# CEP 규칙 Pydantic 모델
# ---------------------------------------------------------------------------
class CEPRule(BaseModel):
    """CEP 모니터링 규칙 정의.

    sql_query 결과의 단일 숫자 값을 condition_type + threshold로 평가한다.
    between 조건의 경우 threshold는 [lo, hi] 리스트로 설정해야 한다.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, max_length=200, description="규칙 이름")
    description: str = Field(default="", max_length=1000, description="규칙 설명")
    sql_query: str = Field(default="", description="모니터링 SQL 쿼리 (참고용)")
    condition_type: ConditionType = Field(..., description="평가 조건 유형")
    threshold: float | list[float] = Field(..., description="임계값 (between은 [lo, hi])")
    severity: Severity = Field(default=Severity.WARNING, description="알림 심각도")
    action: ActionType = Field(default=ActionType.LOG, description="트리거 액션")
    enabled: bool = Field(default=True, description="규칙 활성화 여부")
    schedule_interval_seconds: int = Field(
        default=60,
        ge=1,
        description="실행 주기 (초 단위)",
    )
    tags: list[str] = Field(default_factory=list, description="태그 목록 (분류용)")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="생성 시각",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="수정 시각",
    )

    @field_validator("threshold")
    @classmethod
    def _validate_threshold(cls, v: float | list[float], info: Any) -> float | list[float]:
        """between 조건은 2개 요소 리스트가 필요하다."""
        # info.data 는 이미 파싱된 필드들
        return v

    def validate_for_condition(self) -> None:
        """condition_type과 threshold 호환성을 검증한다."""
        if self.condition_type == ConditionType.BETWEEN:
            if not isinstance(self.threshold, list) or len(self.threshold) != 2:
                raise ValueError("between 조건은 [lo, hi] 2개 요소 리스트가 필요합니다")
            if self.threshold[0] > self.threshold[1]:
                raise ValueError("between 조건에서 lo는 hi보다 작거나 같아야 합니다")
        else:
            if isinstance(self.threshold, list):
                raise ValueError(f"{self.condition_type.value} 조건은 단일 숫자 임계값이 필요합니다")


# ---------------------------------------------------------------------------
# CEP 평가 결과
# ---------------------------------------------------------------------------
@dataclass
class CEPResult:
    """규칙 평가 결과.

    triggered: 조건이 충족되어 알림을 발생시켜야 하는지
    current_value: 평가에 사용된 현재 값
    threshold: 비교에 사용된 임계값
    message: 사람이 읽을 수 있는 결과 설명
    """

    rule_name: str
    triggered: bool
    current_value: float | None
    threshold: float | list[float]
    message: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    severity: str = "warning"
    condition_type: str = "gt"

    def to_dict(self) -> dict:
        """직렬화용 딕셔너리 변환."""
        return {
            "rule_name": self.rule_name,
            "triggered": self.triggered,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "message": self.message,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "condition_type": self.condition_type,
        }


# ---------------------------------------------------------------------------
# CEP 엔진
# ---------------------------------------------------------------------------
# 규칙별 평가 이력 최대 보관 건수
_MAX_HISTORY_PER_RULE = 100


class CEPEngine:
    """인메모리 CEP 규칙 관리 및 평가 엔진.

    규칙을 등록·수정·삭제하고, 현재 값으로 조건을 평가하여
    CEPResult를 반환한다. change_rate 조건은 이전 평가 값과의
    변화율(%)로 판정한다.
    """

    def __init__(self) -> None:
        # 규칙 저장소: rule_id → CEPRule
        self._rules: dict[str, CEPRule] = {}
        # 평가 이력: rule_id → deque[CEPResult]
        self._history: dict[str, deque[CEPResult]] = {}

    # -----------------------------------------------------------------------
    # 규칙 CRUD
    # -----------------------------------------------------------------------
    def add_rule(self, rule: CEPRule) -> CEPRule:
        """규칙을 엔진에 등록한다. 중복 ID는 덮어쓴다."""
        rule.validate_for_condition()
        self._rules[rule.id] = rule
        if rule.id not in self._history:
            self._history[rule.id] = deque(maxlen=_MAX_HISTORY_PER_RULE)
        return rule

    def get_rule(self, rule_id: str) -> CEPRule | None:
        """ID로 규칙을 조회한다."""
        return self._rules.get(rule_id)

    def list_rules(self) -> list[CEPRule]:
        """등록된 모든 규칙 목록을 반환한다."""
        return list(self._rules.values())

    def update_rule(self, rule_id: str, **updates: Any) -> CEPRule | None:
        """기존 규칙을 부분 업데이트한다.

        존재하지 않는 rule_id이면 None을 반환한다.
        """
        existing = self._rules.get(rule_id)
        if existing is None:
            return None

        # 업데이트할 필드만 적용
        data = existing.model_dump()
        for key, value in updates.items():
            if value is not None and key in data:
                data[key] = value
        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        updated = CEPRule(**data)
        updated.validate_for_condition()
        self._rules[rule_id] = updated
        return updated

    def delete_rule(self, rule_id: str) -> bool:
        """규칙을 삭제한다. 이력도 함께 제거된다."""
        if rule_id not in self._rules:
            return False
        del self._rules[rule_id]
        self._history.pop(rule_id, None)
        return True

    # -----------------------------------------------------------------------
    # 평가 로직
    # -----------------------------------------------------------------------
    def evaluate_rule(self, rule: CEPRule, current_value: float | None) -> CEPResult:
        """규칙의 조건을 현재 값으로 평가한다.

        Args:
            rule: 평가할 CEP 규칙
            current_value: SQL 쿼리 결과 등에서 얻은 현재 값 (None이면 미트리거)

        Returns:
            CEPResult: 평가 결과 (triggered 여부 포함)
        """
        # 값이 None이면 평가 불가 → 미트리거
        if current_value is None:
            result = CEPResult(
                rule_name=rule.name,
                triggered=False,
                current_value=None,
                threshold=rule.threshold,
                message=f"[{rule.name}] 평가할 값이 없습니다 (None)",
                severity=rule.severity.value,
                condition_type=rule.condition_type.value,
            )
            self._record_history(rule.id, result)
            return result

        # NaN / Inf 방어
        if math.isnan(current_value) or math.isinf(current_value):
            result = CEPResult(
                rule_name=rule.name,
                triggered=False,
                current_value=current_value,
                threshold=rule.threshold,
                message=f"[{rule.name}] 유효하지 않은 값: {current_value}",
                severity=rule.severity.value,
                condition_type=rule.condition_type.value,
            )
            self._record_history(rule.id, result)
            return result

        triggered, message = self._check_condition(rule, current_value)

        result = CEPResult(
            rule_name=rule.name,
            triggered=triggered,
            current_value=current_value,
            threshold=rule.threshold,
            message=message,
            severity=rule.severity.value,
            condition_type=rule.condition_type.value,
        )
        self._record_history(rule.id, result)
        return result

    def _check_condition(
        self, rule: CEPRule, current_value: float
    ) -> tuple[bool, str]:
        """조건 유형별 판정 로직.

        Returns:
            (triggered: bool, message: str)
        """
        ct = rule.condition_type
        th = rule.threshold
        name = rule.name

        if ct == ConditionType.GT:
            assert isinstance(th, (int, float))
            triggered = current_value > th
            msg = (
                f"[{name}] {current_value} > {th} → 트리거"
                if triggered
                else f"[{name}] {current_value} <= {th} → 정상"
            )
            return triggered, msg

        if ct == ConditionType.LT:
            assert isinstance(th, (int, float))
            triggered = current_value < th
            msg = (
                f"[{name}] {current_value} < {th} → 트리거"
                if triggered
                else f"[{name}] {current_value} >= {th} → 정상"
            )
            return triggered, msg

        if ct == ConditionType.EQ:
            assert isinstance(th, (int, float))
            triggered = math.isclose(current_value, th, rel_tol=1e-9)
            msg = (
                f"[{name}] {current_value} == {th} → 트리거"
                if triggered
                else f"[{name}] {current_value} != {th} → 정상"
            )
            return triggered, msg

        if ct == ConditionType.NE:
            assert isinstance(th, (int, float))
            triggered = not math.isclose(current_value, th, rel_tol=1e-9)
            msg = (
                f"[{name}] {current_value} != {th} → 트리거"
                if triggered
                else f"[{name}] {current_value} == {th} → 정상"
            )
            return triggered, msg

        if ct == ConditionType.BETWEEN:
            assert isinstance(th, list) and len(th) == 2
            lo, hi = th[0], th[1]
            triggered = lo <= current_value <= hi
            msg = (
                f"[{name}] {lo} <= {current_value} <= {hi} → 범위 내 트리거"
                if triggered
                else f"[{name}] {current_value}이(가) [{lo}, {hi}] 범위 밖 → 정상"
            )
            return triggered, msg

        if ct == ConditionType.CHANGE_RATE:
            # 이전 값 대비 변화율(%) 계산
            assert isinstance(th, (int, float))
            previous_value = self._get_last_value(rule.id)
            if previous_value is None:
                # 첫 평가는 비교 대상 없음 → 미트리거
                return (
                    False,
                    f"[{name}] 첫 번째 평가 — 이전 값 없음, 변화율 계산 불가",
                )
            if previous_value == 0:
                # 0→비0은 무한대 변화율로 간주 → 트리거
                if current_value != 0:
                    return (
                        True,
                        f"[{name}] 이전 값 0 → {current_value} (무한대 변화율) → 트리거",
                    )
                return (
                    False,
                    f"[{name}] 이전 값 0 → 0, 변화 없음 → 정상",
                )

            change_pct = abs((current_value - previous_value) / previous_value) * 100
            triggered = change_pct > th
            msg = (
                f"[{name}] 변화율 {change_pct:.2f}% > {th}% → 트리거"
                if triggered
                else f"[{name}] 변화율 {change_pct:.2f}% <= {th}% → 정상"
            )
            return triggered, msg

        # 알 수 없는 조건 유형
        return False, f"[{name}] 알 수 없는 조건: {ct}"

    # -----------------------------------------------------------------------
    # 이력 관리
    # -----------------------------------------------------------------------
    def _record_history(self, rule_id: str, result: CEPResult) -> None:
        """평가 결과를 이력에 추가한다."""
        if rule_id not in self._history:
            self._history[rule_id] = deque(maxlen=_MAX_HISTORY_PER_RULE)
        self._history[rule_id].append(result)

    def _get_last_value(self, rule_id: str) -> float | None:
        """해당 규칙의 가장 최근 평가에서 사용된 current_value를 반환한다.

        change_rate 조건에서 이전 값 참조용.
        """
        history = self._history.get(rule_id)
        if not history:
            return None
        # 가장 최근 결과에서 유효한 값 찾기
        for result in reversed(history):
            if result.current_value is not None:
                return result.current_value
        return None

    def get_history(self, rule_name: str) -> list[CEPResult]:
        """규칙 이름으로 평가 이력을 조회한다.

        이름으로 조회하므로 규칙 ID를 먼저 찾는다.
        일치하는 규칙이 없으면 빈 리스트를 반환한다.
        """
        for rule_id, rule in self._rules.items():
            if rule.name == rule_name:
                return list(self._history.get(rule_id, []))
        return []

    def get_history_by_id(self, rule_id: str) -> list[CEPResult]:
        """규칙 ID로 평가 이력을 조회한다."""
        return list(self._history.get(rule_id, []))

    def clear_history(self, rule_id: str) -> None:
        """특정 규칙의 평가 이력을 초기화한다."""
        if rule_id in self._history:
            self._history[rule_id].clear()

    # -----------------------------------------------------------------------
    # 통계
    # -----------------------------------------------------------------------
    def get_stats(self) -> dict:
        """엔진 전체 통계를 반환한다."""
        total_rules = len(self._rules)
        enabled_rules = sum(1 for r in self._rules.values() if r.enabled)
        total_evaluations = sum(len(h) for h in self._history.values())
        total_triggered = sum(
            sum(1 for r in h if r.triggered) for h in self._history.values()
        )
        return {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "disabled_rules": total_rules - enabled_rules,
            "total_evaluations": total_evaluations,
            "total_triggered": total_triggered,
            "trigger_rate": (
                round(total_triggered / total_evaluations, 4)
                if total_evaluations > 0
                else 0.0
            ),
        }


# ---------------------------------------------------------------------------
# 모듈 수준 싱글턴 (프로세스 내 공유)
# ---------------------------------------------------------------------------
_engine: CEPEngine | None = None


def get_cep_engine() -> CEPEngine:
    """프로세스 내 CEP 엔진 싱글턴을 반환한다."""
    global _engine
    if _engine is None:
        _engine = CEPEngine()
    return _engine


def reset_cep_engine() -> None:
    """테스트용: 싱글턴 엔진을 초기화한다."""
    global _engine
    _engine = None
