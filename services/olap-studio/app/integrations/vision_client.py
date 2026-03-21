"""Vision 연동 클라이언트 — OLAP Studio 큐브를 Vision 분석에서 참조할 수 있게 한다.

Vision의 온톨로지 기반 피벗에서 OLAP Studio 큐브의 측정값이나 차원을
참조 링크로 제공한다. 이는 사용자가 두 시스템 간을 오갈 수 있게 해준다.
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


async def register_cube_reference(
    tenant_id: str,
    cube_id: str,
    cube_name: str,
    fact_table: str,
    measures: list[str],
    service_token: str = "",
) -> bool:
    """Vision에 큐브 참조 메타데이터를 등록한다.

    Vision이 이 정보를 활용하여 KPI/Measure와 OLAP 큐브 간 링크를 제공할 수 있다.
    실패해도 OLAP Studio 동작에 영향 없음.
    """
    try:
        client = _get_http()
        response = await client.post(
            f"{settings.VISION_BASE_URL}/api/v1/vision/references/olap-cubes",
            json={
                "cube_id": cube_id,
                "cube_name": cube_name,
                "fact_table": fact_table,
                "measures": measures,
                "source_service": "olap-studio",
            },
            headers={
                "Authorization": f"Bearer {service_token}",
                "X-Tenant-Id": tenant_id,
            },
        )
        if response.status_code in (200, 201):
            logger.info("vision_cube_reference_registered", cube_id=cube_id)
            return True
        logger.warning("vision_cube_reference_failed", status=response.status_code)
        return False
    except Exception as e:
        logger.warning("vision_cube_reference_error", error=str(e))
        return False
