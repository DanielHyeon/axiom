import asyncio
import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from app.api.datasource import router as datasource_router
from app.api.insight import router as insight_router
from app.api.insight_ontology import router as insight_ontology_router
from app.api.metadata_catalog import router as metadata_catalog_router
from app.api.query import router as query_router
from app.api.document_ingestion import router as document_ingestion_router
from app.api.auto_binding import router as auto_binding_router
from app.api.object_explorer import router as object_explorer_router
from app.api.instance_fetcher import router as instance_fetcher_router
from app.api.materialized_views import router as materialized_views_router
from app.api.quality import router as quality_router
from app.core.config import settings
from app.core.error_codes import public_error_message
from app.core.insight_errors import InsightError, insight_error_handler
from app.core.insight_redis import close_insight_redis, get_insight_redis
from app.core.logging import configure_secret_redaction
from app.services.metrics import metrics_service
from app.services.mindsdb_client import mindsdb_client
from app.services.synapse_metadata_client import synapse_metadata_client
from app.services.postgres_metadata_store import postgres_metadata_store
from app.services.weaver_runtime import weaver_runtime

logger = logging.getLogger("axiom.weaver")

configure_secret_redaction()

app = FastAPI(title="Axiom Weaver", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.weaver_cors_allowed_origins,
    allow_credentials=True,
    allow_methods=settings.weaver_cors_allowed_methods,
    allow_headers=settings.weaver_cors_allowed_headers,
)

app.add_exception_handler(InsightError, insight_error_handler)

app.include_router(datasource_router)
app.include_router(insight_router)
app.include_router(insight_ontology_router)
app.include_router(query_router)
app.include_router(metadata_catalog_router)
app.include_router(document_ingestion_router)
app.include_router(auto_binding_router)
app.include_router(object_explorer_router)
app.include_router(instance_fetcher_router)
app.include_router(materialized_views_router)
app.include_router(quality_router)

# ── DDD-P3-01: Weaver Outbox Relay ── #
_relay_task: asyncio.Task | None = None
_relay_worker = None


@app.on_event("startup")
async def _start_weaver_relay():
    """DDD-P3-01: Weaver Outbox Relay 워커 시작."""
    global _relay_task, _relay_worker
    if not settings.metadata_pg_mode:
        return
    try:
        from app.events.outbox import WeaverRelayWorker, ensure_outbox_table
        await ensure_outbox_table()
        _relay_worker = WeaverRelayWorker(poll_interval=5, max_batch=100)
        _relay_task = asyncio.create_task(_relay_worker.run())
        logger.info("WeaverRelayWorker background task started")
    except Exception:
        logger.warning("WeaverRelayWorker failed to start", exc_info=True)


@app.on_event("shutdown")
async def _stop_weaver_relay():
    global _relay_task, _relay_worker
    if _relay_worker is not None:
        _relay_worker.shutdown()
    if _relay_task and not _relay_task.done():
        _relay_task.cancel()
        try:
            await _relay_task
        except asyncio.CancelledError:
            pass


# ── 품질 수집 백그라운드 워커 ── #
_quality_task: asyncio.Task | None = None
_quality_worker = None


@app.on_event("startup")
async def _start_quality_worker():
    """주기적 품질 수집 워커 시작 (15분 주기)"""
    global _quality_task, _quality_worker
    if not settings.metadata_pg_mode:
        return
    try:
        from app.worker.quality_worker import QualityWorker
        _quality_worker = QualityWorker(poll_interval=900)
        _quality_task = asyncio.create_task(_quality_worker.run())
        logger.info("QualityWorker background task started (15min interval)")
    except Exception:
        logger.warning("QualityWorker failed to start", exc_info=True)


@app.on_event("shutdown")
async def _stop_quality_worker():
    global _quality_task, _quality_worker
    if _quality_worker is not None:
        _quality_worker.shutdown()
    if _quality_task and not _quality_task.done():
        _quality_task.cancel()
        try:
            await _quality_task
        except asyncio.CancelledError:
            pass


# ── P2 §4.5: Synapse 이벤트 기반 품질 스캔 트리거 ── #
_event_listener_task: asyncio.Task | None = None
_event_listener_running: bool = False

# Redis Stream 설정
_SYNAPSE_STREAM = "axiom:synapse:events"
_CONSUMER_GROUP = "weaver-quality"
_CONSUMER_NAME = "weaver-quality-worker-0"
_BLOCK_MS = 5000  # XREAD 블록 타임아웃 (5초)


