"""Backward compatibility shim.

신규 코드는 app.modules.process.api.routes를 직접 import해야 한다.
"""
from app.modules.process.api.routes import router  # noqa: F401
