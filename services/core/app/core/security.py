"""
JWT 인증 및 비밀번호 검증 (07_security/auth-model.md).
"""
import time
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

from app.core.config import settings
from app.core.middleware import get_current_tenant_id

# bcrypt 72-byte limit: truncate_error=False so passlib truncates instead of raising (Docker/env 호환)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)
security_scheme = HTTPBearer(auto_error=False)

# 역할별 기본 권한 (auth-model §2.3 요약; admin은 모든 권한으로 별도 처리)
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [],  # 모든 권한 통과
    "manager": ["case:create", "case:read", "case:write", "process:initiate", "process:submit", "process:approve", "agent:chat", "agent:feedback", "watch:manage", "mcp:configure", "user:manage"],
    "attorney": ["case:read", "case:write", "process:initiate", "process:submit", "agent:chat", "agent:feedback", "watch:manage"],
    "analyst": ["case:read", "process:submit", "agent:chat", "agent:feedback"],
    "engineer": ["case:read", "agent:chat", "datasource:manage", "datasource:read", "ontology:manage", "ontology:read", "schema:edit", "schema:read"],
    "staff": ["case:read", "process:submit", "agent:chat", "watch:manage"],
    "viewer": ["case:read", "agent:chat"],
}


# bcrypt allows at most 72 bytes; truncate to avoid ValueError in some environments
def _truncate_for_bcrypt(s: str, max_bytes: int = 72) -> str:
    b = s.encode("utf-8")
    if len(b) <= max_bytes:
        return s
    return b[:max_bytes].decode("utf-8", errors="ignore") or s[:1]


def hash_password(plain: str) -> str:
    return pwd_context.hash(_truncate_for_bcrypt(plain))


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_truncate_for_bcrypt(plain), hashed)


def _payload_for_access(user_id: str, email: str, tenant_id: str, role: str, permissions: list[str], case_roles: dict[str, str]) -> dict[str, Any]:
    now = int(time.time())
    return {
        "sub": user_id,
        "email": email,
        "tenant_id": tenant_id,
        "role": role,
        "permissions": permissions,
        "case_roles": case_roles or {},
        "iat": now,
        "exp": now + settings.JWT_ACCESS_EXPIRE_SECONDS,
    }


def _payload_for_refresh(user_id: str) -> dict[str, Any]:
    now = int(time.time())
    return {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + settings.JWT_REFRESH_EXPIRE_DAYS * 86400,
    }


def create_access_token(user_id: str, email: str, tenant_id: str, role: str, permissions: list[str] | None = None, case_roles: dict[str, str] | None = None) -> str:
    perms = permissions if permissions is not None else ROLE_PERMISSIONS.get(role, [])
    payload = _payload_for_access(user_id, email, tenant_id, role, perms, case_roles or {})
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = _payload_for_refresh(user_id)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme)) -> dict[str, Any]:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")
    payload = decode_token(credentials.credentials)
    if payload.get("type") == "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Use access token")
    tenant_id = payload["tenant_id"]
    header_tenant = get_current_tenant_id()
    if header_tenant and header_tenant != "default" and header_tenant != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")
    return {
        "user_id": payload["sub"],
        "email": payload.get("email"),
        "tenant_id": tenant_id,
        "role": payload.get("role", "viewer"),
        "permissions": payload.get("permissions", []),
        "case_roles": payload.get("case_roles", {}),
    }


def require_permission(permission: str):
    """경로별 권한 검사용 (A7 선택 시 사용)."""
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] == "admin":
            return user
        if permission not in user.get("permissions", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission '{permission}' required")
        return user
    return _check
