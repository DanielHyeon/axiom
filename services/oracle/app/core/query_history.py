from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog

from app.core.config import settings

logger = structlog.get_logger()


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


def _to_uuid(value: str | UUID | None, *, default: UUID | None = None) -> UUID | None:
    if value is None:
        return default
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


@dataclass
class HistoryPage:
    items: list[dict[str, Any]]
    total_count: int
    page: int
    page_size: int


class QueryHistoryRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self._database_url = database_url or settings.QUERY_HISTORY_DATABASE_URL
        self._schema_ready = False
        self._db_disabled = False
        self._fallback_history: dict[str, list[dict[str, Any]]] = {}
        self._fallback_feedback: dict[str, dict[str, Any]] = {}

    def _connect(self):
        psycopg2, _ = _import_psycopg2()
        return psycopg2.connect(self._database_url, connect_timeout=2)

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS oracle")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS oracle.query_history (
                id UUID PRIMARY KEY,
                tenant_id UUID NOT NULL,
                user_id UUID,
                question TEXT NOT NULL,
                sql TEXT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'success',
                result_json JSONB,
                error_message TEXT,
                execution_time_ms INTEGER,
                row_count INTEGER,
                datasource_id VARCHAR(200) NOT NULL,
                tables_used TEXT[],
                cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
                guard_status VARCHAR(20),
                guard_fixes JSONB,
                pipeline_steps JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS oracle.query_feedback (
                id UUID PRIMARY KEY,
                query_id UUID NOT NULL REFERENCES oracle.query_history(id) ON DELETE CASCADE,
                tenant_id UUID NOT NULL,
                user_id UUID,
                rating VARCHAR(20) NOT NULL,
                corrected_sql TEXT,
                comment TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_query_history_tenant_created ON oracle.query_history(tenant_id, created_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_query_feedback_query_id ON oracle.query_feedback(query_id)")
        conn.commit()
        cur.close()
        conn.close()
        self._schema_ready = True

    def _db_ready(self) -> bool:
        if self._db_disabled:
            return False
        try:
            self._ensure_schema()
            return True
        except Exception as exc:
            self._db_disabled = True
            logger.warning("query_history_db_unavailable_fallback", error=str(exc))
            return False

    def _fallback_save_history(self, record: dict[str, Any], query_id: str, tenant_id: UUID) -> str:
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        item = {
            "id": query_id,
            "tenant_id": str(tenant_id),
            "user_id": str(_to_uuid(record.get("user_id")) or ""),
            "question": str(record.get("question") or ""),
            "sql": str(record.get("sql") or ""),
            "status": str(record.get("status") or "success"),
            "result": record.get("result") if isinstance(record.get("result"), dict) else {},
            "row_count": record.get("row_count"),
            "datasource_id": str(record.get("datasource_id") or ""),
            "created_at": _to_iso(record.get("created_at") or datetime.now(timezone.utc)),
            "metadata": {
                "execution_time_ms": metadata.get("execution_time_ms"),
                "tables_used": metadata.get("tables_used") if isinstance(metadata.get("tables_used"), list) else [],
                "cache_hit": bool(metadata.get("cache_hit", False)),
                "guard_status": metadata.get("guard_status"),
                "guard_fixes": metadata.get("guard_fixes") if isinstance(metadata.get("guard_fixes"), list) else [],
                "pipeline_steps": metadata.get("pipeline_steps") if isinstance(metadata.get("pipeline_steps"), list) else [],
            },
        }
        self._fallback_history.setdefault(str(tenant_id), []).insert(0, item)
        return query_id

    async def save_query_history(self, record: dict[str, Any]) -> str:
        tenant_id = _to_uuid(record.get("tenant_id"), default=UUID("12345678-1234-5678-1234-567812345678"))
        if tenant_id is None:
            raise ValueError("tenant_id is required")
        query_id = str(_to_uuid(record.get("id")) or uuid4())
        if not str(record.get("sql") or ""):
            record = {**record, "sql": "SELECT 1"}

        if not self._db_ready():
            return self._fallback_save_history(record, query_id, tenant_id)

        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        tables_used = metadata.get("tables_used") if isinstance(metadata.get("tables_used"), list) else []
        guard_fixes = metadata.get("guard_fixes") if isinstance(metadata.get("guard_fixes"), list) else []
        pipeline_steps = metadata.get("pipeline_steps") if isinstance(metadata.get("pipeline_steps"), list) else []
        result_json = record.get("result") if isinstance(record.get("result"), (dict, list)) else {}
        user_id = _to_uuid(record.get("user_id"))

        try:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO oracle.query_history(
                    id, tenant_id, user_id, question, sql, status, result_json, error_message,
                    execution_time_ms, row_count, datasource_id, tables_used, cache_hit, guard_status,
                    guard_fixes, pipeline_steps, created_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s::jsonb, %s,
                    %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, COALESCE(%s, NOW())
                )
                """,
                (
                    query_id,
                    str(tenant_id),
                    str(user_id) if user_id else None,
                    str(record.get("question") or ""),
                    str(record.get("sql") or ""),
                    str(record.get("status") or "success"),
                    json.dumps(result_json),
                    record.get("error_message"),
                    metadata.get("execution_time_ms"),
                    record.get("row_count"),
                    str(record.get("datasource_id") or ""),
                    tables_used,
                    bool(metadata.get("cache_hit", False)),
                    metadata.get("guard_status"),
                    json.dumps(guard_fixes),
                    json.dumps(pipeline_steps),
                    record.get("created_at"),
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
            return query_id
        except Exception as exc:
            logger.warning("query_history_db_write_failed_fallback", error=str(exc))
            self._db_disabled = True
            return self._fallback_save_history(record, query_id, tenant_id)

    async def save_feedback(
        self,
        query_id: str,
        rating: str,
        comment: Optional[str] = None,
        corrected_sql: Optional[str] = None,
        tenant_id: str | UUID | None = None,
        user_id: str | UUID | None = None,
    ) -> bool:
        tenant = _to_uuid(tenant_id, default=UUID("12345678-1234-5678-1234-567812345678"))
        if tenant is None:
            raise ValueError("tenant_id is required")

        if not self._db_ready():
            history = self._fallback_history.get(str(tenant), [])
            exists = any(item["id"] == query_id for item in history)
            if not exists:
                return False
            self._fallback_feedback[query_id] = {
                "rating": rating,
                "comment": comment,
                "corrected_sql": corrected_sql,
            }
            return True

        user = _to_uuid(user_id)
        feedback_id = str(uuid4())
        try:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM oracle.query_history WHERE id = %s AND tenant_id = %s LIMIT 1",
                (query_id, str(tenant)),
            )
            if not cur.fetchone():
                cur.close()
                conn.close()
                return False
            cur.execute(
                """
                INSERT INTO oracle.query_feedback(id, query_id, tenant_id, user_id, rating, corrected_sql, comment, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (feedback_id, query_id, str(tenant), str(user) if user else None, rating, corrected_sql, comment),
            )
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as exc:
            logger.warning("query_feedback_db_write_failed_fallback", error=str(exc))
            self._db_disabled = True
            history = self._fallback_history.get(str(tenant), [])
            exists = any(item["id"] == query_id for item in history)
            if exists:
                self._fallback_feedback[query_id] = {
                    "rating": rating,
                    "comment": comment,
                    "corrected_sql": corrected_sql,
                }
            return exists

    async def list_history(
        self,
        tenant_id: str | UUID,
        datasource_id: str | None,
        status: str | None,
        date_from: str | None,
        date_to: str | None,
        page: int,
        page_size: int,
    ) -> HistoryPage:
        tenant = _to_uuid(tenant_id)
        if tenant is None:
            raise ValueError("tenant_id is required")

        if not self._db_ready():
            rows = list(self._fallback_history.get(str(tenant), []))
            filtered = []
            for item in rows:
                if datasource_id and item.get("datasource_id") != datasource_id:
                    continue
                if status and item.get("status") != status:
                    continue
                if date_from and item.get("created_at") < date_from:
                    continue
                if date_to and item.get("created_at") > date_to:
                    continue
                row = {
                    "id": item["id"],
                    "question": item["question"],
                    "sql": item["sql"],
                    "status": item["status"],
                    "execution_time_ms": item["metadata"].get("execution_time_ms"),
                    "row_count": item.get("row_count"),
                    "datasource_id": item.get("datasource_id"),
                    "created_at": item["created_at"],
                    "feedback": self._fallback_feedback.get(item["id"]),
                }
                filtered.append(row)
            total_count = len(filtered)
            offset = (page - 1) * page_size
            return HistoryPage(items=filtered[offset : offset + page_size], total_count=total_count, page=page, page_size=page_size)

        _, cursor_cls = _import_psycopg2()
        where = ["h.tenant_id = %s"]
        params: list[Any] = [str(tenant)]
        if datasource_id:
            where.append("h.datasource_id = %s")
            params.append(datasource_id)
        if status:
            where.append("h.status = %s")
            params.append(status)
        if date_from:
            where.append("h.created_at >= %s::timestamptz")
            params.append(date_from)
        if date_to:
            where.append("h.created_at <= %s::timestamptz")
            params.append(date_to)
        where_sql = " AND ".join(where)
        offset = (page - 1) * page_size

        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=cursor_cls)
            cur.execute(f"SELECT COUNT(*) AS cnt FROM oracle.query_history h WHERE {where_sql}", params)
            total_count = int(cur.fetchone()["cnt"])
            cur.execute(
                f"""
                SELECT
                    h.id, h.question, h.sql, h.status, h.execution_time_ms, h.row_count, h.datasource_id, h.created_at,
                    f.rating AS feedback_rating, f.comment AS feedback_comment
                FROM oracle.query_history h
                LEFT JOIN LATERAL (
                    SELECT rating, comment
                    FROM oracle.query_feedback
                    WHERE query_id = h.id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) f ON TRUE
                WHERE {where_sql}
                ORDER BY h.created_at DESC
                LIMIT %s OFFSET %s
                """,
                params + [page_size, offset],
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
        except Exception as exc:
            logger.warning("query_history_db_read_failed_fallback", error=str(exc))
            self._db_disabled = True
            return await self.list_history(tenant, datasource_id, status, date_from, date_to, page, page_size)

        items = []
        for row in rows:
            item = {
                "id": str(row["id"]),
                "question": row["question"],
                "sql": row["sql"],
                "status": row["status"],
                "execution_time_ms": row["execution_time_ms"],
                "row_count": row["row_count"],
                "datasource_id": row["datasource_id"],
                "created_at": _to_iso(row["created_at"]),
                "feedback": None,
            }
            if row.get("feedback_rating"):
                item["feedback"] = {"rating": row["feedback_rating"], "comment": row.get("feedback_comment")}
            items.append(item)
        return HistoryPage(items=items, total_count=total_count, page=page, page_size=page_size)

    async def get_history_detail(self, tenant_id: str | UUID, query_id: str) -> dict[str, Any] | None:
        tenant = _to_uuid(tenant_id)
        if tenant is None:
            raise ValueError("tenant_id is required")

        if not self._db_ready():
            for item in self._fallback_history.get(str(tenant), []):
                if item["id"] == query_id:
                    return {
                        "id": item["id"],
                        "question": item["question"],
                        "sql": item["sql"],
                        "status": item["status"],
                        "result": item["result"],
                        "metadata": item["metadata"],
                        "row_count": item.get("row_count"),
                        "datasource_id": item.get("datasource_id"),
                        "created_at": item["created_at"],
                        "feedback": self._fallback_feedback.get(item["id"]),
                    }
            return None

        _, cursor_cls = _import_psycopg2()
        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=cursor_cls)
            cur.execute(
                """
                SELECT
                    h.id, h.question, h.sql, h.status, h.result_json, h.execution_time_ms, h.row_count, h.datasource_id,
                    h.tables_used, h.cache_hit, h.guard_status, h.guard_fixes, h.pipeline_steps, h.created_at,
                    f.rating AS feedback_rating, f.comment AS feedback_comment
                FROM oracle.query_history h
                LEFT JOIN LATERAL (
                    SELECT rating, comment
                    FROM oracle.query_feedback
                    WHERE query_id = h.id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) f ON TRUE
                WHERE h.tenant_id = %s AND h.id = %s
                LIMIT 1
                """,
                (str(tenant), query_id),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
        except Exception as exc:
            logger.warning("query_history_detail_db_failed_fallback", error=str(exc))
            self._db_disabled = True
            return await self.get_history_detail(tenant, query_id)

        if not row:
            return None
        result_payload = row["result_json"] if isinstance(row["result_json"], dict) else {}
        feedback = None
        if row.get("feedback_rating"):
            feedback = {"rating": row["feedback_rating"], "comment": row.get("feedback_comment")}
        return {
            "id": str(row["id"]),
            "question": row["question"],
            "sql": row["sql"],
            "status": row["status"],
            "result": result_payload,
            "metadata": {
                "execution_time_ms": row.get("execution_time_ms"),
                "tables_used": row.get("tables_used") or [],
                "cache_hit": bool(row.get("cache_hit", False)),
                "guard_status": row.get("guard_status"),
                "guard_fixes": row.get("guard_fixes") if isinstance(row.get("guard_fixes"), list) else [],
                "pipeline_steps": row.get("pipeline_steps") if isinstance(row.get("pipeline_steps"), list) else [],
            },
            "row_count": row.get("row_count"),
            "datasource_id": row.get("datasource_id"),
            "created_at": _to_iso(row["created_at"]),
            "feedback": feedback,
        }


query_history_repo = QueryHistoryRepository()
