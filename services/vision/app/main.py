import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from app.api.analytics import router as analytics_router
from app.api.analytics_v3 import router as analytics_v3_router
from app.api.olap import router as olap_router
from app.api.root_cause import router as root_cause_router
from app.api.what_if import router as what_if_router
from app.services.vision_runtime import vision_runtime

logger = logging.getLogger("axiom.vision")


# ---------------------------------------------------------------------------
# Demo OLAP cubes — seeded so the OLAP Pivot page has selectable cubes
# ---------------------------------------------------------------------------
_DEMO_CUBES = [
    {
        "name": "매출분석",
        "fact_table": "sales",
        "dimensions": ["company_name", "department", "product_category", "region", "sale_date"],
        "measures": ["revenue", "cost", "quantity"],
        "measure_details": [
            {"name": "revenue", "column": "revenue", "aggregator": "sum", "format": "#,###"},
            {"name": "cost", "column": "cost", "aggregator": "sum", "format": "#,###"},
            {"name": "quantity", "column": "quantity", "aggregator": "sum", "format": "#,###"},
        ],
    },
    {
        "name": "운영분석",
        "fact_table": "operations",
        "dimensions": ["operation_type", "status", "region", "operator_name"],
        "measures": ["duration_minutes", "case_count"],
        "measure_details": [
            {"name": "duration_minutes", "column": "duration_minutes", "aggregator": "avg", "format": "#,##0.0"},
            {"name": "case_count", "column": "id", "aggregator": "count", "format": "#,###"},
        ],
    },
]


def _seed_demo_cubes() -> None:
    """Register demo cubes if not already present."""
    for cube_def in _DEMO_CUBES:
        if cube_def["name"] not in vision_runtime.cubes:
            vision_runtime.create_cube(
                cube_name=cube_def["name"],
                fact_table=cube_def["fact_table"],
                dimensions=cube_def["dimensions"],
                measures=cube_def["measures"],
                measure_details=cube_def.get("measure_details"),
            )
            logger.info("demo_cube_seeded: %s", cube_def["name"])


app = FastAPI(title="Axiom Vision", version="1.0.0")
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

# 기존 /analytics* 엔드포인트(테스트·내부 용도)와
# /api/v3/analytics* 풀스펙 엔드포인트를 모두 제공한다.
app.include_router(analytics_router)
app.include_router(analytics_v3_router)
app.include_router(what_if_router)
app.include_router(olap_router)
app.include_router(root_cause_router)

# ── DDD-P2-03: CaseEventConsumer background task ── #
_consumer_task: asyncio.Task | None = None
# ── DDD-P3-01: Vision Outbox Relay ── #
_relay_task: asyncio.Task | None = None
_relay_worker = None


@app.on_event("startup")
async def _seed_cubes_on_startup():
    """Register demo OLAP cubes so the pivot page has data to work with."""
    try:
        _seed_demo_cubes()
    except Exception:
        logger.warning("demo cube seeding failed", exc_info=True)


@app.on_event("startup")
async def _start_case_event_consumer():
    """CQRS 읽기 모델 갱신 워커를 백그라운드 태스크로 시작."""
    global _consumer_task
    if os.getenv("VISION_CQRS_CONSUMER_ENABLED", "true").lower() not in ("true", "1", "yes"):
        logger.info("CaseEventConsumer disabled via VISION_CQRS_CONSUMER_ENABLED")
        return
    try:
        from app.workers.case_event_consumer import CaseEventConsumer
        consumer = CaseEventConsumer()
        _consumer_task = asyncio.create_task(consumer.start())
        logger.info("CaseEventConsumer background task started")
    except Exception:
        logger.warning("CaseEventConsumer failed to start (redis may be unavailable)", exc_info=True)


@app.on_event("startup")
async def _start_vision_relay():
    """DDD-P3-01: Vision Outbox Relay 워커 시작."""
    global _relay_task, _relay_worker
    try:
        from app.events.outbox import VisionRelayWorker, ensure_outbox_table
        ensure_outbox_table()
        _relay_worker = VisionRelayWorker(poll_interval=5, max_batch=100)
        _relay_task = asyncio.create_task(_relay_worker.run())
        logger.info("VisionRelayWorker background task started")
    except Exception:
        logger.warning("VisionRelayWorker failed to start", exc_info=True)


@app.on_event("shutdown")
async def _stop_background_tasks():
    global _consumer_task, _relay_task, _relay_worker
    if _relay_worker is not None:
        _relay_worker.shutdown()
    for task in (_consumer_task, _relay_task):
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    logger.info("Vision background tasks stopped")


@app.get("/health")
async def health_check():
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    root_cause_metrics = vision_runtime.get_root_cause_operational_metrics()
    return {
        "status": "ready",
        "dependencies": {
            "llm": "up",
            "synapse": "up",
        },
        "root_cause_operational": {
            "calls_total": root_cause_metrics["calls_total"],
            "error_total": root_cause_metrics["error_total"],
            "failure_rate": root_cause_metrics["failure_rate"],
            "avg_latency_ms": root_cause_metrics["avg_latency_ms"],
        },
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return vision_runtime.render_root_cause_metrics_prometheus()
