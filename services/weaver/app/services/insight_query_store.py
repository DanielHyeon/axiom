from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("weaver.insight_query_store")

MAX_SQL_LENGTH = 100_000  # 100 KB — skip logs exceeding this

# ── time_range utilities ─────────────────────────────────────

_ALLOWED_RANGES = {"7d": 7, "30d": 30, "90d": 90}


def parse_time_range_days(time_range: str) -> int:
    """'30d' → 30.  미허용 값은 ValueError."""
    days = _ALLOWED_RANGES.get(time_range)
    if days is None:
        raise ValueError(
            f"Invalid time_range: {time_range!r}. Allowed: {sorted(_ALLOWED_RANGES)}"
        )
    return days


async def insert_batch_record(conn, tenant_id: str, source: str, row_count: int) -> int:
    """Insert an ingest batch record and return its id."""
    row = await conn.fetchrow(
        "INSERT INTO weaver.insight_ingest_batches "
        "(tenant_id, source, row_count) VALUES ($1, $2, $3) RETURNING id",
        tenant_id, source, row_count,
    )
    return row["id"]


async def insert_logs(
    conn,
    tenant_id: str,
    logs: list[dict],
    batch_id: int | None = None,
) -> dict:
    """Write-fast insert with ON CONFLICT dedup.

    Each item in ``logs`` is expected to have:
        query_id, raw_sql, normalized_sql, sql_hash,
        datasource_id, executed_at, duration_ms, user_id, source

    Returns ``{"inserted": N, "deduped": M}``.
    """
    inserted = 0
    deduped = 0
    now = datetime.now(timezone.utc)

    for log in logs:
        raw_sql = log.get("raw_sql", "")
        if len(raw_sql) > MAX_SQL_LENGTH:
            logger.warning(
                "Skipping query_id=%s: raw_sql length %d exceeds MAX_SQL_LENGTH %d",
                log.get("query_id", "?"), len(raw_sql), MAX_SQL_LENGTH,
            )
            deduped += 1
            continue

        row = await conn.fetchrow(
            """
            INSERT INTO weaver.insight_query_logs
                (tenant_id, datasource_id, query_id, raw_sql, normalized_sql,
                 sql_hash, executed_at, received_at, duration_ms, user_id,
                 source, batch_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            ON CONFLICT (tenant_id, query_id) DO NOTHING
            RETURNING id
            """,
            tenant_id,
            log["datasource_id"],
            log["query_id"],
            log["raw_sql"],
            log["normalized_sql"],
            log["sql_hash"],
            log.get("executed_at") or now,
            now,
            log.get("duration_ms"),
            log.get("user_id"),
            log.get("source", "oracle"),
            batch_id,
        )
        if row is not None:
            inserted += 1
        else:
            deduped += 1

    return {"inserted": inserted, "deduped": deduped}


# ── KPI list ─────────────────────────────────────────────────

async def fetch_kpis(
    conn,
    tenant_id: str,
    datasource: str | None,
    days: int,
    offset: int,
    limit: int,
) -> tuple[list[dict], int]:
    """Fetch KPI list from insight_query_logs (Option A — kpi_fingerprint column).

    Returns (rows, total_count).  Only rows with kpi_fingerprint IS NOT NULL.
    """
    time_from = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await conn.fetch(
        """
        SELECT
            kpi_fingerprint                                AS fingerprint,
            COALESCE(MIN(kpi_name), kpi_fingerprint)     AS name,
            datasource_id,
            COUNT(*)                                       AS query_count,
            MAX(executed_at)                               AS last_seen,
            COUNT(*) OVER()                                AS total_count
        FROM weaver.insight_query_logs
        WHERE tenant_id = $1
          AND kpi_fingerprint IS NOT NULL
          AND ($2::text IS NULL OR datasource_id = $2)
          AND executed_at >= $3
        GROUP BY kpi_fingerprint, datasource_id
        ORDER BY query_count DESC
        LIMIT $4 OFFSET $5
        """,
        tenant_id,
        datasource,
        time_from,
        limit,
        offset,
    )
    if not rows:
        return [], 0
    total = int(rows[0]["total_count"])
    result = [
        {
            "id": row["fingerprint"],
            "name": row["name"],
            "source": "query_log",
            "primary": False,
            "fingerprint": row["fingerprint"],
            "datasource": row["datasource_id"],
            "query_count": row["query_count"],
            "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
            "trend": None,
            "aliases": [],
        }
        for row in rows
    ]
    return result, total


# ── Driver list ──────────────────────────────────────────────

