"""
인증 API (07_security/auth-model.md).
POST /api/v1/auth/login, POST /api/v1/auth/refresh
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.database import get_session
from app.core.redis_client import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    ROLE_PERMISSIONS,
)
from app.core.config import settings
from app.models.base_models import User

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_BLACKLIST_PREFIX = "auth:refresh_blacklist:"
BLACKLIST_TTL = settings.JWT_REFRESH_EXPIRE_DAYS * 86400


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


async def _is_refresh_blacklisted(token: str) -> bool:
    r = get_redis()
    key = REFRESH_BLACKLIST_PREFIX + token
    return await r.exists(key) > 0


async def _blacklist_refresh(token: str) -> None:
    r = get_redis()
    key = REFRESH_BLACKLIST_PREFIX + token
    await r.set(key, "1", ex=BLACKLIST_TTL)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    # Tenant 활성 검사는 선택: Tenant 테이블 조회 후 active 확인. 여기서는 생략(tenant_id만 사용).
    permissions = ROLE_PERMISSIONS.get(user.role, [])
    access = create_access_token(
        user_id=user.id,
        email=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
        permissions=permissions,
        case_roles={},
    )
    refresh = create_refresh_token(user.id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.JWT_ACCESS_EXPIRE_SECONDS,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_session)):
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if await _is_refresh_blacklisted(req.refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    await _blacklist_refresh(req.refresh_token)
    permissions = ROLE_PERMISSIONS.get(user.role, [])
    access = create_access_token(
        user_id=user.id,
        email=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
        permissions=permissions,
        case_roles={},
    )
    refresh = create_refresh_token(user.id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.JWT_ACCESS_EXPIRE_SECONDS,
    )
