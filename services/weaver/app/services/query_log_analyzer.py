"""Query log analyzer — aggregate column usage stats from parsed logs.

Reads ``insight_query_logs`` via asyncpg and produces an ``AnalysisResult``
containing per-column statistics used by the driver scorer.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.cooccur_matrix import CooccurConfig, CooccurMatrix, build_cooccur_matrix


# ── Dataclasses ──────────────────────────────────────────────

@dataclass
class AnalyzerConfig:
    max_queries: int = 50_000
    sample_rate: float = 1.0
    max_candidate_columns: int = 500
    exclude_common_columns: frozenset = frozenset(
        {"id", "created_at", "updated_at", "deleted_at", "is_deleted"}
    )


@dataclass
class CandidateStats:
    appear: int = 0
    in_select: int = 0
    in_filter: int = 0
    in_group_by: int = 0
    join_degree: int = 0
    cooccur_with_kpi: int = 0
    distinct_tables: Set[str] = field(default_factory=set)
    distinct_queries: int = 0


@dataclass
class QueryEvidence:
    query_id: str
    datasource: str
    executed_at: str
    tables: list
    joins: list
    predicates: list
    select_cols: list
    group_by: list


@dataclass
class AnalysisResult:
    time_from: str
    time_to: str
    total_queries: int
    used_queries: int
    column_stats: Dict[str, CandidateStats]
    table_counts: Dict[str, int]
    join_edges: Dict[Tuple[str, str], int]
    evidence_samples: Dict[str, List[QueryEvidence]]
    cooccur: Optional[CooccurMatrix] = None


# ── Helpers ──────────────────────────────────────────────────

def _is_time_like(col_name: str) -> bool:
    low = col_name.lower()
    return any(
        kw in low
        for kw in ("date", "time", "timestamp", "created", "updated",
                    "modified", "_at", "_dt", "_ts")
    )


def _normalize_col_key(raw: str) -> str:
    """``'schema.table.column'`` → ``'table.column'`` (strip schema)."""
    parts = raw.strip().lower().split(".")
    if len(parts) >= 3:
        return f"{parts[-2]}.{parts[-1]}"
    if len(parts) == 2:
        return f"{parts[0]}.{parts[1]}"
    return ""


def _safe_json(val: Any) -> list:
    """Parse JSONB field — handles str, list, and None."""
    if val is None:
        return []
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []
    if isinstance(val, list):
        return val
    return []


# ── Main Analysis ────────────────────────────────────────────

async def analyze_query_logs(
    conn: Any,
    tenant_id: str,
    datasource: str,
    time_from_iso: str,
    time_to_iso: str,
    kpi_fingerprint: str,
    config: AnalyzerConfig | None = None,
    kpi_definitions: list | None = None,
) -> AnalysisResult:
    """Read parsed query logs → aggregate column usage statistics.

    Expects RLS to be set before calling.  Only rows with
    ``parse_status IN ('parsed', 'fallback')`` are used.

    Args:
        kpi_definitions: Optional list of ``KpiDefinition`` objects from the
            ontology store.  When provided, KPI presence in each query is
            detected via ``KpiMetricMapper`` (exact/alias/fuzzy) instead of
            simple substring matching.
    """
    if config is None:
        config = AnalyzerConfig()

    # Build KPI mapper once (outside per-row loop) when definitions are available
    kpi_mapper = None
    if kpi_definitions:
        from app.services.kpi_metric_mapper import KpiMetricMapper
        kpi_mapper = KpiMetricMapper(kpi_definitions)

    # asyncpg requires datetime objects, not ISO strings
    def _to_dt(v: Any) -> datetime:
        if isinstance(v, datetime):
            return v
        s = str(v)
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)

    dt_from = _to_dt(time_from_iso)
    dt_to = _to_dt(time_to_iso)

    if datasource:
        rows = await conn.fetch(
            """
            SELECT id, datasource_id, executed_at,
                   parsed_select, parsed_tables, parsed_joins,
                   parsed_predicates, parsed_group_by
            FROM weaver.insight_query_logs
            WHERE tenant_id = $1
              AND datasource_id = $2
              AND executed_at BETWEEN $3 AND $4
              AND parse_status IN ('parsed', 'fallback')
            ORDER BY executed_at DESC
            LIMIT $5
            """,
            tenant_id, datasource, dt_from, dt_to, config.max_queries,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, datasource_id, executed_at,
                   parsed_select, parsed_tables, parsed_joins,
                   parsed_predicates, parsed_group_by
            FROM weaver.insight_query_logs
            WHERE tenant_id = $1
              AND executed_at BETWEEN $2 AND $3
              AND parse_status IN ('parsed', 'fallback')
            ORDER BY executed_at DESC
            LIMIT $4
            """,
            tenant_id, dt_from, dt_to, config.max_queries,
        )
    total = len(rows)

    # Sample if configured
    if config.sample_rate < 1.0 and total > 0:
        import random
        k = max(1, int(total * config.sample_rate))
        used_rows = random.sample(list(rows), k)
    else:
        used_rows = rows

    # Aggregate
    column_stats: Dict[str, CandidateStats] = defaultdict(CandidateStats)
    table_counts: Dict[str, int] = Counter()
    join_edges: Dict[Tuple[str, str], int] = Counter()
    col_to_queries: Dict[str, Set[str]] = defaultdict(set)
    evidence_samples: Dict[str, List[QueryEvidence]] = defaultdict(list)
    per_query_columns: List[Set[str]] = []

    kpi_lower = kpi_fingerprint.lower()

    for row in used_rows:
        query_id = str(row["id"])
        ds = row["datasource_id"] or datasource
        executed_at = row["executed_at"]

        tables = _safe_json(row["parsed_tables"])
        joins = _safe_json(row["parsed_joins"])
        preds = _safe_json(row["parsed_predicates"])
        sel = _safe_json(row["parsed_select"])
        gb = _safe_json(row["parsed_group_by"])

        # Table counts
        for t in tables:
            tbl_name = (t if isinstance(t, str) else (t.get("name") if isinstance(t, dict) else "")).lower()
            if tbl_name:
                table_counts[tbl_name] += 1

        # Join edges
        for j in joins:
            if not isinstance(j, dict):
                continue
            lt = (j.get("left_table") or "").lower()
            rt = (j.get("right_table") or "").lower()
            if lt and rt and lt != rt:
                key = tuple(sorted([lt, rt]))
                join_edges[key] += 1

        # KPI proxy detection
        if kpi_mapper is not None:
            sel_for_match = [
                {"expr": s, "alias": ""} if isinstance(s, str)
                else {"expr": s.get("expr", ""), "alias": s.get("alias", "")}
                for s in sel
            ]
            has_kpi = kpi_mapper.best_match(sel_for_match) is not None
        else:
            has_kpi = False
            for s in sel:
                if isinstance(s, str):
                    if kpi_lower in s.lower():
                        has_kpi = True
                        break
                elif isinstance(s, dict):
                    combined = (s.get("expr", "") + s.get("alias", "")).lower()
                    if kpi_lower in combined:
                        has_kpi = True
                        break

        cols_in_query: Set[str] = set()

        # Select columns
        for s in sel:
            expr = s if isinstance(s, str) else (s.get("expr", "") if isinstance(s, dict) else "")
            col_key = _normalize_col_key(expr)
            if not col_key or "." not in col_key:
                continue
            t, c = col_key.split(".", 1)
            if c in config.exclude_common_columns:
                continue
            cs = column_stats[col_key]
            cs.appear += 1
            cs.in_select += 1
            cs.distinct_tables.add(t)
            col_to_queries[col_key].add(query_id)
            cols_in_query.add(col_key)

        # Filter columns
        for p in preds:
            col_raw = p if isinstance(p, str) else (p.get("column", "") if isinstance(p, dict) else "")
            col_key = _normalize_col_key(col_raw)
            if not col_key or "." not in col_key:
                continue
            t, c = col_key.split(".", 1)
            if c in config.exclude_common_columns:
                continue
            cs = column_stats[col_key]
            cs.appear += 1
            cs.in_filter += 1
            cs.distinct_tables.add(t)
            col_to_queries[col_key].add(query_id)
            cols_in_query.add(col_key)

        # Group-by columns
        for g in gb:
            g_raw = g if isinstance(g, str) else (g.get("column", "") if isinstance(g, dict) else "")
            col_key = _normalize_col_key(g_raw)
            if not col_key or "." not in col_key:
                continue
            t, c = col_key.split(".", 1)
            if c in config.exclude_common_columns:
                continue
            cs = column_stats[col_key]
            cs.appear += 1
            cs.in_group_by += 1
            cs.distinct_tables.add(t)
            col_to_queries[col_key].add(query_id)
            cols_in_query.add(col_key)

        # Join degree
        for j in joins:
            if not isinstance(j, dict):
                continue
            for side in ("left", "right"):
                col_raw = j.get(f"{side}_column") or ""
                col_key = _normalize_col_key(col_raw)
                if not col_key or "." not in col_key:
                    continue
                t, c = col_key.split(".", 1)
                if c in config.exclude_common_columns:
                    continue
                cs = column_stats[col_key]
                cs.appear += 1
                cs.join_degree += 1
                cs.distinct_tables.add(t)
                col_to_queries[col_key].add(query_id)
                cols_in_query.add(col_key)

        # KPI co-occurrence
        if has_kpi:
            for ck in cols_in_query:
                column_stats[ck].cooccur_with_kpi += 1

        # Evidence samples (bounded)
        ev = QueryEvidence(
            query_id=query_id, datasource=ds,
            executed_at=str(executed_at),
            tables=tables, joins=joins,
            predicates=preds, select_cols=sel, group_by=gb,
        )
        for ck in list(cols_in_query)[:50]:
            if len(evidence_samples[ck]) < 10:
                evidence_samples[ck].append(ev)

        # Collect for co-occur matrix (PR8)
        if cols_in_query:
            per_query_columns.append(cols_in_query.copy())

    # Finalize distinct query counts
    for ck, qs in col_to_queries.items():
        column_stats[ck].distinct_queries = len(qs)

    # Hard cap candidates
    if len(column_stats) > config.max_candidate_columns:
        keys_sorted = sorted(
            column_stats.keys(),
            key=lambda k: column_stats[k].cooccur_with_kpi,
            reverse=True,
        )
        keep = set(keys_sorted[:config.max_candidate_columns])
        column_stats = {k: v for k, v in column_stats.items() if k in keep}
        evidence_samples = {k: v for k, v in evidence_samples.items() if k in keep}

    # Build co-occur matrix (PR8)
    cooccur = build_cooccur_matrix(
        per_query_columns=per_query_columns,
        config=CooccurConfig(max_cols_per_query=50, min_cooccur_count=2),
    )

    return AnalysisResult(
        time_from=time_from_iso,
        time_to=time_to_iso,
        total_queries=total,
        used_queries=len(used_rows),
        column_stats=dict(column_stats),
        table_counts=dict(table_counts),
        join_edges=dict(join_edges),
        evidence_samples=dict(evidence_samples),
        cooccur=cooccur,
    )
