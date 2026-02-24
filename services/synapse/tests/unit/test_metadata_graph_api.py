"""Tests for Metadata Graph API (DDD-P2-05).

Validates the REST API routes that Weaver uses to access
the metadata graph via Synapse.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"Authorization": "Bearer local-oracle-token"}


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


_BASE = "/api/v1/metadata/graph"


# ──── Snapshot routes ──── #


@pytest.mark.asyncio
async def test_save_snapshot(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.save_snapshot = AsyncMock()
        r = await ac.post(f"{_BASE}/snapshots", json={"id": "s1", "case_id": "c1", "datasource": "ds1"}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["success"] is True
        svc.save_snapshot.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_snapshots(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.list_snapshots = AsyncMock(return_value=[{"id": "s1"}])
        r = await ac.get(f"{_BASE}/snapshots", params={"case_id": "c1", "datasource": "ds1"}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["data"] == [{"id": "s1"}]


@pytest.mark.asyncio
async def test_get_snapshot_found(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.get_snapshot = AsyncMock(return_value={"id": "s1"})
        r = await ac.get(f"{_BASE}/snapshots/s1", params={"case_id": "c1", "datasource": "ds1"}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["data"]["id"] == "s1"


@pytest.mark.asyncio
async def test_get_snapshot_not_found(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.get_snapshot = AsyncMock(return_value=None)
        r = await ac.get(f"{_BASE}/snapshots/missing", params={"case_id": "c1", "datasource": "ds1"}, headers=AUTH)
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_snapshot(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.delete_snapshot = AsyncMock(return_value=True)
        r = await ac.delete(f"{_BASE}/snapshots/s1", params={"case_id": "c1", "datasource": "ds1"}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["deleted"] is True


# ──── Glossary routes ──── #


@pytest.mark.asyncio
async def test_save_glossary_term(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.save_glossary_term = AsyncMock()
        r = await ac.post(f"{_BASE}/glossary", json={"id": "g1", "term": "test"}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["success"] is True


@pytest.mark.asyncio
async def test_list_glossary_terms(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.list_glossary_terms = AsyncMock(return_value=[{"id": "g1"}])
        r = await ac.get(f"{_BASE}/glossary", headers=AUTH)
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1


@pytest.mark.asyncio
async def test_search_glossary_terms(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.search_glossary_terms = AsyncMock(return_value=[{"id": "g1"}])
        r = await ac.get(f"{_BASE}/glossary", params={"q": "test"}, headers=AUTH)
        assert r.status_code == 200
        svc.search_glossary_terms.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_glossary_term_found(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.get_glossary_term = AsyncMock(return_value={"id": "g1"})
        r = await ac.get(f"{_BASE}/glossary/g1", headers=AUTH)
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_glossary_term_not_found(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.get_glossary_term = AsyncMock(return_value=None)
        r = await ac.get(f"{_BASE}/glossary/missing", headers=AUTH)
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_glossary_term(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.delete_glossary_term = AsyncMock(return_value=True)
        r = await ac.delete(f"{_BASE}/glossary/g1", headers=AUTH)
        assert r.status_code == 200


# ──── Entity Tags routes ──── #


@pytest.mark.asyncio
async def test_add_entity_tag(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.add_entity_tag = AsyncMock(return_value=["pii"])
        r = await ac.post(f"{_BASE}/tags", json={
            "entity_key": "k1", "entity_type": "table", "metadata": {}, "tag": "pii",
        }, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["tags"] == ["pii"]


@pytest.mark.asyncio
async def test_list_entity_tags(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.list_entity_tags = AsyncMock(return_value=["pii", "sensitive"])
        r = await ac.get(f"{_BASE}/tags", params={"entity_key": "k1"}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["tags"] == ["pii", "sensitive"]


@pytest.mark.asyncio
async def test_remove_entity_tag(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.remove_entity_tag = AsyncMock(return_value=True)
        r = await ac.delete(f"{_BASE}/tags", params={"entity_key": "k1", "tag": "pii"}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["removed"] is True


@pytest.mark.asyncio
async def test_entities_by_tag(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.entities_by_tag = AsyncMock(return_value=[{"entity_type": "table"}])
        r = await ac.get(f"{_BASE}/tags/entities", params={"tag": "pii"}, headers=AUTH)
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1


# ──── Datasource routes ──── #


@pytest.mark.asyncio
async def test_upsert_datasource(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.upsert_datasource = AsyncMock()
        r = await ac.post(f"{_BASE}/datasources/upsert", json={"name": "ds1", "engine": "postgresql"}, headers=AUTH)
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_datasource(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.delete_datasource = AsyncMock()
        r = await ac.delete(f"{_BASE}/datasources/ds1", headers=AUTH)
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_save_extracted_catalog(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.save_extracted_catalog = AsyncMock(return_value={"nodes": 5})
        r = await ac.post(f"{_BASE}/datasources/catalog", json={
            "datasource_name": "ds1", "catalog": {"public": {}}, "engine": "postgresql",
        }, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["data"] == {"nodes": 5}


# ──── Stats route ──── #


@pytest.mark.asyncio
async def test_metadata_stats(ac: AsyncClient):
    with patch("app.api.metadata_graph.metadata_graph_service") as svc:
        svc.stats = AsyncMock(return_value={"datasources": 2, "glossary_terms": 3, "snapshots": 1})
        r = await ac.get(f"{_BASE}/stats", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["data"]["datasources"] == 2
