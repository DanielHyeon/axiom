"""API 레이트 리미터 -- 슬라이딩 윈도우 기반 요청 제한.

LLM 호출이 포함된 엔드포인트의 과도한 사용을 방지한다.
테넌트별로 분당 요청 수를 제한한다.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass

from fastapi import HTTPException, Request
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RateLimitConfig:
    """레이트 리밋 설정."""
    max_requests: int = 30      # 윈도우당 최대 요청 수
    window_seconds: int = 60    # 윈도우 크기 (초)


class SlidingWindowRateLimiter:
    """슬라이딩 윈도우 레이트 리미터.

    테넌트 ID별로 요청 타임스탬프를 추적하여
    윈도우 내 요청 수가 한계를 초과하면 429를 반환한다.
    """

    def __init__(self) -> None:
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, key: str, config: RateLimitConfig) -> None:
        """요청을 허용할지 검사한다. 초과 시 HTTPException(429) 발생."""
        now = time.monotonic()
        cutoff = now - config.window_seconds

        async with self._lock:
            # 만료된 타임스탬프 제거
            window = self._windows[key]
            self._windows[key] = [t for t in window if t > cutoff]
            window = self._windows[key]

            # 빈 윈도우 정리 — 메모리 누수 방지
            if not window:
                del self._windows[key]
                self._windows[key] = []
                window = self._windows[key]

            if len(window) >= config.max_requests:
                retry_after = int(config.window_seconds - (now - window[0])) + 1
                logger.warning(
                    "rate_limit_exceeded",
                    key=key,
                    limit=config.max_requests,
                    window=config.window_seconds,
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"요청 한도 초과: {config.max_requests}회/{config.window_seconds}초. {retry_after}초 후 재시도하세요.",
                    headers={"Retry-After": str(retry_after)},
                )

            # 현재 요청 타임스탬프 기록
            window.append(now)

    def get_remaining(self, key: str, config: RateLimitConfig) -> int:
        """남은 요청 가능 횟수를 반환한다."""
        now = time.monotonic()
        cutoff = now - config.window_seconds
        window = [t for t in self._windows.get(key, []) if t > cutoff]
        return max(0, config.max_requests - len(window))


# 모듈 레벨 싱글톤 -- 서비스 전체에서 공유
_limiter = SlidingWindowRateLimiter()

# --- 엔드포인트별 설정 ------------------------------------------------

# AI 큐브 생성 / DDL 생성 -- 분당 10회
AI_GENERATION_LIMIT = RateLimitConfig(max_requests=10, window_seconds=60)

# NL2SQL 실행 -- 분당 20회
NL2SQL_LIMIT = RateLimitConfig(max_requests=20, window_seconds=60)

# 피벗 실행 -- 분당 60회
PIVOT_LIMIT = RateLimitConfig(max_requests=60, window_seconds=60)

# Airflow 트리거 -- 분당 5회
AIRFLOW_TRIGGER_LIMIT = RateLimitConfig(max_requests=5, window_seconds=60)


async def check_rate_limit(request: Request, config: RateLimitConfig) -> None:
    """요청의 테넌트 ID를 키로 레이트 리밋을 검사한다."""
    tenant_id = getattr(getattr(request, "state", None), "tenant_id", "anonymous")
    endpoint = request.url.path
    key = f"{tenant_id}:{endpoint}"
    await _limiter.check(key, config)
