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
from app.core.tenant_context import TenantContext, set_tenant_context, parse_workspace_id, get_workspace_id_header

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

    # ── 토큰 블랙리스트 검사 (Feature Flag로 활성화) ──
    # FF_TOKEN_BLACKLIST=true 일 때만 Redis 블랙리스트를 확인한다.
    # 로그아웃·계정 정지·비밀번호 변경 시 즉시 토큰을 무효화하기 위함.
    from shared.utils.feature_flags import is_enabled
    if is_enabled("TOKEN_BLACKLIST"):
        from shared.auth.token_blacklist import TokenBlacklist
        try:
            from shared.events.safe_publish import get_redis_client  # 공유 Redis 클라이언트
            redis_client = get_redis_client()
        except (ImportError, ConnectionError):
            # Redis 미설정 시 블랙리스트 건너뛰기 (fail-open)
            redis_client = None
        if redis_client is not None:
            blacklist = TokenBlacklist(redis_client)
            if await blacklist.is_revoked(
                jti=payload.get("jti", ""),
                user_id=payload["sub"],
                issued_at=payload.get("iat", 0),
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token revoked",
                )

    tenant_id = payload["tenant_id"]
    header_tenant = get_current_tenant_id()
    if header_tenant and header_tenant != "default" and header_tenant != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    # JWT v1/v2 호환: role(단수 str) ↔ roles(복수 list) 양쪽 지원
    # v1 토큰: {"role": "admin"}  → roles = ["admin"]
    # v2 토큰: {"roles": ["TENANT_ADMIN", "PROCESS_ARCHITECT"]}
    raw_roles = payload.get("roles")
    if isinstance(raw_roles, list):
        roles = raw_roles
    else:
        roles = [payload.get("role", "viewer")]
    primary_role = roles[0] if roles else "viewer"

    # workspace_id: v2 토큰의 active_workspace_id 추출 (v1은 None)
    active_workspace_id = payload.get("active_workspace_id")

    # TenantContext 조립 — audit_logged 데코레이터 등에서 사용
    ctx = TenantContext(
        tenant_id=tenant_id,
        user_id=payload["sub"],
        workspace_id=parse_workspace_id(active_workspace_id or get_workspace_id_header()),
        role_codes=frozenset(roles),
        permission_codes=frozenset(payload.get("permissions", [])),
    )
    set_tenant_context(ctx)

    return {
        "user_id": payload["sub"],
        "email": payload.get("email"),
        "tenant_id": tenant_id,
        "role": primary_role,           # 기존 호환: 단수 문자열
        "roles": roles,                 # v2: 복수 역할 리스트
        "permissions": payload.get("permissions", []),
        "case_roles": payload.get("case_roles", {}),
        "active_workspace_id": active_workspace_id,
    }


def require_permission(permission: str):
    """경로별 권한 검사용 (v1 legacy 전용).

    NOTE: v2 multi-role 및 process graph permissions는 Phase 1에서
    has_process_graph_permission()과 통합 예정. 현재는 user["role"]
    (primary_role)만 검사한다.
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] == "admin":
            return user
        if permission not in user.get("permissions", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission '{permission}' required")
        return user
    return _check
