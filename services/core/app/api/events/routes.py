from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.core.observability import metrics_registry
from app.core.redis_client import get_redis
from app.models.base_models import EventOutbox
from app.workers.sync import SyncWorker

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/sync/run-once")
async def sync_run_once(limit: int = Query(default=100, ge=1, le=1000)):
    worker = SyncWorker(max_batch=limit)
    try:
        result = await worker.publish_pending_once(limit=limit)
        return {"success": True, "data": result}
    except Exception:
        raise HTTPException(status_code=500, detail={"code": "SYNC_WORKER_FAILED", "message": "sync worker failed"})


@router.get("/outbox/backlog")
async def outbox_backlog():
    async with AsyncSessionLocal() as session:
        pending = await session.scalar(select(func.count()).select_from(EventOutbox).where(EventOutbox.status == "PENDING"))
        failed = await session.scalar(select(func.count()).select_from(EventOutbox).where(EventOutbox.status == "FAILED"))
        oldest = await session.scalar(
            select(func.min(EventOutbox.created_at)).where(EventOutbox.status == "PENDING")
        )
    age_seconds = 0.0
    if oldest is not None:
        age_seconds = max(0.0, (datetime.now(timezone.utc) - oldest).total_seconds())
    metrics_registry.set_gauge("core_event_outbox_pending", float(pending or 0))
    return {
        "success": True,
        "data": {
            "pending": int(pending or 0),
            "failed": int(failed or 0),
            "oldest_pending_age_seconds": round(age_seconds, 3),
        },
    }


@router.post("/outbox/retry-failed")
async def retry_failed(limit: int = Query(default=200, ge=1, le=5000)):
    worker = SyncWorker()
    retried = await worker.retry_failed_once(limit=limit)
    return {"success": True, "data": {"retried": retried}}


@router.get("/dlq/{stream_name}")
async def dlq_status(stream_name: str):
    key = f"axiom:dlq:{stream_name}"
    redis = get_redis()
    try:
        depth = int(await redis.xlen(key))
    except Exception:
        depth = 0
    metrics_registry.set_gauge("core_dlq_depth", float(depth))
    return {"success": True, "data": {"stream": key, "depth": depth}}


@router.post("/dlq/{stream_name}/reprocess")
async def dlq_reprocess(stream_name: str, limit: int = Query(default=100, ge=1, le=1000)):
    worker = SyncWorker()
    result = await worker.reprocess_dlq_once(stream_name=stream_name, limit=limit)
    return {"success": True, "data": {"stream": f"axiom:dlq:{stream_name}", **result}}
