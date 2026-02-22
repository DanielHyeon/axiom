from app.services.agent_service import AgentService
from app.services.agent_state_store import AgentStateStore


def test_agent_service_persists_feedback_mcp_and_knowledge(tmp_path) -> None:
    db_path = tmp_path / "core-agent-state.db"
    store = AgentStateStore(str(db_path))
    service = AgentService(store=store)
    service.clear()

    tenant_id = "tenant-a"
    service.submit_feedback(
        tenant_id,
        {
            "workitem_id": "wi-100",
            "feedback_type": "suggestion",
            "content": "규칙을 보완해 주세요",
            "priority": "medium",
        },
    )
    service.configure_mcp(
        tenant_id,
        {
            "servers": [
                {
                    "name": "mcp-main",
                    "url": "http://mcp.local",
                    "tool_filter": ["search_records"],
                }
            ]
        },
    )

    restarted = AgentService(store=AgentStateStore(str(db_path)))
    feedback = restarted.get_feedback(tenant_id, "wi-100")
    assert feedback["status"] == "COMPLETED"

    tools = restarted.list_mcp_tools(tenant_id)
    assert tools["total"] == 1

    knowledge = restarted.list_knowledge(tenant_id)
    assert knowledge["total"] == 1
