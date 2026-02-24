"""WorkItem Lifecycle Application Service — state transitions via domain aggregate."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import ProcessDefinition
from app.models.base_models import WorkItem as WorkItemORM
from app.core.events import EventPublisher
from app.core.event_contract_registry import EventContractError
from app.core.self_verification import self_verification_harness
from app.modules.process.infrastructure.bpm.engine import get_next_activities_after
from app.modules.process.domain.aggregates.work_item import (
    AgentMode,
    WorkItem as WorkItemAggregate,
    WorkItemStatus,
)
from app.modules.process.domain.errors import AlreadyCompleted, InvalidStateTransition
from app.modules.process.infrastructure.mappers.work_item_mapper import WorkItemMapper

_mapper = WorkItemMapper()


class ProcessDomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


async def _publish_domain_events(
    session: AsyncSession,
    aggregate: WorkItemAggregate,
) -> None:
    """Drain domain events from aggregate and publish to Outbox."""
    event_type_map = {
        "WorkItemCreated": "WORKITEM_CREATED",
        "WorkItemStarted": "WORKITEM_STARTED",
        "WorkItemSubmitted": "WORKITEM_SELF_VERIFICATION_FAILED",
        "WorkItemCompleted": "WORKITEM_COMPLETED",
        "WorkItemCancelled": "WORKITEM_CANCELLED",
        "WorkItemReworkRequested": "WORKITEM_REWORK_REQUESTED",
        "HitlApproved": "WORKITEM_HITL_APPROVED",
        "HitlRejected": "WORKITEM_HITL_REJECTED",
    }
    for event in aggregate.collect_events():
        outbox_type = event_type_map.get(type(event).__name__, type(event).__name__)
        payload = {k: v for k, v in event.__dict__.items() if k != "occurred_at"}
        try:
            await EventPublisher.publish(
                session=session,
                event_type=outbox_type,
                aggregate_type="workitem",
                aggregate_id=aggregate.id,
                payload=payload,
            )
        except EventContractError:
            pass


class WorkItemLifecycleService:
    """Application service for WorkItem state transitions."""

    @staticmethod
    async def submit(
        db: AsyncSession,
        item_id: str,
        submit_data: dict,
        force_complete: bool = False,
    ) -> dict:
        result = await db.execute(select(WorkItemORM).where(WorkItemORM.id == item_id))
        orm = result.scalar_one_or_none()
        if not orm:
            raise ProcessDomainError(404, "WORKITEM_NOT_FOUND", "WorkItem not found")

        wi = _mapper.to_domain(orm)
        if wi.is_terminal:
            raise ProcessDomainError(409, "ALREADY_COMPLETED", f"Cannot submit in state {wi.status.value}")

        verification_outcome = self_verification_harness.evaluate(
            workitem_id=item_id,
            payload=submit_data if isinstance(submit_data, dict) else {},
            agent_mode=orm.agent_mode,
        )

        body = submit_data.get("result_data", submit_data)
        if not isinstance(body, dict):
            body = {"value": body}

        try:
            if verification_outcome.decision == "FAIL_ROUTE":
                wi.submit(result_data=body, verification_outcome=verification_outcome.as_dict())
                _mapper.to_orm(wi, orm)
                await _publish_domain_events(db, wi)
                return {
                    "workitem_id": item_id,
                    "status": WorkItemStatus.SUBMITTED,
                    "next_workitems": [],
                    "process_status": "RUNNING",
                    "is_process_completed": False,
                    "self_verification": verification_outcome.as_dict(),
                }

            wi.complete(
                result_data=body,
                force=force_complete,
                verification_outcome=(
                    verification_outcome.as_dict()
                    if verification_outcome.decision == "PASS"
                    else None
                ),
            )
        except (InvalidStateTransition, AlreadyCompleted) as e:
            raise ProcessDomainError(
                422 if isinstance(e, InvalidStateTransition) else 409,
                e.code, e.message,
            )

        _mapper.to_orm(wi, orm)

        # Flow advancement
        next_workitems: list[dict] = []
        process_status = "COMPLETED"
        is_process_completed = True

        if not force_complete:
            definition: dict = {}
            proc_def_id = wi.proc_def_id
            if proc_def_id:
                def_result = await db.execute(
                    select(ProcessDefinition).where(
                        ProcessDefinition.id == proc_def_id,
                        ProcessDefinition.tenant_id == wi.tenant_id,
                    )
                )
                proc_def_row = def_result.scalar_one_or_none()
                if proc_def_row:
                    definition = getattr(proc_def_row, "definition", None) or {}

            next_specs = get_next_activities_after(definition, wi.activity_name)
            for spec in next_specs:
                next_wi = WorkItemAggregate.create(
                    id=str(uuid.uuid4()),
                    proc_inst_id=wi.proc_inst_id,
                    activity_name=spec["activity_name"],
                    activity_type=spec["activity_type"],
                    agent_mode=AgentMode(spec["agent_mode"]),
                    tenant_id=wi.tenant_id,
                    result_data={
                        "proc_def_id": proc_def_id,
                        "input": (wi.result_data or {}).get("input", {}),
                    },
                )
                db.add(_mapper.to_new_orm(next_wi))
                await _publish_domain_events(db, next_wi)
                next_workitems.append({
                    "workitem_id": next_wi.id,
                    "activity_name": next_wi.activity_name,
                    "activity_type": next_wi.activity_type,
                    "agent_mode": next_wi.agent_mode.value,
                    "status": next_wi.status.value,
                })
            if next_workitems:
                process_status = "RUNNING"
                is_process_completed = False

        await _publish_domain_events(db, wi)

        return {
            "workitem_id": item_id,
            "status": WorkItemStatus.DONE,
            "next_workitems": next_workitems,
            "process_status": process_status,
            "is_process_completed": is_process_completed,
        }

    @staticmethod
    async def approve_hitl(db: AsyncSession, item_id: str, approved: bool, feedback: str = "") -> dict:
        if not approved and not feedback:
            raise ProcessDomainError(400, "MISSING_FEEDBACK", "Feedback is required when rejecting")

        result = await db.execute(select(WorkItemORM).where(WorkItemORM.id == item_id))
        orm = result.scalar_one_or_none()
        if not orm:
            raise ProcessDomainError(404, "WORKITEM_NOT_FOUND", "WorkItem not found")

        wi = _mapper.to_domain(orm)
        try:
            if approved:
                wi.approve_hitl(feedback=feedback)
            else:
                wi.reject_hitl(feedback=feedback)
        except (InvalidStateTransition, AlreadyCompleted) as e:
            raise ProcessDomainError(
                422 if isinstance(e, InvalidStateTransition) else 409,
                e.code, e.message,
            )

        _mapper.to_orm(wi, orm)
        await _publish_domain_events(db, wi)

        return {
            "workitem_id": item_id,
            "status": wi.status,
            "approved": approved,
            "feedback_captured": bool(feedback),
            "next_workitems": [],
        }

    @staticmethod
    async def get_feedback(db: AsyncSession, workitem_id: str) -> dict:
        result = await db.execute(select(WorkItemORM).where(WorkItemORM.id == workitem_id))
        workitem = result.scalar_one_or_none()
        if not workitem:
            raise ProcessDomainError(404, "WORKITEM_NOT_FOUND", "WorkItem not found")

        feedback = (workitem.result_data or {}).get("hitl_feedback")
        if not feedback:
            raise ProcessDomainError(404, "FEEDBACK_NOT_FOUND", "Feedback not found")

        return {
            "workitem_id": workitem.id,
            "feedback": feedback,
            "status": workitem.status,
        }

    @staticmethod
    async def list(
        db: AsyncSession,
        tenant_id: str,
        status: Optional[str] = None,
        assignee_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        stmt = select(WorkItemORM).where(WorkItemORM.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(WorkItemORM.status == status)
        if assignee_id:
            stmt = stmt.where(WorkItemORM.assignee_id == assignee_id)
        stmt = stmt.order_by(WorkItemORM.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        workitems = result.scalars().all()
        count_stmt = select(func.count()).select_from(WorkItemORM).where(WorkItemORM.tenant_id == tenant_id)
        if status:
            count_stmt = count_stmt.where(WorkItemORM.status == status)
        if assignee_id:
            count_stmt = count_stmt.where(WorkItemORM.assignee_id == assignee_id)
        total = (await db.execute(count_stmt)).scalar() or 0
        return {
            "items": [
                {
                    "workitem_id": item.id,
                    "proc_inst_id": item.proc_inst_id,
                    "activity_name": item.activity_name,
                    "activity_type": item.activity_type,
                    "assignee_id": item.assignee_id,
                    "agent_mode": item.agent_mode,
                    "status": item.status,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in workitems
            ],
            "total": total,
        }

    @staticmethod
    async def rework(
        db: AsyncSession, item_id: str, reason: str, revert_to_activity_id: Optional[str] = None
    ) -> dict:
        result = await db.execute(select(WorkItemORM).where(WorkItemORM.id == item_id))
        orm = result.scalar_one_or_none()
        if not orm:
            raise ProcessDomainError(404, "WORKITEM_NOT_FOUND", "WorkItem not found")

        branch_result = await db.execute(
            select(WorkItemORM).where(WorkItemORM.proc_inst_id == orm.proc_inst_id)
        )
        orm_items = branch_result.scalars().all()
        items = [_mapper.to_domain(o) for o in orm_items]
        orm_lookup = {o.id: o for o in orm_items}

        if items and all(
            i.status in (WorkItemStatus.DONE, WorkItemStatus.CANCELLED) for i in items
        ):
            raise ProcessDomainError(409, "PROCESS_COMPLETED", "Completed process cannot be reworked")

        target = next(i for i in items if i.id == item_id)
        target.reset_to_todo(reason=reason, revert_to_activity_id=revert_to_activity_id)
        _mapper.to_orm(target, orm_lookup[item_id])

        saga_compensations = []
        for item in items:
            if item.id == item_id:
                continue
            sibling_orm = orm_lookup[item.id]
            if item.status in (WorkItemStatus.DONE, WorkItemStatus.SUBMITTED):
                item.mark_rework()
                _mapper.to_orm(item, sibling_orm)
                saga_compensations.append({
                    "activity": item.activity_name or "unknown",
                    "status": "COMPENSATED",
                    "action": "결과 롤백",
                })
            elif item.status in (WorkItemStatus.TODO, WorkItemStatus.IN_PROGRESS):
                item.force_cancel()
                _mapper.to_orm(item, sibling_orm)
                saga_compensations.append({
                    "activity": item.activity_name or "unknown",
                    "status": "CANCELLED",
                    "action": "진행 중 작업 취소",
                })

        return {
            "workitem_id": item_id,
            "status": WorkItemStatus.TODO,
            "reason": reason,
            "reworked_from": revert_to_activity_id or item_id,
            "saga_compensations": saga_compensations,
        }