async def fetch_drivers(
    conn,
    tenant_id: str,
    datasource: str | None,
    kpi_fingerprint: str | None,
    days: int,  # noqa: ARG001 — reserved for future time-based filtering
    offset: int,
    limit: int,
) -> tuple[list[dict], int]:
    """Fetch driver scores from insight_driver_scores."""
    rows = await conn.fetch(
        """
        SELECT
            column_key,
            role,
            score,
            breakdown,
            kpi_fingerprint,
            created_at,
            COUNT(*) OVER() AS total_count
        FROM weaver.insight_driver_scores
        WHERE tenant_id = $1
          AND ($2::text IS NULL OR datasource_id = $2)
          AND ($3::text IS NULL OR kpi_fingerprint = $3)
        ORDER BY score DESC, created_at DESC
        LIMIT $4 OFFSET $5
        """,
        tenant_id,
        datasource,
        kpi_fingerprint,
        limit,
        offset,
    )
    if not rows:
        return [], 0
    total = int(rows[0]["total_count"])
    result = [
        {
            "driver_key": row["column_key"],
            "role": row["role"],
            "score": row["score"],
            "breakdown": dict(row["breakdown"]) if row["breakdown"] else {},
            "kpi_fingerprint": row["kpi_fingerprint"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]
    return result, total


# ── Driver detail ────────────────────────────────────────────

async def fetch_driver_score(conn, tenant_id: str, driver_key: str) -> dict | None:
    """Fetch the most recent score record for a driver_key."""
    row = await conn.fetchrow(
        """
        SELECT column_key, role, score, breakdown, kpi_fingerprint, created_at
        FROM weaver.insight_driver_scores
        WHERE tenant_id = $1 AND column_key = $2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        tenant_id,
        driver_key,
    )
    if not row:
        return None
    return {
        "driver_key": row["column_key"],
        "role": row["role"],
        "score": row["score"],
        "breakdown": dict(row["breakdown"]) if row["breakdown"] else {},
        "kpi_fingerprint": row["kpi_fingerprint"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def _build_evidence_pattern(driver_key: str) -> str:
    """Build a regex pattern that matches table AND column simultaneously (E6 fix)."""
    parts = driver_key.split(".", 1)
    if len(parts) == 2:
        table, col = parts[0], parts[1]
        # Match table + column in either order within the SQL
        table_esc = re.escape(table)
        col_esc = re.escape(col)
        return rf"\b{table_esc}\b.*\b{col_esc}\b|\b{col_esc}\b.*\b{table_esc}\b"
    # Single-part key: exact word match
    return rf"\b{re.escape(driver_key)}\b"


async def fetch_driver_evidence(
    conn,
    tenant_id: str,
    driver_key: str,
    days: int,
) -> list[dict]:
    """Fetch up to 5 evidence queries for a driver using regex matching (E6)."""
    time_from = datetime.now(timezone.utc) - timedelta(days=days)
    pattern = _build_evidence_pattern(driver_key)
    rows = await conn.fetch(
        """
        SELECT query_id, normalized_sql, executed_at, COUNT(*) AS count
        FROM weaver.insight_query_logs
        WHERE tenant_id = $1
          AND executed_at >= $2
          AND normalized_sql ~* $3
        GROUP BY query_id, normalized_sql, executed_at
        ORDER BY count DESC
        LIMIT 5
        """,
        tenant_id,
        time_from,
        pattern,
    )
    return [
        {
            "query_id": row["query_id"],
            "normalized_sql": row["normalized_sql"],
            "count": row["count"],
            "executed_at": row["executed_at"].isoformat() if row["executed_at"] else None,
        }
        for row in rows
    ]


# ── KPI activity timeseries ──────────────────────────────────

async def fetch_kpi_activity(
    conn,
    tenant_id: str,
    kpi_fingerprint: str,
    driver_key: str | None,
    days: int,
    granularity: str,
) -> list[dict]:
    """Fetch daily/weekly query activity count for a KPI (P2-A, Phase 1)."""
    time_from = datetime.now(timezone.utc) - timedelta(days=days)
    trunc = "week" if granularity == "week" else "day"

    if driver_key:
        pattern = _build_evidence_pattern(driver_key)
        rows = await conn.fetch(
            f"""
            SELECT
                DATE_TRUNC('{trunc}', executed_at)::date AS date,
                COUNT(*)                                  AS value
            FROM weaver.insight_query_logs
            WHERE tenant_id = $1
              AND kpi_fingerprint = $2
              AND executed_at >= $3
              AND normalized_sql ~* $4
            GROUP BY 1
            ORDER BY 1
            """,
            tenant_id,
            kpi_fingerprint,
            time_from,
            pattern,
        )
    else:
        rows = await conn.fetch(
            f"""
            SELECT
                DATE_TRUNC('{trunc}', executed_at)::date AS date,
                COUNT(*)                                  AS value
            FROM weaver.insight_query_logs
            WHERE tenant_id = $1
              AND kpi_fingerprint = $2
              AND executed_at >= $3
            GROUP BY 1
            ORDER BY 1
            """,
            tenant_id,
            kpi_fingerprint,
            time_from,
        )

    return [
        {
            "date": str(row["date"]),
            "value": row["value"],
        }
        for row in rows
    ]


# ── Schema coverage ──────────────────────────────────────────

async def fetch_schema_coverage(
    conn,
    tenant_id: str,
    table: str,
    column: str | None,
    days: int,
) -> dict:
    """Fetch querylog + driver_scores coverage for a table/column (P2-B)."""
    time_from = datetime.now(timezone.utc) - timedelta(days=days)

    if column:
        driver_key = f"{table}.{column}"
        pattern = _build_evidence_pattern(driver_key)
    else:
        pattern = rf"\b{re.escape(table)}\b"

    # Query log count
    log_row = await conn.fetchrow(
        """
        SELECT COUNT(*) AS count, MAX(executed_at) AS last_seen
        FROM weaver.insight_query_logs
        WHERE tenant_id = $1
          AND executed_at >= $2
          AND normalized_sql ~* $3
        """,
        tenant_id,
        time_from,
        pattern,
    )

    # Driver score presence
    score_row = None
    if column:
        score_row = await conn.fetchrow(
            """
            SELECT score, role, kpi_fingerprint
            FROM weaver.insight_driver_scores
            WHERE tenant_id = $1 AND column_key = $2
            ORDER BY created_at DESC LIMIT 1
            """,
            tenant_id,
            driver_key,
        )

    return {
        "table": table,
        "column": column,
        "query_count": int(log_row["count"]) if log_row else 0,
        "last_seen": (
            log_row["last_seen"].isoformat() if log_row and log_row["last_seen"] else None
        ),
        "driver_score": (
            {
                "score": score_row["score"],
                "role": score_row["role"],
                "kpi_fingerprint": score_row["kpi_fingerprint"],
            }
            if score_row
            else None
        ),
    }
