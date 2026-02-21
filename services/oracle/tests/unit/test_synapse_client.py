import pytest
import httpx

from app.core.synapse_client import SynapseClient


@pytest.mark.asyncio
async def test_search_graph_calls_synapse_with_tenant_and_case(monkeypatch: pytest.MonkeyPatch):
    client = SynapseClient()
    captured = {}

    async def fake_request(method: str, path: str, tenant_id: str = "", **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["tenant_id"] = tenant_id
        captured["json"] = kwargs.get("json")
        return {"success": True, "data": {"tables": {"vector_matched": [{"name": "processes"}], "fk_related": []}}}

    monkeypatch.setattr(client, "_request_with_retry", fake_request)
    data = await client.search_graph("효율성", context={"case_id": "c1"}, tenant_id="t1")

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v3/synapse/graph/search"
    assert captured["tenant_id"] == "t1"
    assert captured["json"]["query"] == "효율성"
    assert captured["json"]["case_id"] == "c1"
    assert data["tables"]["vector_matched"][0]["name"] == "processes"


@pytest.mark.asyncio
async def test_search_graph_fallback_on_synapse_error(monkeypatch: pytest.MonkeyPatch):
    client = SynapseClient()

    async def failing_request(method: str, path: str, tenant_id: str = "", **kwargs):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(client, "_request_with_retry", failing_request)
    data = await client.search_graph("효율성", context={"case_id": "c1"}, tenant_id="t1")

    assert data == {"tables": {"vector_matched": [], "fk_related": []}, "similar_queries": [], "value_mappings": []}
