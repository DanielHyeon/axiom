from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


async def _seed_demo_ontology() -> None:
    """Seed demo ontology data for case 00000000-0000-4000-a000-000000000100 (manufacturing process analysis)."""
    from app.api.ontology import ontology_service

    _CASE_ID = "00000000-0000-4000-a000-000000000100"
    _TENANT_ID = "00000000-0000-0000-0000-000000000001"

    # Skip if already seeded
    existing = await ontology_service.get_case_ontology(_CASE_ID, limit=1)
    if existing["summary"]["total_nodes"] > 0:
        logger.info("demo_ontology_already_seeded", case_id=_CASE_ID)
        return

    payload = {
        "case_id": _CASE_ID,
        "entities": [
            # KPI layer
            {"id": "kpi-oee", "layer": "kpi", "label": "Kpi", "properties": {"name": "OEE (Overall Equipment Effectiveness)", "unit": "%", "target": 85}},
            {"id": "kpi-throughput", "layer": "kpi", "label": "Kpi", "properties": {"name": "Throughput Rate", "unit": "units/hr", "target": 500}},
            {"id": "kpi-defect-rate", "layer": "kpi", "label": "Kpi", "properties": {"name": "Defect Rate", "unit": "%", "target": 2}},
            {"id": "kpi-downtime", "layer": "kpi", "label": "Kpi", "properties": {"name": "Unplanned Downtime", "unit": "hours", "target": 10}},
            # Measure layer
            {"id": "msr-availability", "layer": "measure", "label": "Measure", "properties": {"name": "Availability Rate", "formula": "uptime / planned_time"}},
            {"id": "msr-performance", "layer": "measure", "label": "Measure", "properties": {"name": "Performance Efficiency", "formula": "actual_output / ideal_output"}},
            {"id": "msr-quality", "layer": "measure", "label": "Measure", "properties": {"name": "Quality Rate", "formula": "good_count / total_count"}},
            {"id": "msr-cycle-time", "layer": "measure", "label": "Measure", "properties": {"name": "Average Cycle Time", "unit": "seconds"}},
            {"id": "msr-mtbf", "layer": "measure", "label": "Measure", "properties": {"name": "MTBF (Mean Time Between Failures)", "unit": "hours"}},
            # Process layer
            {"id": "proc-assembly", "layer": "process", "label": "Process", "properties": {"name": "Assembly Line", "stage": "production"}},
            {"id": "proc-inspection", "layer": "process", "label": "Process", "properties": {"name": "Quality Inspection", "stage": "quality"}},
            {"id": "proc-packaging", "layer": "process", "label": "Process", "properties": {"name": "Packaging & Shipping", "stage": "logistics"}},
            {"id": "proc-maintenance", "layer": "process", "label": "Process", "properties": {"name": "Preventive Maintenance", "stage": "support"}},
            {"id": "proc-material-prep", "layer": "process", "label": "Process", "properties": {"name": "Material Preparation", "stage": "pre-production"}},
            # Resource layer
            {"id": "res-machine-a", "layer": "resource", "label": "Resource", "properties": {"name": "CNC Machine A", "type": "equipment"}},
            {"id": "res-machine-b", "layer": "resource", "label": "Resource", "properties": {"name": "Robot Arm B", "type": "equipment"}},
            {"id": "res-operator", "layer": "resource", "label": "Resource", "properties": {"name": "Production Operators", "type": "human"}},
            {"id": "res-material", "layer": "resource", "label": "Resource", "properties": {"name": "Raw Materials", "type": "material"}},
            {"id": "res-sensor", "layer": "resource", "label": "Resource", "properties": {"name": "IoT Sensor Array", "type": "equipment"}},
        ],
        "relations": [
            # KPI ← Measure (KPI is derived from measures)
            {"source_id": "kpi-oee", "target_id": "msr-availability", "type": "DERIVED_FROM"},
            {"source_id": "kpi-oee", "target_id": "msr-performance", "type": "DERIVED_FROM"},
            {"source_id": "kpi-oee", "target_id": "msr-quality", "type": "DERIVED_FROM"},
            {"source_id": "kpi-throughput", "target_id": "msr-cycle-time", "type": "DERIVED_FROM"},
            {"source_id": "kpi-defect-rate", "target_id": "msr-quality", "type": "DERIVED_FROM"},
            {"source_id": "kpi-downtime", "target_id": "msr-mtbf", "type": "DERIVED_FROM"},
            # Measure ← Process (measures are observed from processes)
            {"source_id": "msr-availability", "target_id": "proc-assembly", "type": "OBSERVED_IN"},
            {"source_id": "msr-performance", "target_id": "proc-assembly", "type": "OBSERVED_IN"},
            {"source_id": "msr-quality", "target_id": "proc-inspection", "type": "OBSERVED_IN"},
            {"source_id": "msr-cycle-time", "target_id": "proc-assembly", "type": "OBSERVED_IN"},
            {"source_id": "msr-mtbf", "target_id": "proc-maintenance", "type": "OBSERVED_IN"},
            # Process → Process (flow)
            {"source_id": "proc-material-prep", "target_id": "proc-assembly", "type": "PRECEDES"},
            {"source_id": "proc-assembly", "target_id": "proc-inspection", "type": "PRECEDES"},
            {"source_id": "proc-inspection", "target_id": "proc-packaging", "type": "PRECEDES"},
            {"source_id": "proc-maintenance", "target_id": "proc-assembly", "type": "SUPPORTS"},
            # Process ← Resource (resources are used by processes)
            {"source_id": "proc-assembly", "target_id": "res-machine-a", "type": "USES"},
            {"source_id": "proc-assembly", "target_id": "res-machine-b", "type": "USES"},
            {"source_id": "proc-assembly", "target_id": "res-operator", "type": "USES"},
            {"source_id": "proc-material-prep", "target_id": "res-material", "type": "USES"},
            {"source_id": "proc-inspection", "target_id": "res-sensor", "type": "USES"},
            {"source_id": "proc-maintenance", "target_id": "res-operator", "type": "USES"},
        ],
    }

    result = await ontology_service.extract_ontology(tenant_id=_TENANT_ID, payload=payload)
    logger.info("demo_ontology_seeded", case_id=_CASE_ID, stats=result["stats"])


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
    # Seed demo ontology data
    try:
        await _seed_demo_ontology()
    except Exception as e:
        logger.warning("demo_ontology_seed_failed", error=str(e))
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
# Middleware order: last added = first executed
# TenantMiddleware must run AFTER CORSMiddleware so CORS preflight isn't blocked
app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
