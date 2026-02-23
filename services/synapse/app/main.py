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
from app.events.consumer import run_ontology_ingest_consumer
import structlog

logger = structlog.get_logger()

_ingest_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ingest_task
    logger.info("synapse_startup")
    try:
        _bootstrap = Neo4jBootstrap(neo4j_client)
        await _bootstrap.initialize()
    except Exception as e:
        logger.error("neo4j_bootstrap_error", error=str(e))
        raise
    if get_redis() is not None:
        _ingest_task = asyncio.create_task(run_ontology_ingest_consumer())
    yield
    logger.info("synapse_shutdown")
    if _ingest_task is not None and not _ingest_task.done():
        _ingest_task.cancel()
        try:
            await _ingest_task
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
