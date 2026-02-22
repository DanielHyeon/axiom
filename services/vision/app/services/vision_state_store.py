from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


class VisionStateStore:
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
                self.database_url = "sqlite:////tmp/axiom_vision_state_fallback.db"
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
                    CREATE TABLE IF NOT EXISTS what_if_scenarios (
                        case_id TEXT NOT NULL,
                        scenario_id TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        PRIMARY KEY (case_id, scenario_id)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cubes (
                        cube_name TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS etl_jobs (
                        job_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS root_cause_analyses (
                        case_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
                cur.close()
            else:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS what_if_scenarios (
                        case_id TEXT NOT NULL,
                        scenario_id TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        PRIMARY KEY (case_id, scenario_id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cubes (
                        cube_name TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS etl_jobs (
                        job_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS root_cause_analyses (
                        case_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
            conn.commit()

    def clear(self) -> None:
        with self._connect() as conn:
            if self._is_postgres:
                cur = conn.cursor()
                cur.execute("DELETE FROM what_if_scenarios")
                cur.execute("DELETE FROM cubes")
                cur.execute("DELETE FROM etl_jobs")
                cur.execute("DELETE FROM root_cause_analyses")
                cur.close()
            else:
                conn.execute("DELETE FROM what_if_scenarios")
                conn.execute("DELETE FROM cubes")
                conn.execute("DELETE FROM etl_jobs")
                conn.execute("DELETE FROM root_cause_analyses")
            conn.commit()

    def load_state(self) -> dict[str, Any]:
        cursor_kwargs = {}
        if self._is_postgres:
            _, cursor_cls = self._import_psycopg2()
            cursor_kwargs["cursor_factory"] = cursor_cls

        with self._connect() as conn:
            cur = conn.cursor(**cursor_kwargs)
            cur.execute("SELECT case_id, payload_json FROM what_if_scenarios")
            scenario_rows = cur.fetchall()
            cur.execute("SELECT cube_name, payload_json FROM cubes")
            cube_rows = cur.fetchall()
            cur.execute("SELECT job_id, payload_json FROM etl_jobs")
            etl_rows = cur.fetchall()
            cur.execute("SELECT case_id, payload_json FROM root_cause_analyses")
            root_cause_rows = cur.fetchall()
            cur.close()

        what_if_by_case: dict[str, dict[str, dict[str, Any]]] = {}
        for row in scenario_rows:
            payload = json.loads(row["payload_json"])
            case_id = str(row["case_id"])
            scenario_id = str(payload.get("id") or "")
            if not scenario_id:
                continue
            what_if_by_case.setdefault(case_id, {})[scenario_id] = payload

        cubes = {
            str(row["cube_name"]): json.loads(row["payload_json"])
            for row in cube_rows
        }
        etl_jobs = {
            str(row["job_id"]): json.loads(row["payload_json"])
            for row in etl_rows
        }
        root_cause_by_case = {
            str(row["case_id"]): json.loads(row["payload_json"])
            for row in root_cause_rows
        }
        return {
            "what_if_by_case": what_if_by_case,
            "cubes": cubes,
            "etl_jobs": etl_jobs,
            "root_cause_by_case": root_cause_by_case,
        }

    def upsert_scenario(self, case_id: str, scenario_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            if self._is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO what_if_scenarios(case_id, scenario_id, payload_json)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(case_id, scenario_id)
                    DO UPDATE SET payload_json = EXCLUDED.payload_json
                    """,
                    (case_id, scenario_id, json.dumps(payload, ensure_ascii=True)),
                )
                cur.close()
            else:
                conn.execute(
                    """
                    INSERT INTO what_if_scenarios(case_id, scenario_id, payload_json)
                    VALUES (?, ?, ?)
                    ON CONFLICT(case_id, scenario_id)
                    DO UPDATE SET payload_json = excluded.payload_json
                    """,
                    (case_id, scenario_id, json.dumps(payload, ensure_ascii=True)),
                )
            conn.commit()

    def delete_scenario(self, case_id: str, scenario_id: str) -> None:
        with self._connect() as conn:
            if self._is_postgres:
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM what_if_scenarios WHERE case_id = %s AND scenario_id = %s",
                    (case_id, scenario_id),
                )
                cur.close()
            else:
                conn.execute(
                    "DELETE FROM what_if_scenarios WHERE case_id = ? AND scenario_id = ?",
                    (case_id, scenario_id),
                )
            conn.commit()

    def upsert_cube(self, cube_name: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            if self._is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO cubes(cube_name, payload_json)
                    VALUES (%s, %s)
                    ON CONFLICT(cube_name)
                    DO UPDATE SET payload_json = EXCLUDED.payload_json
                    """,
                    (cube_name, json.dumps(payload, ensure_ascii=True)),
                )
                cur.close()
            else:
                conn.execute(
                    """
                    INSERT INTO cubes(cube_name, payload_json)
                    VALUES (?, ?)
                    ON CONFLICT(cube_name)
                    DO UPDATE SET payload_json = excluded.payload_json
                    """,
                    (cube_name, json.dumps(payload, ensure_ascii=True)),
                )
            conn.commit()

    def upsert_etl_job(self, job_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            if self._is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO etl_jobs(job_id, payload_json)
                    VALUES (%s, %s)
                    ON CONFLICT(job_id)
                    DO UPDATE SET payload_json = EXCLUDED.payload_json
                    """,
                    (job_id, json.dumps(payload, ensure_ascii=True)),
                )
                cur.close()
            else:
                conn.execute(
                    """
                    INSERT INTO etl_jobs(job_id, payload_json)
                    VALUES (?, ?)
                    ON CONFLICT(job_id)
                    DO UPDATE SET payload_json = excluded.payload_json
                    """,
                    (job_id, json.dumps(payload, ensure_ascii=True)),
                )
            conn.commit()

    def upsert_root_cause_analysis(self, case_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            if self._is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO root_cause_analyses(case_id, payload_json)
                    VALUES (%s, %s)
                    ON CONFLICT(case_id)
                    DO UPDATE SET payload_json = EXCLUDED.payload_json
                    """,
                    (case_id, json.dumps(payload, ensure_ascii=True)),
                )
                cur.close()
            else:
                conn.execute(
                    """
                    INSERT INTO root_cause_analyses(case_id, payload_json)
                    VALUES (?, ?)
                    ON CONFLICT(case_id)
                    DO UPDATE SET payload_json = excluded.payload_json
                    """,
                    (case_id, json.dumps(payload, ensure_ascii=True)),
                )
            conn.commit()
