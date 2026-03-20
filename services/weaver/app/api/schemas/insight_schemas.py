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


# ── 노드 상세 응답 (P0-3: GET /nodes/{node_id}) ─────────────

class NodeNeighborItem(BaseModel):
    """이웃 노드 요약 정보."""
    id: str
    name: str = ""
    layer: str = ""
    type: str = ""


class NodeRelationItem(BaseModel):
    """노드 간 관계 정보."""
    source: str
    target: str
    type: str = ""
    weight: Optional[float] = None
    confidence: Optional[float] = None


class NodeDetailResponse(BaseModel):
    """GET /api/insight/nodes/{node_id} 응답.

    온톨로지 노드의 상세 정보 + 이웃 + 관계를 반환한다.
    """
    node: dict[str, Any]
    neighbors: list[NodeNeighborItem] = []
    relations: list[NodeRelationItem] = []


# ── 온톨로지 KPI 항목 (P0-3: kpis 병합용) ───────────────────

class OntologyKpiItem(BaseModel):
    """온톨로지에서 가져온 KPI 노드 항목."""
    id: str
    name: str
    description: str = ""
    unit: str = ""
    current_value: Optional[float] = None
    source: str = "ontology"
    primary: bool = True
    fingerprint: str = ""
    datasource: str = ""
    query_count: int = 0
    last_seen: Optional[str] = None
    trend: Optional[str] = None
    aliases: list[str] = []


# ── 온톨로지 Driver 항목 (P0-3: drivers 확장) ────────────────

class OntologyDriverItem(BaseModel):
    """온톨로지에서 가져온 Driver(원인) 노드 항목."""
    id: str
    name: str
    layer: str = ""
    relation_type: str = ""
    weight: Optional[float] = None
    confidence: Optional[float] = None


# ── 데이터소스 기반 스키마 커버리지 (P0-3) ────────────────────

class UnmappedTableItem(BaseModel):
    """온톨로지에 매핑되지 않은 테이블."""
    table_name: str
    schema_name: str = "public"


class DatasourceSchemaCoverageResponse(BaseModel):
    """GET /api/insight/schema-coverage/datasource 응답.

    데이터소스의 전체 스키마 중 온톨로지에 매핑된 비율을 반환한다.
    """
    datasource_id: str
    total_tables: int = 0
    mapped_tables: int = 0
    coverage_pct: float = 0.0
    unmapped_tables: list[UnmappedTableItem] = []
    total_columns: int = 0
    mapped_columns: int = 0
    column_coverage_pct: float = 0.0
