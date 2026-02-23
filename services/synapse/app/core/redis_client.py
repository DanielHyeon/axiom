"""Optional Redis client for ontology ingest event consumer (Phase S7)."""
from __future__ import annotations

import redis.asyncio as redis

from app.core.config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    """Returns Redis client when REDIS_URL is set; otherwise None (consumer disabled)."""
    global _client
    if not (getattr(settings, "REDIS_URL", None) or "").strip():
        return None
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
