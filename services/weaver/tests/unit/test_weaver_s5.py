import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_api_weaver_readiness_probe_returns_up():
    res = client.get("/health/ready")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"
    assert res.json()["dependencies"]["neo4j"] == "up"

@pytest.mark.asyncio
async def test_weaver_dataflow_chunks_accurately():
    from app.core.data_flow import DataFlowManager
    manager = DataFlowManager(chunk_size=1000)
    
    # 2500 records should equate to precisely 3 chunks to secure memory thresholds
    res = await manager.extract_and_stream("session_abc", total_records=2500)
    assert res["chunks_yielded"] == 3
    assert res["max_memory_bound_enforced"] is True
