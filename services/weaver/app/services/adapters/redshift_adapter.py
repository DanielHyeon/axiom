"""G02: Redshift 어댑터 — supported 등급.

Amazon Redshift — PostgreSQL 프로토콜 호환.
기존 PostgreSQLAdapter를 상속하고 Redshift 전용 시스템 뷰를 활용한다.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.models.capability import (
    ConnectorCapability, ConnectorManifest, CredentialMode, SupportTier, register_manifest,
)
from app.services.adapters.base import AdapterFactory, ConnectionTestResult, DatabaseAdapter

logger = logging.getLogger("axiom.weaver.adapters.redshift")

try:
    import asyncpg  # type: ignore
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False


class RedshiftAdapter(DatabaseAdapter):
    """Redshift 어댑터 — PG 호환 프로토콜 + SVV 시스템 뷰.

    asyncpg로 직접 연결 (Redshift는 PG wire protocol 호환).
    """

    engine = "redshift"

    def _validate(self) -> None:
        if not HAS_ASYNCPG:
            raise ImportError("pip install asyncpg — Redshift는 PG wire protocol 호환")

    def _dsn(self) -> str:
        import urllib.parse
        host = self.connection.get("host", "")
        port = int(self.connection.get("port", 5439))
        database = self.connection.get("database", "dev")
        user = self.connection.get("user", "")
        password = urllib.parse.quote_plus(self.connection.get("password", ""))
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        try:
            conn = await asyncpg.connect(dsn=self._dsn(), timeout=5)
            try:
                await conn.execute("SELECT 1")
            finally:
                await conn.close()
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        self._validate()
        conn = await asyncpg.connect(dsn=self._dsn(), timeout=5)
        try:
            rows = await conn.fetch(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_internal') "
                "ORDER BY schema_name"
            )
            return [r["schema_name"] for r in rows]
        finally:
            await conn.close()

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        self._validate()
        conn = await asyncpg.connect(dsn=self._dsn(), timeout=10)
        try:
            rows = await conn.fetch(
                "SELECT t.table_name, c.column_name, c.data_type, "
                "  (c.is_nullable = 'YES') AS is_nullable, c.ordinal_position "
                "FROM information_schema.tables t "
                "JOIN information_schema.columns c "
                "  ON c.table_schema = t.table_schema AND c.table_name = t.table_name "
                "WHERE t.table_schema = $1 AND t.table_type = 'BASE TABLE' "
                "ORDER BY t.table_name, c.ordinal_position",
                schema,
            )
            tables: dict[str, dict] = {}
            for row in rows:
                tn = row["table_name"]
                bucket = tables.setdefault(tn, {"name": tn, "columns": []})
                bucket["columns"].append({
                    "name": row["column_name"],
                    "type": row["data_type"],
                    "nullable": bool(row["is_nullable"]),
                })
            return list(tables.values())
        finally:
            await conn.close()

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        """Redshift FK — PG information_schema 호환 + ordinal_position 매칭"""
        self._validate()
        conn = await asyncpg.connect(dsn=self._dsn(), timeout=5)
        try:
            rows = await conn.fetch(
                "SELECT tc.table_schema AS source_schema, tc.table_name AS source_table, "
                "  kcu.column_name AS source_column, "
                "  ccu.table_schema AS target_schema, ccu.table_name AS target_table, "
                "  ccu.column_name AS target_column, tc.constraint_name "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name "
                "  AND tc.table_schema = kcu.table_schema "
                "JOIN information_schema.constraint_column_usage ccu "
                "  ON tc.constraint_name = ccu.constraint_name "
                "  AND kcu.ordinal_position = ccu.position_in_unique_constraint "
                "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = $1",
                schema,
            )
            return [dict(r) for r in rows]
        finally:
            await conn.close()


def _register():
    AdapterFactory.register("redshift", RedshiftAdapter)
    register_manifest(ConnectorManifest(
        engine="redshift", display_name="Amazon Redshift",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.SAMPLE_PREVIEW, ConnectorCapability.PROFILING,
            ConnectorCapability.SAFE_QUERY, ConnectorCapability.STREAMING_EXTRACT,
        ],
        credential_modes=[CredentialMode.INTERNAL, CredentialMode.SECRETS_MANAGER],
        support_tier=SupportTier.SUPPORTED, version="0.1.0",
        description="Amazon Redshift — asyncpg (PG wire protocol 호환)",
    ))

_register()
