"""Backward compatibility shim.

신규 코드는 app.modules.process.infrastructure.bpm.engine을 직접 import해야 한다.
"""
from app.modules.process.infrastructure.bpm.engine import (  # noqa: F401
    get_initial_activity,
    get_next_activities_after,
)
