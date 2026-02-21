from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("weaver.audit")


class AuditLogService:
    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def clear(self) -> None:
        self._events.clear()

    def list_events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def emit(
        self,
        *,
        action: str,
        actor_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        request_id: str | None = None,
        outcome: str = "success",
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "actor_id": actor_id,
            "tenant_id": tenant_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "request_id": request_id or "",
            "outcome": outcome,
            "duration_ms": duration_ms,
            "metadata": metadata or {},
        }
        self._events.append(event)
        logger.info("audit_event=%s", event)


audit_log_service = AuditLogService()
