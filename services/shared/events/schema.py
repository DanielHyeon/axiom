"""이벤트 공통 봉투 스키마 — 모든 이벤트가 이 형식을 따른다.

왜 봉투(Envelope)가 필요한가?
    - 이벤트를 받는 쪽에서 "이게 어떤 종류의 이벤트인지", "어디서 보낸 건지",
      "이전에 이미 처리한 건 아닌지"를 알 수 있어야 한다.
    - schema_version이 있어야 나중에 이벤트 형식이 바뀌어도
      옛날 이벤트와 새 이벤트를 구분해서 처리할 수 있다.

사용법:
    from shared.events import EventEnvelope

    envelope = EventEnvelope(
        event_type="QUALITY_SCORE_UPDATED",
        source_service="weaver",
        payload={"table_id": 123, "score": 0.85},
    )
    data = envelope.model_dump()
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    """이벤트 공통 봉투 — 모든 이벤트가 이 형식을 따른다.

    필드 설명:
        event_id:         이 이벤트의 고유 ID (자동 생성)
        event_type:       이벤트 종류 (예: "SEMANTIC_ENTITY_PUBLISHED")
        schema_version:   봉투 형식 버전 — 나중에 필드가 바뀌면 올린다
        source_service:   이벤트를 보낸 서비스 이름 (예: "weaver", "synapse")
        timestamp:        이벤트 생성 시각 (ISO 8601, UTC)
        idempotency_key:  중복 처리 방지용 키 — 같은 키면 같은 이벤트로 취급
        payload:          실제 데이터 (이벤트마다 내용이 다르다)
        tenant_id:        멀티테넌트 격리를 위한 테넌트 ID (선택)
        correlation_id:   요청 추적용 ID — request_id와 동일하게 설정 가능 (선택)
    """

    event_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="이벤트 고유 식별자 (UUID hex)",
    )
    event_type: str = Field(
        ...,
        description="이벤트 종류 (예: QUALITY_SCORE_UPDATED)",
    )
    schema_version: str = Field(
        default="1.0",
        description="봉투 스키마 버전 — 형식이 바뀌면 올린다",
    )
    source_service: str = Field(
        ...,
        description="이벤트를 발행한 서비스 이름",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="이벤트 생성 시각 (ISO 8601 UTC)",
    )
    idempotency_key: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="중복 처리 방지 키 — 같은 키의 이벤트는 한 번만 처리한다",
    )
    payload: dict = Field(
        default_factory=dict,
        description="이벤트 실제 데이터 (이벤트 종류마다 다르다)",
    )
    tenant_id: str | None = Field(
        default=None,
        description="멀티테넌트 격리를 위한 테넌트 ID (선택)",
    )
    correlation_id: str | None = Field(
        default=None,
        description="요청 추적용 ID (선택, request_id와 동일하게 사용)",
    )

    model_config = {"json_schema_extra": {"examples": [
        {
            "event_id": "a1b2c3d4e5f6",
            "event_type": "QUALITY_SCORE_UPDATED",
            "schema_version": "1.0",
            "source_service": "weaver",
            "timestamp": "2026-03-24T09:00:00+00:00",
            "idempotency_key": "f6e5d4c3b2a1",
            "payload": {"table_id": 123, "score": 0.85},
            "tenant_id": "tenant-001",
            "correlation_id": "req-abc-123",
        }
    ]}}
