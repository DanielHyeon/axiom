import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import AsyncSessionLocal, engine
from app.main import app
from app.models.base_models import Base, WatchAlert


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_watch_alerts_and_subscriptions():
    headers = {"X-Tenant-Id": "acme-corp"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        create_sub = await ac.post(
            "/api/v1/watches/subscriptions",
            json={"user_id": "user-1", "event_type": "DEADLINE_APPROACHING", "channels": ["in_app"]},
            headers=headers,
        )
        assert create_sub.status_code == 200
        subscription_id = create_sub.json()["subscription_id"]

        list_sub = await ac.get("/api/v1/watches/subscriptions", params={"user_id": "user-1"}, headers=headers)
        assert list_sub.status_code == 200
        assert len(list_sub.json()["data"]) == 1

        async with AsyncSessionLocal() as session:
            session.add(
                WatchAlert(
                    id="alert-1",
                    subscription_id=subscription_id,
                    event_type="DEADLINE_APPROACHING",
                    severity="HIGH",
                    message="deadline in 1 day",
                    status="unread",
                    meta={"remaining_days": 1},
                    tenant_id="acme-corp",
                )
            )
            session.add(
                WatchAlert(
                    id="alert-2",
                    subscription_id=subscription_id,
                    event_type="CASH_LOW",
                    severity="CRITICAL",
                    message="cash low",
                    status="unread",
                    meta={"cash_ratio": 0.04},
                    tenant_id="acme-corp",
                )
            )
            await session.commit()

        list_alerts = await ac.get("/api/v1/watches/alerts", headers=headers)
        assert list_alerts.status_code == 200
        assert len(list_alerts.json()["data"]) == 2
        assert list_alerts.json()["summary"]["total_unread"] == 2

        ack = await ac.put("/api/v1/watches/alerts/alert-1/acknowledge", headers=headers)
        assert ack.status_code == 200
        assert ack.json()["status"] == "acknowledged"

        read_all = await ac.put("/api/v1/watches/alerts/read-all", headers=headers)
        assert read_all.status_code == 200
        assert read_all.json()["acknowledged_count"] == 1

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
