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
async def test_graph_search_vector_fk_stats(ac: AsyncClient):
    headers = {"Authorization": "Bearer local-oracle-token"}
    search = await ac.post(
        "/api/v3/synapse/graph/search",
        json={"query": "프로세스 효율성", "case_id": "case-1"},
        headers=headers,
    )
    assert search.status_code == 200
    body = search.json()["data"]
    assert "tables" in body
    assert "vector_matched" in body["tables"]
    assert "fk_related" in body["tables"]

    vec = await ac.post(
        "/api/v3/synapse/graph/vector-search",
        json={"query": "조직", "target": "table", "top_k": 3, "min_score": 0.0},
        headers=headers,
    )
    assert vec.status_code == 200
    assert vec.json()["data"]["total"] >= 1

    fk = await ac.post(
        "/api/v3/synapse/graph/fk-path",
        json={"start_table": "processes", "max_hops": 2},
        headers=headers,
    )
    assert fk.status_code == 200
    assert fk.json()["data"]["start_table"] == "processes"

    related = await ac.get("/api/v3/synapse/graph/tables/processes/related?max_hops=2", headers=headers)
    assert related.status_code == 200
    assert related.json()["data"]["total"] >= 1

    stats = await ac.get("/api/v3/synapse/graph/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["data"]["table_count"] >= 1


@pytest.mark.asyncio
async def test_ontology_path_uses_ontology_nodes(ac: AsyncClient):
    headers = {"Authorization": "Bearer local-oracle-token"}
    n1 = await ac.post(
        "/api/v3/synapse/ontology/nodes",
        json={
            "id": "on-a",
            "case_id": "case-graph",
            "layer": "resource",
            "labels": ["Company"],
            "properties": {"name": "ACME"},
        },
        headers=headers,
    )
    assert n1.status_code == 200
    n2 = await ac.post(
        "/api/v3/synapse/ontology/nodes",
        json={
            "id": "on-b",
            "case_id": "case-graph",
            "layer": "process",
            "labels": ["Process"],
            "properties": {"name": "효율"},
        },
        headers=headers,
    )
    assert n2.status_code == 200

    path = await ac.post(
        "/api/v3/synapse/graph/ontology-path",
        json={"case_id": "case-graph", "query": "효율", "max_depth": 4},
        headers=headers,
    )
    assert path.status_code == 200
    body = path.json()["data"]
    assert body["case_id"] == "case-graph"
    assert body["matched_nodes"] >= 1
