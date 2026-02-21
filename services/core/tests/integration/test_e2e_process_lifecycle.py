import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import engine
from app.main import app
from app.models.base_models import Base


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_process_lifecycle_endpoints():
    headers = {"X-Tenant-Id": "acme-corp"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        create_def_resp = await ac.post(
            "/api/v1/process/definitions",
            json={
                "name": "proc-def-1",
                "description": "a,b,c",
                "source": "natural_language",
                "activities_hint": ["a", "b", "c"],
            },
            headers=headers,
        )
        assert create_def_resp.status_code == 201
        proc_def_id = create_def_resp.json()["proc_def_id"]

        initiate_resp = await ac.post(
            "/api/v1/process/initiate",
            json={
                "proc_def_id": proc_def_id,
                "input_data": {"case_id": "case-1"},
                "role_bindings": [{"role_name": "reviewer", "user_id": "user-1"}],
            },
            headers=headers,
        )
        assert initiate_resp.status_code == 201
        initiate_data = initiate_resp.json()
        proc_inst_id = initiate_data["proc_inst_id"]
        workitem_id = initiate_data["current_workitems"][0]["workitem_id"]

        status_resp = await ac.get(f"/api/v1/process/{proc_inst_id}/status", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "RUNNING"

        workitems_resp = await ac.get(f"/api/v1/process/{proc_inst_id}/workitems", headers=headers)
        assert workitems_resp.status_code == 200
        assert len(workitems_resp.json()["data"]) == 1

        reject_resp = await ac.post(
            "/api/v1/process/approve-hitl",
            json={
                "workitem_id": workitem_id,
                "approved": False,
                "modifications": {"feedback": "needs corrections"},
            },
            headers=headers,
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json()["status"] == "REWORK"

        rework_resp = await ac.post(
            "/api/v1/process/rework",
            json={"workitem_id": workitem_id, "reason": "manual retry"},
            headers=headers,
        )
        assert rework_resp.status_code == 200
        assert rework_resp.json()["status"] == "TODO"

        submit_resp = await ac.post(
            "/api/v1/process/submit",
            json={"workitem_id": workitem_id, "result_data": {"ok": True}, "force_complete": True},
            headers=headers,
        )
        assert submit_resp.status_code == 200
        assert submit_resp.json()["status"] == "DONE"

        final_status_resp = await ac.get(f"/api/v1/process/{proc_inst_id}/status", headers=headers)
        assert final_status_resp.status_code == 200
        assert final_status_resp.json()["status"] == "COMPLETED"
