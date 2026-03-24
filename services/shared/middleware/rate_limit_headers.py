"""Rate Limit 응답 헤더 유틸.

기존 레이트 리미터가 산출한 limit/remaining/reset 값을
표준 HTTP 헤더로 변환하여 응답에 추가한다.

표준 헤더 3종:
- X-RateLimit-Limit     : 윈도우 내 최대 허용 요청 수
- X-RateLimit-Remaining : 윈도우 내 남은 요청 수
- X-RateLimit-Reset     : 윈도우가 초기화되는 Unix 타임스탬프 (초)

429 응답에는 추가로:
- Retry-After            : 다시 요청할 수 있을 때까지 남은 초

사용법 (FastAPI Response):
    from shared.middleware.rate_limit_headers import inject_rate_limit_headers
    inject_rate_limit_headers(response.headers, limit=100, remaining=42, reset_at=1711234567)

사용법 (raw ASGI headers list):
    headers = [(b"content-type", b"application/json")]
    inject_rate_limit_headers(headers, limit=100, remaining=0, reset_at=1711234567, retry_after=30)
"""
from __future__ import annotations

from typing import Union


def inject_rate_limit_headers(
    response_headers: Union[list, "MutableHeaders"],  # noqa: F821
    *,
    limit: int,
    remaining: int,
    reset_at: int,
    retry_after: int | None = None,
) -> None:
    """응답에 X-RateLimit-* 헤더를 추가한다.

    Args:
        response_headers: Starlette MutableHeaders 또는 ASGI raw 헤더 리스트.
            - MutableHeaders이면 딕셔너리처럼 넣는다.
            - list[tuple[bytes, bytes]]이면 튜플을 append한다.
        limit: 윈도우 내 최대 허용 요청 수 (예: 100)
        remaining: 윈도우 내 남은 요청 수 (0 이상으로 클램프됨)
        reset_at: 윈도우가 초기화되는 Unix 타임스탬프 (초 단위 정수)
        retry_after: 429 응답일 때만 설정 — 다시 요청 가능한 시점까지 남은 초.
            None이면 Retry-After 헤더를 추가하지 않는다.
    """
    # remaining이 음수가 되지 않도록 보정한다
    remaining = max(0, remaining)

    if isinstance(response_headers, list):
        # ── raw ASGI 헤더 리스트: list[tuple[bytes, bytes]] ──
        response_headers.append(
            (b"x-ratelimit-limit", str(limit).encode())
        )
        response_headers.append(
            (b"x-ratelimit-remaining", str(remaining).encode())
        )
        response_headers.append(
            (b"x-ratelimit-reset", str(reset_at).encode())
        )
        if retry_after is not None:
            response_headers.append(
                (b"retry-after", str(retry_after).encode())
            )
    else:
        # ── Starlette MutableHeaders (딕셔너리처럼 사용) ──
        response_headers["X-RateLimit-Limit"] = str(limit)
        response_headers["X-RateLimit-Remaining"] = str(remaining)
        response_headers["X-RateLimit-Reset"] = str(reset_at)
        if retry_after is not None:
            response_headers["Retry-After"] = str(retry_after)


def compute_remaining(limit: int, current_count: int) -> int:
    """현재 요청 횟수로부터 남은 요청 수를 계산한다.

    Args:
        limit: 윈도우 내 최대 허용 요청 수
        current_count: 현재까지 사용한 요청 수 (이번 요청 포함)

    Returns:
        남은 요청 수 (0 이상)
    """
    return max(0, limit - current_count)


def compute_reset_at(window_start: float, window_seconds: int) -> int:
    """윈도우 시작 시각과 윈도우 크기로 reset 타임스탬프를 계산한다.

    Args:
        window_start: 윈도우가 시작된 Unix 타임스탬프 (초)
        window_seconds: 윈도우 크기 (초)

    Returns:
        윈도우가 초기화되는 Unix 타임스탬프 (정수, 올림)
    """
    import math
    return math.ceil(window_start + window_seconds)
