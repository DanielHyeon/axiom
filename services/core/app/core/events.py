import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base_models import EventOutbox
from app.core.middleware import get_current_tenant_id
from app.core.event_contract_registry import EventContractError, enforce_event_contract
from app.core.observability import metrics_registry

class EventPublisher:
    @staticmethod
    def _detect_legacy_write_violation(event_type: str, aggregate_type: str, payload: dict) -> bool:
        if bool(payload.get("legacy_write")):
            return True
        if event_type.upper().startswith("LEGACY_"):
            return True
        if aggregate_type.lower().startswith("legacy"):
            return True
        return False

    @staticmethod
    async def publish(
        session: AsyncSession,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict,
        tenant_id: str | None = None,
    ):
        """
        Inserts an event into the outbox table within the SAME transaction
        as the business logic updates. tenant_id가 없으면 요청 컨텍스트의 tenant 사용.
        """
        try:
            safe_payload = enforce_event_contract(event_type=event_type, payload=payload, aggregate_id=aggregate_id)
        except EventContractError:
            raise

        if EventPublisher._detect_legacy_write_violation(event_type=event_type, aggregate_type=aggregate_type, payload=safe_payload):
            metrics_registry.inc("core_legacy_write_violations_total")
            safe_payload["legacy_policy"] = {
                "violation_detected": True,
                "policy": "legacy-data-isolation-policy",
                "action": "detected",
            }

        tid = tenant_id if tenant_id is not None else get_current_tenant_id()
        outbox_entry = EventOutbox(
            id=str(uuid.uuid4()),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=safe_payload,
            status="PENDING",
            tenant_id=tid,
        )
        session.add(outbox_entry)
