"""Synapse 연동 클라이언트 — 리니지 그래프를 Neo4j에 동기화한다.

OLAP Studio가 리니지 이벤트를 발행하면, 이 클라이언트를 통해
Synapse의 메타데이터 그래프에 직접 동기화할 수도 있다.
이벤트 기반 비동기 연동이 권장되지만, 즉시 반영이 필요한 경우 사용한다.
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
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client


async def close_http() -> None:
    """애플리케이션 종료 시 httpx 클라이언트를 정리한다."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


async def sync_lineage_to_graph(
    tenant_id: str,
    entities: list[dict],
    edges: list[dict],
    service_token: str = "",
) -> dict:
    """리니지 엔티티와 엣지를 Synapse Neo4j 그래프에 동기화한다.

    Synapse의 /api/v3/synapse/metadata/graph/lineage 엔드포인트를 호출한다.
    실패 시 빈 결과를 반환하고 로그만 남긴다 (호출자에게 예외 전파하지 않음).
    """
    try:
        client = _get_http()
        response = await client.post(
            f"{settings.SYNAPSE_BASE_URL}/api/v3/synapse/metadata/graph/lineage",
            json={
                "tenant_id": tenant_id,
                "entities": entities,
                "edges": edges,
            },
            headers={
                "Authorization": f"Bearer {service_token}",
                "X-Tenant-Id": tenant_id,
            },
        )
        if response.status_code == 200:
            logger.info("synapse_lineage_synced", entities=len(entities), edges=len(edges))
            return response.json()
        else:
            logger.warning("synapse_lineage_sync_failed", status=response.status_code, body=response.text[:200])
            return {}
    except Exception as e:
        logger.warning("synapse_lineage_sync_error", error=str(e))
        return {}


async def notify_cube_metadata(
    tenant_id: str,
    cube_id: str,
    cube_name: str,
    dimensions: list[str],
    measures: list[str],
    service_token: str = "",
) -> bool:
    """큐브 게시 시 Synapse에 메타데이터를 알린다.

    Synapse가 이 정보를 글로서리나 검색 인덱스에 반영할 수 있다.
    """
    try:
        client = _get_http()
        response = await client.post(
            f"{settings.SYNAPSE_BASE_URL}/api/v3/synapse/metadata/catalog/register",
            json={
                "tenant_id": tenant_id,
                "source": "olap-studio",
                "entity_type": "CUBE",
                "entity_id": cube_id,
                "entity_name": cube_name,
                "metadata": {
                    "dimensions": dimensions,
                    "measures": measures,
                },
            },
            headers={
                "Authorization": f"Bearer {service_token}",
                "X-Tenant-Id": tenant_id,
            },
        )
        return response.status_code == 200
    except Exception as e:
        logger.warning("synapse_metadata_notify_error", error=str(e))
        return False
