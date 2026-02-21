import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.config import settings


@pytest.fixture(autouse=True)
def _restore_readiness_settings():
    old_external = settings.external_mode
    old_pg = settings.metadata_pg_mode
    old_neo4j = settings.metadata_external_mode
    try:
        yield
    finally:
        settings.external_mode = old_external
        settings.metadata_pg_mode = old_pg
        settings.metadata_external_mode = old_neo4j


@pytest.mark.asyncio
async def test_api_weaver_readiness_probe_returns_up():
    settings.external_mode = False
    settings.metadata_pg_mode = False
    settings.metadata_external_mode = False
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health/ready")
        assert res.status_code == 200
        assert res.json()["status"] == "ready"
        assert res.json()["dependencies"]["neo4j"] == "disabled"
        assert res.json()["dependencies"]["mindsdb"] == "disabled"
        assert res.json()["dependencies"]["postgres"] == "disabled"


@pytest.mark.asyncio
async def test_api_weaver_readiness_probe_returns_503_when_enabled_dependency_down(monkeypatch: pytest.MonkeyPatch):
    settings.external_mode = True
    settings.metadata_pg_mode = False
    settings.metadata_external_mode = False

    async def _down() -> dict[str, object]:
        raise RuntimeError("mindsdb unavailable")

    monkeypatch.setattr("app.main.mindsdb_client.health_check", _down)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health/ready")
        assert res.status_code == 503
        assert res.json()["status"] == "degraded"
        assert res.json()["dependencies"]["mindsdb"] == "down"


@pytest.mark.asyncio
async def test_api_weaver_readiness_probe_redacts_sensitive_error_details(monkeypatch: pytest.MonkeyPatch):
    settings.external_mode = True
    settings.metadata_pg_mode = False
    settings.metadata_external_mode = False

    async def _down() -> dict[str, object]:
        raise RuntimeError('auth failed password="super-secret" token=topsecret')

    monkeypatch.setattr("app.main.mindsdb_client.health_check", _down)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health/ready")
        assert res.status_code == 503
        detail = res.json()["details"]["mindsdb"]
        assert "super-secret" not in detail
        assert "topsecret" not in detail
        assert "***REDACTED***" in detail


@pytest.mark.asyncio
async def test_weaver_dataflow_chunks_accurately():
    from app.core.data_flow import DataFlowManager
    manager = DataFlowManager(chunk_size=1000)
    
    # 2500 records should equate to precisely 3 chunks to secure memory thresholds
    res = await manager.extract_and_stream("session_abc", total_records=2500)
    assert res["chunks_yielded"] == 3
    assert res["records_per_chunk"] == [1000, 1000, 500]
    assert res["peak_chunk_memory_bytes"] == 256000
    assert res["max_memory_bound_enforced"] is True


@pytest.mark.asyncio
async def test_weaver_dataflow_rejects_invalid_inputs():
    from app.core.data_flow import DataFlowManager

    with pytest.raises(ValueError):
        DataFlowManager(chunk_size=0)

    manager = DataFlowManager(chunk_size=100)
    with pytest.raises(ValueError):
        await manager.extract_and_stream("", total_records=10)
    with pytest.raises(ValueError):
        await manager.extract_and_stream("s", total_records=-1)
