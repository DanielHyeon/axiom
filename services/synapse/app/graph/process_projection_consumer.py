"""
프로세스 그래프 Projection Consumer.

Phase 3: Redis Streams에서 process.* 이벤트를 소비하여 Neo4j에 투영.
7종 이벤트 처리: definition.created/updated, version.published,
steps.bulk_upserted, relation.created/deleted, transitions.bulk_upserted.
"""
from __future__ import annotations

import json
import structlog

from app.core.neo4j_client import Neo4jClient
from app.graph.process_definition_projector import ProcessDefinitionProjector

logger = structlog.get_logger()

# 이벤트 타입 → 처리 핸들러 매핑
EVENT_HANDLERS = {
    "process.definition.created",
    "process.definition.updated",
    "process.version.published",
    "process.steps.bulk_upserted",
    "process.relation.created",
    "process.relation.deleted",
    "process.transitions.bulk_upserted",
}


class ProcessProjectionConsumer:
    """Redis Streams process.* 이벤트 소비자.

    Synapse main.py startup에서 백그라운드 태스크로 실행한다.
    """

    def __init__(self, neo4j: Neo4jClient, redis):
        self.neo4j = neo4j
        self.redis = redis
        self.projector = ProcessDefinitionProjector(neo4j)
        self.stream_name = "axiom:core:events"
        self.consumer_group = "synapse-process-projection"
        self.consumer_name = "synapse-projector-1"

    async def initialize(self) -> None:
        """Consumer group 생성 (이미 존재하면 무시)."""
        try:
            await self.redis.xgroup_create(
                self.stream_name, self.consumer_group, id="0", mkstream=True,
            )
        except Exception:
            pass  # 이미 존재
        logger.info("process_projection_consumer_initialized", stream=self.stream_name)

    async def consume_once(self, count: int = 100) -> int:
        """이벤트 배치 1회 소비. 처리 건수를 반환한다."""
        entries = await self.redis.xreadgroup(
            self.consumer_group, self.consumer_name,
            {self.stream_name: ">"}, count=count, block=5000,
        )
        if not entries:
            return 0

        processed = 0
        for stream, messages in entries:
            for msg_id, fields in messages:
                event_type = fields.get(b"event_type", b"").decode()
                if event_type not in EVENT_HANDLERS:
                    # 프로세스 그래프와 무관한 이벤트 — ACK만 하고 skip
                    await self.redis.xack(self.stream_name, self.consumer_group, msg_id)
                    continue

                try:
                    payload = json.loads(fields.get(b"payload", b"{}"))
                    await self._dispatch(event_type, payload, fields)
                    await self.redis.xack(self.stream_name, self.consumer_group, msg_id)
                    processed += 1
                except Exception:
                    logger.error("projection_event_failed", event_type=event_type, msg_id=msg_id, exc_info=True)
                    # ACK하지 않음 → pending 상태로 재시도 대상

        return processed

    async def _dispatch(self, event_type: str, payload: dict, fields: dict) -> None:
        """이벤트 타입에 따라 적절한 projector 메서드 호출."""
        tenant_id = fields.get(b"tenant_id", b"").decode()

        if event_type in ("process.definition.created", "process.definition.updated"):
            await self.projector.upsert_definition(payload)

        elif event_type == "process.version.published":
            await self.projector.upsert_version(payload)

        elif event_type == "process.steps.bulk_upserted":
            version_id = payload.get("versionId", "")
            steps = payload.get("steps", [])
            await self.projector.upsert_steps(version_id, tenant_id, steps)

        elif event_type == "process.relation.created":
            await self.projector.upsert_relation(payload)

        elif event_type == "process.relation.deleted":
            edge_id = payload.get("edgeId", "")
            await self.projector.soft_delete_relation(edge_id, tenant_id)

        elif event_type == "process.transitions.bulk_upserted":
            transitions = payload.get("transitions", [])
            await self.projector.upsert_transitions(tenant_id, transitions)
