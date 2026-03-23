"""PostgreSQL 어댑터 — 기존 core/adapters.py PostgresAdapter의 플러그인 래퍼.

기존 코드를 깨뜨리지 않고 AdapterFactory에 등록하는 브릿지 어댑터.
Phase 1 Sprint 2 이후 직접 구현으로 점진 교체 가능.
"""

from __future__ import annotations

import time
from typing import Any

from app.services.adapters.base import AdapterFactory, ConnectionTestResult, DatabaseAdapter


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL 어댑터 — certified 등급"""

    engine = "postgresql"

    async def test_connection(self) -> ConnectionTestResult:
        """기존 core/adapters.py의 PostgresAdapter.test_connection 위임"""
        from app.core.adapters import get_adapter
        start = time.monotonic()
        try:
            legacy = get_adapter("postgresql", self.connection)
            ok = await legacy.test_connection()
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionTestResult(success=ok, response_time_ms=elapsed)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionTestResult(success=False, response_time_ms=elapsed, error=str(e))

    async def _get_legacy_schema(self, include_row_counts: bool = False) -> dict:
        """레거시 어댑터 결과 캐싱 — 동일 세션 내 중복 쿼리 방지"""
        cache_key = f"_cached_schema_{include_row_counts}"
        if not hasattr(self, cache_key):
            from app.core.adapters import get_adapter
            legacy = get_adapter("postgresql", self.connection)
            setattr(self, cache_key, await legacy.extract_schema(
                include_row_counts=include_row_counts,
            ))
        return getattr(self, cache_key)

    async def get_schemas(self) -> list[str]:
        return ["public"]

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        result = await self._get_legacy_schema(include_row_counts)
        return result.get("tables", [])

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        result = await self._get_legacy_schema()
        return result.get("foreign_keys", [])

    async def execute_query(self, sql: str, limit: int = 100) -> dict:
        """PostgreSQL Direct SQL 실행 — SELECT만 허용, 서브쿼리 래핑으로 안전 실행"""
        import re
        import asyncpg  # type: ignore
        from app.core.adapters import _connection_to_pg_dsn

        # SQL 인젝션 방어: SELECT만 허용 + 세미콜론 제거 + 서브쿼리 래핑
        cleaned = sql.rstrip().rstrip(";")
        if not re.match(r"^\s*SELECT\b", cleaned, re.IGNORECASE):
            raise ValueError("SELECT 문만 실행할 수 있습니다")

        dsn = _connection_to_pg_dsn(self.connection)
        start = time.monotonic()
        conn = await asyncpg.connect(dsn=dsn, timeout=3.0)
        try:
            # 파라미터 바인딩으로 LIMIT 적용 (f-string 금지)
            rows = await conn.fetch(
                f"SELECT * FROM ({cleaned}) AS _q LIMIT $1", limit
            )
            elapsed = (time.monotonic() - start) * 1000
            if rows:
                columns = list(rows[0].keys())
                return {
                    "columns": columns,
                    "rows": [dict(r) for r in rows],
                    "row_count": len(rows),
                    "execution_time_ms": elapsed,
                }
            return {"columns": [], "rows": [], "row_count": 0, "execution_time_ms": elapsed}
        finally:
            await conn.close()


class MySQLPluginAdapter(DatabaseAdapter):
    """MySQL 어댑터 — certified 등급. 기존 core/adapters.py MySQLAdapter 브릿지."""

    engine = "mysql"

    async def _get_legacy_schema(self, include_row_counts: bool = False) -> dict:
        cache_key = f"_cached_schema_{include_row_counts}"
        if not hasattr(self, cache_key):
            from app.core.adapters import get_adapter
            legacy = get_adapter("mysql", self.connection)
            setattr(self, cache_key, await legacy.extract_schema(
                include_row_counts=include_row_counts,
            ))
        return getattr(self, cache_key)

    async def test_connection(self) -> ConnectionTestResult:
        from app.core.adapters import get_adapter
        start = time.monotonic()
        try:
            legacy = get_adapter("mysql", self.connection)
            ok = await legacy.test_connection()
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionTestResult(success=ok, response_time_ms=elapsed)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionTestResult(success=False, response_time_ms=elapsed, error=str(e))

    async def get_schemas(self) -> list[str]:
        db = self.connection.get("database", "")
        return [db] if db else ["information_schema"]

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        result = await self._get_legacy_schema(include_row_counts)
        return result.get("tables", [])

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        result = await self._get_legacy_schema()
        return result.get("foreign_keys", [])


class OraclePluginAdapter(DatabaseAdapter):
    """Oracle 어댑터 — certified 등급. 기존 core/adapters.py OracleAdapter 브릿지."""

    engine = "oracle"

    async def _get_legacy_schema(self, include_row_counts: bool = False) -> dict:
        cache_key = f"_cached_schema_{include_row_counts}"
        if not hasattr(self, cache_key):
            from app.core.adapters import get_adapter
            legacy = get_adapter("oracle", self.connection)
            setattr(self, cache_key, await legacy.extract_schema(
                include_row_counts=include_row_counts,
            ))
        return getattr(self, cache_key)

    async def test_connection(self) -> ConnectionTestResult:
        from app.core.adapters import get_adapter
        start = time.monotonic()
        try:
            legacy = get_adapter("oracle", self.connection)
            ok = await legacy.test_connection()
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionTestResult(success=ok, response_time_ms=elapsed)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return ConnectionTestResult(success=False, response_time_ms=elapsed, error=str(e))

    async def get_schemas(self) -> list[str]:
        user = self.connection.get("user", "")
        return [user.upper()] if user else []

    async def get_tables(self, schema: str, *, include_row_counts: bool = False) -> list[dict]:
        result = await self._get_legacy_schema(include_row_counts)
        return result.get("tables", [])

    async def get_foreign_keys(self, schema: str) -> list[dict]:
        result = await self._get_legacy_schema()
        return result.get("foreign_keys", [])


# ── 팩토리 등록 ── #

def register_builtin_adapters() -> None:
    """기존 3종 어댑터를 AdapterFactory에 등록"""
    AdapterFactory.register("postgresql", PostgreSQLAdapter)
    AdapterFactory.register("mysql", MySQLPluginAdapter)
    AdapterFactory.register("oracle", OraclePluginAdapter)


# 모듈 임포트 시 자동 등록
register_builtin_adapters()
