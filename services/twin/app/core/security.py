"""
Twin 서비스 — JWT 인증 + 테넌트 추출.

Core 서비스의 security.py와 동일한 JWT 검증 로직을 사용하되,
Twin 전용 경량 구현으로 의존성을 최소화한다.
"""
from __future__ import annotations

from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)


def decode_token(token: str) -> dict[str, Any]:
    """JWT 토큰 디코딩."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict[str, Any]:
    """JWT에서 사용자 정보 추출 — tenant_id, user_id, roles 포함."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")

    payload = decode_token(credentials.credentials)
    if payload.get("type") == "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Use access token")

    tenant_id = payload.get("tenant_id", "default")

    # JWT v1/v2 호환
    raw_roles = payload.get("roles")
    if isinstance(raw_roles, list):
        roles = raw_roles
    else:
        roles = [payload.get("role", "viewer")]

    return {
        "user_id": payload["sub"],
        "tenant_id": tenant_id,
        "role": roles[0] if roles else "viewer",
        "roles": roles,
        "active_workspace_id": payload.get("active_workspace_id"),
    }
