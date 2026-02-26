from __future__ import annotations

from typing import List

from fastapi import Depends, Request

from app.core.auth import auth_service, CurrentUser


async def get_current_insight_user(request: Request) -> CurrentUser:
    """Extract and verify the JWT bearer token from the request."""
    auth_header = request.headers.get("Authorization")
    return auth_service.verify_token(auth_header)


async def get_effective_tenant_id(
    user: CurrentUser = Depends(get_current_insight_user),
) -> str:
    """Return the tenant_id from the verified JWT — used for RLS scoping."""
    return user.tenant_id


def require_insight_role(*allowed_roles: str):
    """Factory that returns a FastAPI dependency checking the user's role."""

    async def _check(user: CurrentUser = Depends(get_current_insight_user)) -> CurrentUser:
        auth_service.requires_role(user, list(allowed_roles))
        return user

    return Depends(_check)
