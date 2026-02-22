"""
사용자 API (Phase B2).
GET /api/v1/users/me — 현재 로그인 사용자 정보 (auth-model, api-contracts).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


class CurrentUserResponse(BaseModel):
    id: str
    email: str | None
    role: str
    tenantId: str
    permissions: list[str]
    caseRoles: dict[str, str]


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
