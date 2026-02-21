import logging

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import _sanitize_origins, settings
from app.core.logging import SecretRedactionFilter
from app.main import app


def test_sanitize_origins_removes_wildcard() -> None:
    assert _sanitize_origins(["*", "https://app.axiom.kr"]) == ["https://app.axiom.kr"]


def test_secret_redaction_filter_masks_password_fields() -> None:
    filt = SecretRedactionFilter()
    record = logging.LogRecord(
        name="weaver.security",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg={"password": "plain", "nested": {"token": "abc"}, "user": "reader"},
        args=(),
        exc_info=None,
    )
    assert filt.filter(record) is True
    assert record.msg["password"] == "***REDACTED***"
    assert record.msg["nested"]["token"] == "***REDACTED***"
    assert record.msg["user"] == "reader"


@pytest.mark.asyncio
async def test_cors_allows_configured_origin_on_preflight() -> None:
    origin = settings.weaver_cors_allowed_origins[0]
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "GET",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.options("/health", headers=headers)
    assert res.status_code in (200, 204)
    assert res.headers.get("access-control-allow-origin") == origin


@pytest.mark.asyncio
async def test_cors_blocks_unlisted_origin_on_preflight() -> None:
    headers = {
        "Origin": "https://evil.example.com",
        "Access-Control-Request-Method": "GET",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.options("/health", headers=headers)
    assert res.headers.get("access-control-allow-origin") is None
