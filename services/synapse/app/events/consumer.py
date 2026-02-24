"""
Phase S7: Redis Streams 소비 — case.* 이벤트를 받아 온톨로지 인제스트 파이프라인 실행.
Core event-outbox → axiom:events 스트림, consumer group synapse_group.
"""
from __future__ import annotations

import asyncio
import json
import structlog

from app.core.redis_client import get_redis
from app.graph.ontology_ingest import OntologyIngestor

logger = structlog.get_logger()

STREAM_KEY = "axiom:core:events"
CONSUMER_GROUP = "synapse_group"
CONSUMER_NAME = "synapse-ingest-1"
BLOCK_MS = 5000
CASE_PREFIX = "case."


async def run_ontology_ingest_consumer() -> None:
    """Redis에서 case.* 이벤트를 읽어 OntologyIngestor로 처리 후 Neo4j MERGE."""
    redis = get_redis()
    if redis is None:
        logger.info("ontology_ingest_consumer_skipped", reason="REDIS_URL not set")
        return
    ingestor = OntologyIngestor()
    try:
        await redis.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True)
    except Exception:
        pass  # group already exists
    logger.info("ontology_ingest_consumer_started", stream=STREAM_KEY, group=CONSUMER_GROUP)
    while True:
        try:
            messages = await redis.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams={STREAM_KEY: ">"},
                count=10,
                block=BLOCK_MS,
            )
            for _stream, entries in messages:
                for entry_id, data in entries:
                    event_type = (data.get("event_type") or "").strip()
                    if not event_type.startswith(CASE_PREFIX):
                        await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
                        continue
                    payload_raw = data.get("payload") or "{}"
                    try:
                        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else (payload_raw or {})
                    except json.JSONDecodeError:
                        payload = {}
                    try:
                        result = await ingestor.process_event(event_type, payload)
                        if result.get("accepted"):
                            await ingestor.merge_from_ingest_result(
                                result.get("entities") or [],
                                result.get("relations") or [],
                            )
                            logger.info(
                                "ontology_ingest_event_processed",
                                event_type=event_type,
                                msg_id=entry_id,
                                case_id=result.get("case_id"),
                            )
                        else:
                            logger.debug(
                                "ontology_ingest_event_skipped",
                                event_type=event_type,
                                reason=result.get("reason"),
                            )
                    except Exception as e:
                        logger.error(
                            "ontology_ingest_event_failed",
                            event_type=event_type,
                            msg_id=entry_id,
                            error=str(e),
                        )
                    await redis.xack(STREAM_KEY, CONSUMER_GROUP, entry_id)
        except asyncio.CancelledError:
            logger.info("ontology_ingest_consumer_stopped", stream=STREAM_KEY)
            break
        except Exception as e:
            logger.error("ontology_ingest_consumer_error", error=str(e))
            await asyncio.sleep(5)
