"""메타데이터 추출 오케스트레이션. extract-metadata SSE 스트림 및 카탈로그 반환."""
from __future__ import annotations

from typing import Any, AsyncGenerator

from app.core.adapters import get_adapter


def schema_result_to_catalog(schema_result: dict[str, Any]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """extract_schema() 결과를 weaver 런타임 catalog 형식으로 변환."""
    catalog: dict[str, dict[str, list[dict[str, Any]]]] = {}
    schema_name = str(schema_result.get("schema") or "public").strip()
    tables = schema_result.get("tables") or []
    for table in tables:
        if not isinstance(table, dict):
            continue
        table_name = str(table.get("name") or "").strip()
        if not table_name:
            continue
        columns = table.get("columns") or []
        col_list = []
        for col in columns:
            if not isinstance(col, dict):
                continue
            name = str(col.get("name") or "").strip()
            if not name:
                continue
            col_list.append({
                "name": name,
                "data_type": str(col.get("type") or col.get("data_type") or "string"),
                "nullable": bool(col.get("nullable", True)),
            })
        catalog.setdefault(schema_name, {})[table_name] = col_list
    return catalog


async def extract_metadata_stream(
    datasource_name: str,
    engine: str,
    connection: dict[str, Any],
    *,
    target_schemas: list[str] | None = None,
    include_sample_data: bool = False,
    sample_limit: int = 5,
    include_row_counts: bool = True,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    어댑터로 스키마 추출 후 SSE용 이벤트를 yield.
    metadata-api.md §2.4 이벤트: started, progress, schema_found, table_found, columns_extracted, fk_extracted, complete, error.
    """
    yield {
        "event": "started",
        "data": {"datasource": datasource_name, "engine": engine},
    }
    try:
        adapter = get_adapter(engine, connection)
    except Exception as e:
        yield {"event": "error", "data": {"message": str(e), "code": "ADAPTER_ERROR"}}
        raise
    try:
        schema_result = await adapter.extract_schema(include_row_counts=include_row_counts)
    except Exception as e:
        yield {"event": "error", "data": {"message": str(e), "code": "EXTRACTION_ERROR"}}
        raise
    schema_name = str(schema_result.get("schema") or "public").strip()
    if target_schemas and schema_name not in target_schemas:
        yield {"event": "complete", "data": {"tables_count": 0, "message": "no matching schemas"}}
        return
    yield {"event": "schema_found", "data": {"schema": schema_name}}
    yield {"event": "progress", "data": {"phase": "schemas", "completed": 1, "total": 1, "percent": 100}}
    tables = schema_result.get("tables") or []
    total_tables = len([t for t in tables if isinstance(t, dict) and str(t.get("name") or "").strip()])
    foreign_keys = schema_result.get("foreign_keys") or []
    fks_by_table: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for fk in foreign_keys:
        if not isinstance(fk, dict):
            continue
        key = (str(fk.get("source_schema") or schema_name).strip(), str(fk.get("source_table") or "").strip())
        if key[1]:
            fks_by_table.setdefault(key, []).append(fk)
    for idx, table in enumerate(tables):
        if not isinstance(table, dict):
            continue
        table_name = str(table.get("name") or "").strip()
        if not table_name:
            continue
        if total_tables > 0:
            pct = min(100, int(100 * (idx + 1) / total_tables))
            yield {"event": "progress", "data": {"phase": "tables", "completed": idx + 1, "total": total_tables, "percent": pct}}
        columns = table.get("columns") or []
        row_count = table.get("row_count") if include_row_counts else None
        table_found_data = {"table": table_name, "schema": schema_name, "columns_count": len(columns)}
        if row_count is not None:
            table_found_data["row_count"] = row_count
        yield {"event": "table_found", "data": table_found_data}
        yield {"event": "columns_extracted", "data": {"table": table_name, "schema": schema_name, "columns": columns}}
        fks_for_table = fks_by_table.get((schema_name, table_name)) or []
        if fks_for_table:
            targets = list(dict.fromkeys([f["target_table"] for f in fks_for_table]))
            yield {"event": "fk_extracted", "data": {"schema": schema_name, "table": table_name, "fk_count": len(fks_for_table), "targets": targets}}
    catalog = schema_result_to_catalog(schema_result)
    tables_count = sum(len(t) for t in catalog.values())
    # catalog·foreign_keys는 서버에서 ds 갱신·Neo4j FK_TO용; SSE에는 tables_count/schemas_count만 전송
    yield {"event": "complete", "data": {"tables_count": tables_count, "schemas_count": len(catalog), "_catalog": catalog, "_foreign_keys": foreign_keys}}
