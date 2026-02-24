"""
Core Service HTTP Client — Anti-Corruption Layer (DDD-P0-02).

Vision은 Core BC 소유 데이터에 직접 SQL로 접근하지 않고,
이 클라이언트를 통해 Core API 엔드포인트만 호출한다.

동기(sync)·비동기(async) 양쪽 모두 지원:
- AnalyticsService (psycopg2, 동기) → get_case_stats_sync / get_case_trend_sync / get_case_info_sync
- FastAPI 라우트 핸들러 (비동기) → get_case_stats / get_case_trend / get_case_info
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("axiom.vision.core_client")

CORE_BASE_URL = os.getenv("CORE_BASE_URL", "http://core-svc:8002")
_TIMEOUT = 10.0


class CoreClientError(RuntimeError):
    """Core API 호출 실패."""
    pass


class CoreClient:
    """Core 서비스와의 통신을 담당하는 Anti-Corruption Layer."""

    def __init__(self, base_url: str | None = None, timeout: float = _TIMEOUT) -> None:
        self._base_url = (base_url or CORE_BASE_URL).rstrip("/")
        self._timeout = timeout

    def _headers(self, tenant_id: str) -> dict[str, str]:
        return {"X-Tenant-Id": tenant_id}

    # ──────────────── Synchronous API (for psycopg2-based AnalyticsService) ──────────────── #

    def get_case_stats_sync(self, tenant_id: str) -> dict[str, Any]:
        """케이스 집계 통계 조회 (동기).

        Returns: {"total_cases": int, "active_cases": int}
        """
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(
                    f"{self._base_url}/api/v1/cases/stats",
                    headers=self._headers(tenant_id),
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning("Core /cases/stats returned %d: %s", e.response.status_code, e.response.text[:200])
            return {"total_cases": 0, "active_cases": 0}
        except Exception as e:
            logger.warning("Core /cases/stats unavailable: %s", e)
            return {"total_cases": 0, "active_cases": 0}

    def get_case_trend_sync(
        self, tenant_id: str, from_date: str, to_date: str, granularity: str = "monthly"
    ) -> list[dict[str, Any]]:
        """월별 케이스 추이 조회 (동기).

        Returns: list of {"period", "new_cases", "completed_cases", "active_cases"}
        """
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(
                    f"{self._base_url}/api/v1/cases/trend",
                    params={
                        "from_date": from_date,
                        "to_date": to_date,
                        "granularity": granularity,
                    },
                    headers=self._headers(tenant_id),
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("series", [])
        except Exception as e:
            logger.warning("Core /cases/trend unavailable: %s", e)
            return []

    def get_case_info_sync(self, case_id: str, tenant_id: str) -> dict[str, Any] | None:
        """개별 케이스 정보 조회 (동기).

        Returns: {"id", "title", "status"} or None if not found
        """
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(
                    f"{self._base_url}/api/v1/cases/{case_id}/info",
                    headers=self._headers(tenant_id),
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning("Core /cases/%s/info unavailable: %s", case_id, e)
            return None

    # ──────────────── Async API (for FastAPI route handlers) ──────────────── #

    async def get_case_stats(self, tenant_id: str) -> dict[str, Any]:
        """케이스 집계 통계 조회 (비동기)."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/api/v1/cases/stats",
                    headers=self._headers(tenant_id),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning("Core /cases/stats unavailable: %s", e)
            return {"total_cases": 0, "active_cases": 0}

    async def get_case_trend(
        self, tenant_id: str, from_date: str, to_date: str, granularity: str = "monthly"
    ) -> list[dict[str, Any]]:
        """월별 케이스 추이 조회 (비동기)."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/api/v1/cases/trend",
                    params={"from_date": from_date, "to_date": to_date, "granularity": granularity},
                    headers=self._headers(tenant_id),
                )
                resp.raise_for_status()
                return resp.json().get("series", [])
        except Exception as e:
            logger.warning("Core /cases/trend unavailable: %s", e)
            return []

    async def get_case_info(self, case_id: str, tenant_id: str) -> dict[str, Any] | None:
        """개별 케이스 정보 조회 (비동기)."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/api/v1/cases/{case_id}/info",
                    headers=self._headers(tenant_id),
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning("Core /cases/%s/info unavailable: %s", case_id, e)
            return None


# Singleton
_core_client: CoreClient | None = None


def get_core_client() -> CoreClient:
    global _core_client
    if _core_client is None:
        _core_client = CoreClient()
    return _core_client
