"""
Vision API 공용 인증 헬퍼.

여러 API 라우터에서 중복 정의되던 get_current_user를 한곳에 모아
일관된 인증 로직을 공유한다.
"""
from __future__ import annotations

from fastapi import Header

from app.core.auth import CurrentUser, auth_service


async def get_current_user(
    authorization: str = Header("mock_token", alias="Authorization"),
) -> CurrentUser:
    """인증 토큰에서 현재 사용자 추출."""
    return auth_service.verify_token(authorization)