async def _synapse_event_listener() -> None:
    """Synapse Redis Stream 이벤트 리스너.

    SEMANTIC_ENTITY_PUBLISHED 이벤트를 수신하면
    QualityWorker의 즉시 스캔을 트리거한다.
    """
    global _event_listener_running
    _event_listener_running = True
    rd = await get_insight_redis()
    if rd is None:
        logger.warning("synapse_event_listener: Redis 미사용 — 이벤트 리스너 비활성")
        return

    # 컨슈머 그룹 생성 (이미 존재하면 무시)
    try:
        await rd.xgroup_create(_SYNAPSE_STREAM, _CONSUMER_GROUP, id="0", mkstream=True)
        logger.info("synapse_event_listener: consumer group '%s' created", _CONSUMER_GROUP)
    except Exception as exc:
        # BUSYGROUP = 이미 존재 → 정상
        if "BUSYGROUP" in str(exc):
            logger.debug("synapse_event_listener: consumer group already exists")
        else:
            logger.warning("synapse_event_listener: xgroup_create failed: %s", exc)

    logger.info("synapse_event_listener started (stream=%s, group=%s)", _SYNAPSE_STREAM, _CONSUMER_GROUP)

    while _event_listener_running:
        try:
            # 미처리 메시지 읽기 (> = 새 메시지만)
            messages = await rd.xreadgroup(
                groupname=_CONSUMER_GROUP,
                consumername=_CONSUMER_NAME,
                streams={_SYNAPSE_STREAM: ">"},
                count=10,
                block=_BLOCK_MS,
            )
            if not messages:
                continue

            for stream_name, entries in messages:
                for msg_id, data in entries:
                    await _handle_synapse_event(rd, msg_id, data)

        except asyncio.CancelledError:
            logger.info("synapse_event_listener cancelled")
            break
        except Exception:
            logger.exception("synapse_event_listener_error")
            # 에러 후 잠시 대기하여 빠른 재시도 루프 방지
            await asyncio.sleep(2)

    _event_listener_running = False


async def _handle_synapse_event(rd, msg_id: str, data: dict) -> None:
    """개별 Synapse 이벤트 처리 — SEMANTIC_ENTITY_PUBLISHED만 반응"""
    event_type = data.get("event_type", "")

    if event_type != "SEMANTIC_ENTITY_PUBLISHED":
        # 관심 없는 이벤트 → ACK만 하고 넘어감
        await rd.xack(_SYNAPSE_STREAM, _CONSUMER_GROUP, msg_id)
        return

    tenant_id = data.get("tenant_id", "")
    # payload는 JSON 문자열일 수 있음
    payload_raw = data.get("payload", "{}")
    if isinstance(payload_raw, str):
        import json
        try:
            payload = json.loads(payload_raw)
        except (json.JSONDecodeError, TypeError):
            payload = {}
    else:
        payload = payload_raw

    entity_id = payload.get("entity_id", "") or data.get("aggregate_id", "")
    physical_source_ref = payload.get("physical_source_ref", "")

    if not all([tenant_id, entity_id, physical_source_ref]):
        logger.debug(
            "synapse_event: incomplete data, skipping (tenant=%s, entity=%s, ref=%s)",
            tenant_id, entity_id, physical_source_ref,
        )
        await rd.xack(_SYNAPSE_STREAM, _CONSUMER_GROUP, msg_id)
        return

    # QualityWorker를 통해 즉시 스캔 트리거
    if _quality_worker is not None:
        result = await _quality_worker.handle_entity_published(
            tenant_id=tenant_id,
            entity_id=entity_id,
            physical_source_ref=physical_source_ref,
        )
        logger.info(
            "synapse_event_processed",
            extra={"msg_id": msg_id, "event_type": event_type, "result": result},
        )
    else:
        logger.warning("synapse_event: QualityWorker not initialized, skipping")

    # 처리 완료 ACK
    await rd.xack(_SYNAPSE_STREAM, _CONSUMER_GROUP, msg_id)


@app.on_event("startup")
async def _start_synapse_event_listener():
    """P2 §4.5: Synapse 이벤트 기반 품질 스캔 리스너 시작"""
    global _event_listener_task
    if not settings.metadata_pg_mode:
        return
    try:
        _event_listener_task = asyncio.create_task(_synapse_event_listener())
        logger.info("Synapse event listener background task started")
    except Exception:
        logger.warning("Synapse event listener failed to start", exc_info=True)


@app.on_event("shutdown")
async def _stop_synapse_event_listener():
    global _event_listener_task, _event_listener_running
    _event_listener_running = False
    if _event_listener_task and not _event_listener_task.done():
        _event_listener_task.cancel()
        try:
            await _event_listener_task
        except asyncio.CancelledError:
            pass


