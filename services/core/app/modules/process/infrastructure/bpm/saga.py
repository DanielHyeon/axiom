"""
Saga 보상 트랜잭션 (bpm-engine.md §5).
실패 시 완료된 액티비티 역순 보상 실행.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventPublisher
from app.core.event_contract_registry import EventContractError
from app.models.base_models import ProcessDefinition, WorkItem
from app.modules.process.application.process_service_facade import ProcessService
from app.modules.process.domain.aggregates.work_item import WorkItemStatus

logger = logging.getLogger("axiom.bpm")


@dataclass
class CompensationStep:
    activity_id: str
    activity_name: str
    compensation_action: str
    compensation_data: dict[str, Any]
    status: str = "PENDING"  # PENDING, EXECUTED, FAILED, SKIPPED


class SagaManager:
    """Saga 보상 트랜잭션 관리자. 완료된 Activity 역순 조회 → 보상 단계 실행 → 프로세스 종료 → 이벤트 발행."""

    async def trigger_compensation(
        self,
        db: AsyncSession,
        proc_inst_id: str,
        failed_workitem_id: str,
        failure_reason: str,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """
        보상 트랜잭션 시작.
        failed_workitem_id: 실패한 워크아이템 ID. 이 워크아이템보다 먼저 완료된 DONE 항목만 역순 보상.
        """
        # 1. 완료된 워크아이템 목록 (실패 항목 이전, created_at 오름차순)
        completed = await ProcessService.get_completed_workitems_for_compensation(
            db=db,
            proc_inst_id=proc_inst_id,
            before_workitem_id=failed_workitem_id,
        )
        if not completed:
            await self._update_process_status(db, proc_inst_id)
            await self._publish_event(db, proc_inst_id, failed_workitem_id, failure_reason, [], tenant_id)
            return {
                "proc_inst_id": proc_inst_id,
                "failed_workitem_id": failed_workitem_id,
                "failure_reason": failure_reason,
                "status": "TERMINATED",
                "compensation_steps": [],
            }

        # proc_def_id 및 정의 로드 (첫 워크아이템 result_data에서)
        proc_def_id = (completed[0].result_data or {}).get("proc_def_id")
        if not proc_def_id:
            for w in completed:
                proc_def_id = (w.result_data or {}).get("proc_def_id")
                if proc_def_id:
                    break
        if not proc_def_id:
            logger.warning("Saga: proc_def_id not found in workitem result_data, skipping compensation steps")
            compensation_steps: list[CompensationStep] = []
        else:
            def_result = await db.execute(select(ProcessDefinition).where(ProcessDefinition.id == proc_def_id))
            proc_def = def_result.scalar_one_or_none()
            definition = (proc_def.definition or {}) if proc_def else {}
            activities_by_name = {}
            for a in (definition.get("activities") or []):
                if isinstance(a, dict) and a.get("name"):
                    activities_by_name[a["name"]] = a

            # 2. 보상 단계 생성 (역순)
            compensation_steps = []
            for workitem in reversed(completed):
                activity_spec = activities_by_name.get(workitem.activity_name or "")
                compensation = activity_spec.get("compensation") if isinstance(activity_spec, dict) else None
                if not compensation:
                    step = CompensationStep(
                        activity_id=activity_spec.get("id", workitem.id) if isinstance(activity_spec, dict) else workitem.id,
                        activity_name=workitem.activity_name or "unknown",
                        compensation_action="",
                        compensation_data=(workitem.result_data or {}),
                        status="SKIPPED",
                    )
                    compensation_steps.append(step)
                    continue
                step = CompensationStep(
                    activity_id=activity_spec.get("id", workitem.id) if isinstance(activity_spec, dict) else workitem.id,
                    activity_name=workitem.activity_name or "unknown",
                    compensation_action=compensation,
                    compensation_data=(workitem.result_data or {}),
                )
                compensation_steps.append(step)

            # 3. 보상 실행
            results = []
            for step in compensation_steps:
                if step.status == "SKIPPED":
                    results.append({"step": step.activity_name, "status": "SKIPPED"})
                    continue
                try:
                    await self._execute_compensation(step)
                    step.status = "EXECUTED"
                    results.append({"step": step.activity_name, "status": "EXECUTED"})
                except Exception as e:
                    step.status = "FAILED"
                    logger.exception("Saga compensation failed: %s", e)
                    results.append({"step": step.activity_name, "status": "FAILED", "error": str(e)})
                    await self._notify_compensation_failure(proc_inst_id, step, str(e))

        # 4. 프로세스 상태 변경 (미완료 워크아이템 CANCELLED)
        await self._update_process_status(db, proc_inst_id)

        # 5. 이벤트 발행
        results_summary = [
            {"step": s.activity_name, "status": s.status}
            for s in compensation_steps
        ]
        await self._publish_event(db, proc_inst_id, failed_workitem_id, failure_reason, results_summary, tenant_id)

        return {
            "proc_inst_id": proc_inst_id,
            "failed_workitem_id": failed_workitem_id,
            "failure_reason": failure_reason,
            "status": "TERMINATED",
            "message": "Saga compensation completed.",
            "compensation_steps": results_summary,
        }

    async def _execute_compensation(self, step: CompensationStep) -> dict[str, Any]:
        """개별 보상 단계 실행. MCP 도구 호출 (mcp_client 미구현 시 no-op)."""
        if not step.compensation_action:
            return {}
        try:
            from app.orchestrator.mcp_client import execute_mcp_tool
            return await execute_mcp_tool(
                tool_name=step.compensation_action,
                parameters=step.compensation_data,
                timeout=30,
            )
        except ImportError:
            logger.debug("Saga: mcp_client not available, compensation step no-op: %s", step.activity_name)
            return {}
        except Exception as e:
            logger.warning("Saga: execute_mcp_tool failed for %s: %s", step.compensation_action, e)
            raise

    async def _notify_compensation_failure(self, proc_inst_id: str, step: CompensationStep, error: str) -> None:
        """보상 실패 알림 (Watch/이벤트 연동은 추후)."""
        logger.warning(
            "Saga compensation failure proc_inst_id=%s activity=%s error=%s",
            proc_inst_id,
            step.activity_name,
            error,
        )

    async def _update_process_status(self, db: AsyncSession, proc_inst_id: str) -> None:
        """미완료 워크아이템을 CANCELLED로 변경."""
        await ProcessService.terminate_process_instance(db=db, proc_inst_id=proc_inst_id)

    async def _publish_event(
        self,
        db: AsyncSession,
        proc_inst_id: str,
        failed_workitem_id: str,
        failure_reason: str,
        compensation_results: list[dict],
        tenant_id: str | None,
    ) -> None:
        """SAGA_COMPENSATION_COMPLETED 이벤트 발행."""
        payload = {
            "proc_inst_id": proc_inst_id,
            "failed_workitem_id": failed_workitem_id,
            "failure_reason": failure_reason,
            "compensation_results": compensation_results,
        }
        try:
            await EventPublisher.publish(
                session=db,
                event_type="SAGA_COMPENSATION_COMPLETED",
                aggregate_type="process",
                aggregate_id=proc_inst_id,
                payload=payload,
                tenant_id=tenant_id,
            )
        except EventContractError as err:
            logger.warning("Saga: event contract error for SAGA_COMPENSATION_COMPLETED: %s", err)
