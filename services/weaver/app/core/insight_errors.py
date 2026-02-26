from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class InsightError(Exception):
    """Standardized error for Insight View endpoints.

    Attributes:
        retryable: If True, frontend may auto-retry after ``poll_after_ms``.
        hint: Human-readable guidance for recovery.
    """

    status_code: int
    error_code: str
    error_message: str
    retryable: bool = False
    hint: str = ""
    poll_after_ms: int = 0


async def insight_error_handler(request: Request, exc: InsightError) -> JSONResponse:
    """FastAPI exception handler registered on ``InsightError``."""
    trace_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-Id", "")
    body: dict = {
        "error": {
            "code": exc.error_code,
            "message": exc.error_message,
            "retryable": exc.retryable,
            "hint": exc.hint,
        },
        "trace_id": trace_id,
    }
    if exc.poll_after_ms:
        body["poll_after_ms"] = exc.poll_after_ms
    return JSONResponse(status_code=exc.status_code, content=body)
