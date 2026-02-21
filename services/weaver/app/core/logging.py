from __future__ import annotations

import logging
import re
from typing import Any

_SENSITIVE_KEYS = {"password", "pwd", "token", "secret", "authorization"}
_VALUE_PATTERN = re.compile(r'(?i)("?(?:password|pwd|token|secret|authorization)"?\s*[:=]\s*)(".*?"|\'.*?\'|[^\s,}\]]+)')


def _redact_text(value: str) -> str:
    return _VALUE_PATTERN.sub(r'\1"***REDACTED***"', value)


def redact_secrets(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                out[key] = "***REDACTED***"
            else:
                out[key] = redact_secrets(item)
        return out
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_secrets(record.msg)
        if record.args:
            record.args = redact_secrets(record.args)
        return True


def configure_secret_redaction() -> None:
    loggers = [
        logging.getLogger(),
        logging.getLogger("weaver"),
        logging.getLogger("uvicorn"),
        logging.getLogger("uvicorn.error"),
        logging.getLogger("uvicorn.access"),
    ]
    for logger in loggers:
        if any(isinstance(x, SecretRedactionFilter) for x in logger.filters):
            continue
        logger.addFilter(SecretRedactionFilter())
