from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from app.api.analytics import router as analytics_router
from app.api.analytics_v3 import router as analytics_v3_router
from app.api.olap import router as olap_router
from app.api.root_cause import router as root_cause_router
from app.api.what_if import router as what_if_router
from app.services.vision_runtime import vision_runtime

app = FastAPI(title="Axiom Vision", version="1.0.0")

# 기존 /analytics* 엔드포인트(테스트·내부 용도)와
# /api/v3/analytics* 풀스펙 엔드포인트를 모두 제공한다.
app.include_router(analytics_router)
app.include_router(analytics_v3_router)
app.include_router(what_if_router)
app.include_router(olap_router)
app.include_router(root_cause_router)


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
