from typing import Any, List

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from uuid import UUID

from app.core.config import settings

# 401/403 응답 형식 통일 (O3-2): { "code", "message" }
_DETAIL_401 = lambda msg: {"code": "UNAUTHORIZED", "message": msg}
_DETAIL_403 = lambda msg: {"code": "FORBIDDEN", "message": msg}


class CurrentUser(BaseModel):
    user_id: UUID
    tenant_id: UUID
    role: str
    permissions: List[str] = []


security_scheme = HTTPBearer(auto_error=False)


def _parse_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_DETAIL_401("Invalid token: user_id or tenant_id invalid"),
        )


class AuthService:
    """JWT verification aligned with Core (07_security, O3). Core와 동일 JWT_SECRET_KEY·JWT_ALGORITHM 사용."""

    def verify_token(self, token: str) -> CurrentUser:
        """
        Decode and verify JWT issued by Core. Expects payload: sub, tenant_id, role, permissions.
        Uses same JWT_SECRET_KEY and JWT_ALGORITHM as Core for symmetric verification.
        """
        if not token or not token.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_DETAIL_401("Authorization token missing"),
            )
        token = token.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_DETAIL_401("Invalid or expired token"),
            )
        if payload.get("type") == "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_DETAIL_401("Use access token"),
            )
        sub = payload.get("sub")
        tenant_id_raw = payload.get("tenant_id")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_DETAIL_401("Invalid token: missing sub"),
            )
        if not tenant_id_raw:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_DETAIL_401("Invalid token: missing tenant_id"),
            )
        return CurrentUser(
            user_id=_parse_uuid(sub),
            tenant_id=_parse_uuid(tenant_id_raw),
            role=payload.get("role", "viewer"),
            permissions=payload.get("permissions") or [],
        )

    def requires_role(self, user: CurrentUser, allowed_roles: List[str]) -> None:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_DETAIL_403(f"Role {user.role} not permitted to access this resource."),
            )


auth_service = AuthService()
