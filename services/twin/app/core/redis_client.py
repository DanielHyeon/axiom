"""Twin 서비스 Redis 클라이언트."""
import redis.asyncio as aioredis
from app.core.config import settings

_redis = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis
