"""
API 속도 제한 (gateway-api.md §4).
Redis 기반 고정 윈도우 카운터. 경로 패턴별 limit/window 적용.
미들웨어로 전역 적용 시 IP 기준; Depends(check) 사용 시 request.state.user_id 있으면 사용자 기준.
"""
from __future__ import annotations

import json
import logging

from fastapi import Request, HTTPException

from app.core.redis_client import get_redis

logger = logging.getLogger("axiom.core")

# (path_prefix, limit, window_seconds) — 경로 prefix 매칭 순서 유지 (긴 것 먼저)
RULES: list[tuple[str, int, int]] = [
    ("/api/v1/auth/login", 10, 60),   # 10 req/min per key (브루트포스 방지)
    ("/api/v1/completion/", 30, 60),  # 30 req/min
    ("/api/v1/agents/", 20, 60),      # 20 req/min (에이전트 남용 방지)
]
DEFAULT_LIMIT, DEFAULT_WINDOW = 100, 60  # /api/v1/** 기본


def get_rule(path: str) -> tuple[int, int]:
    """경로에 맞는 (limit, window_seconds) 반환. prefix 매칭."""
    match = next((r for r in RULES if path.startswith(r[0])), None)
    return (match[1], match[2]) if match else (DEFAULT_LIMIT, DEFAULT_WINDOW)


def _key_suffix(request: Request) -> str:
    """user_id가 있으면 사용(의존성 주입 후), 없으면 IP."""
    if hasattr(request.state, "user_id") and request.state.user_id:
        return str(request.state.user_id)
    return request.client.host if request.client else "unknown"


async def check(request: Request) -> None:
    """
    속도 제한 확인(의존성). 초과 시 HTTP 429.
    Redis 오류 시 로그만 하고 통과(fail open).
    """
    path = request.url.path
    suffix = _key_suffix(request)
    limit, window = get_rule(path)
    redis_key = f"ratelimit:{path}:{suffix}"

    try:
        redis = get_redis()
        current = await redis.incr(redis_key)
        if current == 1:
            await redis.expire(redis_key, window)
        if current > limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMITED",
                    "message": f"Rate limit exceeded. Max {limit} requests per {window}s.",
                    "retry_after_seconds": window,
                },
                headers={"Retry-After": str(window)},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("rate_limiter check failed (fail open): %s", e)


class RateLimitMiddleware:
    """ASGI 미들웨어: 경로·IP 기준 Redis rate limit. 초과 시 429 응답."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        client = scope.get("client")
        client_host = client[0] if client else "unknown"
        limit, window = get_rule(path)
        redis_key = f"ratelimit:{path}:{client_host}"

        try:
            redis = get_redis()
            current = await redis.incr(redis_key)
            if current == 1:
                await redis.expire(redis_key, window)
            if current > limit:
                body = json.dumps({
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"Rate limit exceeded. Max {limit} requests per {window}s.",
                        "retry_after_seconds": window,
                    }
                }).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", str(window).encode()),
                    ],
                })
                await send({"type": "http.response.body", "body": body})
                return
        except Exception as e:
            logger.warning("rate_limit middleware failed (fail open): %s", e)

        await self.app(scope, receive, send)
