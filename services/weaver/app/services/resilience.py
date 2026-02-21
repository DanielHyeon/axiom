from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class CircuitBreakerOpenError(RuntimeError):
    pass


class SimpleCircuitBreaker:
    def __init__(self, *, failure_threshold: int = 3, reset_timeout_seconds: float = 20.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.failure_count = 0
        self.opened_at: float | None = None

    def preflight(self) -> None:
        if self.opened_at is None:
            return
        if (time.time() - self.opened_at) >= self.reset_timeout_seconds:
            self.failure_count = 0
            self.opened_at = None
            return
        raise CircuitBreakerOpenError("circuit breaker is open")

    def on_success(self) -> None:
        self.failure_count = 0
        self.opened_at = None

    def on_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.opened_at = time.time()


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    retries: int = 2,
    base_delay_seconds: float = 0.05,
) -> T:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= retries:
                break
            await asyncio.sleep(base_delay_seconds * (attempt + 1))
    assert last_exc is not None
    raise last_exc
