from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from app.core.neo4j_client import neo4j_client
from app.core.redis_client import close_redis, get_redis
from app.graph.neo4j_bootstrap import Neo4jBootstrap
from app.core.middleware import TenantMiddleware
from app.api.graph import router as graph_router
from app.api.event_logs import router as event_logs_router
from app.api.extraction import router as extraction_router
from app.api.mining import router as mining_router
from app.api.ontology import router as ontology_router
from app.api.schema_edit import router as schema_edit_router
from app.api.metadata_graph import router as metadata_graph_router
from app.api.concept_mapping import router as concept_mapping_router
from app.events.consumer import run_ontology_ingest_consumer
from app.events.outbox import SynapseRelayWorker, ensure_outbox_table
import structlog

logger = structlog.get_logger()

_ingest_task: asyncio.Task | None = None
_relay_task: asyncio.Task | None = None
_relay_worker: SynapseRelayWorker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ingest_task, _relay_task, _relay_worker
    logger.info("synapse_startup")
    try:
        _bootstrap = Neo4jBootstrap(neo4j_client)
        await _bootstrap.initialize()
    except Exception as e:
        logger.error("neo4j_bootstrap_error", error=str(e))
        raise
    # DDD-P3-01: Outbox 테이블 보장 + Relay 워커 시작
    ensure_outbox_table()
    if get_redis() is not None:
        _ingest_task = asyncio.create_task(run_ontology_ingest_consumer())
        _relay_worker = SynapseRelayWorker(poll_interval=5, max_batch=100)
        _relay_task = asyncio.create_task(_relay_worker.run())
    yield
    logger.info("synapse_shutdown")
    if _relay_worker is not None:
        _relay_worker.shutdown()
    for task in (_ingest_task, _relay_task):
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    await close_redis()
    await neo4j_client.close()

app = FastAPI(title="Axiom Synapse", version="2.0.0", lifespan=lifespan)
app.add_middleware(TenantMiddleware)
app.include_router(graph_router)
app.include_router(event_logs_router)
app.include_router(extraction_router)
app.include_router(mining_router)
app.include_router(ontology_router)
app.include_router(schema_edit_router)
app.include_router(metadata_graph_router)
app.include_router(concept_mapping_router)

@app.get("/health/live")
async def health_live():
    return {"status": "alive"}

@app.get("/health")
async def health_check():
    neo4j_status = "unreachable"
    try:
        async with neo4j_client.session() as session:
            await asyncio.wait_for(session.run("RETURN 1"), timeout=1.0)
            neo4j_status = "healthy"
    except Exception:
        pass
        
    all_healthy = neo4j_status == "healthy"
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": {
            "neo4j": neo4j_status == "healthy"
        },
        "version": "2.0.0"
    }
