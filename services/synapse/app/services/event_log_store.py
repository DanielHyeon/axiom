"""
Event Log 영속 저장소 (Phase S1).
PostgreSQL에 event_logs 메타데이터 및 events/raw_events 저장.
"""
import json
import sys
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


class EventLogStore:
    """Event log metadata and events persisted to PostgreSQL."""

    def __init__(self, database_url: str | None = None) -> None:
        self._database_url = database_url or settings.SCHEMA_EDIT_DATABASE_URL
        self._schema_ready = False

    def _connect(self):
        psycopg2, _ = _import_psycopg2()
        return psycopg2.connect(self._database_url)

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS event_logs (
              log_id TEXT NOT NULL PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              name TEXT NOT NULL,
              source_type TEXT NOT NULL,
              status TEXT NOT NULL,
              source_config JSONB NOT NULL DEFAULT '{}',
              options JSONB NOT NULL DEFAULT '{}',
              filter_config JSONB NOT NULL DEFAULT '{}',
              column_mapping JSONB NOT NULL DEFAULT '{}',
              source_columns JSONB NOT NULL DEFAULT '[]',
              raw_events JSONB NOT NULL DEFAULT '[]',
              events JSONB NOT NULL DEFAULT '[]',
              created_at TIMESTAMPTZ NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS event_logs_tenant_case ON event_logs (tenant_id, case_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS event_logs_created ON event_logs (created_at DESC)"
        )
        conn.commit()
        cur.close()
        conn.close()
        self._schema_ready = True

    def insert(
        self,
        log_id: str,
        tenant_id: str,
        case_id: str,
        name: str,
        source_type: str,
        status: str,
        source_config: dict[str, Any],
        options: dict[str, Any],
        filter_config: dict[str, Any],
        column_mapping: dict[str, Any],
        source_columns: list[str],
        raw_events: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> None:
        self._ensure_schema()
        now = _now_iso()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO event_logs (
              log_id, tenant_id, case_id, name, source_type, status,
              source_config, options, filter_config, column_mapping, source_columns,
              raw_events, events, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                log_id,
                tenant_id,
                case_id,
                name,
                source_type,
                status,
                json.dumps(source_config),
                json.dumps(options),
                json.dumps(filter_config),
                json.dumps(column_mapping),
                json.dumps(source_columns),
                json.dumps(raw_events),
                json.dumps(events),
                now,
                now,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()

    def get(self, tenant_id: str, log_id: str) -> dict[str, Any] | None:
        self._ensure_schema()
        _, cursor_cls = _import_psycopg2()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(
            """
            SELECT log_id, tenant_id, case_id, name, source_type, status,
                   source_config, options, filter_config, column_mapping, source_columns,
                   raw_events, events, created_at, updated_at
            FROM event_logs WHERE log_id = %s AND tenant_id = %s
            """,
            (log_id, tenant_id),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        d = dict(row)
        d["source_config"] = d["source_config"] or {}
        d["options"] = d["options"] or {}
        d["filter"] = d.pop("filter_config") or {}
        d["column_mapping"] = d["column_mapping"] or {}
        d["source_columns"] = set(d["source_columns"] or [])
        d["raw_events"] = d["raw_events"] or []
        d["events"] = d["events"] or []
        d["created_at"] = d["created_at"].isoformat() if hasattr(d["created_at"], "isoformat") else str(d["created_at"])
        d["updated_at"] = d["updated_at"].isoformat() if hasattr(d["updated_at"], "isoformat") else str(d["updated_at"])
        return d

    def list_by_case(self, tenant_id: str, case_id: str, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        self._ensure_schema()
        _, cursor_cls = _import_psycopg2()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(
            "SELECT COUNT(*) FROM event_logs WHERE tenant_id = %s AND case_id = %s",
            (tenant_id, case_id),
        )
        total = cur.fetchone()["count"]
        cur.execute(
            """
            SELECT log_id, name, source_type, events, created_at
            FROM event_logs WHERE tenant_id = %s AND case_id = %s
            ORDER BY created_at DESC LIMIT %s OFFSET %s
            """,
            (tenant_id, case_id, limit, offset),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        logs = []
        for row in rows:
            events = row["events"] or []
            total_events = len(events)
            case_ids = {e.get("case_id") for e in events if e.get("case_id")}
            total_cases = len(case_ids)
            activities = {e.get("activity") for e in events if e.get("activity")}
            timestamps = [e.get("timestamp") for e in events if e.get("timestamp")]
            date_start = min(timestamps) if timestamps else None
            date_end = max(timestamps) if timestamps else None
            created = row["created_at"]
            created_at = created.isoformat() if hasattr(created, "isoformat") else str(created)
            logs.append({
                "log_id": row["log_id"],
                "name": row["name"],
                "source_type": row["source_type"],
                "total_events": total_events,
                "total_cases": total_cases,
                "unique_activities": len(activities),
                "date_range_start": date_start,
                "date_range_end": date_end,
                "created_at": created_at,
            })
        return logs, int(total)

    def update_events_and_mapping(
        self,
        tenant_id: str,
        log_id: str,
        column_mapping: dict[str, Any],
        raw_events: list[dict[str, Any]],
        events: list[dict[str, Any]],
        source_columns: list[str],
    ) -> None:
        self._ensure_schema()
        now = _now_iso()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE event_logs
            SET column_mapping = %s, raw_events = %s, events = %s, source_columns = %s, updated_at = %s
            WHERE log_id = %s AND tenant_id = %s
            """,
            (
                json.dumps(column_mapping),
                json.dumps(raw_events),
                json.dumps(events),
                json.dumps(source_columns),
                now,
                log_id,
                tenant_id,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()

    def delete(self, tenant_id: str, log_id: str) -> bool:
        self._ensure_schema()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM event_logs WHERE log_id = %s AND tenant_id = %s", (log_id, tenant_id))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        conn.close()
        return deleted

    def clear(self) -> None:
        """테스트용: 모든 레코드 삭제."""
        self._ensure_schema()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM event_logs")
        conn.commit()
        cur.close()
        conn.close()


_event_log_store: EventLogStore | None = None


def get_event_log_store() -> EventLogStore | None:
    """기본 저장소 반환. None이면 인메모리 모드(서비스에서 _logs 사용)."""
    global _event_log_store
    if _event_log_store is None:
        try:
            _event_log_store = EventLogStore()
        except Exception:
            return None
    return _event_log_store
