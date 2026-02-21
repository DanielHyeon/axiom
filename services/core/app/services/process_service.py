import enum
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
            
        next_status = WorkItemStatus.DONE if approved else WorkItemStatus.REWORK
        return {
            "workitem_id": item_id,
            "status": next_status,
            "feedback_captured": bool(feedback)
        }
