import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base_models import EventOutbox
from app.core.middleware import get_current_tenant_id

class EventPublisher:
    @staticmethod
    async def publish(
        session: AsyncSession,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict
    ):
        """
        Inserts an event into the outbox table within the SAME transaction
        as the business logic updates.
        """
        outbox_entry = EventOutbox(
            id=str(uuid.uuid4()),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            status="PENDING",
            tenant_id=get_current_tenant_id()
        )
        session.add(outbox_entry)
