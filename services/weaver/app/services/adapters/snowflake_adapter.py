"""G02: Snowflake 어댑터 — supported 등급.

Snowflake 데이터 웨어하우스의 메타데이터 인트로스펙션.
INFORMATION_SCHEMA 기반, snowflake-connector-python 드라이버.
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

logger = logging.getLogger("axiom.weaver.adapters.snowflake")

import re

try:
    import snowflake.connector  # type: ignore
    HAS_SNOWFLAKE = True
except ImportError:
    HAS_SNOWFLAKE = False

# SQL 식별자 안전성 검증 패턴 (리뷰 #1 수정: SQL 인젝션 방지)
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,254}$")

def _safe_ident(value: str) -> str:
    """SQL 식별자 안전성 검증 — 허용: 영문, 숫자, 언더스코어"""
    if not _IDENT_RE.match(value):
        raise ValueError(f"안전하지 않은 SQL 식별자: {value!r}")
    return value


class SnowflakeAdapter(DatabaseAdapter):
    """Snowflake 어댑터 — account/warehouse/database/schema 기반 연결"""

    engine = "snowflake"

    def _validate(self) -> None:
        if not HAS_SNOWFLAKE:
            raise ImportError("pip install snowflake-connector-python")

    def _conn_params(self) -> dict:
        return {
            "account": self.connection.get("account", ""),
            "user": self.connection.get("user", ""),
            "password": self.connection.get("password", ""),
            "warehouse": self.connection.get("warehouse", "COMPUTE_WH"),
            "database": self.connection.get("database", ""),
            "schema": self.connection.get("schema", "PUBLIC"),
            "role": self.connection.get("role", ""),
            "login_timeout": 10,
        }

    async def test_connection(self) -> ConnectionTestResult:
        self._validate()
        start = time.monotonic()
        try:
            def _test():
                conn = snowflake.connector.connect(**self._conn_params())
                try:
                    conn.cursor().execute("SELECT 1")
                finally:
                    conn.close()
            await asyncio.to_thread(_test)
            return ConnectionTestResult(True, (time.monotonic() - start) * 1000)
        except Exception as e:
            return ConnectionTestResult(False, (time.monotonic() - start) * 1000, str(e))

    async def get_schemas(self) -> list[str]:
        self._validate()
        def _fetch():
            conn = snowflake.connector.connect(**self._conn_params())
            try:
                cur = conn.cursor()
                cur.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                            "WHERE SCHEMA_NAME NOT IN ('INFORMATION_SCHEMA') ORDER BY SCHEMA_NAME")
                return [row[0] for row in cur.fetchall()]
            finally:
                conn.close()
        return await asyncio.to_thread(_fetch)

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        self._validate()
        def _fetch():
            conn = snowflake.connector.connect(**self._conn_params())
            try:
                cur = conn.cursor()
                # Snowflake INFORMATION_SCHEMA는 스키마별 조회 가능
                cur.execute(
                    "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, "
                    "  IS_NULLABLE, ORDINAL_POSITION "
                    "FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME, ORDINAL_POSITION",
                    (schema.upper(),),
                )
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in rows]
            finally:
                conn.close()
        raw = await asyncio.to_thread(_fetch)
        # 테이블별 그룹핑
        tables: dict[str, dict] = {}
        for row in raw:
            tn = row["TABLE_NAME"]
            bucket = tables.setdefault(tn, {"name": tn, "columns": []})
            bucket["columns"].append({
                "name": row["COLUMN_NAME"],
                "type": row["DATA_TYPE"],
                "nullable": row["IS_NULLABLE"] == "YES",
            })
        return list(tables.values())

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        self._validate()
        def _fetch():
            conn = snowflake.connector.connect(**self._conn_params())
            try:
                cur = conn.cursor()
                # Snowflake: SHOW IMPORTED KEYS로 FK 조회
                db = _safe_ident(self.connection.get("database", ""))
                safe_schema = _safe_ident(schema.upper())
                cur.execute(f'SHOW IMPORTED KEYS IN SCHEMA "{db}"."{safe_schema}"')
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
                return [dict(zip(cols, row)) for row in rows]
            finally:
                conn.close()
        raw = await asyncio.to_thread(_fetch)
        # Snowflake FK 결과를 표준 형식으로 변환
        fks = []
        for row in raw:
            fks.append({
                "source_schema": row.get("fk_schema_name", schema),
                "source_table": row.get("fk_table_name", ""),
                "source_column": row.get("fk_column_name", ""),
                "target_schema": row.get("pk_schema_name", ""),
                "target_table": row.get("pk_table_name", ""),
                "target_column": row.get("pk_column_name", ""),
                "constraint_name": row.get("fk_name", ""),
            })
        return fks


def _register():
    AdapterFactory.register("snowflake", SnowflakeAdapter)
    register_manifest(ConnectorManifest(
        engine="snowflake", display_name="Snowflake",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION, ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.SAMPLE_PREVIEW, ConnectorCapability.PROFILING,
            ConnectorCapability.SAFE_QUERY, ConnectorCapability.STREAMING_EXTRACT,
        ],
        credential_modes=[CredentialMode.INTERNAL, CredentialMode.SECRETS_MANAGER],
        support_tier=SupportTier.SUPPORTED, version="0.1.0",
        description="Snowflake — snowflake-connector-python",
    ))

_register()
