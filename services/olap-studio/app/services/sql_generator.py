"""피벗 SQL 생성기 — 스타 스키마 기반 SELECT 쿼리 빌더.

큐브 메타데이터를 기반으로 피벗 질의를 PostgreSQL SELECT 문으로 변환한다.
모든 사용자 입력 값은 $N 파라미터로 바인딩하여 SQL 인젝션을 방지한다.
"""
from __future__ import annotations

import re

from app.models.query import PivotQuery

# 허용된 SQL 연산자 — 화이트리스트 기반 검증
ALLOWED_OPERATORS = frozenset({"=", "!=", ">", "<", ">=", "<=", "IN", "NOT IN", "LIKE"})
ALLOWED_AGGREGATORS = frozenset({"SUM", "COUNT", "AVG", "MIN", "MAX", "COUNT_DISTINCT"})


def _sanitize_identifier(name: str) -> str:
    """식별자를 안전하게 이스케이프한다.

    영숫자+언더스코어만 포함하면 그대로 반환하고,
    그 외에는 큰따옴표로 감싸되 내부 큰따옴표는 이중 이스케이프한다.
    """
    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        return name
    # 큰따옴표 이스케이프: " → ""
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def generate_pivot_sql(
    query: PivotQuery,
    schema_prefix: str = "dw",
) -> tuple[str, list]:
    """PivotQuery를 PostgreSQL SELECT 문 + 파라미터 리스트로 변환한다.

    SQL 문은 $1, $2, ... 플레이스홀더를 사용하고,
    실제 값은 params 리스트에 담아 asyncpg에 전달한다.
    반환값 (sql, params) — sql이 비어있으면 생성 실패.
    """
    if not query.measures:
        return "", []

    params: list = []
    select_parts: list[str] = []
    group_by_parts: list[str] = []

    # 행/열 차원 — 식별자만 사용 (파라미터 바인딩 불필요)
    for field in query.rows + query.columns:
        col_ref = f"{_sanitize_identifier(schema_prefix)}.{_sanitize_identifier(field.dimension)}.{_sanitize_identifier(field.level)}"
        select_parts.append(col_ref)
        group_by_parts.append(col_ref)

    # 측정값 — 집계 함수 화이트리스트 검증
    for m in query.measures:
        agg = m.aggregator.upper()
        if agg not in ALLOWED_AGGREGATORS:
            agg = "SUM"  # 안전한 기본값으로 폴백
        measure_col = _sanitize_identifier(m.name)
        select_parts.append(f"{agg}({measure_col}) AS {measure_col}")

    # FROM (현재는 고정 — 추후 큐브 메타에서 fact_table 참조)
    from_clause = f"{_sanitize_identifier(schema_prefix)}.fact_table"

    # WHERE — 모든 값은 파라미터 바인딩
    where_parts: list[str] = []
    for f in query.filters:
        op = f.operator.upper()
        if op not in ALLOWED_OPERATORS:
            raise ValueError(f"허용되지 않은 연산자: {f.operator}")

        col = f"{_sanitize_identifier(schema_prefix)}.{_sanitize_identifier(f.dimension)}.{_sanitize_identifier(f.level)}"

        if op in ("IN", "NOT IN") and isinstance(f.value, list):
            placeholders = ", ".join(f"${len(params) + i + 1}" for i in range(len(f.value)))
            params.extend(f.value)
            where_parts.append(f"{col} {op} ({placeholders})")
        else:
            params.append(f.value if isinstance(f.value, str) else str(f.value))
            where_parts.append(f"{col} {op} ${len(params)}")

    # SQL 조합
    sql_lines = [
        "SELECT",
        "    " + ",\n    ".join(select_parts),
        f"FROM {from_clause}",
    ]
    if where_parts:
        sql_lines.append("WHERE " + " AND ".join(where_parts))
    if group_by_parts:
        sql_lines.append("GROUP BY " + ", ".join(group_by_parts))
        sql_lines.append("ORDER BY " + ", ".join(group_by_parts))
    # LIMIT 상한 보호 — 최대 10000행
    sql_lines.append(f"LIMIT {min(query.limit, 10000)}")

    return "\n".join(sql_lines), params
