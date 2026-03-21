"""LLM 캐시 관리 API -- 캐시 통계 조회 및 무효화."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.services.llm_cache import get_cache_metrics

router = APIRouter(prefix="/api/v2/oracle/cache", tags=["LLM 캐시"])


@router.get("/metrics")
async def api_cache_metrics(request: Request):
    """캐시 적중/미적중 통계 조회.

    Returns:
        hits, misses, sets, hit_rate (%) 포함 메트릭 딕셔너리
    """
    # Redis 클라이언트는 lifespan에서 app.state.redis에 바인딩됨
    redis_client = getattr(request.app.state, "redis", None)
    metrics = await get_cache_metrics(redis_client)
    return {"success": True, "data": metrics}
