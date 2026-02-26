from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.insight_auth import get_current_insight_user, get_effective_tenant_id
from app.core.insight_errors import InsightError
from app.core.insight_redis import get_insight_redis
from app.core.rls_session import rls_session
from app.api.schemas.insight_schemas import (
    ImpactAcceptedResponse,
    ImpactCachedResponse,
    ImpactRequest,
    IngestLogsRequest,
    IngestLogsResponse,
    JobStatusResponse,
    QuerySubgraphRequest,
)
from app.core.rls_session import rls_session
from app.services.insight_store import insight_store, InsightStoreUnavailableError
from app.services.insight_job_store import (
    JobStoreUnavailableError,
    _build_cache_key,
    finish_job,
    get_job,
    get_or_create_job,
    update_job,
)
from app.services.sql_normalize import normalize_sql, mask_pii
from app.services.idempotency import realtime_query_id, batch_query_id
from app.services.insight_query_store import insert_logs, insert_batch_record
from app.worker.impact_task import run_impact_task

logger = logging.getLogger("weaver.insight_api")

router = APIRouter(prefix="/api/insight", tags=["insight"])


# ── POST /logs (realtime single-log path) ────────────────────

@router.post("/logs", status_code=201, response_model=IngestLogsResponse)
async def ingest_logs_realtime(
    body: IngestLogsRequest,
    request: Request,
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """Realtime ingest — typically one log per call from Oracle service."""
    try:
        pool = await insight_store.get_pool()
    except InsightStoreUnavailableError as exc:
        raise InsightError(
            status_code=503, error_code="STORE_UNAVAILABLE",
            error_message=str(exc), retryable=True, hint="DB may be starting up",
        ) from exc

    trace_id = getattr(request.state, "request_id", "") or request.headers.get("X-Request-Id", "")
    prepared = []
    for item in body.logs:
        norm = mask_pii(normalize_sql(item.raw_sql))
        sql_hash = hashlib.sha256(norm.encode()).hexdigest()[:16]
        qid = realtime_query_id(
            norm, tenant_id, item.datasource_id,
            item.request_id or str(uuid.uuid4()),
        )
        prepared.append({
            "query_id": qid,
            "raw_sql": item.raw_sql,
            "normalized_sql": norm,
            "sql_hash": sql_hash,
            "datasource_id": item.datasource_id,
            "executed_at": item.executed_at or datetime.now(timezone.utc),
            "duration_ms": item.duration_ms,
            "user_id": item.user_id,
            "source": body.source,
        })

    async with rls_session(pool, tenant_id) as conn:
        result = await insert_logs(conn, tenant_id, prepared)

    return IngestLogsResponse(
        inserted=result["inserted"],
        deduped=result["deduped"],
        trace_id=trace_id,
    )


# ── POST /logs:ingest (batch path from Oracle) ──────────────

@router.post("/logs:ingest", status_code=201, response_model=IngestLogsResponse)
async def ingest_logs_batch(
    body: IngestLogsRequest,
    request: Request,
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """Batch ingest — Oracle service sends multiple logs at once."""
    try:
        pool = await insight_store.get_pool()
    except InsightStoreUnavailableError as exc:
        raise InsightError(
            status_code=503, error_code="STORE_UNAVAILABLE",
            error_message=str(exc), retryable=True, hint="DB may be starting up",
        ) from exc

    trace_id = getattr(request.state, "request_id", "") or request.headers.get("X-Request-Id", "")
    prepared = []
    for item in body.logs:
        norm = mask_pii(normalize_sql(item.raw_sql))
        sql_hash = hashlib.sha256(norm.encode()).hexdigest()[:16]
        exec_at = item.executed_at or datetime.now(timezone.utc)
        qid = batch_query_id(norm, tenant_id, item.datasource_id, exec_at)
        prepared.append({
            "query_id": qid,
            "raw_sql": item.raw_sql,
            "normalized_sql": norm,
            "sql_hash": sql_hash,
            "datasource_id": item.datasource_id,
            "executed_at": exec_at,
            "duration_ms": item.duration_ms,
            "user_id": item.user_id,
            "source": body.source,
        })

    async with rls_session(pool, tenant_id) as conn:
        batch_id = await insert_batch_record(conn, tenant_id, body.source, len(prepared))
        result = await insert_logs(conn, tenant_id, prepared, batch_id=batch_id)

    return IngestLogsResponse(
        inserted=result["inserted"],
        deduped=result["deduped"],
        batch_id=batch_id,
        trace_id=trace_id,
    )


# ── GET /impact (async job creation — 202 or 200) ────────────

@router.post("/impact", status_code=202)
async def request_impact(
    body: ImpactRequest,
    request: Request,
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """Request impact analysis for a KPI.

    Returns **202** with a ``job_id`` when a new analysis job is queued, or
    **200** with the cached graph if a completed result already exists.
    """
    trace_id = getattr(request.state, "request_id", "") or request.headers.get("X-Request-Id", "")

    rd = await get_insight_redis()
    if rd is None:
        raise InsightError(
            status_code=503,
            error_code="REDIS_UNAVAILABLE",
            error_message="Job store (Redis) is not available",
            retryable=True,
            hint="Redis may be starting up",
            poll_after_ms=3000,
        )

    # Cache-first: check for a completed result before creating a new job
    cache_key = _build_cache_key(
        tenant_id, body.datasource_id, body.kpi_fingerprint, body.time_range, body.top
    )
    cached_raw = await rd.get(cache_key)
    if cached_raw:
        try:
            cache_data = json.loads(cached_raw)
            graph = cache_data.get("result")
            if graph:
                graph.setdefault("graph", {}).setdefault("meta", {})["cache_hit"] = True
                return JSONResponse(
                    status_code=200,
                    content=ImpactCachedResponse(
                        job_id=cache_data.get("job_id", ""),
                        status="done",
                        graph=graph,
                        trace_id=trace_id,
                    ).model_dump(),
                )
        except (json.JSONDecodeError, TypeError, KeyError, AttributeError):
            pass  # Fall through to job-based path

    try:
        job_id, is_new = await get_or_create_job(
            rd,
            tenant_id=tenant_id,
            datasource_id=body.datasource_id,
            kpi_fingerprint=body.kpi_fingerprint,
            time_range=body.time_range,
            top=body.top,
        )
    except JobStoreUnavailableError as exc:
        raise InsightError(
            status_code=503,
            error_code="REDIS_UNAVAILABLE",
            error_message=str(exc),
            retryable=True,
            hint="Redis may be starting up",
            poll_after_ms=3000,
        ) from exc

    # If existing job is done, return cached result immediately
    if not is_new:
        job = await get_job(rd, job_id)
        if job and job.get("status") == "done" and job.get("result"):
            try:
                graph = json.loads(job["result"])
            except (json.JSONDecodeError, TypeError):
                graph = None
            return JSONResponse(
                status_code=200,
                content=ImpactCachedResponse(
                    job_id=job_id,
                    status="done",
                    graph=graph,
                    trace_id=trace_id,
                ).model_dump(),
            )

    # Enqueue worker when job is new
    if is_new:
        asyncio.create_task(_run_impact_job(
            rd, job_id, tenant_id, body,
        ))

    poll_url = f"/api/insight/jobs/{job_id}"
    return JSONResponse(
        status_code=202,
        content=ImpactAcceptedResponse(
            job_id=job_id,
            status="queued",
            poll_url=poll_url,
            poll_after_ms=2000,
            trace_id=trace_id,
        ).model_dump(),
    )


async def _run_impact_job(
    rd, job_id: str, tenant_id: str, body: ImpactRequest,
) -> None:
    """Fire-and-forget wrapper — acquire a connection and run the impact task."""
    try:
        pool = await insight_store.get_pool()
        async with rls_session(pool, tenant_id) as conn:
            await run_impact_task(
                rd, conn,
                job_id=job_id,
                tenant_id=tenant_id,
                datasource_id=body.datasource_id,
                kpi_fingerprint=body.kpi_fingerprint,
                time_range=body.time_range,
                top=body.top,
            )
    except Exception as exc:
        logger.error("_run_impact_job failed: job=%s err=%s", job_id, exc, exc_info=True)
        from app.services.insight_job_store import finish_job as _finish
        try:
            await _finish(rd, job_id, error=str(exc)[:500])
        except Exception:
            pass


# ── GET /jobs/{job_id} (poll for status) ──────────────────────

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    request: Request,
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """Poll job status. Returns current state and result if done."""
    trace_id = getattr(request.state, "request_id", "") or request.headers.get("X-Request-Id", "")

    rd = await get_insight_redis()
    if rd is None:
        raise InsightError(
            status_code=503,
            error_code="REDIS_UNAVAILABLE",
            error_message="Job store (Redis) is not available",
            retryable=True,
            hint="Redis may be starting up",
            poll_after_ms=3000,
        )

    try:
        job = await get_job(rd, job_id)
    except JobStoreUnavailableError as exc:
        raise InsightError(
            status_code=503,
            error_code="REDIS_UNAVAILABLE",
            error_message=str(exc),
            retryable=True,
            poll_after_ms=3000,
        ) from exc

    if job is None:
        raise InsightError(
            status_code=404,
            error_code="JOB_NOT_FOUND",
            error_message=f"Job {job_id} not found or expired",
        )

    # Tenant isolation: only return jobs that belong to this tenant
    if job.get("tenant_id") != tenant_id:
        raise InsightError(
            status_code=404,
            error_code="JOB_NOT_FOUND",
            error_message=f"Job {job_id} not found or expired",
        )

    graph = None
    if job.get("status") == "done" and job.get("result"):
        try:
            graph = json.loads(job["result"])
        except (json.JSONDecodeError, TypeError):
            graph = None

    return JobStatusResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        progress=int(job.get("progress", 0)),
        error=job.get("error", ""),
        graph=graph,
        trace_id=trace_id,
    )


# ── POST /query-subgraph (SQL → subgraph) ─────────────────────

def _parse_result_to_graph(result, datasource: str, trace_id: str) -> dict:
    """Convert ParseResult into a GraphData dict (TABLE/COLUMN/PREDICATE nodes).

    Uses node_id.py conventions so Impact Graph and Instance Graph share the
    same node IDs for TABLE (``tbl:schema.table``) and COLUMN
    (``col:schema.table.column``) nodes.
    """
    from app.services.node_id import table_node_id, column_node_id
    now = datetime.now(timezone.utc).isoformat()

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_node_ids: set[str] = set()

    # TABLE nodes ── tbl:{schema}.{table}
    table_id_map: dict[str, str] = {}
    tbl_coords: dict[str, tuple[str, str]] = {}  # node_id → (schema, table)
    for tbl in result.tables:
        tbl_parts = tbl.split(".")
        tbl_schema = tbl_parts[0] if len(tbl_parts) >= 2 else "public"
        tbl_name = tbl_parts[-1]
        node_id = table_node_id(tbl_schema, tbl_name)
        table_id_map[tbl.lower()] = node_id
        short = tbl_name.lower()
        if short not in table_id_map:
            table_id_map[short] = node_id
        tbl_coords[node_id] = (tbl_schema, tbl_name)
        if node_id not in seen_node_ids:
            seen_node_ids.add(node_id)
            nodes.append({
                "id": node_id,
                "label": tbl_name,
                "type": "TABLE",
                "source": "sql_parse",
                "confidence": result.confidence,
                "layer": "data",
                "properties": {
                    "full_name": tbl,
                    "schema": tbl_schema if "." in tbl else None,
                },
            })

    def _find_tbl(ref: str) -> str | None:
        r = ref.lower().strip()
        if r in table_id_map:
            return table_id_map[r]
        return table_id_map.get(r.split(".")[-1])

    first_tbl = next(iter(table_id_map.values()), None)

    def _col_node_id(col_label: str, tbl_id: str | None) -> str:
        """col:{schema}.{table}.{column} using resolved table coords."""
        if tbl_id and tbl_id in tbl_coords:
            schema, tbl = tbl_coords[tbl_id]
        else:
            schema, tbl = "public", "unknown"
        return column_node_id(schema, tbl, col_label)

    # SELECT COLUMN nodes ── col:{schema}.{table}.{column}
    for col in result.select_columns:
        if not col or col == "*":
            continue
        parts = col.split(".")
        col_label = parts[-1]
        tbl_ref = parts[-2] if len(parts) >= 2 else None
        tbl_id = _find_tbl(tbl_ref) if tbl_ref else first_tbl
        node_id = _col_node_id(col_label, tbl_id)
        if node_id not in seen_node_ids:
            seen_node_ids.add(node_id)
            nodes.append({
                "id": node_id,
                "label": col_label,
                "type": "COLUMN",
                "source": "sql_parse",
                "confidence": result.confidence,
                "layer": "select",
                "properties": {"position": "select", "expr": col},
            })
        if tbl_id:
            edges.append({
                "source": tbl_id,
                "target": node_id,
                "type": "DERIVE",
                "confidence": result.confidence,
                "weight": 0.7,
            })

    # JOIN edges between TABLE nodes
    for j in result.joins:
        jt = j.get("table", "") if isinstance(j, dict) else ""
        jt_id = _find_tbl(jt) if jt else None
        if jt_id and first_tbl and jt_id != first_tbl:
            edges.append({
                "source": first_tbl,
                "target": jt_id,
                "type": "JOIN",
                "label": (j.get("type", "JOIN") if isinstance(j, dict) else "JOIN").strip(),
                "confidence": result.confidence,
                "weight": 0.9,
            })

    # WHERE PREDICATE nodes (no column_node_id equivalent — keep positional IDs)
    for i, pred in enumerate(result.predicates):
        raw = pred.get("raw", "") if isinstance(pred, dict) else str(pred)
        if not raw:
            continue
        node_id = f"pred_where_{i}"
        nodes.append({
            "id": node_id,
            "label": raw[:40] + ("..." if len(raw) > 40 else ""),
            "type": "PREDICATE",
            "source": "sql_parse",
            "confidence": result.confidence * 0.8,
            "layer": "filter",
            "properties": {"expression": raw, "clause": "WHERE"},
        })
        matched = next(
            (tid for tbl, tid in table_id_map.items() if tbl.split(".")[-1] in raw.lower()),
            first_tbl,
        )
        if matched:
            edges.append({
                "source": node_id,
                "target": matched,
                "type": "WHERE_FILTER",
                "confidence": result.confidence * 0.8,
                "weight": 0.6,
            })

    # GROUP BY edges
    for i, gb_col in enumerate(result.group_by):
        if not gb_col:
            continue
        parts = gb_col.split(".")
        col_label = parts[-1]
        tbl_ref = parts[-2] if len(parts) >= 2 else None
        tbl_id = _find_tbl(tbl_ref) if tbl_ref else first_tbl
        # Reuse existing SELECT column node if label matches
        existing = next(
            (n["id"] for n in nodes if n["type"] == "COLUMN" and n["label"].lower() == col_label.lower()),
            None,
        )
        if existing and tbl_id:
            edges.append({"source": existing, "target": tbl_id, "type": "GROUP_BY",
                          "confidence": result.confidence, "weight": 0.8})
        elif tbl_id:
            gb_id = _col_node_id(col_label, tbl_id)
            if gb_id not in seen_node_ids:
                seen_node_ids.add(gb_id)
                nodes.append({
                    "id": gb_id,
                    "label": col_label,
                    "type": "COLUMN",
                    "source": "sql_parse",
                    "confidence": result.confidence,
                    "layer": "group_by",
                    "properties": {"position": "group_by", "expr": gb_col},
                })
            edges.append({"source": gb_id, "target": tbl_id, "type": "GROUP_BY",
                          "confidence": result.confidence, "weight": 0.8})

    meta = {
        "schema_version": "insight/v3",
        "analysis_version": "2026-02-26.1",
        "generated_at": now,
        "time_range": {"from": now, "to": now},
        "datasource": datasource,
        "cache_hit": False,
        "limits": {"max_nodes": 50, "max_edges": 100, "depth": 1},
        "truncated": False,
        "trace_id": trace_id,
        "explain": {
            "total_queries_analyzed": 1,
            "time_range_used": "realtime",
            "fallback_used": result.mode == "fallback",
            "mode": result.mode if result.mode in ("primary", "fallback") else "fallback",
        },
    }
    return {"meta": meta, "nodes": nodes, "edges": edges}


@router.post("/query-subgraph")
async def query_subgraph(
    body: QuerySubgraphRequest,
    request: Request,
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """Parse SQL and return a query subgraph (TABLE/COLUMN/PREDICATE nodes)."""
    from app.worker.parse_task import parse_sql_regex

    trace_id = (
        getattr(request.state, "request_id", "")
        or request.headers.get("X-Request-Id", "")
    )

    norm = normalize_sql(body.sql)
    result = parse_sql_regex(norm)

    if result.mode == "failed" or not result.tables:
        raise InsightError(
            status_code=422,
            error_code="SQL_PARSE_FAILED",
            error_message=f"Could not parse SQL: {'; '.join(result.errors) or 'no tables found'}",
            hint="Ensure the SQL contains at least one FROM clause",
        )

    graph = _parse_result_to_graph(result, body.datasource, trace_id)

    parse_result_data = {
        "mode": result.mode,
        "confidence": result.confidence,
        "tables": [{"name": t} for t in result.tables],
        "joins": result.joins,
        "predicates": result.predicates,
        "select_columns": [{"column": c} for c in result.select_columns],
        "group_by_columns": result.group_by,
        "warnings": result.warnings,
        "errors": result.errors,
    }

    return {"parse_result": parse_result_data, "graph": graph, "trace_id": trace_id}