# ── Phase 2-D: Document→Ontology 파이프라인 테이블 보장 ── #
@app.on_event("startup")
async def _ensure_document_tables():
    """문서 업로드 + DDD 추출 파이프라인용 테이블 생성 보장."""
    if not settings.metadata_pg_mode:
        return
    try:
        from app.db.document_schema import ensure_document_tables
        await ensure_document_tables()
    except Exception:
        logger.warning("Document tables DDL failed (non-fatal)", exc_info=True)


@app.on_event("startup")
async def _start_insight_redis():
    """Eagerly initialise the Insight Redis connection (non-fatal)."""
    try:
        await get_insight_redis()
    except Exception:
        logger.warning("Insight Redis init failed (non-fatal)", exc_info=True)


@app.on_event("shutdown")
async def _stop_insight_redis():
    await close_insight_redis()


@app.on_event("startup")
async def _cleanup_stale_insight_jobs():
    """Mark any 'running' insight jobs as failed after a server restart.

    Without this, jobs interrupted mid-flight remain in 'running' state
    forever (until their TTL expires) and block new requests from seeing
    a fresh result via the jobmap dedup key.
    """
    try:
        rd = await get_insight_redis()
        if rd is None:
            return
        from app.services.insight_job_store import finish_job
        count = 0
        async for key in rd.scan_iter("insight:job:*"):
            job = await rd.hgetall(key)
            if job and job.get("status") == "running":
                job_id = job.get("job_id", key.split(":")[-1])
                await finish_job(rd, job_id, error="server_restart")
                count += 1
        if count:
            logger.warning("Marked %d stale running insight job(s) as failed", count)
    except Exception:
        logger.warning("Insight job cleanup failed (non-fatal)", exc_info=True)


@app.on_event("startup")
async def hydrate_runtime_from_store():
    """Startup hydration: restore in-memory registries from PostgreSQL (DDD-P0-03).

    When metadata_pg_mode is enabled, loads datasources and glossary terms
    from PostgresMetadataStore into WeaverRuntime so data survives restarts.
    """
    if not settings.metadata_pg_mode:
        logger.info("Weaver startup: metadata_pg_mode disabled, skipping hydration")
        return
    try:
        # Hydrate datasources
        stats = await postgres_metadata_store.stats()
        ds_count = stats.get("datasources", 0)
        glossary_count = stats.get("glossary_terms", 0)
        logger.info(
            "Weaver startup: hydrating from PostgreSQL (datasources=%d, glossary=%d)",
            ds_count, glossary_count,
        )

        # Hydrate glossary terms
        terms = await postgres_metadata_store.list_glossary_terms()
        for term in terms:
            key = f"{term.get('tenant_id', '')}:{term['id']}"
            weaver_runtime.glossary[key] = term

        logger.info(
            "Weaver startup: hydration complete (glossary=%d terms loaded)",
            len(terms),
        )
    except Exception as exc:
        logger.warning("Weaver startup: hydration failed (non-fatal): %s", exc)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or f"req-{uuid.uuid4().hex}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


@app.get("/health")
async def health_check():
    return {"status": "alive"}


@app.get("/health/live")
async def health_live():
    return {"status": "alive"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return metrics_service.render_prometheus()


@app.get("/health/ready")
async def health_ready():
    dependencies: dict[str, str] = {
        "mindsdb": "disabled",
        "postgres": "disabled",
        "synapse_graph": "disabled",
    }
    details: dict[str, str] = {}

    if settings.external_mode:
        try:
            await mindsdb_client.health_check()
            dependencies["mindsdb"] = "up"
        except Exception as exc:
            dependencies["mindsdb"] = "down"
            details["mindsdb"] = public_error_message(exc)

    if settings.metadata_pg_mode:
        try:
            await postgres_metadata_store.health_check()
            dependencies["postgres"] = "up"
        except Exception as exc:
            dependencies["postgres"] = "down"
            details["postgres"] = public_error_message(exc)

    if settings.metadata_external_mode:
        try:
            await synapse_metadata_client.health_check()
            dependencies["synapse_graph"] = "up"
        except Exception as exc:
            dependencies["synapse_graph"] = "down"
            details["synapse_graph"] = public_error_message(exc)

    is_ready = all(state != "down" for state in dependencies.values())
    body = {
        "status": "ready" if is_ready else "degraded",
        "dependencies": dependencies,
        "details": details,
    }
    if is_ready:
        return body
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body)
