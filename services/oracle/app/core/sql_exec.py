from __future__ import annotations

import asyncio
from typing import Any
import re
import time

import structlog
from pydantic import BaseModel

from app.core.auth import CurrentUser
from app.core.config import settings
from app.infrastructure.acl.synapse_acl import oracle_synapse_acl
from app.infrastructure.acl.weaver_acl import oracle_weaver_acl

logger = structlog.get_logger()

class ExecutionResult(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    execution_time_ms: int
    backend: str = "mock"

class SQLExecutor:
    def __init__(self, sql_timeout: int = 30, max_rows: int = 10000):
        self.sql_timeout = sql_timeout
        self.max_rows = max_rows
        self.execution_mode = settings.ORACLE_SQL_EXECUTION_MODE.lower()

    @staticmethod
    def _extract_limit(sql: str, default: int = 2, upper_bound: int = 10000) -> int:
        match = re.search(r"\bLIMIT\s+(\d+)\b", sql, flags=re.IGNORECASE)
        if not match:
            return default
        try:
            limit = int(match.group(1))
        except ValueError:
            return default
        return max(1, min(limit, upper_bound))

    @staticmethod
    def _extract_columns(sql: str) -> list[str]:
        match = re.search(r"SELECT\s+(.*?)\s+FROM\s", sql, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return ["value"]
        segment = match.group(1).strip()
        if segment == "*":
            return ["id", "status", "value"]

        columns: list[str] = []
        for raw in segment.split(","):
            token = raw.strip()
            if alias_match := re.search(r"\bAS\s+([a-zA-Z_][a-zA-Z0-9_]*)$", token, flags=re.IGNORECASE):
                columns.append(alias_match.group(1))
                continue
            parts = token.split(".")
            columns.append(parts[-1].strip('"` '))
        return [c for c in columns if c] or ["value"]

    def _resolve_database_name(self, datasource_id: str) -> str | None:
        """ACL을 통해 데이터소스의 DB 이름 조회."""
        for ds in oracle_synapse_acl.list_datasources():
            if ds.id == datasource_id:
                return ds.database or None
        return None

    async def _execute_via_weaver(self, sql: str, datasource_id: str, user: CurrentUser, timeout: int) -> ExecutionResult:
        """ACL을 통해 Weaver에 SQL 실행 후 Oracle ExecutionResult로 변환."""
        database = self._resolve_database_name(datasource_id)
        acl_result = await oracle_weaver_acl.execute_query(
            sql=sql,
            database=database,
            tenant_id=str(user.tenant_id),
            timeout=timeout,
        )
        return ExecutionResult(
            columns=acl_result.columns,
            rows=acl_result.rows,
            row_count=acl_result.row_count,
            truncated=acl_result.truncated,
            execution_time_ms=acl_result.execution_time_ms,
            backend="weaver",
        )

    async def _execute_mock(self, sql: str, user: CurrentUser) -> ExecutionResult:
        limit = self._extract_limit(sql, default=2, upper_bound=self.max_rows)
        columns = self._extract_columns(sql)
        rows: list[list[Any]] = []
        for idx in range(limit):
            row: list[Any] = []
            for col in columns:
                if "id" in col.lower():
                    row.append(idx + 1)
                elif "status" in col.lower():
                    row.append("SUCCESS" if idx % 2 == 0 else "FAILED")
                else:
                    row.append(f"{col}_{idx + 1}")
            rows.append(row)
        logger.warning("sql_exec_mock_fallback", tenant=str(user.tenant_id), rows=len(rows))
        return ExecutionResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=False,
            execution_time_ms=5,
            backend="mock",
        )

    @staticmethod
    def _serialize_value(val: Any) -> Any:
        """PostgreSQL 네이티브 타입을 JSON 직렬화 가능한 타입으로 변환."""
        if val is None:
            return None
        from decimal import Decimal
        if isinstance(val, Decimal):
            return float(val)
        if hasattr(val, 'isoformat'):
            return val.isoformat()
        if isinstance(val, (bytes, memoryview)):
            return str(val)
        if isinstance(val, (dict, list)):
            return val
        return val

    def _execute_direct_pg_sync(self, sql: str) -> ExecutionResult:
        """PostgreSQL에 직접 SQL을 동기로 실행한다 (스레드 풀에서 호출).

        이벤트 루프 블로킹을 방지하기 위해 _execute_direct_pg에서
        asyncio.to_thread로 위임받아 실행된다.
        """
        import psycopg2

        db_url = settings.QUERY_HISTORY_DATABASE_URL
        started = time.perf_counter()
        try:
            conn = psycopg2.connect(db_url)
            try:
                conn.set_session(readonly=True, autocommit=True)
                with conn.cursor() as cur:
                    cur.execute(sql)
                    columns = [desc[0] for desc in cur.description] if cur.description else []
                    rows_raw = cur.fetchmany(self.max_rows + 1)
                    truncated = len(rows_raw) > self.max_rows
                    rows = [[self._serialize_value(v) for v in r] for r in rows_raw[:self.max_rows]]
            finally:
                conn.close()
            elapsed_ms = max(int((time.perf_counter() - started) * 1000), 1)
            logger.info("sql_exec_direct_pg_ok", rows=len(rows), cols=len(columns), ms=elapsed_ms)
            return ExecutionResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                truncated=truncated,
                execution_time_ms=elapsed_ms,
                backend="direct_pg",
            )
        except Exception as exc:
            elapsed_ms = max(int((time.perf_counter() - started) * 1000), 1)
            logger.error("sql_exec_direct_pg_failed", error=str(exc), ms=elapsed_ms)
            raise

    async def _execute_direct_pg(self, sql: str, user: CurrentUser) -> ExecutionResult:
        """PostgreSQL 직접 실행 (비동기 래퍼).

        동기 psycopg2 호출을 asyncio.to_thread로 감싸서
        이벤트 루프를 블로킹하지 않는다.
        """
        return await asyncio.to_thread(self._execute_direct_pg_sync, sql)

    async def execute_sql(self, sql: str, datasource_id: str, user: CurrentUser, timeout: int | None = None) -> ExecutionResult:
        logger.info("sql_exec_start", sql_len=len(sql), tenant=str(user.tenant_id))
        effective_timeout = timeout or settings.ORACLE_SQL_EXECUTION_TIMEOUT_SEC

        if self.execution_mode not in {"mock", "hybrid", "weaver", "direct"}:
            logger.warning("invalid_sql_execution_mode", mode=self.execution_mode)
            self.execution_mode = "hybrid"

        if self.execution_mode == "direct":
            try:
                return await self._execute_direct_pg(sql, user)
            except Exception as exc:
                logger.warning("sql_exec_direct_fallback_to_mock", reason=str(exc))

        if self.execution_mode in {"hybrid", "weaver"}:
            try:
                return await self._execute_via_weaver(sql, datasource_id, user, effective_timeout)
            except Exception as exc:
                logger.warning("sql_exec_weaver_failed", mode=self.execution_mode, reason=str(exc))
                if self.execution_mode == "weaver":
                    raise

        return await self._execute_mock(sql, user)

    def _execute_sql_with_params_sync(
        self,
        sql: str,
        params: list[Any],
        timeout_seconds: float,
    ) -> ExecutionResult:
        """파라미터 바인딩 SQL을 동기로 실행한다 (스레드 풀에서 호출).

        이벤트 루프 블로킹을 방지하기 위해 execute_sql_with_params에서
        asyncio.to_thread로 위임받아 실행된다.

        보안 주의: sql에 사용자 입력을 직접 삽입하지 말 것.
                  반드시 params를 통해 파라미터 바인딩을 사용할 것.
        """
        import psycopg2

        db_url = settings.QUERY_HISTORY_DATABASE_URL
        started = time.perf_counter()

        conn = psycopg2.connect(db_url)
        try:
            conn.set_session(readonly=True, autocommit=True)
            with conn.cursor() as cur:
                # psycopg2는 $1 대신 %s를 사용하므로 변환
                pg_sql = re.sub(r'\$\d+', '%s', sql)

                # 타임아웃 설정 — autocommit=True이므로 SET (LOCAL 아님) 사용
                timeout_ms = int(timeout_seconds * 1000)
                if not (0 < timeout_ms <= 300_000):
                    raise ValueError(f"타임아웃 범위 초과: {timeout_ms}ms")
                cur.execute("SET statement_timeout = %s", (timeout_ms,))

                cur.execute(pg_sql, params)
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows_raw = cur.fetchall()
                rows = [[self._serialize_value(v) for v in r] for r in rows_raw]

                # 타임아웃 리셋 (후속 쿼리에 영향 방지)
                cur.execute("SET statement_timeout = 0")

            elapsed_ms = max(int((time.perf_counter() - started) * 1000), 1)
            return ExecutionResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                truncated=False,
                execution_time_ms=elapsed_ms,
                backend="direct_pg_params",
            )
        except Exception as exc:
            elapsed_ms = max(int((time.perf_counter() - started) * 1000), 1)
            logger.debug(
                "sql_exec_params_failed",
                error=str(exc),
                ms=elapsed_ms,
                sql_len=len(sql),
            )
            raise
        finally:
            conn.close()

    async def execute_sql_with_params(
        self,
        sql: str,
        params: list[Any],
        datasource_id: str,
        timeout_seconds: float = 2.0,
    ) -> ExecutionResult:
        """파라미터 바인딩을 사용하여 SQL을 실행한다 (비동기 래퍼).

        동기 psycopg2 호출을 asyncio.to_thread로 감싸서
        이벤트 루프를 블로킹하지 않는다.

        Args:
            sql: 파라미터 플레이스홀더($1, $2...)가 포함된 SQL
            params: 바인딩할 파라미터 값 목록
            datasource_id: 데이터소스 ID
            timeout_seconds: 쿼리 타임아웃 (초)
        """
        return await asyncio.to_thread(
            self._execute_sql_with_params_sync, sql, params, timeout_seconds
        )


sql_executor = SQLExecutor()
