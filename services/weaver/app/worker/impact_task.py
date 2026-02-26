"""Impact Worker — build KPI impact graph via real analysis pipeline.

Queue-agnostic: ``run_impact_task(rd, conn, payload)`` can be invoked
from Celery, RQ, Arq, or a simple ``asyncio.create_task`` loop.

Job state transitions: ``queued`` → ``running`` → ``done`` | ``failed``

Pipeline: query_log_analyzer → driver_scorer → impact_graph_builder
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.driver_scorer import DriverScoreConfig, score_candidates
from app.services.impact_graph_builder import GraphLimits, build_impact_graph
from app.services.insight_job_store import (
    TTL_DONE,
    _build_cache_key,
    finish_job,
    heartbeat,
    update_job,
)
from app.services.query_log_analyzer import AnalyzerConfig, analyze_query_logs

logger = logging.getLogger("weaver.impact_task")


def _parse_time_range(time_range: str) -> tuple[str, str]:
    """Convert '30d' → (time_from_iso, time_to_iso)."""
    now = datetime.now(timezone.utc)
    if time_range.endswith("d"):
        days = int(time_range[:-1])
    elif time_range.endswith("w"):
        days = int(time_range[:-1]) * 7
    else:
        days = 30
    time_from = now - timedelta(days=days)
    return time_from.isoformat(), now.isoformat()


async def run_impact_task(
    rd: Any,
    conn: Any,
    *,
    job_id: str,
    tenant_id: str,
    datasource_id: str,
    kpi_fingerprint: str,
    time_range: str = "30d",
    top: int = 50,
) -> None:
    """Execute an impact analysis job.

    Steps:
    1. Set job to running
    2. Analyze query logs → AnalysisResult
    3. Score drivers/dimensions
    4. Build impact graph JSON
    5. Store result and mark done
    """
    try:
        await update_job(rd, job_id, status="running", progress="10")

        # Step 1: Parse time range
        time_from, time_to = _parse_time_range(time_range)

        # Step 1.5: Load KPI definitions for improved KPI detection
        await update_job(rd, job_id, progress="15")
        await heartbeat(rd, job_id)
        try:
            from app.services.kpi_metric_mapper import load_kpi_definitions
            kpi_defs = await load_kpi_definitions(conn, tenant_id, datasource_id)
        except Exception:
            logger.warning("Failed to load kpi_definitions — falling back to substring match")
            kpi_defs = []

        # Step 2: Analyze query logs
        await update_job(rd, job_id, progress="20")
        await heartbeat(rd, job_id)
        analysis = await analyze_query_logs(
            conn,
            tenant_id=tenant_id,
            datasource=datasource_id,
            time_from_iso=time_from,
            time_to_iso=time_to,
            kpi_fingerprint=kpi_fingerprint,
            config=AnalyzerConfig(max_queries=50_000),
            kpi_definitions=kpi_defs or None,
        )
        logger.info(
            "impact_task: analyzed %d/%d queries, %d columns",
            analysis.used_queries, analysis.total_queries, len(analysis.column_stats),
        )

        # Step 3: Score candidates
        await update_job(rd, job_id, progress="50")
        await heartbeat(rd, job_id)
        drivers, dimensions = score_candidates(
            analysis,
            kpi_fingerprint=kpi_fingerprint,
            cfg=DriverScoreConfig(top_drivers=top, top_dimensions=top),
        )
        logger.info(
            "impact_task: scored %d drivers, %d dimensions",
            len(drivers), len(dimensions),
        )

        # Step 4: Build graph
        await update_job(rd, job_id, progress="80")
        await heartbeat(rd, job_id)
        result = build_impact_graph(
            analysis=analysis,
            kpi_fingerprint=kpi_fingerprint,
            drivers=drivers,
            dimensions=dimensions,
            limits=GraphLimits(max_nodes=120, max_edges=300, depth=3, top_paths=3),
        )

        # Enrich graph metadata
        graph_meta = result["graph"]["meta"]
        graph_meta["generated_at"] = datetime.now(timezone.utc).isoformat()
        graph_meta["datasource"] = datasource_id
        graph_meta["explain"]["columns_found"] = len(analysis.column_stats)
        graph_meta["explain"]["drivers_scored"] = len(drivers)
        graph_meta["explain"]["dimensions_scored"] = len(dimensions)

        # Step 5: Store result in cache + mark done
        cache_key = _build_cache_key(tenant_id, datasource_id, kpi_fingerprint, time_range, top)
        cache_payload = {"job_id": job_id, "result": result}
        await rd.set(
            cache_key,
            json.dumps(cache_payload, ensure_ascii=False),
            ex=TTL_DONE,
        )
        await finish_job(rd, job_id, graph_json=result)

        g = result["graph"]
        logger.info(
            "impact_task done: job=%s kpi=%s nodes=%d edges=%d",
            job_id, kpi_fingerprint,
            len(g.get("nodes", [])),
            len(g.get("edges", [])),
        )

    except Exception as exc:
        logger.error("impact_task failed: job=%s error=%s", job_id, exc, exc_info=True)
        await finish_job(rd, job_id, error=str(exc)[:500])
