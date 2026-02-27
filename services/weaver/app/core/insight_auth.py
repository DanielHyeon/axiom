from __future__ import annotations

from typing import List

from fastapi import Depends, HTTPException, Request

from app.core.auth import auth_service, CurrentUser
from app.core.config import settings


async def get_current_insight_user(request: Request) -> CurrentUser:
    """Extract and verify the JWT bearer token from the request.

    Supports two modes:
    1. Standard JWT bearer — returns CurrentUser from decoded payload.
    2. Service token (WEAVER_INSIGHT_SERVICE_TOKEN) — used by Oracle for
       service-to-service calls.  Tenant is taken from the X-Tenant-Id header.
    """
    auth_header = request.headers.get("Authorization", "")

    # Service token path (E7 fix): bypass JWT when internal token matches
    prefix = "bearer "
    if (
        settings.insight_service_token
        and auth_header.lower().startswith(prefix)
        and (raw_token := auth_header[len(prefix):].strip()) == settings.insight_service_token
    ):
        if not (tenant_id := request.headers.get("X-Tenant-Id", "").strip()):
            raise HTTPException(
                status_code=400,
                detail="X-Tenant-Id header required for service-token requests",
            )
        return CurrentUser(user_id="service:oracle", tenant_id=tenant_id, role="staff")

    return auth_service.verify_token(auth_header or None)


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
