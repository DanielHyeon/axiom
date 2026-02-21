import logging
from typing import Any


class _CompatLogger:
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def info(self, event: str, **kwargs: Any) -> None:
        self._logger.info("%s %s", event, kwargs if kwargs else "")

    def warning(self, event: str, **kwargs: Any) -> None:
        self._logger.warning("%s %s", event, kwargs if kwargs else "")

    def error(self, event: str, **kwargs: Any) -> None:
        self._logger.error("%s %s", event, kwargs if kwargs else "")

    def exception(self, event: str, **kwargs: Any) -> None:
        self._logger.exception("%s %s", event, kwargs if kwargs else "")


def get_logger(name: str | None = None) -> _CompatLogger:
    logging.basicConfig(level=logging.INFO)
    return _CompatLogger(logging.getLogger(name or "oracle"))
