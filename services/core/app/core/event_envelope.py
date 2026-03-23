"""
멀티테넌트 프로세스 그래프 — EventEnvelope 표준.

Phase 0 (플랫폼 하드닝): 모든 도메인 이벤트가 준수하는 18필드 envelope 표준.
순수 dataclass로 구현하여 ORM 의존 없이 모든 서비스에서 import 가능.

NOTE: 이 envelope는 데이터 계약이며, 기존 EventPublisher/EventOutbox와의
      통합은 Phase 1에서 outbox 컬럼 ALTER 후 수행한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

SCHEMA_VERSION = "1.0"


@dataclass
class EventEnvelope:
    """18필드 이벤트 envelope 표준.

    twin_events DDL, event_outbox DDL과 1:1 대응한다.
    저장 레이어 전용 컬럼(source_channel, processing_status, published 등)은
    이 envelope에 포함하지 않는다.
    """
    # 필수 필드
    event_id: UUID
    event_type: str
    event_version: int
    schema_version: str
    tenant_id: str
    workspace_id: UUID | None
    aggregate_type: str
    aggregate_id: UUID
    ordering_key: str
    aggregate_seq: int
    idempotency_key: str
    occurred_at: datetime
    producer_service: str
    actor_user_id: str | None

    # 추적 필드
    trace_id: str
    correlation_id: UUID | None
    causation_id: UUID | None

    # 페이로드
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        tenant_id: str,
        aggregate_type: str,
        aggregate_id: UUID,
        aggregate_seq: int,
        idempotency_key: str,
        producer_service: str,
        payload: dict[str, Any] | None = None,
        workspace_id: UUID | None = None,
        actor_user_id: str | None = None,
        trace_id: str = "",
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        event_version: int = 1,
    ) -> EventEnvelope:
        """표준 기본값으로 envelope을 생성한다.

        event_id, occurred_at, schema_version, ordering_key는 자동 생성.
        """
        return cls(
            event_id=uuid4(),
            event_type=event_type,
            event_version=event_version,
            schema_version=SCHEMA_VERSION,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            ordering_key=f"{aggregate_type}:{aggregate_id}",
            aggregate_seq=aggregate_seq,
            idempotency_key=idempotency_key,
            occurred_at=datetime.now(timezone.utc),
            producer_service=producer_service,
            actor_user_id=actor_user_id,
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload=payload or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON 직렬화용 dict 변환. UUID→str, datetime→ISO."""
        def _ser(v: Any) -> Any:
            if isinstance(v, UUID):
                return str(v)
            if isinstance(v, datetime):
                return v.isoformat()
            return v

        return {
            "event_id": _ser(self.event_id),
            "event_type": self.event_type,
            "event_version": self.event_version,
            "schema_version": self.schema_version,
            "tenant_id": self.tenant_id,
            "workspace_id": _ser(self.workspace_id),
            "aggregate_type": self.aggregate_type,
            "aggregate_id": _ser(self.aggregate_id),
            "ordering_key": self.ordering_key,
            "aggregate_seq": self.aggregate_seq,
            "idempotency_key": self.idempotency_key,
            "occurred_at": _ser(self.occurred_at),
            "producer_service": self.producer_service,
            "actor_user_id": self.actor_user_id,
            "trace_id": self.trace_id,
            "correlation_id": _ser(self.correlation_id),
            "causation_id": _ser(self.causation_id),
            "payload": self.payload,
        }
