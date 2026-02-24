import asyncio
import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from app.api.datasource import router as datasource_router
from app.api.metadata_catalog import router as metadata_catalog_router
from app.api.query import router as query_router
from app.core.config import settings
from app.core.error_codes import public_error_message
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

app.include_router(datasource_router)
app.include_router(query_router)
app.include_router(metadata_catalog_router)

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
