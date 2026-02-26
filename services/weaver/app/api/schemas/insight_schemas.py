from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Ingest request ───────────────────────────────────────────

class LogItem(BaseModel):
    raw_sql: str = Field(..., min_length=1)
    datasource_id: str = Field(..., min_length=1)
    executed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None


class IngestLogsRequest(BaseModel):
    logs: list[LogItem] = Field(..., min_length=1, max_length=5000)
    source: str = Field(default="oracle")


# ── Ingest response ──────────────────────────────────────────

class IngestLogsResponse(BaseModel):
    inserted: int
    deduped: int
    batch_id: Optional[int] = None
    trace_id: str = ""


# ── Impact request / response ────────────────────────────────

class ImpactRequest(BaseModel):
    datasource_id: str = Field(default="")   # optional — empty means all datasources
    kpi_fingerprint: str = Field(..., min_length=1)
    time_range: str = Field(default="30d")
    top: int = Field(default=50, ge=1, le=200)


class ImpactAcceptedResponse(BaseModel):
    """202 Accepted — job was created or is already running."""
    job_id: str
    status: str = "queued"
    poll_url: str = ""
    poll_after_ms: int = 2000
    trace_id: str = ""


class ImpactCachedResponse(BaseModel):
    """200 OK — cached result available."""
    job_id: str
    status: str = "done"
    graph: Any = None
    trace_id: str = ""


# ── Job status response ─────────────────────────────────────

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    error: str = ""
    graph: Any = None
    trace_id: str = ""


# ── Query subgraph request ───────────────────────────────────

class QuerySubgraphRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    datasource: str = Field(default="")
