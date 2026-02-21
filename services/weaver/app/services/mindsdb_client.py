from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import settings
from app.services.resilience import CircuitBreakerOpenError, SimpleCircuitBreaker, with_retry


class MindsDBUnavailableError(RuntimeError):
    pass


class MindsDBClient:
    def __init__(self) -> None:
        self._breaker = SimpleCircuitBreaker(failure_threshold=3, reset_timeout_seconds=20.0)

    @staticmethod
    def _client_kwargs() -> dict[str, Any]:
        kwargs: dict[str, Any] = {"timeout": settings.mindsdb_timeout_seconds}
        if settings.mindsdb_user:
            kwargs["auth"] = (settings.mindsdb_user, settings.mindsdb_password)
        return kwargs

    async def _post_sql(self, query: str) -> dict[str, Any]:
        try:
            self._breaker.preflight()
        except CircuitBreakerOpenError as exc:
            raise MindsDBUnavailableError(str(exc)) from exc
        url = f"{settings.mindsdb_url}/api/sql/query"
        async def _call() -> httpx.Response:
            async with httpx.AsyncClient(**self._client_kwargs()) as client:
                return await client.post(url, json={"query": query})
        try:
            res = await with_retry(_call, retries=2, base_delay_seconds=0.05)
        except CircuitBreakerOpenError as exc:
            raise MindsDBUnavailableError(str(exc)) from exc
        except httpx.HTTPError as exc:
            self._breaker.on_failure()
            raise MindsDBUnavailableError(str(exc)) from exc
        if res.status_code >= 400:
            self._breaker.on_failure()
            raise MindsDBUnavailableError(f"mindsdb status={res.status_code}: {res.text[:300]}")
        self._breaker.on_success()
        payload = res.json()
        if isinstance(payload, dict):
            return payload
        return {"data": payload}

    async def health_check(self) -> dict[str, Any]:
        try:
            self._breaker.preflight()
        except CircuitBreakerOpenError as exc:
            raise MindsDBUnavailableError(str(exc)) from exc
        url = f"{settings.mindsdb_url}/api/status"
        async def _call() -> httpx.Response:
            async with httpx.AsyncClient(**self._client_kwargs()) as client:
                return await client.get(url)
        try:
            res = await with_retry(_call, retries=2, base_delay_seconds=0.05)
        except CircuitBreakerOpenError as exc:
            raise MindsDBUnavailableError(str(exc)) from exc
        except httpx.HTTPError as exc:
            self._breaker.on_failure()
            raise MindsDBUnavailableError(str(exc)) from exc
        if res.status_code >= 400:
            self._breaker.on_failure()
            raise MindsDBUnavailableError(f"mindsdb status={res.status_code}")
        self._breaker.on_success()
        body = res.json()
        if isinstance(body, dict):
            return body
        return {"status": "unknown"}

    async def show_databases(self) -> list[str]:
        payload = await self._post_sql("SHOW DATABASES")
        rows = payload.get("data") or payload.get("result") or []
        names: list[str] = []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    name = row.get("name") or row.get("database") or row.get("DATABASE")
                    if name:
                        names.append(str(name))
                elif isinstance(row, (list, tuple)) and row:
                    names.append(str(row[0]))
        return names

    async def create_database(self, name: str, engine: str, connection: dict[str, Any]) -> None:
        params = json.dumps(connection, ensure_ascii=True)
        query = f"CREATE DATABASE {name} WITH ENGINE = '{engine}', PARAMETERS = {params}"
        await self._post_sql(query)

    async def drop_database(self, name: str) -> None:
        await self._post_sql(f"DROP DATABASE {name}")

    async def execute_query(self, sql: str, database: str | None = None) -> dict[str, Any]:
        query = sql if not database else f"USE {database}; {sql}"
        payload = await self._post_sql(query)
        rows = payload.get("data") or payload.get("rows") or []
        columns = payload.get("column_names") or payload.get("columns") or []
        return {"columns": columns, "data": rows}


mindsdb_client = MindsDBClient()
