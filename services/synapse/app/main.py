from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.neo4j_client import neo4j_client
from app.graph.neo4j_bootstrap import Neo4jBootstrap
from app.core.middleware import TenantMiddleware
from app.api.graph import router as graph_router
from app.api.mining import router as mining_router
from app.api.ontology import router as ontology_router
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("synapse_startup")
    try:
        bootstrap = Neo4jBootstrap(neo4j_client)
        # await bootstrap.initialize() 
    except Exception as e:
        logger.error("neo4j_bootstrap_error", error=str(e))
    yield
    logger.info("synapse_shutdown")
    await neo4j_client.close()

app = FastAPI(title="Axiom Synapse", version="2.0.0", lifespan=lifespan)
app.add_middleware(TenantMiddleware)
app.include_router(graph_router)
app.include_router(mining_router)
app.include_router(ontology_router)

@app.get("/health/live")
async def health_live():
    return {"status": "alive"}

@app.get("/health")
async def health_check():
    neo4j_status = "unreachable"
    try:
        async with neo4j_client.session() as session:
            await session.run("RETURN 1")
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
