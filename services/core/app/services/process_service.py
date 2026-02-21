import enum
import uuid
from typing import Optional, Dict
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.base_models import WorkItem
from app.core.events import EventPublisher

class WorkItemStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    DONE = "DONE"
    REWORK = "REWORK"
    CANCELLED = "CANCELLED"

class AgentMode(str, enum.Enum):
    MANUAL = "MANUAL"
    SUPERVISED = "SUPERVISED"
    AUTONOMOUS = "AUTONOMOUS"
    SELF_VERIFY = "SELF_VERIFY"

class WorkItemUpdateModel(BaseModel):
    workitem_id: str
    result_data: Optional[Dict] = None

class ProcessService:
    @staticmethod
    async def initiate_process(
        db: AsyncSession,
        proc_def_id: str,
        input_data: Optional[dict] = None,
    ) -> dict:
        proc_inst_id = str(uuid.uuid4())
        workitem_id = str(uuid.uuid4())
        seed_activity = (input_data or {}).get("initial_activity_name", "Initial Review")
        tenant_id = (input_data or {}).get("tenant_id", "default")

        workitem = WorkItem(
            id=workitem_id,
            proc_inst_id=proc_inst_id,
            activity_name=seed_activity,
            status=WorkItemStatus.TODO,
            tenant_id=tenant_id,
            result_data={"proc_def_id": proc_def_id, "input": input_data or {}},
            version=1,
        )
        db.add(workitem)
        await EventPublisher.publish(
            session=db,
            event_type="PROCESS_INITIATED",
            aggregate_type="process",
            aggregate_id=proc_inst_id,
            payload={"proc_def_id": proc_def_id, "workitem_id": workitem_id},
        )
        return {
            "proc_inst_id": proc_inst_id,
            "status": "RUNNING",
            "current_workitems": [
                {
                    "workitem_id": workitem_id,
                    "activity_name": seed_activity,
                    "status": WorkItemStatus.TODO,
                }
            ],
        }

    @staticmethod
    async def submit_workitem(db: AsyncSession, item_id: str, submit_data: dict) -> dict:
        """
        Submits a workitem, advancing its state depending on the agent_mode.
        For MANUAL mode: TODO -> IN_PROGRESS -> DONE
        For SUPERVISED mode: IN_PROGRESS -> SUBMITTED
        """
        result = await db.execute(select(WorkItem).where(WorkItem.id == item_id))
        workitem = result.scalar_one_or_none()

        if not workitem:
            raise ValueError("WorkItem not found")

        if workitem.status in [WorkItemStatus.DONE, WorkItemStatus.CANCELLED]:
            raise ValueError(f"Cannot submit a workitem in state: {workitem.status}")

        # Basic state transition logic
        next_status = WorkItemStatus.DONE
        workitem.status = next_status
        workitem.result_data = submit_data.get("result_data", {})
        workitem.version += 1
        
        # Insert event into outbox atomically
        await EventPublisher.publish(
            session=db,
            event_type="WORKITEM_COMPLETED",
            aggregate_type="workitem",
            aggregate_id=item_id,
            payload={"result": workitem.result_data}
        )
        
        # Explicit commit expected to be handled by caller/router
        
        return {
            "workitem_id": item_id,
            "status": next_status,
            "tenant_id": workitem.tenant_id
        }

    @staticmethod
    async def approve_hitl(db: AsyncSession, item_id: str, approved: bool, feedback: str = "") -> dict:
        if not approved and not feedback:
            raise ValueError("Feedback is required when rejecting a workitem.")

        result = await db.execute(select(WorkItem).where(WorkItem.id == item_id))
        workitem = result.scalar_one_or_none()
        if not workitem:
            raise ValueError("WorkItem not found")

        next_status = WorkItemStatus.DONE if approved else WorkItemStatus.REWORK
        workitem.status = next_status
        existing = workitem.result_data or {}
        existing["hitl_feedback"] = feedback
        workitem.result_data = existing
        workitem.version += 1
        return {
            "workitem_id": item_id,
            "status": next_status,
            "feedback_captured": bool(feedback)
        }

    @staticmethod
    async def get_process_status(db: AsyncSession, proc_inst_id: str) -> dict:
        result = await db.execute(select(WorkItem).where(WorkItem.proc_inst_id == proc_inst_id))
        workitems = result.scalars().all()
        if not workitems:
            raise ValueError("Process instance not found")

        states = {w.status for w in workitems}
        if WorkItemStatus.REWORK in states:
            status = "REWORK"
        elif states == {WorkItemStatus.DONE}:
            status = "COMPLETED"
        else:
            status = "RUNNING"

        return {
            "proc_inst_id": proc_inst_id,
            "status": status,
            "workitem_count": len(workitems),
        }

    @staticmethod
    async def get_workitems(db: AsyncSession, proc_inst_id: str) -> list[dict]:
        result = await db.execute(select(WorkItem).where(WorkItem.proc_inst_id == proc_inst_id))
        workitems = result.scalars().all()
        if not workitems:
            raise ValueError("Process instance not found")

        return [
            {
                "workitem_id": item.id,
                "activity_name": item.activity_name,
                "status": item.status,
                "result_data": item.result_data,
            }
            for item in workitems
        ]

    @staticmethod
    async def rework_workitem(
        db: AsyncSession, item_id: str, reason: str, revert_to_activity_id: Optional[str] = None
    ) -> dict:
        result = await db.execute(select(WorkItem).where(WorkItem.id == item_id))
        workitem = result.scalar_one_or_none()
        if not workitem:
            raise ValueError("WorkItem not found")

        workitem.status = WorkItemStatus.TODO
        payload = workitem.result_data or {}
        payload["rework_reason"] = reason
        payload["revert_to_activity_id"] = revert_to_activity_id
        workitem.result_data = payload
        workitem.version += 1

        return {
            "workitem_id": item_id,
            "status": WorkItemStatus.TODO,
            "reason": reason,
            "reworked_from": revert_to_activity_id,
        }
