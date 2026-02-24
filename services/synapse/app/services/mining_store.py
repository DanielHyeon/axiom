"""
Process Mining Task/Result/참조 모델 영속 저장소 (Phase S4).
PostgreSQL에 mining_tasks, mining_results, mining_models 저장.
"""
import json
import sys
from typing import Any

from app.core.config import settings


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


class MiningStore:
    """Mining tasks, results, and imported models persisted to PostgreSQL."""

    _DB_SCHEMA = "synapse"

    def __init__(self, database_url: str | None = None) -> None:
        self._database_url = database_url or settings.SCHEMA_EDIT_DATABASE_URL
        self._schema_ready = False

    def _connect(self):
        psycopg2, _ = _import_psycopg2()
        conn = psycopg2.connect(self._database_url)
        cur = conn.cursor()
        cur.execute(f"SET search_path TO {self._DB_SCHEMA}, public")
        cur.close()
        return conn

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self._DB_SCHEMA}")
        conn.commit()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS mining_tasks (
              task_id TEXT NOT NULL PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              task_type TEXT NOT NULL,
              case_id TEXT NOT NULL,
              log_id TEXT NOT NULL,
              status TEXT NOT NULL,
              result_id TEXT,
              created_at TIMESTAMPTZ NOT NULL,
              started_at TIMESTAMPTZ,
              completed_at TIMESTAMPTZ,
              updated_at TIMESTAMPTZ NOT NULL,
              requested_by TEXT,
              error JSONB
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS mining_results (
              result_id TEXT NOT NULL PRIMARY KEY,
              task_id TEXT NOT NULL,
              task_type TEXT NOT NULL,
              case_id TEXT NOT NULL,
              log_id TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL,
              result JSONB NOT NULL DEFAULT '{}'
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS mining_models (
              model_id TEXT NOT NULL PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              type TEXT NOT NULL,
              xml TEXT NOT NULL,
              activities JSONB NOT NULL DEFAULT '[]',
              created_by TEXT,
              imported_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS mining_tasks_tenant ON mining_tasks (tenant_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS mining_tasks_status ON mining_tasks (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS mining_results_task ON mining_results (task_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS mining_models_tenant ON mining_models (tenant_id)")
        conn.commit()
        cur.close()
        conn.close()
        self._schema_ready = True

    def insert_task(
        self,
        task_id: str,
        tenant_id: str,
        task_type: str,
        case_id: str,
        log_id: str,
        requested_by: str | None,
    ) -> str:
        self._ensure_schema()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO mining_tasks (task_id, tenant_id, task_type, case_id, log_id, status, created_at, updated_at, requested_by)
            VALUES (%s, %s, %s, %s, %s, 'queued', %s, %s, %s)
            """,
            (task_id, tenant_id, task_type, case_id, log_id, now, now, requested_by),
        )
        conn.commit()
        cur.close()
        conn.close()
        return now

    def set_running(self, task_id: str) -> str:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "UPDATE mining_tasks SET status = 'running', started_at = %s, updated_at = %s WHERE task_id = %s",
            (now, now, task_id),
        )
        conn.commit()
        cur.close()
        conn.close()
        return now

    def set_completed(self, task_id: str, result_id: str, result_payload: dict[str, Any]) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT tenant_id, task_type, case_id, log_id, created_at FROM mining_tasks WHERE task_id = %s",
            (task_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return
        tenant_id, task_type, case_id, log_id, created_at = row
        cur.execute(
            """
            UPDATE mining_tasks SET status = 'completed', result_id = %s, completed_at = %s, updated_at = %s
            WHERE task_id = %s
            """,
            (result_id, now, now, task_id),
        )
        cur.execute(
            """
            INSERT INTO mining_results (result_id, task_id, task_type, case_id, log_id, created_at, result)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (result_id, task_id, task_type, case_id, log_id, now, json.dumps(result_payload)),
        )
        conn.commit()
        cur.close()
        conn.close()

    def get_task(self, tenant_id: str, task_id: str) -> dict[str, Any] | None:
        self._ensure_schema()
        _, cursor_cls = _import_psycopg2()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(
            "SELECT task_id, tenant_id, task_type, case_id, log_id, status, result_id, created_at, started_at, completed_at, updated_at, requested_by, error FROM mining_tasks WHERE task_id = %s AND tenant_id = %s",
            (task_id, tenant_id),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        d = dict(row)
        for key in ("created_at", "started_at", "completed_at", "updated_at"):
            if d.get(key) and hasattr(d[key], "isoformat"):
                d[key] = d[key].isoformat()
        return d

    def get_result(self, tenant_id: str, result_id: str) -> dict[str, Any] | None:
        self._ensure_schema()
        _, cursor_cls = _import_psycopg2()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(
            "SELECT r.result_id, r.task_id, r.task_type, r.case_id, r.log_id, r.created_at, r.result FROM mining_results r JOIN mining_tasks t ON r.task_id = t.task_id WHERE r.result_id = %s AND t.tenant_id = %s",
            (result_id, tenant_id),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        d = dict(row)
        d["result"] = d["result"] if isinstance(d["result"], dict) else (json.loads(d["result"]) if d["result"] else {})
        if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
        return {"id": d["result_id"], "task_id": d["task_id"], "task_type": d["task_type"], "case_id": d["case_id"], "log_id": d["log_id"], "created_at": d["created_at"], "result": d["result"]}

    def get_result_by_task_id(self, tenant_id: str, task_id: str) -> dict[str, Any] | None:
        self._ensure_schema()
        _, cursor_cls = _import_psycopg2()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(
            "SELECT result_id FROM mining_tasks WHERE task_id = %s AND tenant_id = %s",
            (task_id, tenant_id),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row or not row.get("result_id"):
            return None
        return self.get_result(tenant_id, row["result_id"])

    def count_active_tasks(self, tenant_id: str | None = None) -> int:
        self._ensure_schema()
        conn = self._connect()
        cur = conn.cursor()
        if tenant_id:
            cur.execute("SELECT COUNT(*) FROM mining_tasks WHERE status IN ('queued', 'running') AND tenant_id = %s", (tenant_id,))
        else:
            cur.execute("SELECT COUNT(*) FROM mining_tasks WHERE status IN ('queued', 'running')")
        n = cur.fetchone()[0]
        cur.close()
        conn.close()
        return int(n or 0)

    def insert_model(
        self,
        model_id: str,
        tenant_id: str,
        case_id: str,
        model_type: str,
        xml: str,
        activities: list[str],
        created_by: str | None,
    ) -> str:
        self._ensure_schema()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO mining_models (model_id, tenant_id, case_id, type, xml, activities, created_by, imported_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (model_id, tenant_id, case_id, model_type, xml, json.dumps(activities), created_by, now),
        )
        conn.commit()
        cur.close()
        conn.close()
        return now.isoformat()

    def get_model(self, tenant_id: str, model_id: str) -> dict[str, Any] | None:
        self._ensure_schema()
        _, cursor_cls = _import_psycopg2()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(
            "SELECT model_id, tenant_id, case_id, type, xml, activities, created_by, imported_at FROM mining_models WHERE model_id = %s AND tenant_id = %s",
            (model_id, tenant_id),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        d = dict(row)
        d["activities"] = d["activities"] if isinstance(d["activities"], list) else (json.loads(d["activities"]) if d["activities"] else [])
        if d.get("imported_at") and hasattr(d["imported_at"], "isoformat"):
            d["imported_at"] = d["imported_at"].isoformat()
        return d

    def clear(self) -> None:
        self._ensure_schema()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM mining_results")
        cur.execute("DELETE FROM mining_tasks")
        cur.execute("DELETE FROM mining_models")
        conn.commit()
        cur.close()
        conn.close()


_mining_store: MiningStore | None = None


def get_mining_store() -> MiningStore | None:
    """기본 저장소 반환. None이면 인메모리 모드."""
    global _mining_store
    if _mining_store is None:
        try:
            _mining_store = MiningStore()
        except Exception:
            return None
    return _mining_store
