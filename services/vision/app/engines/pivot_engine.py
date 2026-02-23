# 큐브 메타 기반 피벗 SQL 생성 (olap-api.md, mondrian-parser.md, V3-2)
from __future__ import annotations

import re
from typing import Any

ALLOWED_TABLES = frozenset({
    "mv_business_fact", "mv_cashflow_fact",
    "dim_case_type", "dim_org", "dim_time", "dim_stakeholder_type",
    "dim_organization", "dim_stakeholder",
})

AGGREGATOR_SQL = {
    "sum": "SUM(f.{col})",
    "avg": "AVG(f.{col})",
    "count": "COUNT(f.{col})",
    "min": "MIN(f.{col})",
    "max": "MAX(f.{col})",
    "distinct-count": "COUNT(DISTINCT f.{col})",
}


def _resolve_level_column(cube: dict[str, Any], dimension_level: str) -> tuple[str, str]:
    """'Dimension.Level' → (table_alias, column_name)."""
    if "." not in dimension_level:
        return "f", dimension_level
    dim_name, level_name = dimension_level.split(".", 1)
    dim_name = dim_name.strip()
    level_name = level_name.strip()
    for d in cube.get("dimension_details") or []:
        if (d.get("name") or "").strip() != dim_name:
            continue
        table = (d.get("table") or "").strip()
        if table and table not in ALLOWED_TABLES:
            table = "f"
        alias = _table_alias(table) if table else "f"
        for lev in d.get("levels") or []:
            if (lev.get("name") or "").strip() == level_name:
                col = (lev.get("column") or level_name).strip()
                return alias, col
        return alias, (d.get("levels") or [{}])[0].get("column", level_name) if d.get("levels") else level_name
    return "f", dimension_level.replace(".", "_")


def _table_alias(table: str) -> str:
    """안전한 테이블 별칭 (영숫자만)."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", table)[:20] or "t"


def _measure_expr(cube: dict[str, Any], measure_name: str) -> str:
    """측도 이름 → SQL 집계 식."""
    for m in cube.get("measure_details") or []:
        if (m.get("name") or "").strip() == measure_name.strip():
            col = (m.get("column") or measure_name).strip()
            agg = (m.get("aggregator") or "sum").strip().lower()
            tpl = AGGREGATOR_SQL.get(agg) or AGGREGATOR_SQL["sum"]
            return tpl.format(col=col)
    col = measure_name.strip().replace(" ", "_")
    return f"SUM(f.{col})"


def generate_pivot_sql(
    cube: dict[str, Any],
    rows: list[str],
    columns: list[str],
    measures: list[str],
    filters: list[dict[str, Any]],
    sort_by: str | None = None,
    sort_order: str = "DESC",
    limit: int = 1000,
    offset: int = 0,
) -> tuple[str, list[Any]]:
    """
    피벗 요청으로부터 SELECT SQL과 파라미터 리스트 생성.
    Returns (sql, params) for parameterized execution.
    """
    fact_table = (cube.get("fact_table") or "mv_business_fact").strip()
    if fact_table not in ALLOWED_TABLES:
        fact_table = "mv_business_fact"
    params: list[Any] = []
    select_parts = []
    group_parts = []
    join_set = set()
    join_clauses = []

    def add_select(alias: str, col: str, label: str) -> None:
        safe_col = re.sub(r"[^a-zA-Z0-9_.]", "", col)
        safe_label = re.sub(r"[^a-zA-Z0-9_.]", "_", label)
        select_parts.append(f"{alias}.{safe_col} AS \"{safe_label}\"")
        group_parts.append(f"{alias}.{safe_col}")

    for r in rows:
        alias, col = _resolve_level_column(cube, r)
        add_select(alias, col, r)
        if alias != "f" and alias not in join_set:
            join_set.add(alias)
            dim = next((d for d in (cube.get("dimension_details") or []) if _table_alias(d.get("table", "")) == alias), None)
            if dim:
                ft = dim.get("foreign_key", "")
                if ft:
                    join_clauses.append(f"LEFT JOIN {dim.get('table', '')} {alias} ON f.{ft} = {alias}.{dim.get('primary_key', 'id')}")

    for c in columns:
        alias, col = _resolve_level_column(cube, c)
        add_select(alias, col, c)
        if alias != "f" and alias not in join_set:
            join_set.add(alias)
            dim = next((d for d in (cube.get("dimension_details") or []) if _table_alias(d.get("table", "")) == alias), None)
            if dim:
                ft = dim.get("foreign_key", "")
                if ft:
                    join_clauses.append(f"LEFT JOIN {dim.get('table', '')} {alias} ON f.{ft} = {alias}.{dim.get('primary_key', 'id')}")

    for m in measures:
        expr = _measure_expr(cube, m)
        safe_label = re.sub(r"[^a-zA-Z0-9_.]", "_", m)
        select_parts.append(f"{expr} AS \"{safe_label}\"")

    where_parts = []
    for f in filters:
        dim_level = (f.get("dimension_level") or "").strip()
        op = (f.get("operator") or "=").strip().lower()
        vals = f.get("values") or []
        alias, col = _resolve_level_column(cube, dim_level)
        safe_col = re.sub(r"[^a-zA-Z0-9_.]", "", col)
        if op == "=" and len(vals) == 1:
            where_parts.append(f"{alias}.{safe_col} = %s")
            params.append(vals[0])
        elif op == "!=" and len(vals) == 1:
            where_parts.append(f"{alias}.{safe_col} != %s")
            params.append(vals[0])
        elif op == "in" and vals:
            placeholders = ", ".join(["%s"] * len(vals))
            where_parts.append(f"{alias}.{safe_col} IN ({placeholders})")
            params.extend(vals)
        elif op == "not_in" and vals:
            placeholders = ", ".join(["%s"] * len(vals))
            where_parts.append(f"{alias}.{safe_col} NOT IN ({placeholders})")
            params.extend(vals)
        elif op == ">=" and len(vals) == 1:
            where_parts.append(f"{alias}.{safe_col} >= %s")
            params.append(vals[0])
        elif op == "<=" and len(vals) == 1:
            where_parts.append(f"{alias}.{safe_col} <= %s")
            params.append(vals[0])
        elif op == "between" and len(vals) >= 2:
            where_parts.append(f"{alias}.{safe_col} BETWEEN %s AND %s")
            params.append(vals[0])
            params.append(vals[1])

    sql = f"SELECT {', '.join(select_parts)} FROM {fact_table} f"
    if join_clauses:
        sql += " " + " ".join(join_clauses)
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    if group_parts:
        sql += " GROUP BY " + ", ".join(group_parts)
    else:
        sql += " GROUP BY ()"  # only measures
    if sort_by:
        sort_col = _measure_expr(cube, sort_by) if sort_by in (measures or []) else f'"{sort_by}"'
        order = "DESC" if (sort_order or "DESC").strip().upper() == "DESC" else "ASC"
        sql += f" ORDER BY {sort_col} {order}"
    sql += f" LIMIT %s OFFSET %s"
    params.append(limit)
    params.append(offset)
    return sql, params
