from __future__ import annotations

from fastapi import HTTPException
from app.core.logging import redact_secrets


def public_error_message(message: object) -> str:
    candidate: object = str(message) if isinstance(message, BaseException) else message
    redacted = redact_secrets(candidate)
    return redacted if isinstance(redacted, str) else str(redacted)


def external_service_http_exception(
    *,
    service: str,
    code: str,
    message: str,
    status_code: int = 503,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "service": service,
            "message": public_error_message(message),
        },
    )
