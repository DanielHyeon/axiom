"""Async Redis client for Insight View (optional, graceful fallback).

Follows the same optional-import pattern as ``request_guard.py`` but uses
``redis.asyncio`` for non-blocking operations in FastAPI async endpoints.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

try:
    import redis.asyncio as aioredis
except Exception:  # pragma: no cover
    aioredis = None  # type: ignore[assignment]

logger = logging.getLogger("weaver.insight_redis")

_client: Any | None = None
_initialised: bool = False


async def get_insight_redis() -> Any | None:
    """Return a shared async Redis client, or *None* if unavailable.

    First call creates and pings the connection.  Subsequent calls return
    the cached client (or *None* if the first attempt failed).
    """
    global _client, _initialised

    if _initialised:
        return _client

    _initialised = True

    if aioredis is None:
        logger.warning("redis.asyncio not available; insight Redis features disabled")
        return None

    try:
        _client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
        await _client.ping()
        logger.info("Insight Redis connected: %s", settings.redis_url)
        return _client
    except Exception as exc:
        logger.warning("Insight Redis unavailable (non-fatal): %s", exc)
        _client = None
        return None


async def close_insight_redis() -> None:
    """Gracefully close the Redis connection on shutdown."""
    global _client, _initialised
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:
            pass
    _client = None
    _initialised = False
