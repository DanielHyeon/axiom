"""Job store for Insight impact analysis jobs (Redis HASH-backed).

Each job is stored as a Redis HASH with key ``insight:job:{job_id}``.
A secondary *jobmap* key provides deduplication so identical requests
(same tenant + datasource + kpi_fingerprint + time_range + top) reuse an existing job.

Cache results are stored separately under ``insight:cache:{...}`` by impact_task
and read directly by the API for cache-first responses.

Graceful degradation: all public functions accept ``rd=None`` and raise
``JobStoreUnavailableError`` so the caller can return a 503.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any

logger = logging.getLogger("weaver.insight_job_store")

JOB_PREFIX    = "insight:job:"
JOBMAP_PREFIX = "insight:jobmap:"
CACHE_PREFIX  = "insight:cache:"

# Per-state TTLs
TTL_QUEUED  = 600    # 10 min  — waiting to be picked up
TTL_RUNNING = 3600   # 1 hour  — analysis in progress
TTL_DONE    = 3600   # 1 hour  — cached result available
TTL_FAILED  = 300    # 5 min   — allow fast client retry

# Back-compat alias used by impact_task.py
DEFAULT_JOB_TTL = TTL_DONE


class JobStoreUnavailableError(Exception):
    """Redis is not connected — caller should surface 503."""


# ── Key helpers ───────────────────────────────────────────────

def _job_key(job_id: str) -> str:
    return f"{JOB_PREFIX}{job_id}"


def _jobmap_key(
    tenant_id: str,
    datasource_id: str,
    kpi_fp: str,
    time_range: str,
    top: int,
) -> str:
    """Deterministic dedup key — includes datasource_id to isolate per-source results."""
    raw = f"{tenant_id}|{datasource_id}|{kpi_fp}|{time_range}|{top}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:20]
    return f"{JOBMAP_PREFIX}{h}"


def _build_cache_key(
    tenant_id: str,
    datasource_id: str,
    kpi_fp: str,
    time_range: str,
    top: int,
) -> str:
    """Shared cache key used by both impact_task (write) and API (read)."""
    return f"{CACHE_PREFIX}{tenant_id}:{datasource_id}:{kpi_fp}:{time_range}:{top}"


# ── Public API ────────────────────────────────────────────────

async def get_or_create_job(
    rd: Any | None,
    tenant_id: str,
    datasource_id: str,
    kpi_fingerprint: str,
    time_range: str = "30d",
    top: int = 50,
) -> tuple[str, bool]:
    """Return ``(job_id, is_new)``.

    Uses atomic ``SET NX`` on the jobmap key to prevent duplicate jobs under
    concurrent requests.  Cleans up a tentative job HASH if NX fails.
    """
    if rd is None:
        raise JobStoreUnavailableError("Redis not connected")

    map_key = _jobmap_key(tenant_id, datasource_id, kpi_fingerprint, time_range, top)

    # ── Prepare a new job HASH (written before NX attempt) ────
    new_job_id = uuid.uuid4().hex
    now_ts = str(time.time())
    job_data = {
        "job_id":          new_job_id,
        "tenant_id":       tenant_id,
        "datasource_id":   datasource_id,
        "kpi_fingerprint": kpi_fingerprint,
        "time_range":      time_range,
        "top":             str(top),
        "status":          "queued",
        "created_at":      now_ts,
        "updated_at":      now_ts,
        "progress":        "0",
        "error":           "",
        "result":          "",
        "map_key":         map_key,   # stored so heartbeat can refresh jobmap TTL
    }
    await rd.hset(_job_key(new_job_id), mapping=job_data)
    await rd.expire(_job_key(new_job_id), TTL_QUEUED)

    # ── Atomic NX: only succeed if no existing mapping ────────
    set_ok = await rd.set(map_key, new_job_id, nx=True, ex=TTL_RUNNING)
    if set_ok:
        return new_job_id, True

    # NX failed — another request already owns this slot
    await rd.delete(_job_key(new_job_id))   # discard our tentative job

    existing_id = await rd.get(map_key)
    if existing_id:
        job = await get_job(rd, existing_id)
        if job and job.get("status") not in ("failed",):
            return existing_id, False

    # Extreme race: existing job was deleted between NX fail and re-read.
    # Recreate and force-set the mapping (no NX — we accept last-write-wins here).
    new_job_id2 = uuid.uuid4().hex
    job_data["job_id"] = new_job_id2
    job_data["map_key"] = map_key
    await rd.hset(_job_key(new_job_id2), mapping=job_data)
    await rd.expire(_job_key(new_job_id2), TTL_QUEUED)
    await rd.set(map_key, new_job_id2, ex=TTL_RUNNING)
    return new_job_id2, True


async def get_job(rd: Any | None, job_id: str) -> dict[str, Any] | None:
    """Fetch job state from Redis HASH.  Returns None if not found."""
    if rd is None:
        raise JobStoreUnavailableError("Redis not connected")
    data = await rd.hgetall(_job_key(job_id))
    return dict(data) if data else None


async def update_job(rd: Any | None, job_id: str, **fields: Any) -> None:
    """Update specific fields in a job HASH."""
    if rd is None:
        raise JobStoreUnavailableError("Redis not connected")
    fields["updated_at"] = str(time.time())
    str_fields = {k: str(v) for k, v in fields.items()}
    await rd.hset(_job_key(job_id), mapping=str_fields)


async def heartbeat(rd: Any | None, job_id: str) -> None:
    """Touch updated_at, refresh job TTL, and refresh jobmap TTL.

    Call from long-running workers at each pipeline step to prevent
    TTL expiry mid-analysis.
    """
    if rd is None:
        raise JobStoreUnavailableError("Redis not connected")
    await rd.hset(_job_key(job_id), mapping={"updated_at": str(time.time())})
    await rd.expire(_job_key(job_id), TTL_RUNNING)

    # Also refresh the jobmap key so it doesn't expire before the job finishes
    if map_key := (await rd.hgetall(_job_key(job_id)) or {}).get("map_key"):
        await rd.expire(map_key, TTL_RUNNING)


async def finish_job(
    rd: Any | None,
    job_id: str,
    *,
    graph_json: dict | None = None,
    error: str = "",
    ttl: int | None = None,
) -> None:
    """Mark job as done (or failed) and apply per-state TTL."""
    if rd is None:
        raise JobStoreUnavailableError("Redis not connected")

    fields: dict[str, str] = {"updated_at": str(time.time())}
    if error:
        fields["status"] = "failed"
        fields["error"] = error
        effective_ttl = ttl if ttl is not None else TTL_FAILED
    else:
        fields["status"] = "done"
        fields["progress"] = "100"
        if graph_json is not None:
            fields["result"] = json.dumps(graph_json, ensure_ascii=False)
        effective_ttl = ttl if ttl is not None else TTL_DONE

    await rd.hset(_job_key(job_id), mapping=fields)
    await rd.expire(_job_key(job_id), effective_ttl)
