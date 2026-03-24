"""비동기 Circuit Breaker — 외부 서비스 장애 전파 방지.

회로 차단기 패턴으로 외부 서비스(DB, Redis, 다른 마이크로서비스)가
고장났을 때 우리 서비스까지 같이 느려지거나 죽는 것을 막는다.

3가지 상태:
    CLOSED  (정상) → 실패가 threshold 이상 누적되면 OPEN으로 전환
    OPEN    (차단) → recovery_timeout 후 HALF_OPEN으로 전환
    HALF_OPEN (시험) → 한 번 성공하면 CLOSED, 실패하면 다시 OPEN

사용법:
    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60, name="neo4j")

    try:
        result = await breaker.call(some_async_func, arg1, arg2)
    except CircuitBreakerOpenError:
        # 회로가 열려있어서 호출을 차단했다 → 캐시된 값이나 기본값 사용
        result = fallback_value
"""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger("axiom.circuit_breaker")


class CircuitBreakerOpenError(Exception):
    """회로가 열려있어서(OPEN) 호출을 차단했을 때 발생하는 예외.

    이 예외를 잡아서 폴백(fallback) 로직을 실행하면 된다.
    """

    def __init__(self, name: str, remaining_seconds: float):
        self.name = name
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"CircuitBreaker '{name}' 열림 — "
            f"{remaining_seconds:.1f}초 후 재시도 가능"
        )


class CircuitBreaker:
    """비동기 Circuit Breaker — 외부 서비스 장애 전파 방지.

    timeout -> bounded retry -> breaker -> fallback cache 순서의 보호 체계.
    """

    # --- 3가지 상태 ---
    CLOSED = "closed"       # 정상: 요청을 그대로 통과시킨다
    OPEN = "open"           # 차단: 요청을 즉시 거부한다
    HALF_OPEN = "half_open"  # 시험: 딱 한 번만 통과시켜본다

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        name: str = "default",
    ):
        """
        Args:
            failure_threshold: 연속 실패 몇 번이면 OPEN으로 전환할지 (기본 5번)
            recovery_timeout: OPEN 상태에서 몇 초 뒤에 HALF_OPEN을 시도할지 (기본 60초)
            name: 이 브레이커의 이름 (로그에 표시된다)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name

        # --- 내부 상태 ---
        self._state: str = self.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._success_count: int = 0
        self._total_calls: int = 0

        # HALF_OPEN 상태에서 동시에 여러 요청이 들어오는 것을 막는 잠금
        self._half_open_lock = asyncio.Lock()

    def _evaluate_state(self) -> str:
        """현재 상태를 평가한다. OPEN이면서 시간이 지났으면 HALF_OPEN으로 전환."""
        if self._state == self.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = self.HALF_OPEN
                logger.info(
                    "CircuitBreaker '%s': OPEN -> HALF_OPEN (%.1f초 경과)",
                    self.name,
                    elapsed,
                )
        return self._state

    @property
    def state(self) -> str:
        """현재 상태를 반환한다 (모니터링용)."""
        return self._evaluate_state()

    async def call(self, func, *args, **kwargs):
        """보호된 함수 호출. OPEN 상태면 CircuitBreakerOpenError 발생.

        상태 전환과 HALF_OPEN 진입을 단일 Lock으로 보호하여
        동시 요청 간 race condition을 방지한다.

        Args:
            func: 호출할 비동기 함수 (코루틴)
            *args, **kwargs: 함수에 전달할 인자

        Returns:
            func의 반환값

        Raises:
            CircuitBreakerOpenError: 회로가 열려있을 때
            Exception: func에서 발생한 원래 예외 (CLOSED/HALF_OPEN 상태에서)
        """
        self._total_calls += 1

        # Lock 안에서 상태 평가 + HALF_OPEN 진입을 원자적으로 처리
        async with self._half_open_lock:
            current_state = self._evaluate_state()

            # --- OPEN 상태: 즉시 거부 ---
            if current_state == self.OPEN:
                remaining = self.recovery_timeout - (
                    time.monotonic() - self._last_failure_time
                )
                logger.warning(
                    "CircuitBreaker '%s': 요청 차단 (OPEN, %.1f초 남음)",
                    self.name,
                    max(0, remaining),
                )
                raise CircuitBreakerOpenError(self.name, max(0, remaining))

            # --- HALF_OPEN 상태: Lock 안에서 한 번만 실행 ---
            if current_state == self.HALF_OPEN:
                return await self._execute(func, *args, **kwargs)

        # --- CLOSED 상태: Lock 밖에서 정상 통과 (동시성 허용) ---
        return await self._execute(func, *args, **kwargs)

    async def _execute(self, func, *args, **kwargs):
        """실제로 함수를 호출하고 성공/실패를 기록한다."""
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure(exc)
            raise

    def _on_success(self):
        """호출 성공 시: 실패 카운터를 초기화하고 CLOSED로 전환한다."""
        previous_state = self._state
        self._failure_count = 0
        self._state = self.CLOSED
        self._success_count += 1

        if previous_state != self.CLOSED:
            logger.info(
                "CircuitBreaker '%s': %s -> CLOSED (성공)",
                self.name,
                previous_state,
            )

    def _on_failure(self, exc: Exception):
        """호출 실패 시: 실패 카운터를 올리고 threshold에 도달하면 OPEN으로 전환."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        logger.warning(
            "CircuitBreaker '%s': 실패 %d/%d — %s",
            self.name,
            self._failure_count,
            self.failure_threshold,
            str(exc)[:200],
        )

        # HALF_OPEN에서 실패하면 바로 OPEN으로
        if self._state == self.HALF_OPEN:
            self._state = self.OPEN
            logger.warning(
                "CircuitBreaker '%s': HALF_OPEN -> OPEN (시험 호출 실패)",
                self.name,
            )
            return

        # CLOSED에서 threshold에 도달하면 OPEN으로
        if self._failure_count >= self.failure_threshold:
            self._state = self.OPEN
            logger.error(
                "CircuitBreaker '%s': CLOSED -> OPEN "
                "(연속 실패 %d회 — %.0f초간 차단)",
                self.name,
                self._failure_count,
                self.recovery_timeout,
            )

    def reset(self):
        """수동으로 브레이커를 초기화한다 (운영 중 긴급 복구용)."""
        self._state = self.CLOSED
        self._failure_count = 0
        logger.info("CircuitBreaker '%s': 수동 리셋 -> CLOSED", self.name)

    def get_state(self) -> dict:
        """현재 상태를 딕셔너리로 반환한다 (모니터링/API 응답용).

        예: {"name": "neo4j", "state": "closed", "failure_count": 0, ...}
        """
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_sec": self.recovery_timeout,
            "success_count": self._success_count,
            "total_calls": self._total_calls,
        }
