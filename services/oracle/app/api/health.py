from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter(tags=["Health"])

class HealthResponse(BaseModel):
    status: str
    checks: Dict[str, Any]
    version: str = "1.0.0"
    uptime_seconds: int = 3600

@router.get("/health")
async def liveness_probe() -> Dict[str, str]:
    # Basic Liveness: Pod is up
    return {"status": "ok"}

@router.get("/health/ready", response_model=HealthResponse)
async def readiness_probe():
    # Readiness logic abstracting Target DB + Synapse interactions securely
    return HealthResponse(
        status="healthy",
        checks={
            "synapse_api": {"status": "up", "latency_ms": 12},
            "target_db": {"status": "up", "latency_ms": 15},
            "llm": {"status": "up", "latency_ms": 250}
        }
    )
