"""Backward compatibility shim.

신규 코드는 app.modules.agent.application.agent_service를 직접 import해야 한다.
"""
from app.modules.agent.application.agent_service import (  # noqa: F401
    AgentDomainError,
    AgentService,
    agent_service,
)
