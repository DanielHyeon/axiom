from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("weaver.insight_query_store")

MAX_SQL_LENGTH = 100_000  # 100 KB — skip logs exceeding this


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
