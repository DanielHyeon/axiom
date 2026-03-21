"""Weaver 연동 클라이언트 — 카탈로그에 OLAP 메타데이터를 동기화한다.

Weaver의 데이터 패브릭 카탈로그에 OLAP Studio의 데이터소스, 큐브, ETL 정보를
등록하여 전사적 데이터 디스커버리를 지원한다.
"""
from __future__ import annotations

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# httpx 싱글턴 — 매 요청마다 클라이언트를 생성하지 않고 커넥션 풀을 재사용
_http_client: httpx.AsyncClient | None = None


def _get_http() -> httpx.AsyncClient:
    """httpx AsyncClient 싱글턴을 지연 초기화하여 반환한다."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=5.0)
    return _http_client


async def close_http() -> None:
    """애플리케이션 종료 시 httpx 클라이언트를 정리한다."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


async def sync_datasource_to_catalog(
    tenant_id: str,
    datasource_id: str,
    datasource_name: str,
    source_type: str,
    service_token: str = "",
) -> bool:
    """OLAP 데이터소스를 Weaver 카탈로그에 등록한다."""
    try:
        client = _get_http()
        response = await client.post(
            f"{settings.WEAVER_BASE_URL}/api/v2/weaver/catalog/external-sources",
            json={
                "source_id": datasource_id,
                "source_name": datasource_name,
                "source_type": source_type,
                "origin_service": "olap-studio",
            },
            headers={
                "Authorization": f"Bearer {service_token}",
                "X-Tenant-Id": tenant_id,
            },
        )
        return response.status_code in (200, 201)
    except Exception as e:
        logger.warning("weaver_catalog_sync_error", error=str(e))
        return False


async def sync_etl_summary_to_catalog(
    tenant_id: str,
    pipeline_id: str,
    pipeline_name: str,
    status: str,
    last_run_at: str | None = None,
    rows_written: int = 0,
    service_token: str = "",
) -> bool:
    """ETL 파이프라인 요약 정보를 Weaver 카탈로그에 동기화한다.

    Weaver가 이 정보를 활용하여 데이터 신선도(freshness) 메트릭을 제공할 수 있다.
    """
    try:
        client = _get_http()
        response = await client.post(
            f"{settings.WEAVER_BASE_URL}/api/v2/weaver/catalog/etl-summaries",
            json={
                "pipeline_id": pipeline_id,
                "pipeline_name": pipeline_name,
                "status": status,
                "last_run_at": last_run_at,
                "rows_written": rows_written,
                "origin_service": "olap-studio",
            },
            headers={
                "Authorization": f"Bearer {service_token}",
                "X-Tenant-Id": tenant_id,
            },
        )
        return response.status_code in (200, 201)
    except Exception as e:
        logger.warning("weaver_etl_summary_sync_error", error=str(e))
        return False
