"""Backward compatibility shim.

신규 코드는 app.modules.agent.infrastructure.state.agent_state_store를 직접 import해야 한다.
"""
from app.modules.agent.infrastructure.state.agent_state_store import (  # noqa: F401
    AgentStateStore,
)
