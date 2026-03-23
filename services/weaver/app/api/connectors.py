"""Task 0.6: Connector Capability Matrix API.

프론트엔드에서 데이터소스 유형별 지원 기능을 표시할 때 사용한다.
인증은 기존 Weaver 패턴을 따른다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.core.auth import AuthService, CurrentUser
from app.models.capability import list_manifests, get_manifest

router = APIRouter(prefix="/api/v3/weaver/connectors", tags=["connectors"])

_auth = AuthService()


async def _get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    return _auth.verify_token(authorization)


class ConnectorListResponse(BaseModel):
    success: bool = True
    data: list[dict]
    total: int


@router.get("")
async def list_connectors(
    user: CurrentUser = Depends(_get_current_user),
) -> ConnectorListResponse:
    """등록된 모든 커넥터 매니페스트 목록 조회"""
    manifests = list_manifests()
    return ConnectorListResponse(
        data=[m.model_dump() for m in manifests],
        total=len(manifests),
    )


@router.get("/{engine}")
async def get_connector(
    engine: str,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """특정 엔진의 매니페스트 조회"""
    manifest = get_manifest(engine)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"알 수 없는 커넥터 엔진: {engine}")
    return {"success": True, "data": manifest.model_dump()}
