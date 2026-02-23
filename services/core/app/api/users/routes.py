"""
사용자 API (Phase B2, Phase M).
GET /api/v1/users/me — 현재 로그인 사용자 정보.
POST /api/v1/users — 사용자 생성 (admin 또는 user:manage).
GET /api/v1/users — 사용자 목록 (admin: 전체 tenant, 그 외: 본인 tenant).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user, hash_password, ROLE_PERMISSIONS
from app.models.base_models import User, Tenant

router = APIRouter(prefix="/users", tags=["users"])


class CurrentUserResponse(BaseModel):
    id: str
    email: str | None
    role: str
    tenantId: str
    permissions: list[str]
    caseRoles: dict[str, str]


class UserCreateRequest(BaseModel):
    email: str
    password: str
    tenant_id: str
    role: str = "viewer"


class UserListItem(BaseModel):
    id: str
    email: str | None
    role: str
    tenant_id: str
    active: bool


def _require_admin_or_manage(current_user: dict) -> None:
    role = current_user.get("role", "viewer")
    perms = current_user.get("permissions") or []
    if role == "admin":
        return
    if "user:manage" in perms:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin or user:manage permission required",
    )


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_me(current_user: dict = Depends(get_current_user)):
    """JWT에서 추출한 현재 사용자 정보. Canvas authStore / 설정 > 사용자 연동용."""
    return CurrentUserResponse(
        id=current_user["user_id"],
        email=current_user.get("email"),
        role=current_user.get("role", "viewer"),
        tenantId=current_user["tenant_id"],
        permissions=current_user.get("permissions", []),
        caseRoles=current_user.get("case_roles", {}),
    )


@router.post("", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """사용자 생성. admin 또는 user:manage 권한 필요. tenant_id는 기존 tenant여야 함. 비관리자는 본인 tenant만 가능."""
    _require_admin_or_manage(current_user)
    if current_user.get("role") != "admin" and body.tenant_id != current_user.get("tenant_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only create users in your own tenant")
    # tenant 존재 확인
    r = await db.execute(select(Tenant).where(Tenant.id == body.tenant_id))
    tenant = r.scalar_one_or_none()
    if not tenant or not tenant.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or inactive tenant_id")
    # 이메일 중복 확인
    r = await db.execute(select(User).where(User.email == body.email))
    if r.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    role = body.role if body.role in ROLE_PERMISSIONS else "viewer"
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        tenant_id=body.tenant_id,
        role=role,
        active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserListItem(id=user.id, email=user.email, role=user.role, tenant_id=user.tenant_id, active=user.active)


@router.get("", response_model=list[UserListItem])
async def list_users(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """사용자 목록. admin은 전체, 그 외는 본인 tenant만."""
    q = select(User).where(User.active.is_(True))
    if current_user.get("role") != "admin":
        q = q.where(User.tenant_id == current_user.get("tenant_id", ""))
    r = await db.execute(q)
    users = r.scalars().all()
    return [
        UserListItem(id=u.id, email=u.email, role=u.role, tenant_id=u.tenant_id, active=u.active)
        for u in users
    ]
