"""Shared fixtures for Oracle unit tests. JWT auth required for protected endpoints (Phase O3)."""
import time
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import settings
from app.main import app


def make_admin_token() -> str:
    """Core-compatible access token for tests (admin role)."""
    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "role": "admin",
        "permissions": [],
        "iat": now,
        "exp": now + 900,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers():
    """Authorization: Bearer <admin JWT> for protected endpoints."""
    return {"Authorization": f"Bearer {make_admin_token()}"}
