"""Backward compatibility shim.

신규 코드는 app.modules.process.application.role_binding_service를 직접 import해야 한다.
"""
from app.modules.process.application.role_binding_service import (  # noqa: F401
    ProcessDomainError,
    RoleBindingService,
)
