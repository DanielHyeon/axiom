import asyncio
import os
import pathlib
import subprocess

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.synapse_gateway_service import synapse_gateway_service


@pytest_asyncio.fixture(scope="module")
async def synapse_live_base_url():
    repo_root = pathlib.Path(__file__).resolve().parents[4]
    synapse_dir = repo_root / "services" / "synapse"
    python_bin = synapse_dir / "venv" / "bin" / "python"
    port = int(os.getenv("SYNAPSE_LIVE_TEST_PORT", "18002"))
    base_url = f"http://127.0.0.1:{port}"

    proc = await asyncio.create_subprocess_exec(
        str(python_bin),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        cwd=str(synapse_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    healthy = False
    async with httpx.AsyncClient(timeout=1.0) as client:
        for _ in range(80):
            try:
                resp = await client.get(f"{base_url}/health/live")
                if resp.status_code == 200:
                    healthy = True
                    break
            except Exception:
                pass
            await asyncio.sleep(0.25)

    if not healthy:
        proc.terminate()
        await proc.wait()
        pytest.fail("failed to start live synapse test server")

    try:
        yield base_url
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_gateway_extraction_and_schema_edit_live_http(ac: AsyncClient, synapse_live_base_url: str):
    original_base = synapse_gateway_service.base_url
    synapse_gateway_service.base_url = synapse_live_base_url.rstrip("/")

    headers = {"X-Tenant-Id": "acme-corp", "Authorization": "Bearer local-oracle-token"}
    doc_id = "doc-live-1"
    case_id = "case-live-ext-1"
    try:
        start = await ac.post(
            f"/api/v1/extraction/documents/{doc_id}/extract-ontology",
            json={"case_id": case_id, "options": {"auto_commit_threshold": 0.95}},
            headers=headers,
        )
        assert start.status_code == 202
        assert start.json()["success"] is True

        status_res = await ac.get(f"/api/v1/extraction/documents/{doc_id}/ontology-status", headers=headers)
        assert status_res.status_code == 200
        assert status_res.json()["data"]["status"] == "completed"

        result_res = await ac.get(
            f"/api/v1/extraction/documents/{doc_id}/ontology-result",
            params={"status": "all", "include_rejected": "true"},
            headers=headers,
        )
        assert result_res.status_code == 200
        entities = result_res.json()["data"]["entities"]
        assert len(entities) >= 1
        entity_id = entities[0]["id"]

        confirm = await ac.put(
            f"/api/v1/extraction/ontology/{entity_id}/confirm",
            json={"action": "approve", "reviewer_id": "reviewer-1"},
            headers=headers,
        )
        assert confirm.status_code == 200
        assert confirm.json()["data"]["status"] == "committed"

        queue = await ac.get(
            f"/api/v1/extraction/cases/{case_id}/review-queue",
            params={"limit": 10, "offset": 0},
            headers=headers,
        )
        assert queue.status_code == 200
        assert queue.json()["success"] is True

        retry = await ac.post(f"/api/v1/extraction/documents/{doc_id}/retry", headers=headers)
        assert retry.status_code == 202
        assert retry.json()["success"] is True

        revert = await ac.post(f"/api/v1/extraction/documents/{doc_id}/revert-extraction", headers=headers)
        assert revert.status_code == 200
        assert revert.json()["data"]["status"] == "reverted"

        tables = await ac.get("/api/v1/schema-edit/tables", headers=headers)
        assert tables.status_code == 200
        table_items = tables.json()["data"]["tables"]
        assert len(table_items) >= 1
        table_name = table_items[0]["name"]

        table_detail = await ac.get(f"/api/v1/schema-edit/tables/{table_name}", headers=headers)
        assert table_detail.status_code == 200
        columns = table_detail.json()["data"]["columns"]
        assert len(columns) >= 1
        column_name = columns[0]["name"]

        table_desc = await ac.put(
            f"/api/v1/schema-edit/tables/{table_name}/description",
            json={"description": "라이브 E2E 업데이트 설명"},
            headers=headers,
        )
        assert table_desc.status_code == 200
        assert table_desc.json()["data"]["embedding_updated"] is True

        col_desc = await ac.put(
            f"/api/v1/schema-edit/columns/{table_name}/{column_name}/description",
            json={"description": "라이브 E2E 컬럼 설명"},
            headers=headers,
        )
        assert col_desc.status_code == 200

        relationships = await ac.get("/api/v1/schema-edit/relationships", headers=headers)
        assert relationships.status_code == 200

        create_rel = await ac.post(
            "/api/v1/schema-edit/relationships",
            json={
                "source_table": "processes",
                "source_column": "org_id",
                "target_table": "organizations",
                "target_column": "id",
                "relationship_type": "FK_TO",
                "description": "live-e2e relation",
            },
            headers=headers,
        )
        assert create_rel.status_code == 200
        rel_id = create_rel.json()["data"]["id"]

        delete_rel = await ac.delete(f"/api/v1/schema-edit/relationships/{rel_id}", headers=headers)
        assert delete_rel.status_code == 200
        assert delete_rel.json()["data"]["deleted"] is True

        embedding = await ac.post(f"/api/v1/schema-edit/tables/{table_name}/embedding", headers=headers)
        assert embedding.status_code == 200

        batch = await ac.post(
            "/api/v1/schema-edit/batch-update-embeddings",
            json={"target": "all", "force": False},
            headers=headers,
        )
        assert batch.status_code == 202
        assert batch.json()["data"]["status"] == "processing"
    finally:
        synapse_gateway_service.base_url = original_base
