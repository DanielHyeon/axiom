"""Parse Worker — parse pending query logs and update parsed_* columns.

Queue-agnostic: ``run_parse_task(conn, tenant_id, row_id)`` can be invoked
from Celery, RQ, Arq, or a simple ``asyncio.create_task`` loop.

parse_status transitions: ``pending`` → ``parsed`` | ``fallback`` | ``failed``
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("weaver.parse_task")


# ── Parse result ─────────────────────────────────────────────

@dataclass
class ParseResult:
    mode: str = "failed"          # primary | warn | fallback | failed
    confidence: float = 0.0
    tables: list[str] = field(default_factory=list)
    joins: list[dict] = field(default_factory=list)
    predicates: list[dict] = field(default_factory=list)
    select_columns: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ── Regex-based SQL parser (v1, no sqlglot dependency) ───────

_RE_TABLE = re.compile(
    r"""(?:FROM|JOIN|INTO|UPDATE)\s+"""
    r"""(?:(\w+)\.)?(\w+)""",
    re.IGNORECASE,
)

_RE_SELECT_COL = re.compile(
    r"""SELECT\s+(.+?)\s+FROM""",
    re.IGNORECASE | re.DOTALL,
)

_RE_JOIN = re.compile(
    r"""((?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN)\s+"""
    r"""(?:(\w+)\.)?(\w+)\s+(?:\w+\s+)?ON\s+(.+?)(?=(?:WHERE|JOIN|ORDER|GROUP|HAVING|LIMIT|$))""",
    re.IGNORECASE | re.DOTALL,
)

_RE_WHERE_PRED = re.compile(
    r"""WHERE\s+(.+?)(?=(?:GROUP|ORDER|HAVING|LIMIT|$))""",
    re.IGNORECASE | re.DOTALL,
)

_RE_GROUP_BY = re.compile(
    r"""GROUP\s+BY\s+(.+?)(?=(?:HAVING|ORDER|LIMIT|$))""",
    re.IGNORECASE | re.DOTALL,
)


def _extract_tables(sql: str) -> list[str]:
    tables = []
    for m in _RE_TABLE.finditer(sql):
        schema = m.group(1) or ""
        table = m.group(2)
        full = f"{schema}.{table}" if schema else table
        if full.lower() not in [t.lower() for t in tables]:
            tables.append(full)
    return tables


def _extract_select_columns(sql: str) -> list[str]:
    m = _RE_SELECT_COL.search(sql)
    if not m:
        return []
    raw = m.group(1).strip()
    if raw == "*":
        return ["*"]
    cols = []
    for part in raw.split(","):
        col = part.strip().split()[-1] if part.strip() else ""
        if col:
            cols.append(col)
    return cols


def _extract_joins(sql: str) -> list[dict]:
    joins = []
    for m in _RE_JOIN.finditer(sql):
        joins.append({
            "type": m.group(1).strip(),
            "table": f"{m.group(2)}.{m.group(3)}" if m.group(2) else m.group(3),
            "condition": m.group(4).strip(),
        })
    return joins


def _extract_predicates(sql: str) -> list[dict]:
    m = _RE_WHERE_PRED.search(sql)
    if not m:
        return []
    raw = m.group(1).strip()
    # Simple split on AND/OR for v1
    parts = re.split(r"\s+(?:AND|OR)\s+", raw, flags=re.IGNORECASE)
    return [{"raw": p.strip()} for p in parts if p.strip()]


def _extract_group_by(sql: str) -> list[str]:
    m = _RE_GROUP_BY.search(sql)
    if not m:
        return []
    raw = m.group(1).strip()
    return [c.strip() for c in raw.split(",") if c.strip()]


def parse_sql_regex(sql: str) -> ParseResult:
    """Best-effort regex SQL parsing (v1 — no sqlglot dependency)."""
    if not sql or not sql.strip():
        return ParseResult(mode="failed", errors=["empty SQL"])

    tables = _extract_tables(sql)
    select_cols = _extract_select_columns(sql)
    joins = _extract_joins(sql)
    predicates = _extract_predicates(sql)
    group_by = _extract_group_by(sql)

    warnings: list[str] = []
    if not tables:
        return ParseResult(
            mode="failed",
            errors=["no tables found"],
            warnings=warnings,
        )

    # Determine confidence
    if select_cols and tables:
        mode = "primary"
        confidence = 0.9
    else:
        mode = "fallback"
        confidence = 0.4
        warnings.append("incomplete extraction")

    return ParseResult(
        mode=mode,
        confidence=confidence,
        tables=tables,
        joins=joins,
        predicates=predicates,
        select_columns=select_cols,
        group_by=group_by,
        warnings=warnings,
    )


# ── Main task entry point ────────────────────────────────────

async def run_parse_task(
    conn: Any,
    tenant_id: str,
    row_id: int,
) -> str:
    """Parse a single pending query log row.

    Returns the resulting parse_status string.
    """
    row = await conn.fetchrow(
        "SELECT normalized_sql FROM weaver.insight_query_logs "
        "WHERE tenant_id = $1 AND id = $2 AND parse_status = 'pending'",
        tenant_id, row_id,
    )
    if not row:
        return "skipped"

    normalized_sql = row["normalized_sql"]
    result = parse_sql_regex(normalized_sql)

    # Determine parse_status
    if result.mode == "primary":
        parse_status = "parsed"
    elif result.mode == "warn":
        parse_status = "parsed"
    elif result.mode == "fallback":
        parse_status = "fallback" if result.tables else "failed"
    else:
        parse_status = "failed"

    await conn.execute(
        """
        UPDATE weaver.insight_query_logs
        SET parse_status     = $1,
            parse_warnings   = $2::jsonb,
            parse_errors     = $3::jsonb,
            parsed_tables    = $4::jsonb,
            parsed_joins     = $5::jsonb,
            parsed_predicates = $6::jsonb,
            parsed_select    = $7::jsonb,
            parsed_group_by  = $8::jsonb,
            parse_mode       = $9,
            parse_confidence = $10
        WHERE tenant_id = $11 AND id = $12
        """,
        parse_status,
        json.dumps(result.warnings),
        json.dumps(result.errors),
        json.dumps(result.tables),
        json.dumps(result.joins),
        json.dumps(result.predicates),
        json.dumps(result.select_columns),
        json.dumps(result.group_by),
        result.mode,
        result.confidence,
        tenant_id,
        row_id,
    )

    logger.info(
        "parse_task: tenant=%s row=%d status=%s tables=%d",
        tenant_id, row_id, parse_status, len(result.tables),
    )
    return parse_status


async def run_parse_batch(
    conn: Any,
    tenant_id: str,
    limit: int = 100,
) -> dict[str, int]:
    """Parse a batch of pending rows.  Returns counts by status."""
    rows = await conn.fetch(
        "SELECT id FROM weaver.insight_query_logs "
        "WHERE tenant_id = $1 AND parse_status = 'pending' "
        "ORDER BY id LIMIT $2",
        tenant_id, limit,
    )

    counts: dict[str, int] = {"parsed": 0, "fallback": 0, "failed": 0, "skipped": 0}
    for row in rows:
        status = await run_parse_task(conn, tenant_id, row["id"])
        counts[status] = counts.get(status, 0) + 1

    return counts
