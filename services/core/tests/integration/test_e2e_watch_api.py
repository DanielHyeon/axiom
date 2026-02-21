from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from starlette.responses import StreamingResponse

from app.core.database import get_session
from app.main import app
from app.api.watch import routes as watch_routes
from app.services.watch_service import WatchService


@pytest_asyncio.fixture
async def ac():
    class DummySession:
        async def commit(self):
            return None

        async def rollback(self):
            return None

    async def override_session():
        yield DummySession()

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_watch_alerts_and_subscriptions(ac: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    headers = {"X-Tenant-Id": "acme-corp"}

    sub_obj = type("Sub", (), {"id": "sub-1", "event_type": "DEADLINE_APPROACHING", "case_id": None, "channels": ["in_app"], "active": True, "created_at": None, "rule": {"type": "deadline", "days_before": 7}, "severity_override": None})
    rule_obj = type("Rule", (), {"id": "rule-1", "name": "critical-cash", "event_type": "CASH_LOW", "active": True})
    rule_detail_obj = type(
        "RuleDetail",
        (),
        {
            "id": "rule-1",
            "name": "critical-cash",
            "event_type": "CASH_LOW",
            "active": True,
            "definition": {"type": "threshold", "field": "cash_ratio", "operator": "lt", "threshold": 0.1},
            "created_at": None,
            "updated_at": None,
        },
    )

    monkeypatch.setattr(WatchService, "create_subscription", AsyncMock(return_value=sub_obj))
    monkeypatch.setattr(WatchService, "list_subscriptions", AsyncMock(return_value=[sub_obj]))
    monkeypatch.setattr(
        WatchService,
        "list_alerts",
        AsyncMock(
            return_value={
                "data": [
                    {"alert_id": "alert-1", "status": "unread", "severity": "HIGH", "message": "deadline", "event_type": "DEADLINE_APPROACHING", "case_id": None, "case_name": None, "triggered_at": None, "action_url": None, "metadata": {}},
                    {"alert_id": "alert-2", "status": "unread", "severity": "CRITICAL", "message": "cash low", "event_type": "CASH_LOW", "case_id": None, "case_name": None, "triggered_at": None, "action_url": None, "metadata": {}},
                ],
                "cursor": {"next": None, "has_more": False},
                "summary": {"total_unread": 2, "critical_count": 1, "high_count": 1},
            }
        ),
    )
    monkeypatch.setattr(WatchService, "acknowledge_alert", AsyncMock(return_value={"alert_id": "alert-1", "status": "acknowledged"}))
    monkeypatch.setattr(WatchService, "dismiss_alert", AsyncMock(return_value={"alert_id": "alert-2", "status": "dismissed"}))
    monkeypatch.setattr(WatchService, "read_all_alerts", AsyncMock(return_value={"acknowledged_count": 0, "message": "0 alerts marked as read"}))
    monkeypatch.setattr(WatchService, "create_rule", AsyncMock(return_value=rule_obj))
    monkeypatch.setattr(WatchService, "list_rules", AsyncMock(return_value=[rule_obj]))
    monkeypatch.setattr(WatchService, "get_rule", AsyncMock(return_value=rule_detail_obj))
    monkeypatch.setattr(WatchService, "update_rule", AsyncMock(return_value=rule_detail_obj))
    monkeypatch.setattr(WatchService, "delete_rule", AsyncMock(return_value=None))

    create_sub = await ac.post(
        "/api/v1/watches/subscriptions",
        json={"user_id": "user-1", "event_type": "DEADLINE_APPROACHING", "channels": ["in_app"]},
        headers=headers,
    )
    assert create_sub.status_code == 201
    assert create_sub.json()["subscription_id"] == "sub-1"

    list_sub = await ac.get("/api/v1/watches/subscriptions", params={"user_id": "user-1"}, headers=headers)
    assert list_sub.status_code == 200
    assert len(list_sub.json()["data"]) == 1

    list_alerts = await ac.get("/api/v1/watches/alerts", headers=headers)
    assert list_alerts.status_code == 200
    assert len(list_alerts.json()["data"]) == 2
    assert list_alerts.json()["summary"]["total_unread"] == 2

    ack = await ac.put("/api/v1/watches/alerts/alert-1/acknowledge", headers=headers)
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"

    dismiss = await ac.put("/api/v1/watches/alerts/alert-2/dismiss", headers=headers)
    assert dismiss.status_code == 200
    assert dismiss.json()["status"] == "dismissed"

    read_all = await ac.put("/api/v1/watches/alerts/read-all", headers=headers)
    assert read_all.status_code == 200
    assert read_all.json()["acknowledged_count"] == 0

    create_rule = await ac.post(
        "/api/v1/watches/rules",
        json={
            "name": "critical-cash",
            "event_type": "CASH_LOW",
            "definition": {"type": "threshold", "field": "cash_ratio", "operator": "<", "threshold": 0.1},
        },
        headers=headers,
    )
    assert create_rule.status_code == 200

    list_rules = await ac.get("/api/v1/watches/rules", headers=headers)
    assert list_rules.status_code == 200
    assert len(list_rules.json()["data"]) == 1

    rule_detail = await ac.get("/api/v1/watches/rules/rule-1", headers=headers)
    assert rule_detail.status_code == 200
    assert rule_detail.json()["rule_id"] == "rule-1"

    update_rule = await ac.put(
        "/api/v1/watches/rules/rule-1",
        json={"name": "critical-cash-v2", "active": True},
        headers=headers,
    )
    assert update_rule.status_code == 200
    assert update_rule.json()["rule_id"] == "rule-1"

    delete_rule = await ac.delete("/api/v1/watches/rules/rule-1", headers=headers)
    assert delete_rule.status_code == 200
    assert delete_rule.json()["deleted"] is True

    scheduler_start = await ac.post("/api/v1/watches/scheduler/start", headers=headers)
    assert scheduler_start.status_code == 200
    assert scheduler_start.json()["running"] is True

    scheduler_status = await ac.get("/api/v1/watches/scheduler/status", headers=headers)
    assert scheduler_status.status_code == 200
    assert "running" in scheduler_status.json()

    scheduler_stop = await ac.post("/api/v1/watches/scheduler/stop", headers=headers)
    assert scheduler_stop.status_code == 200
    assert scheduler_stop.json()["running"] is False


@pytest.mark.asyncio
async def test_watch_stream_requires_token(ac: AsyncClient):
    res = await ac.get("/api/v1/watches/stream", headers={"X-Tenant-Id": "acme-corp"})
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_watch_stream_contract(ac: AsyncClient):
    scope = {"type": "http", "method": "GET", "path": "/api/v1/watches/stream", "headers": []}
    req = Request(scope)
    res = await watch_routes.watch_stream(request=req, token="test-token")
    assert isinstance(res, StreamingResponse)
    assert res.media_type == "text/event-stream"
    assert watch_routes._HEARTBEAT_INTERVAL_SECONDS == 30
