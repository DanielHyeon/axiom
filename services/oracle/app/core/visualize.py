"""
시각화 추천: 결과 컬럼·행 수 기반 chart_type/config (nl2sql-pipeline §3.7, text2sql-api data.visualization).
"""
from __future__ import annotations

from typing import Any


def _infer_column_role(name: str, col_type: str, sample: Any) -> str:
    name_lower = (name or "").lower()
    type_lower = (col_type or "").lower()
    if "date" in type_lower or "time" in type_lower or "at" in name_lower and "date" in name_lower:
        return "time"
    if "id" in name_lower and name_lower != "id":
        return "dimension"
    if "name" in name_lower or "label" in name_lower or "title" in name_lower:
        return "category"
    if "count" in name_lower or "amount" in name_lower or "value" in name_lower or "rate" in name_lower:
        return "measure"
    if type_lower in ("integer", "int", "bigint", "numeric", "decimal", "float", "real"):
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
