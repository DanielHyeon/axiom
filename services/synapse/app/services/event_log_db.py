import json
import os
import re
import sys
from typing import Any


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DISALLOWED_WHERE = re.compile(
    r"(;|--|/\*|\*/|\b(insert|update|delete|drop|alter|create|truncate|grant|revoke)\b)",
    re.IGNORECASE,
)


class EventLogDbError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _validate_identifier(value: str, name: str) -> str:
    text = (value or "").strip()
    if not text or not _IDENT.fullmatch(text):
        raise EventLogDbError("INVALID_REQUEST", f"invalid {name}")
    return text


def _validate_where_clause(where_clause: str | None) -> str | None:
    if where_clause is None:
        return None
    text = where_clause.strip()
    if not text:
        return None
    if _DISALLOWED_WHERE.search(text):
        raise EventLogDbError("INVALID_REQUEST", "unsafe where_clause")
    return text


def _load_registry() -> dict[str, Any]:
    raw = os.getenv("AXIOM_EVENTLOG_CONNECTIONS_JSON", "{}").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EventLogDbError("DATABASE_CONNECTION_FAILED", "invalid connection registry json") from exc
    if not isinstance(payload, dict):
        raise EventLogDbError("DATABASE_CONNECTION_FAILED", "connection registry must be object")
    return payload


def _resolve_connection(source_config: dict[str, Any]) -> dict[str, Any]:
    connection_id = source_config.get("connection_id")
    if not connection_id:
        raise EventLogDbError("DATABASE_CONNECTION_FAILED", "connection_id is required")

    registry = _load_registry()
    config = registry.get(connection_id)
    if not isinstance(config, dict):
        raise EventLogDbError("DATABASE_CONNECTION_FAILED", "connection config not found")

    engine = str(config.get("engine") or "").strip().lower()
    if engine not in {"postgres", "postgresql"}:
        raise EventLogDbError("DATABASE_CONNECTION_FAILED", f"unsupported engine: {engine}")

    database_url = str(config.get("database_url") or "").strip()
    if not database_url:
        host = str(config.get("host") or "").strip()
        port = int(config.get("port") or 5432)
        database = str(config.get("database") or "").strip()
        user = str(config.get("user") or config.get("username") or "").strip()
        password = str(config.get("password") or "").strip()
        if not host or not database or not user:
            raise EventLogDbError("DATABASE_CONNECTION_FAILED", "postgres connection config missing")
        database_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"

    return {"engine": engine, "database_url": database_url}


def _import_psycopg2():
    try:
        import psycopg2  # type: ignore
        from psycopg2.extras import RealDictCursor  # type: ignore

        return psycopg2, RealDictCursor
    except Exception:
        for path in ("/usr/lib/python3/dist-packages", "/home/daniel/.local/lib/python3.12/site-packages"):
            if path not in sys.path:
                sys.path.append(path)
        import psycopg2  # type: ignore
        from psycopg2.extras import RealDictCursor  # type: ignore

        return psycopg2, RealDictCursor


def fetch_database_rows(
    source_config: dict[str, Any],
    mapping: dict[str, Any],
    where_clause: str | None,
    max_rows: int,
) -> tuple[list[dict[str, Any]], set[str]]:
    conn_info = _resolve_connection(source_config)
    table_name = _validate_identifier(str(source_config.get("table_name") or ""), "table_name")
    schema = str(source_config.get("schema") or "").strip()
    safe_where = _validate_where_clause(where_clause)
    safe_limit = max(1, min(int(max_rows or 1000000), 1000000))

    columns = {
        mapping.get("case_id_column"),
        mapping.get("activity_column"),
        mapping.get("timestamp_column"),
    }
    if mapping.get("resource_column"):
        columns.add(mapping.get("resource_column"))
    for item in mapping.get("additional_columns", []) or []:
        columns.add(item)
    clean_columns = sorted({_validate_identifier(str(col), "column") for col in columns if col})
    if not clean_columns:
        raise EventLogDbError("MISSING_COLUMN", "column mapping is required")

    qualified_table = table_name
    if schema:
        qualified_table = f"{_validate_identifier(schema, 'schema')}.{table_name}"
    select_cols = ", ".join(f'"{col}"' for col in clean_columns)
    sql = f"SELECT {select_cols} FROM {qualified_table}"
    if safe_where:
        sql += f" WHERE {safe_where}"
    sql += f" LIMIT {safe_limit}"

    try:
        psycopg2, cursor_cls = _import_psycopg2()
        conn = psycopg2.connect(conn_info["database_url"])
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(sql)
        rows = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception as exc:
        raise EventLogDbError("DATABASE_CONNECTION_FAILED", f"database query failed: {exc}") from exc

    return rows, set(clean_columns)
