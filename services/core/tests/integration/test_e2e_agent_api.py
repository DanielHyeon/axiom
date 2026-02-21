import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.services.agent_service import agent_service


@pytest_asyncio.fixture(autouse=True)
async def reset_state():
    agent_service.clear()
    yield
    agent_service.clear()


@pytest.mark.asyncio
async def test_agent_feedback_mcp_and_knowledge_flow(monkeypatch: pytest.MonkeyPatch):
    headers = {"X-Tenant-Id": "acme-corp"}

    class DummyResponse:
        status_code = 200
        content = b'{"result":{"ok":true}}'

        @staticmethod
        def json():
            return {"result": {"ok": True}, "cached": False}

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: DummyResponse())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        feedback = await ac.post(
            "/api/v1/agents/feedback",
            json={
                "workitem_id": "wi-1",
                "feedback_type": "suggestion",
                "content": "이 데이터는 일반 데이터입니다",
            },
            headers=headers,
        )
        assert feedback.status_code == 202

        feedback_status = await ac.get("/api/v1/agents/feedback/wi-1", headers=headers)
        assert feedback_status.status_code == 200
        assert feedback_status.json()["status"] == "COMPLETED"

        mcp = await ac.post(
            "/api/v1/mcp/config",
            json={
                "servers": [
                    {
                        "name": "axiom-skills",
                        "url": "http://mcp-skills:8080",
                        "tool_filter": ["search_records", "calculate_optimization_rate"],
                    }
                ]
            },
            headers=headers,
        )
        assert mcp.status_code == 200
        assert mcp.json()["servers_count"] == 1

        tools = await ac.get("/api/v1/mcp/tools", headers=headers)
        assert tools.status_code == 200
        assert tools.json()["total"] == 2

        execute = await ac.post(
            "/api/v1/mcp/execute-tool",
            json={"tool_name": "search_records", "parameters": {"case_id": "c1"}},
            headers=headers,
        )
        assert execute.status_code == 200
        assert execute.json()["result"]["ok"] is True

        completion = await ac.post(
            "/api/v1/completion/complete",
            json={"prompt": "요약해줘"},
            headers=headers,
        )
        assert completion.status_code == 200
        assert "usage" in completion.json()

        chat = await ac.post(
            "/api/v1/agents/chat",
            json={"message": "상태 알려줘", "stream": False},
            headers=headers,
        )
        assert chat.status_code == 200
        assert "response" in chat.json()

        stream_chat = await ac.post(
            "/api/v1/agents/chat",
            json={"message": "스트리밍으로 알려줘", "stream": True},
            headers=headers,
        )
        assert stream_chat.status_code == 200
        assert "data:" in stream_chat.text

        knowledge = await ac.get("/api/v1/agents/knowledge", headers=headers)
        assert knowledge.status_code == 200
        assert knowledge.json()["total"] >= 1
        knowledge_id = knowledge.json()["data"][0]["id"]

        deleted = await ac.delete(f"/api/v1/agents/knowledge/{knowledge_id}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True


@pytest.mark.asyncio
async def test_agent_external_error_mapping(monkeypatch: pytest.MonkeyPatch):
    headers = {"X-Tenant-Id": "acme-corp"}
    old_llm_url = settings.LLM_COMPLETION_URL
    try:
        settings.LLM_COMPLETION_URL = "http://llm.local/complete"

        def raise_timeout(*args, **kwargs):
            raise httpx.TimeoutException("timeout")

        monkeypatch.setattr(httpx, "post", raise_timeout)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            llm = await ac.post("/api/v1/completion/complete", json={"prompt": "hello"}, headers=headers)
            assert llm.status_code == 408
            assert llm.json()["detail"]["code"] == "AGENT_TIMEOUT"

            configured = await ac.post(
                "/api/v1/mcp/config",
                json={
                    "servers": [
                        {
                            "name": "external-mcp",
                            "url": "http://mcp.local",
                            "tool_filter": ["search_records"],
                        }
                    ]
                },
                headers=headers,
            )
            assert configured.status_code == 200
            mcp = await ac.post(
                "/api/v1/mcp/execute-tool",
                json={"tool_name": "search_records", "parameters": {"q": "x"}, "server_name": "external-mcp"},
                headers=headers,
            )
            assert mcp.status_code == 408
            assert mcp.json()["detail"]["code"] == "AGENT_TIMEOUT"
    finally:
        settings.LLM_COMPLETION_URL = old_llm_url


@pytest.mark.asyncio
async def test_agent_feedback_conflict_and_mcp_auth_validation():
    headers = {"X-Tenant-Id": "acme-corp"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        conflict = await ac.post(
            "/api/v1/agents/feedback",
            json={
                "workitem_id": "wi-2",
                "feedback_type": "correction",
                "content": "이 규칙은 전면 수정이 필요합니다",
                "corrected_output": {"field_name": "risk", "corrected_value": "high"},
                "priority": "high",
            },
            headers=headers,
        )
        assert conflict.status_code == 422
        assert conflict.json()["detail"]["code"] == "KNOWLEDGE_CONFLICT_HIGH"
        conflict_status = await ac.get("/api/v1/agents/feedback/wi-2", headers=headers)
        assert conflict_status.status_code == 200
        assert conflict_status.json()["status"] == "NEEDS_REVIEW"
        assert conflict_status.json()["analysis"]["conflict_level"] == "HIGH"

        invalid_auth = await ac.post(
            "/api/v1/mcp/config",
            json={
                "servers": [
                    {
                        "name": "ext",
                        "url": "http://mcp.local",
                        "auth": {"type": "bearer"},
                    }
                ]
            },
            headers=headers,
        )
        assert invalid_auth.status_code == 400
        assert invalid_auth.json()["detail"]["code"] == "INVALID_REQUEST"
