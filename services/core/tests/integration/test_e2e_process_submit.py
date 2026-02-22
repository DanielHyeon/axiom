import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app
from app.models.base_models import Base, WorkItem
from app.core.database import engine, AsyncSessionLocal

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_api_submit_workitem_e2e():
    """E2E Test: Hitting the POST /process/submit endpoint."""
    
    # 1. Seed DB with a target WorkItem
    async with AsyncSessionLocal() as session:
        wi = WorkItem(id="e2e-wi-1", status="TODO", tenant_id="acme-corp")
        session.add(wi)
        await session.commit()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        
        # 2. Make the HTTP request
        payload = {
            "item_id": "e2e-wi-1",
            "result_data": {"extracted": True}
        }
        headers = {"X-Tenant-Id": "acme-corp"}
        
        response = await ac.post("/api/v1/process/submit", json=payload, headers=headers)
        
        # 3. Assert Response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "DONE"
        
    # 4. Assert DB state (Router commit success)
    async with AsyncSessionLocal() as session:
        outbox = await session.execute(text("SELECT * FROM event_outbox WHERE aggregate_id = 'e2e-wi-1'"))
        row = outbox.fetchone()
        assert row is not None
        assert getattr(row, "event_type", row[1]) == "WORKITEM_COMPLETED"


@pytest.mark.asyncio
async def test_api_submit_workitem_self_verification_fail_routing():
    async with AsyncSessionLocal() as session:
        wi = WorkItem(id="e2e-wi-sv-1", status="TODO", tenant_id="acme-corp", agent_mode="SELF_VERIFY")
        session.add(wi)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "item_id": "e2e-wi-sv-1",
            "result_data": {
                "extracted": True,
                "self_verification": {"enabled": True, "risk_level": "high", "force_fail": True},
            },
        }
        headers = {"X-Tenant-Id": "acme-corp"}

        response = await ac.post("/api/v1/process/submit", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUBMITTED"
        assert data["self_verification"]["decision"] == "FAIL_ROUTE"

    async with AsyncSessionLocal() as session:
        outbox = await session.execute(
            text("SELECT * FROM event_outbox WHERE aggregate_id = 'e2e-wi-sv-1' ORDER BY created_at DESC LIMIT 1")
        )
        row = outbox.fetchone()
        assert row is not None
        assert getattr(row, "event_type", row[1]) == "WORKITEM_SELF_VERIFICATION_FAILED"
