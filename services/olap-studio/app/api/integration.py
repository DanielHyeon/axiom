"""서비스 연계 API — Vision/Synapse/Weaver 연동 상태 조회 및 수동 동기화."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.context import get_request_context, require_capability
from app.integrations import synapse_client, vision_client, weaver_client

router = APIRouter(prefix="/integrations", tags=["서비스 연계"])


@router.get("/status")
async def get_integration_status(request: Request):
    """연동 서비스 상태 조회."""
    ctx = get_request_context(request)
    return {
        "success": True,
        "data": {
            "synapse": {"url": synapse_client.SYNAPSE_BASE_URL, "description": "리니지 그래프 동기화"},
            "vision": {"url": vision_client.VISION_BASE_URL, "description": "큐브 참조 메타데이터"},
            "weaver": {"url": weaver_client.WEAVER_BASE_URL, "description": "카탈로그 동기화"},
        },
    }
