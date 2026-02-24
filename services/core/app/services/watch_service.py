"""Backward compatibility shim.

신규 코드는 app.modules.watch.application.watch_service를 직접 import해야 한다.
"""
from app.modules.watch.application.watch_service import (  # noqa: F401
    WatchDomainError,
    WatchService,
)
