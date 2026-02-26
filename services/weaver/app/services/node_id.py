"""Unified node ID convention for Instance Graph / Impact Graph.

Node ID patterns:
  - Table:      ``tbl:{schema}.{table}``
  - Column:     ``col:{schema}.{table}.{column}``
  - KPI:        ``kpi:{kpi_id}``
  - Metric:     ``metric:{fingerprint}``
  - Datasource: ``ds:{datasource_id}``

Both Instance Graph (schema-based) and Impact Graph (query-based)
use these functions so that frontend can seamlessly switch between
exploration and insight views.
"""
from __future__ import annotations

import re
from typing import Optional

PREFIX_TABLE = "tbl"
PREFIX_COLUMN = "col"
PREFIX_KPI = "kpi"
PREFIX_METRIC = "metric"
PREFIX_DATASOURCE = "ds"

_VALID_PREFIXES = frozenset({
    PREFIX_TABLE, PREFIX_COLUMN, PREFIX_KPI,
    PREFIX_METRIC, PREFIX_DATASOURCE,
})


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9_.:-]", "", s.lower().strip())


def table_node_id(schema: str, table: str) -> str:
    return f"{PREFIX_TABLE}:{_norm(schema)}.{_norm(table)}"


def column_node_id(schema: str, table: str, column: str) -> str:
    return f"{PREFIX_COLUMN}:{_norm(schema)}.{_norm(table)}.{_norm(column)}"


def column_node_id_from_key(column_key: str, schema: str = "public") -> str:
    """Convert legacy ``table.column`` key to unified ``col:schema.table.column``."""
    parts = column_key.lower().split(".")
    if len(parts) == 2:
        return f"{PREFIX_COLUMN}:{_norm(schema)}.{parts[0]}.{parts[1]}"
    if len(parts) >= 3:
        return f"{PREFIX_COLUMN}:{parts[0]}.{parts[1]}.{parts[2]}"
    return f"{PREFIX_COLUMN}:{_norm(schema)}.unknown.{column_key.lower()}"


def kpi_node_id(kpi_id: str) -> str:
    return f"{PREFIX_KPI}:{_norm(kpi_id)}"


def metric_node_id(fingerprint: str) -> str:
    return f"{PREFIX_METRIC}:{_norm(fingerprint)}"


def datasource_node_id(datasource_id: str) -> str:
    return f"{PREFIX_DATASOURCE}:{_norm(datasource_id)}"


def parse_node_id(node_id: str) -> Optional[dict]:
    """Parse a unified node ID back into components.

    Returns ``{"prefix": "col", "parts": ["public", "orders", "amount"]}``
    or ``None`` if invalid.
    """
    if ":" not in node_id:
        return None
    prefix, rest = node_id.split(":", 1)
    if prefix not in _VALID_PREFIXES:
        return None
    return {"prefix": prefix, "parts": rest.split(".")}


def is_same_entity(id_a: str, id_b: str) -> bool:
    """Check if two node IDs refer to the same logical entity.

    Handles schema defaulting (e.g., ``col:orders.amount`` == ``col:public.orders.amount``).
    """
    pa = parse_node_id(id_a)
    pb = parse_node_id(id_b)
    if not pa or not pb:
        return False
    if pa["prefix"] != pb["prefix"]:
        return False

    a_parts = pa["parts"]
    b_parts = pb["parts"]
    if pa["prefix"] == PREFIX_COLUMN:
        if len(a_parts) == 2:
            a_parts = ["public"] + a_parts
        if len(b_parts) == 2:
            b_parts = ["public"] + b_parts
    elif pa["prefix"] == PREFIX_TABLE:
        if len(a_parts) == 1:
            a_parts = ["public"] + a_parts
        if len(b_parts) == 1:
            b_parts = ["public"] + b_parts

    return a_parts == b_parts
