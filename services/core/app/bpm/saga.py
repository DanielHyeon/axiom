"""
Saga 보상 트랜잭션 (bpm-engine.md §5).
실패 시 완료된 액티비티 역순 보상 실행. 현재는 스텁.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CompensationStep:
    activity_id: str
    activity_name: str
    compensation_action: str
    compensation_data: dict[str, Any]
    status: str = "PENDING"  # PENDING, EXECUTED, FAILED, SKIPPED


class SagaManager:
    """Saga 보상 트랜잭션 관리자. 실제 보상 실행은 추후 연동."""

    async def trigger_compensation(
        self,
        proc_inst_id: str,
        failed_activity_id: str,
        failure_reason: str,
    ) -> dict[str, Any]:
        """
        보상 트랜잭션 시작.
        현재: 완료된 액티비티 역순 조회/실행은 미구현; 상태만 반환.
        """
        return {
            "proc_inst_id": proc_inst_id,
            "failed_activity_id": failed_activity_id,
            "failure_reason": failure_reason,
            "status": "STUB",
            "message": "Saga compensation not yet implemented; manual intervention required.",
            "compensation_steps": [],
        }
