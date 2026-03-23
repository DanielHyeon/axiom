"""G02: ClickHouse 어댑터 — supported 등급.

ClickHouse 데이터 웨어하우스 메타데이터 인트로스펙션.
system.tables / system.columns 기반, clickhouse-driver 사용.
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

logger = logging.getLogger("axiom.weaver.adapters.clickhouse")

try:
    from clickhouse_driver import Client as CHClient  # type: ignore
    HAS_CLICKHOUSE = True
except ImportError:
    HAS_CLICKHOUSE = False


class ClickHouseAdapter(DatabaseAdapter):
    """ClickHouse 어댑터 — system 테이블 기반 인트로스펙션"""

    engine = "clickhouse"

    def _validate(self) -> None:
        if not HAS_CLICKHOUSE:
            raise ImportError("pip install clickhouse-driver")

    def _get_client(self) -> Any:
        return CHClient(
            host=self.connection.get("host", "localhost"),
            port=int(self.connection.get("port", 9000)),
            user=self.connection.get("user", "default"),
            password=self.connection.get("password", ""),
            database=self.connection.get("database", "default"),
            connect_timeout=5,
        )

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        try:
            def _test():
                client = self._get_client()
                try:
                    client.execute("SELECT 1")
                finally:
                    client.disconnect()
            await asyncio.to_thread(_test)
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        self._validate()
        def _fetch():
            client = self._get_client()
            try:
                rows = client.execute("SELECT name FROM system.databases WHERE name NOT IN ('system', 'INFORMATION_SCHEMA', 'information_schema') ORDER BY name")
                return [row[0] for row in rows]
            finally:
                client.disconnect()
        return await asyncio.to_thread(_fetch)

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        self._validate()
        def _fetch():
            client = self._get_client()
            try:
                rows = client.execute(
                    "SELECT table, name, type, "
                    "  position "
                    "FROM system.columns "
                    "WHERE database = %(db)s "
                    "ORDER BY table, position",
                    {"db": schema},
                )
                return rows
            finally:
                client.disconnect()
        raw = await asyncio.to_thread(_fetch)
        tables: dict[str, dict] = {}
        for row in raw:
            tn = row[0]
            bucket = tables.setdefault(tn, {"name": tn, "columns": []})
            bucket["columns"].append({
                "name": row[1],
                "type": row[2],
                "nullable": "Nullable" in row[2],
            })
        return list(tables.values())

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        """ClickHouse는 FK를 지원하지 않음"""
        return []


def _register():
    AdapterFactory.register("clickhouse", ClickHouseAdapter)
    register_manifest(ConnectorManifest(
        engine="clickhouse", display_name="ClickHouse",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.SAMPLE_PREVIEW, ConnectorCapability.SAFE_QUERY,
            ConnectorCapability.STREAMING_EXTRACT,
        ],
        credential_modes=[CredentialMode.INTERNAL, CredentialMode.SECRETS_MANAGER],
        support_tier=SupportTier.SUPPORTED, version="0.1.0",
        description="ClickHouse 21+ — clickhouse-driver (native protocol)",
    ))

_register()
