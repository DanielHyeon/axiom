from __future__ import annotations

import time
from typing import Dict

from fastapi import HTTPException, status


class RateLimitExceeded(Exception):
    """Rate limit 초과 시 사용. 429 + Retry-After 헤더로 변환."""

    def __init__(self, retry_after_seconds: int, detail: dict | None = None):
        self.retry_after_seconds = retry_after_seconds
        self.detail = detail or {
            "code": "RATE_LIMITED",
            "message": "rate limit exceeded",
            "retry_after_seconds": retry_after_seconds,
        }


class InMemoryRateLimiter:
    """
    간단한 인메모리 rate limiter (프로세스 단위).
    key 단위로 60초 윈도우 내 호출 횟수를 제한한다.
    사용자별: text2sql-api.md §5.3 — /ask 30/분, /react 10/분, /direct-sql 60/분.
    """

    def __init__(self) -> None:
        self._windows: Dict[str, Dict[str, float | int]] = {}

    def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.time()
        window = self._windows.get(key) or {"start": now, "count": 0}
        if now - float(window["start"]) >= window_seconds:
            window = {"start": now, "count": 0}
        count = int(window["count"]) + 1
        window["count"] = count
        self._windows[key] = window
        if count > limit:
            retry_after = max(1, window_seconds - int(now - float(window["start"])))
            raise RateLimitExceeded(
                retry_after_seconds=retry_after,
                detail={
                    "code": "RATE_LIMITED",
                    "message": "rate limit exceeded",
                    "retry_after_seconds": retry_after,
                },
            )


rate_limiter = InMemoryRateLimiter()

