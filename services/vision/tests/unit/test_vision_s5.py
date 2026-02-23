import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_api_vision_readiness_probe_returns_up():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health/ready")
        assert res.status_code == 200
        assert res.json()["status"] == "ready"
        assert res.json()["dependencies"]["synapse"] == "up"

@pytest.mark.asyncio
async def test_scenario_solver_detects_cost_regressions():
    from app.engines.scenario_solver import scenario_solver
    
    mods = [{"metric": "Marketing_Cost", "adjustment": "+50%"}]
    res = await scenario_solver.evaluate_what_if("cache_hash_999", modifications=mods)
    
    assert res["solver_status"] == "complete"
    assert len(res["regressions"]) == 1
    assert "Operating margin contraction" in res["regressions"][0]
