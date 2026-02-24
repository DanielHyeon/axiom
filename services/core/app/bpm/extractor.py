"""Backward compatibility shim.

신규 코드는 app.modules.process.infrastructure.bpm.extractor를 직접 import해야 한다.
"""
from app.modules.process.infrastructure.bpm.extractor import *  # noqa: F401, F403
