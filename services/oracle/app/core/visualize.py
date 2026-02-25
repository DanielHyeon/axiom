"""
시각화 추천: 결과 컬럼·행 수 기반 chart_type/config (nl2sql-pipeline §3.7, text2sql-api data.visualization).
"""
from __future__ import annotations

from typing import Any


# Column names commonly used as time/date axis
_TIME_NAME_HINTS = frozenset([
    "date", "sale_date", "started_at", "completed_at", "occurred_at",
    "created_at", "updated_at", "month", "quarter", "year",
])

# Column names commonly used as numeric measures
_MEASURE_NAME_HINTS = frozenset([
    "revenue", "cost", "quantity", "amount", "total", "sum", "avg",
    "count", "rate", "score", "duration", "duration_minutes",
    "duration_seconds", "price", "profit", "margin",
])

_NUMERIC_PG_TYPES = frozenset([
    "integer", "int", "int4", "int8", "bigint", "smallint",
    "numeric", "decimal", "float", "float4", "float8",
    "real", "double precision", "serial", "bigserial",
    "numeric(15,2)", "numeric(10,2)",
])


def _is_numeric_value(val: Any) -> bool:
    """Check if a sample value looks numeric."""
    if val is None:
        return False
    if isinstance(val, (int, float)):
        return True
    if isinstance(val, str):
        try:
            float(val.replace(",", ""))
            return True
        except (ValueError, AttributeError):
            return False
    return False


def _is_date_value(val: Any) -> bool:
    """Check if a sample value looks like a date/time."""
    if val is None:
        return False
    if hasattr(val, "isoformat"):  # datetime, date objects
        return True
    if isinstance(val, str):
        s = val.strip()
        # ISO date: 2024-06-20 or 2024-06-20T10:00:00
        if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
            return True
        # YYYY-MM format
        if len(s) == 7 and s[4:5] == "-":
            return True
    return False


def _infer_column_role(name: str, col_type: str, sample: Any) -> str:
    name_lower = (name or "").lower()
    type_lower = (col_type or "").lower()

    # 1. Check declared type first
    if "date" in type_lower or "timestamp" in type_lower:
        return "time"
    if type_lower in _NUMERIC_PG_TYPES:
        return "measure"

    # 2. Check column name hints
    if name_lower in _TIME_NAME_HINTS:
        return "time"
    # Patterns like *_at, *_date
    if name_lower.endswith("_at") or name_lower.endswith("_date"):
        return "time"
    # Korean time-related suffixes in aliases
    if any(k in name_lower for k in ("년", "월", "분기", "yyyy")):
        return "time"

    if name_lower in _MEASURE_NAME_HINTS:
        return "measure"
    # Patterns containing common measure words
    if any(k in name_lower for k in (
        "count", "amount", "value", "rate", "total", "sum", "avg",
        "revenue", "cost", "quantity", "price", "profit", "margin",
        "매출", "비용", "건수", "합계", "평균", "수량", "이익", "성장률",
        "시간", "duration",
    )):
        return "measure"

    if "id" in name_lower and name_lower != "id":
        return "dimension"
    if any(k in name_lower for k in ("name", "label", "title", "type", "status", "region", "category")):
        return "category"

    # 3. Infer from actual sample data
    if _is_date_value(sample):
        return "time"
    if _is_numeric_value(sample):
        return "measure"

    return "category"


def recommend_visualization(
    columns: list[dict[str, Any]],
    rows: list[list[Any]],
    row_count: int,
) -> dict[str, Any] | None:
    """
    컬럼 타입·이름·데이터 패턴으로 chart_type과 config 추천.
    반환: {"chart_type": "bar"|"line"|"pie"|"scatter"|"kpi_card"|"table", "config": {...}} 또는 None.
    """
    if not columns or row_count == 0:
        return None
    col_names = [c.get("name") or str(i) for i, c in enumerate(columns)]
    col_types = [str((c.get("type") or "varchar")).lower() for c in columns]
    samples = rows[0] if rows else []
    roles = [
        _infer_column_role(col_names[i], col_types[i], samples[i] if i < len(samples) else None)
        for i in range(len(col_names))
    ]
    measures = [i for i, r in enumerate(roles) if r == "measure"]
    categories = [i for i, r in enumerate(roles) if r == "category"]
    time_cols = [i for i, r in enumerate(roles) if r == "time"]

    x_col = None
    y_col = None
    if time_cols and measures:
        x_col = col_names[time_cols[0]]
        y_col = col_names[measures[0]]
        return {
            "chart_type": "line",
            "config": {
                "x_column": x_col,
                "y_column": y_col,
                "x_label": x_col,
                "y_label": y_col,
            },
        }
    if categories and measures:
        x_col = col_names[categories[0]]
        y_col = col_names[measures[0]]
        return {
            "chart_type": "bar",
            "config": {
                "x_column": x_col,
                "y_column": y_col,
                "x_label": x_col,
                "y_label": y_col,
            },
        }
    if len(measures) >= 2 and not categories and not time_cols:
        return {
            "chart_type": "scatter",
            "config": {
                "x_column": col_names[measures[0]],
                "y_column": col_names[measures[1]],
                "x_label": col_names[measures[0]],
                "y_label": col_names[measures[1]],
            },
        }
    if len(measures) == 1 and (row_count == 1 or not categories):
        return {
            "chart_type": "kpi_card",
            "config": {"value_column": col_names[measures[0]], "label": col_names[measures[0]]},
        }
    if categories and len(categories) >= 1 and row_count <= 12:
        return {
            "chart_type": "pie",
            "config": {
                "label_column": col_names[categories[0]],
                "value_column": col_names[measures[0]] if measures else col_names[0],
            },
        }
    return {
        "chart_type": "table",
        "config": {"columns": col_names},
    }
