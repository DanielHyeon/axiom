"""Anti-Corruption Layer: Weaver BC → Oracle internal domain models.

Oracle의 SQL 실행 엔진이 Weaver API 응답 형식에 직접 의존하지 않도록
모든 Weaver 응답을 Oracle 내부 도메인 모델로 변환한다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Oracle 내부 도메인 모델 (Weaver 응답 형식에 의존하지 않음)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QueryExecutionResult:
    """Weaver 쿼리 실행 결과의 Oracle 내부 표현."""

    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    execution_time_ms: int = 0


# ---------------------------------------------------------------------------
# ACL 구현
# ---------------------------------------------------------------------------


class OracleWeaverACL:
    """Anti-Corruption Layer: Weaver BC의 쿼리 실행 응답을 Oracle 내부 모델로 변환.

    기존 sql_exec._execute_via_weaver()의 raw HTTP 호출을 대체하여,
    외부 BC 응답 → 내부 도메인 모델 변환 책임을 집중한다.
    """

    def __init__(
        self,
        query_url: str | None = None,
        bearer_token: str | None = None,
    ):
        self._query_url = query_url or settings.WEAVER_QUERY_API_URL
        self._bearer_token = (bearer_token or settings.WEAVER_BEARER_TOKEN).strip()

    @property
    def is_configured(self) -> bool:
        return bool(self._bearer_token)

    async def execute_query(
        self,
        sql: str,
        database: str | None = None,
        tenant_id: str = "",
        timeout: int = 30,
    ) -> QueryExecutionResult:
        """Weaver에 SQL을 전달하고 결과를 Oracle QueryExecutionResult로 변환."""
        if not self._bearer_token:
            raise RuntimeError("WEAVER_BEARER_TOKEN is not configured")

        payload: dict[str, Any] = {"sql": sql}
        if database:
            payload["database"] = database

        headers = {
            "Authorization": f"Bearer {self._bearer_token}",
            "Content-Type": "application/json",
            "X-Tenant-Id": tenant_id,
        }

        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                self._query_url, json=payload, headers=headers
            )
            response.raise_for_status()
            body = response.json()
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        return self._translate_query_result(body, elapsed_ms)

    @staticmethod
    def _translate_query_result(
        body: dict[str, Any], fallback_elapsed_ms: int
    ) -> QueryExecutionResult:
        """Weaver 쿼리 응답 → Oracle QueryExecutionResult 변환 (ACL 핵심).

        Weaver 응답 형식:
            {"data": [[...], ...], "columns": [...], "row_count": N, "execution_time_ms": N}
        """
        rows = body.get("data") or []
        columns = body.get("columns") or []
        row_count = int(body.get("row_count", len(rows)))
        truncated = row_count > len(rows)
        execution_time_ms = max(
            int(body.get("execution_time_ms", fallback_elapsed_ms)), 1
        )

        return QueryExecutionResult(
            columns=[str(c) for c in columns],
            rows=rows if isinstance(rows, list) else [],
            row_count=row_count,
            truncated=truncated,
            execution_time_ms=execution_time_ms,
        )


# Singleton
oracle_weaver_acl = OracleWeaverACL()
