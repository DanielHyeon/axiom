"""
트윈 상태 계산기.

Phase 4: TwinEvent로부터 TwinState를 파생 계산한다.
건강도 점수, SLA 상태, 대기열 크기, 예외율 등을 계산.
"""
from __future__ import annotations

from decimal import Decimal


def calculate_health_score(
    overdue_ratio: float,
    exception_rate: float,
    queue_pressure: float,
    cycle_time_breach: float,
) -> Decimal:
    """건강도 점수 계산 (0~100)."""
    score = (
        100.0
        - overdue_ratio * 25.0
        - exception_rate * 30.0
        - queue_pressure * 20.0
        - cycle_time_breach * 25.0
    )
    return Decimal(str(max(0.0, min(100.0, score)))).quantize(Decimal("0.01"))


def determine_sla_status(overdue_ratio: float) -> str:
    """SLA 상태 판정."""
    if overdue_ratio > 0.15:
        return "BREACHED"
    if overdue_ratio > 0.05:
        return "AT_RISK"
    return "ON_TRACK"


def determine_state_code(health_score: Decimal) -> str:
    """건강도 기반 상태 코드 결정."""
    score = float(health_score)
    if score >= 80:
        return "HEALTHY"
    if score >= 60:
        return "DEGRADED"
    if score >= 40:
        return "WAITING"
    if score >= 20:
        return "BLOCKED"
    return "FAILED"
