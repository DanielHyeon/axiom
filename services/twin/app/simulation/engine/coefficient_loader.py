"""보정계수 로더 — simulation_coefficients 테이블에서 프로세스/단계별 계수를 로드."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.simulation.models.scenario import SimulationCoefficient

# 전역 기본값 (DB에 없을 때 사용)
DEFAULT_COEFFICIENTS: dict[str, dict[str, float]] = {
    "AUTOMATION_RATE_CHANGE": {"avg_cycle_time": -0.6, "exception_rate": -0.3},
    "RESOURCE_CAPACITY_CHANGE": {"queue_size": -0.4, "avg_wait_time": -0.5},
    "THRESHOLD_RULE_CHANGE": {"exception_rate": 0.2, "avg_cycle_time": 0.1},
    "PRIORITY_POLICY_CHANGE": {"avg_wait_time": -0.3, "queue_size": -0.2},
    "STEP_SLA_CHANGE": {"avg_cycle_time": -0.2, "exception_rate": -0.1},
    "ROUTING_RULE_CHANGE": {"avg_cycle_time": -0.15, "exception_rate": 0.05},
}


async def load_coefficients(
    session: AsyncSession,
    tenant_id: str,
    workspace_id: UUID,
    target_entity_id: UUID | None = None,
) -> dict[str, dict[str, float]]:
    """DB에서 보정계수를 로드한다. 없으면 전역 기본값 사용."""
    q = select(SimulationCoefficient).where(
        SimulationCoefficient.tenant_id == tenant_id,
        SimulationCoefficient.workspace_id == workspace_id,
        SimulationCoefficient.is_deleted == False,
    )
    if target_entity_id:
        q = q.where(SimulationCoefficient.target_entity_id == target_entity_id)

    result = await session.execute(q)
    rows = result.scalars().all()

    if not rows:
        return DEFAULT_COEFFICIENTS

    # DB 결과를 {change_type: {effect_metric: coefficient}} 구조로 변환
    coefficients: dict[str, dict[str, float]] = {}
    for row in rows:
        if row.change_type not in coefficients:
            coefficients[row.change_type] = {}
        coefficients[row.change_type][row.effect_metric] = float(row.coefficient)

    return coefficients
