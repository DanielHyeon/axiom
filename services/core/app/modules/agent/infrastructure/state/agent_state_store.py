from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


class AgentStateStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = self._normalize_database_url(database_url)
        self._is_postgres = self.database_url.startswith("postgresql://") or self.database_url.startswith("postgres://")
        if self._is_postgres:
            try:
                self._init_schema()
                return
            except Exception:
                # Keep runtime available when local Postgres is not running.
                self._is_postgres = False
                self.database_url = "sqlite:////tmp/axiom_core_agent_state_fallback.db"
        self.db_path = Path(self._sqlite_path(self.database_url))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @staticmethod
    def _normalize_database_url(database_url: str) -> str:
        value = (database_url or "").strip()
        if value.startswith("postgresql+asyncpg://"):
            return "postgresql://" + value[len("postgresql+asyncpg://") :]
        return value

    @staticmethod
    def _sqlite_path(database_url: str) -> str:
        if database_url.startswith("sqlite:///"):
            return database_url[len("sqlite:///") :]
        if database_url.startswith("sqlite://"):
            return database_url[len("sqlite://") :]
        return database_url

    @staticmethod
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

    def _connect(self):
        if self._is_postgres:
            psycopg2, _ = self._import_psycopg2()
            return psycopg2.connect(self.database_url)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            if self._is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback_state (
                        tenant_id TEXT NOT NULL,
                        workitem_id TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        PRIMARY KEY (tenant_id, workitem_id)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mcp_state (
                        tenant_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_state (
                        tenant_id TEXT NOT NULL,
                        knowledge_id TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        PRIMARY KEY (tenant_id, knowledge_id)
                    )
                    """
                )
                cur.close()
            else:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS feedback_state (
                        tenant_id TEXT NOT NULL,
                        workitem_id TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        PRIMARY KEY (tenant_id, workitem_id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mcp_state (
                        tenant_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_state (
                        tenant_id TEXT NOT NULL,
                        knowledge_id TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        PRIMARY KEY (tenant_id, knowledge_id)
                    )
                    """
                )
            conn.commit()

    def clear(self) -> None:
        with self._connect() as conn:
            if self._is_postgres:
                cur = conn.cursor()
                cur.execute("DELETE FROM feedback_state")
                cur.execute("DELETE FROM mcp_state")
                cur.execute("DELETE FROM knowledge_state")
                cur.close()
            else:
                conn.execute("DELETE FROM feedback_state")
                conn.execute("DELETE FROM mcp_state")
                conn.execute("DELETE FROM knowledge_state")
            conn.commit()

    def load_state(self) -> dict[str, Any]:
        cursor_kwargs = {}
        if self._is_postgres:
            _, cursor_cls = self._import_psycopg2()
            cursor_kwargs["cursor_factory"] = cursor_cls

        with self._connect() as conn:
            cur = conn.cursor(**cursor_kwargs)
            cur.execute("SELECT tenant_id, workitem_id, payload_json FROM feedback_state")
            feedback_rows = cur.fetchall()
            cur.execute("SELECT tenant_id, payload_json FROM mcp_state")
            mcp_rows = cur.fetchall()
            cur.execute("SELECT tenant_id, knowledge_id, payload_json FROM knowledge_state")
            knowledge_rows = cur.fetchall()
            cur.close()

        feedback_by_tenant: dict[str, dict[str, dict[str, Any]]] = {}
        for row in feedback_rows:
            tenant_id = str(row["tenant_id"])
            workitem_id = str(row["workitem_id"])
            feedback_by_tenant.setdefault(tenant_id, {})[workitem_id] = json.loads(row["payload_json"])

        mcp_by_tenant: dict[str, dict[str, Any]] = {}
        for row in mcp_rows:
            mcp_by_tenant[str(row["tenant_id"])] = json.loads(row["payload_json"])

        knowledge_by_tenant: dict[str, dict[str, dict[str, Any]]] = {}
        for row in knowledge_rows:
            tenant_id = str(row["tenant_id"])
            knowledge_id = str(row["knowledge_id"])
            knowledge_by_tenant.setdefault(tenant_id, {})[knowledge_id] = json.loads(row["payload_json"])

        return {
            "feedback_by_tenant": feedback_by_tenant,
            "mcp_by_tenant": mcp_by_tenant,
            "knowledge_by_tenant": knowledge_by_tenant,
        }

    def upsert_feedback(self, tenant_id: str, workitem_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            if self._is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO feedback_state(tenant_id, workitem_id, payload_json)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(tenant_id, workitem_id)
                    DO UPDATE SET payload_json = EXCLUDED.payload_json
                    """,
                    (tenant_id, workitem_id, json.dumps(payload, ensure_ascii=True)),
                )
                cur.close()
            else:
                conn.execute(
                    """
                    INSERT INTO feedback_state(tenant_id, workitem_id, payload_json)
                    VALUES (?, ?, ?)
                    ON CONFLICT(tenant_id, workitem_id)
                    DO UPDATE SET payload_json = excluded.payload_json
                    """,
                    (tenant_id, workitem_id, json.dumps(payload, ensure_ascii=True)),
                )
            conn.commit()

    def upsert_mcp(self, tenant_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            if self._is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO mcp_state(tenant_id, payload_json)
                    VALUES (%s, %s)
                    ON CONFLICT(tenant_id)
                    DO UPDATE SET payload_json = EXCLUDED.payload_json
                    """,
                    (tenant_id, json.dumps(payload, ensure_ascii=True)),
                )
                cur.close()
            else:
                conn.execute(
                    """
                    INSERT INTO mcp_state(tenant_id, payload_json)
                    VALUES (?, ?)
                    ON CONFLICT(tenant_id)
                    DO UPDATE SET payload_json = excluded.payload_json
                    """,
                    (tenant_id, json.dumps(payload, ensure_ascii=True)),
                )
            conn.commit()

    def upsert_knowledge(self, tenant_id: str, knowledge_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            if self._is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO knowledge_state(tenant_id, knowledge_id, payload_json)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(tenant_id, knowledge_id)
                    DO UPDATE SET payload_json = EXCLUDED.payload_json
                    """,
                    (tenant_id, knowledge_id, json.dumps(payload, ensure_ascii=True)),
                )
                cur.close()
            else:
                conn.execute(
                    """
                    INSERT INTO knowledge_state(tenant_id, knowledge_id, payload_json)
                    VALUES (?, ?, ?)
                    ON CONFLICT(tenant_id, knowledge_id)
                    DO UPDATE SET payload_json = excluded.payload_json
                    """,
                    (tenant_id, knowledge_id, json.dumps(payload, ensure_ascii=True)),
                )
            conn.commit()

    def delete_knowledge(self, tenant_id: str, knowledge_id: str) -> None:
        with self._connect() as conn:
            if self._is_postgres:
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM knowledge_state WHERE tenant_id = %s AND knowledge_id = %s",
                    (tenant_id, knowledge_id),
                )
                cur.close()
            else:
                conn.execute(
                    "DELETE FROM knowledge_state WHERE tenant_id = ? AND knowledge_id = ?",
                    (tenant_id, knowledge_id),
                )
            conn.commit()
