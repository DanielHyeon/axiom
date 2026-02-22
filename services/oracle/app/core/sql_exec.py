from __future__ import annotations

from typing import Any, Optional
import re
import time

import httpx
import structlog
from pydantic import BaseModel

from app.core.auth import CurrentUser
from app.core.config import settings
from app.core.synapse_client import synapse_client

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
        self.weaver_query_url = settings.WEAVER_QUERY_API_URL
        self.weaver_bearer_token = settings.WEAVER_BEARER_TOKEN.strip()

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
        for item in synapse_client.list_datasources():
            if item.get("id") == datasource_id:
                db_name = str(item.get("database") or "").strip()
                return db_name or None
        return None

    async def _execute_via_weaver(self, sql: str, datasource_id: str, user: CurrentUser, timeout: int) -> ExecutionResult:
        if not self.weaver_bearer_token:
            raise RuntimeError("WEAVER_BEARER_TOKEN is not configured")

        payload: dict[str, Any] = {"sql": sql}
        if database := self._resolve_database_name(datasource_id):
            payload["database"] = database

        headers = {
            "Authorization": f"Bearer {self.weaver_bearer_token}",
            "Content-Type": "application/json",
            "X-Tenant-Id": str(user.tenant_id),
        }
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(self.weaver_query_url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()

        rows = body.get("data") or []
        columns = body.get("columns") or []
        row_count = int(body.get("row_count", len(rows)))
        truncated = row_count > len(rows)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ExecutionResult(
            columns=[str(c) for c in columns],
            rows=rows if isinstance(rows, list) else [],
            row_count=row_count,
            truncated=truncated,
            execution_time_ms=max(int(body.get("execution_time_ms", elapsed_ms)), 1),
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

    async def execute_sql(self, sql: str, datasource_id: str, user: CurrentUser, timeout: Optional[int] = None) -> ExecutionResult:
        logger.info("sql_exec_start", sql_len=len(sql), tenant=str(user.tenant_id))
        effective_timeout = timeout or settings.ORACLE_SQL_EXECUTION_TIMEOUT_SEC

        if self.execution_mode not in {"mock", "hybrid", "weaver"}:
            logger.warning("invalid_sql_execution_mode", mode=self.execution_mode)
            self.execution_mode = "hybrid"

        if self.execution_mode in {"hybrid", "weaver"}:
            try:
                return await self._execute_via_weaver(sql, datasource_id, user, effective_timeout)
            except Exception as exc:
                logger.warning("sql_exec_weaver_failed", mode=self.execution_mode, reason=str(exc))
                if self.execution_mode == "weaver":
                    raise

        return await self._execute_mock(sql, user)

sql_executor = SQLExecutor()
