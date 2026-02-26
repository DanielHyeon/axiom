"""PR3 tests: Insight auth dependencies."""
from __future__ import annotations

import jwt
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.core.config import settings
from app.core.insight_auth import get_current_insight_user, get_effective_tenant_id
from app.core.auth import CurrentUser


def _make_token(
    tenant_id: str = "tenant-1",
    role: str = "admin",
    user_id: str = "user-1",
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "permissions": None,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _mock_request(token: str | None = None) -> MagicMock:
    request = MagicMock()
    if token:
        request.headers = {"Authorization": f"Bearer {token}"}
    else:
        request.headers = {}
    return request


class TestGetCurrentInsightUser:

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        token = _make_token(tenant_id="t-abc", role="analyst", user_id="u-42")
        request = _mock_request(token)

        user = await get_current_insight_user(request)

        assert isinstance(user, CurrentUser)
        assert user.tenant_id == "t-abc"
        assert user.role == "analyst"
        assert user.user_id == "u-42"

    @pytest.mark.asyncio
    async def test_missing_token_raises_401(self):
        request = _mock_request(token=None)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_current_insight_user(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        request = _mock_request(token="garbage.token.here")

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_current_insight_user(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "u1",
            "tenant_id": "t1",
            "role": "admin",
            "permissions": None,
            "iat": int((now - timedelta(hours=1)).timestamp()),
            "exp": int((now - timedelta(minutes=1)).timestamp()),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        request = _mock_request(token)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_current_insight_user(request)
        assert exc_info.value.status_code == 401


class TestGetEffectiveTenantId:

    @pytest.mark.asyncio
    async def test_returns_tenant_id_from_user(self):
        user = CurrentUser(user_id="u1", tenant_id="t-xyz", role="admin", permissions=[])
        tid = await get_effective_tenant_id(user=user)
        assert tid == "t-xyz"
