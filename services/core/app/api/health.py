from fastapi import APIRouter

router = APIRouter()

@router.get("/health/startup")
async def startup():
    return {"status": "started"}

@router.get("/health/live")
async def liveness():
    return {"status": "alive"}

@router.get("/health/ready")
async def readiness():
    # We will expand this with real DB checks next.
    checks = {"database": "unhealthy", "redis": "unhealthy"}
    return {"status": "unhealthy", "checks": checks}

@router.get("/metrics")
async def metrics():
    # Placeholder for Prometheus metrics
    # In future sprints, Prometheus instrumentation will be bound here.
    return "# HELP axiom_core_requests_total Total requests\n# TYPE axiom_core_requests_total counter\naxiom_core_requests_total 0"
