import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def reset_state():
    from app.api import ontology as ontology_api

    ontology_api.ontology_service.clear()
    yield
    ontology_api.ontology_service.clear()


@pytest.mark.asyncio
async def test_get_ontology_requires_case_id(ac: AsyncClient):
    resp = await ac.get(
        "/api/v3/synapse/ontology/",
        headers={"Authorization": "Bearer local-oracle-token"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_ontology_success(monkeypatch: pytest.MonkeyPatch, ac: AsyncClient):
    async def fake_get_case_ontology(case_id: str, limit: int = 200):
        assert case_id == "case-1"
        return {"case_id": case_id, "nodes": [], "relations": [], "summary": {"nodes": 0, "relations": 0}}

    from app.api import ontology as ontology_api

    monkeypatch.setattr(ontology_api.ontology_service, "get_case_ontology", fake_get_case_ontology)
    resp = await ac.get(
        "/api/v3/synapse/ontology/?case_id=case-1",
        headers={"Authorization": "Bearer local-oracle-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["case_id"] == "case-1"


@pytest.mark.asyncio
async def test_extract_ontology_validation(ac: AsyncClient):
    resp = await ac.post(
        "/api/v3/synapse/ontology/extract-ontology",
        json={"entities": []},
        headers={"Authorization": "Bearer local-oracle-token"},
    )
    assert resp.status_code == 400
    assert "case_id is required" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_extract_ontology_success(monkeypatch: pytest.MonkeyPatch, ac: AsyncClient):
    async def fake_extract_ontology(tenant_id: str, payload: dict):
        assert tenant_id == "system"
        assert payload["case_id"] == "case-1"
        return {"task_id": "onto-1", "status": "completed", "case_id": "case-1", "stats": {"nodes": 1, "relations": 0}}

    from app.api import ontology as ontology_api

    monkeypatch.setattr(ontology_api.ontology_service, "extract_ontology", fake_extract_ontology)
    resp = await ac.post(
        "/api/v3/synapse/ontology/extract-ontology",
        json={"case_id": "case-1", "entities": [{"id": "n1"}], "relations": []},
        headers={"Authorization": "Bearer local-oracle-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["task_id"] == "onto-1"


@pytest.mark.asyncio
async def test_ontology_crud_summary_and_path(ac: AsyncClient):
    headers = {"Authorization": "Bearer local-oracle-token"}
    n1 = await ac.post(
        "/api/v3/synapse/ontology/nodes",
        json={
            "id": "node-a",
            "case_id": "case-1",
            "layer": "resource",
            "labels": ["Company"],
            "properties": {"name": "ACME", "verified": True},
        },
        headers=headers,
    )
    assert n1.status_code == 200

    n2 = await ac.post(
        "/api/v3/synapse/ontology/nodes",
        json={
            "id": "node-b",
            "case_id": "case-1",
            "layer": "process",
            "labels": ["Process"],
            "properties": {"name": "Flow"},
        },
        headers=headers,
    )
    assert n2.status_code == 200

    rel = await ac.post(
        "/api/v3/synapse/ontology/relations",
        json={
            "case_id": "case-1",
            "source_id": "node-a",
            "target_id": "node-b",
            "type": "PARTICIPATES_IN",
        },
        headers=headers,
    )
    assert rel.status_code == 200
    relation_id = rel.json()["data"]["id"]

    summary = await ac.get("/api/v3/synapse/ontology/cases/case-1/ontology/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["data"]["node_counts"]["resource"]["total"] == 1

    neighbors = await ac.get("/api/v3/synapse/ontology/nodes/node-a/neighbors", headers=headers)
    assert neighbors.status_code == 200
    assert neighbors.json()["data"]["total"] == 1

    path = await ac.get("/api/v3/synapse/ontology/nodes/node-a/path-to/node-b", headers=headers)
    assert path.status_code == 200
    assert path.json()["data"]["path"] == ["node-a", "node-b"]

    del_rel = await ac.delete(f"/api/v3/synapse/ontology/relations/{relation_id}", headers=headers)
    assert del_rel.status_code == 200

    del_node = await ac.delete("/api/v3/synapse/ontology/nodes/node-a", headers=headers)
    assert del_node.status_code == 200
