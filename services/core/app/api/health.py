from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.observability import metrics_registry
from app.core.redis_client import get_redis

router = APIRouter()

@router.get("/health/startup")
async def startup():
    return {"status": "started"}

@router.get("/health/live")
async def liveness():
    return {"status": "alive"}

@router.get("/health/ready")
async def readiness():
    checks = {"database": "unhealthy", "redis": "unhealthy"}
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        pass

    try:
        await get_redis().ping()
        checks["redis"] = "healthy"
    except Exception:
        pass

    status = "healthy" if all(value == "healthy" for value in checks.values()) else "unhealthy"
    return {"status": status, "checks": checks}

@router.get("/metrics")
async def metrics():
    return metrics_registry.render_prometheus()
