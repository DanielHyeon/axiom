"""G27: MSSQL 어댑터 — supported 등급.

SQL Server 데이터소스의 메타데이터 인트로스펙션.
INFORMATION_SCHEMA 기반으로 PostgreSQL 어댑터와 유사한 구조.
pymssql 드라이버 사용 (aioodbc보다 설치 간편).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.models.capability import (
    ConnectorCapability,
    ConnectorManifest,
    CredentialMode,
    SupportTier,
    register_manifest,
)
from app.services.adapters.base import AdapterFactory, ConnectionTestResult, DatabaseAdapter

logger = logging.getLogger("axiom.weaver.adapters.mssql")

# pymssql 선택적 의존성
try:
    import pymssql  # type: ignore
    HAS_PYMSSQL = True
except ImportError:
    HAS_PYMSSQL = False
    pymssql = None  # type: ignore


class MSSQLAdapter(DatabaseAdapter):
    """SQL Server 어댑터 — INFORMATION_SCHEMA 기반 인트로스펙션"""

    engine = "mssql"

    def _validate_dependency(self) -> None:
        if not HAS_PYMSSQL:
            raise ImportError(
                "pymssql 패키지가 설치되지 않았습니다. "
                "pip install pymssql 로 설치하세요."
            )

    def _get_conn_params(self) -> dict:
        return {
            "server": self.connection.get("host", "localhost"),
            "port": str(self.connection.get("port", "1433")),
            "user": self.connection.get("user", ""),
            "password": self.connection.get("password", ""),
            "database": self.connection.get("database", "master"),
        }

    async def test_connection(self) -> ConnectionTestResult:
        """연결 테스트 — pymssql은 동기이므로 스레드에서 실행"""
        self._validate_dependency()
        import asyncio
        start = time.monotonic()
        try:
            params = self._get_conn_params()
            # pymssql은 동기 → asyncio.to_thread로 비동기 래핑
            def _test():
                conn = pymssql.connect(**params, login_timeout=3)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
            finally:
                conn.close()

            await asyncio.to_thread(_test)
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionTestResult(success=True, response_time_ms=elapsed)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionTestResult(success=False, response_time_ms=elapsed, error=str(e))

    async def get_schemas(self) -> list[str]:
        """스키마 목록 조회"""
        self._validate_dependency()
        import asyncio

        params = self._get_conn_params()

        def _fetch():
            conn = pymssql.connect(**params, login_timeout=3)
            try:
                cursor = conn.cursor(as_dict=True)
                cursor.execute(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                    "WHERE SCHEMA_NAME NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest') "
                    "ORDER BY SCHEMA_NAME"
                )
                return [row["SCHEMA_NAME"] for row in cursor.fetchall()]
            finally:
                conn.close()

        return await asyncio.to_thread(_fetch)

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        """INFORMATION_SCHEMA에서 테이블+컬럼 조회"""
        self._validate_dependency()
        import asyncio

        params = self._get_conn_params()

        def _fetch():
            conn = pymssql.connect(**params, login_timeout=5)
            try:
                cursor = conn.cursor(as_dict=True)
                cursor.execute(
                    "SELECT t.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, "
                    "  CASE WHEN c.IS_NULLABLE = 'YES' THEN 1 ELSE 0 END AS is_nullable, "
                    "  c.ORDINAL_POSITION "
                    "FROM INFORMATION_SCHEMA.TABLES t "
                    "JOIN INFORMATION_SCHEMA.COLUMNS c "
                    "  ON c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME "
                    "WHERE t.TABLE_SCHEMA = %s AND t.TABLE_TYPE = 'BASE TABLE' "
                    "ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION",
                    (schema,),
                )
                return cursor.fetchall()
            finally:
                conn.close()

        rows = await asyncio.to_thread(_fetch)

        # 테이블별 컬럼 그룹핑
        tables: dict[str, dict] = {}
        for row in rows:
            table_name = row["TABLE_NAME"]
            bucket = tables.setdefault(table_name, {"name": table_name, "columns": []})
            bucket["columns"].append({
                "name": row["COLUMN_NAME"],
                "type": row["DATA_TYPE"],
                "nullable": bool(row["is_nullable"]),
            })

        return list(tables.values())

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        """INFORMATION_SCHEMA에서 FK 관계 조회 — ORDINAL_POSITION 매칭으로 복합 FK 정확 처리"""
        self._validate_dependency()
        import asyncio

        params = self._get_conn_params()

        def _fetch():
            conn = pymssql.connect(**params, login_timeout=5)
            try:
                cursor = conn.cursor(as_dict=True)
                # ORDINAL_POSITION 매칭으로 복합 FK cartesian product 방지 (리뷰 #2 수정)
                cursor.execute(
                    "SELECT "
                    "  fk.TABLE_SCHEMA AS source_schema, "
                    "  fk.TABLE_NAME AS source_table, "
                    "  cu.COLUMN_NAME AS source_column, "
                    "  pk.TABLE_SCHEMA AS target_schema, "
                    "  pk.TABLE_NAME AS target_table, "
                    "  pt.COLUMN_NAME AS target_column, "
                    "  c.CONSTRAINT_NAME AS constraint_name "
                    "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS c "
                    "JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS fk "
                    "  ON c.CONSTRAINT_NAME = fk.CONSTRAINT_NAME "
                    "JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS pk "
                    "  ON c.UNIQUE_CONSTRAINT_NAME = pk.CONSTRAINT_NAME "
                    "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE cu "
                    "  ON c.CONSTRAINT_NAME = cu.CONSTRAINT_NAME "
                    "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE pt "
                    "  ON c.UNIQUE_CONSTRAINT_NAME = pt.CONSTRAINT_NAME "
                    "  AND cu.ORDINAL_POSITION = pt.ORDINAL_POSITION "
                    "WHERE fk.TABLE_SCHEMA = %s "
                    "ORDER BY fk.TABLE_NAME, cu.ORDINAL_POSITION",
                    (schema,),
                )
                return cursor.fetchall()
            finally:
                conn.close()

        rows = await asyncio.to_thread(_fetch)

        return [
            {
                "source_schema": row.get("source_schema", schema),
                "source_table": row.get("source_table", ""),
                "source_column": row.get("source_column", ""),
                "target_schema": row.get("target_schema", ""),
                "target_table": row.get("target_table", ""),
                "target_column": row.get("target_column", ""),
                "constraint_name": row.get("constraint_name", ""),
            }
            for row in rows
        ]


# ── 팩토리 + 매니페스트 등록 ── #

def register_mssql() -> None:
    """MSSQL 어댑터를 AdapterFactory + ConnectorRegistry에 등록"""
    AdapterFactory.register("mssql", MSSQLAdapter)
    register_manifest(ConnectorManifest(
        engine="mssql",
        display_name="SQL Server",
        capabilities=[
            ConnectorCapability.TEST_CONNECTION,
            ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.SAMPLE_PREVIEW,
            ConnectorCapability.PROFILING,
            ConnectorCapability.SAFE_QUERY,
            ConnectorCapability.STREAMING_EXTRACT,
        ],
        credential_modes=[CredentialMode.INTERNAL, CredentialMode.SECRETS_MANAGER],
        support_tier=SupportTier.SUPPORTED,
        version="0.1.0",
        description="SQL Server 2016+ — pymssql 드라이버",
    ))


# 모듈 임포트 시 자동 등록
register_mssql()
