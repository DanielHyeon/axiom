import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

from tests.unit.conftest import make_admin_token


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def _admin_headers():
    return {"Authorization": f"Bearer {make_admin_token()}"}


@pytest.mark.asyncio
async def test_events_rules_crud_and_scheduler(monkeypatch, ac: AsyncClient):
    import app.api.events as events_api

    async def fake_core_request(method, path, user, params=None, json_body=None):
        if method == "POST" and path == "/watches/rules":
            return {"rule_id": "r1"}
        if method == "GET" and path == "/watches/rules":
            return {"data": [{"rule_id": "r1", "name": "n1", "event_type": "THRESHOLD_ALERT", "active": True}]}
        if method == "GET" and path == "/watches/rules/r1":
            return {"rule_id": "r1", "name": "n1", "event_type": "THRESHOLD_ALERT", "active": True}
        if method == "PUT" and path == "/watches/rules/r1":
            return {"rule_id": "r1", "name": "n2", "event_type": "THRESHOLD_ALERT", "active": True}
        if method == "DELETE" and path == "/watches/rules/r1":
            return {"deleted": True}
        if method == "POST" and path == "/watches/scheduler/start":
            return {"running": True}
        if method == "POST" and path == "/watches/scheduler/stop":
            return {"running": False}
        if method == "GET" and path == "/watches/scheduler/status":
            return {"running": False}
        raise AssertionError(f"unexpected call: {method} {path}")

    monkeypatch.setattr(events_api, "_core_request", fake_core_request)

    create_payload = {
        "name": "rule-1",
        "event_type": "THRESHOLD_ALERT",
        "datasource_id": "ds_business_main",
        "sql": "SELECT 1",
        "schedule": {"type": "interval", "value": "1h"},
        "condition": {"type": "threshold", "operator": "gt", "threshold": 0},
        "actions": [{"type": "notification", "channel": "sse", "template": "x"}],
        "enabled": True,
    }
    create_res = await ac.post("/text2sql/events/rules", json=create_payload, headers=_admin_headers())
    assert create_res.status_code == 200
    assert create_res.json()["data"]["rule_id"] == "r1"

    list_res = await ac.get("/text2sql/events/rules", headers=_admin_headers())
    assert list_res.status_code == 200
    assert list_res.json()["data"]["total"] == 1

    get_res = await ac.get("/text2sql/events/rules/r1", headers=_admin_headers())
    assert get_res.status_code == 200
    assert get_res.json()["data"]["rule_id"] == "r1"

    update_res = await ac.put("/text2sql/events/rules/r1", json=create_payload, headers=_admin_headers())
    assert update_res.status_code == 200
    assert update_res.json()["data"]["name"] == "n2"

    delete_res = await ac.delete("/text2sql/events/rules/r1", headers=_admin_headers())
    assert delete_res.status_code == 200
    assert delete_res.json()["data"]["deleted"] is True

    start_res = await ac.post("/text2sql/events/scheduler/start", headers=_admin_headers())
    assert start_res.status_code == 200
    assert start_res.json()["data"]["running"] is True

    stop_res = await ac.post("/text2sql/events/scheduler/stop", headers=_admin_headers())
    assert stop_res.status_code == 200
    assert stop_res.json()["data"]["running"] is False

    status_res = await ac.get("/text2sql/events/scheduler/status", headers=_admin_headers())
    assert status_res.status_code == 200
    assert status_res.json()["data"]["running"] is False


@pytest.mark.asyncio
async def test_events_watch_agent_chat(monkeypatch, ac: AsyncClient):
    import app.api.events as events_api

    async def fake_core_request(method, path, user, params=None, json_body=None):
        assert method == "POST"
        assert path == "/agents/chat"
        return {"response": "감시 룰 등록안을 생성했습니다."}

    monkeypatch.setattr(events_api, "_core_request", fake_core_request)
    payload = {
        "message": "매출이 10% 이상 하락하면 알려줘",
        "datasource_id": "ds_business_main",
        "session_id": "watch-session-1",
    }
    res = await ac.post("/text2sql/watch-agent/chat", json=payload, headers=_admin_headers())
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["session_id"] == "watch-session-1"
    assert body["data"]["proposed_rule"]["datasource_id"] == "ds_business_main"
    assert body["data"]["proposed_rule"]["schedule"]["value"] == "1h"
    assert body["data"]["proposed_rule"]["condition"]["type"] in {"row_count", "threshold"}


@pytest.mark.asyncio
async def test_events_stream_alarms_forwards_token(monkeypatch, ac: AsyncClient):
    import app.api.events as events_api

    captured = {}

    class DummyStreamResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield "event: heartbeat"
            yield 'data: {"timestamp":"2026-02-22T00:00:00Z"}'
            return

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, headers=None, params=None):
            captured["method"] = method
            captured["url"] = url
            captured["params"] = params or {}
            return DummyStreamResponse()

    monkeypatch.setattr(events_api.httpx, "AsyncClient", DummyClient)
    res = await ac.get("/text2sql/events/stream/alarms", params={"token": "sse-token"}, headers=_admin_headers())
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert captured["method"] == "GET"
    assert captured["params"]["token"] == "sse-token"
