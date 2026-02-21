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
async def test_gateway_graph_and_ontology_live_http(ac: AsyncClient, synapse_live_base_url: str):
    original_base = synapse_gateway_service.base_url
    synapse_gateway_service.base_url = synapse_live_base_url.rstrip("/")

    headers = {"X-Tenant-Id": "acme-corp", "Authorization": "Bearer local-oracle-token"}
    try:
        create1 = await ac.post(
            "/api/v1/ontology/nodes",
            json={
                "id": "live-node-1",
                "case_id": "case-live-1",
                "layer": "resource",
                "labels": ["Company"],
                "properties": {"name": "ACME"},
            },
            headers=headers,
        )
        assert create1.status_code == 200

        create2 = await ac.post(
            "/api/v1/ontology/nodes",
            json={
                "id": "live-node-2",
                "case_id": "case-live-1",
                "layer": "process",
                "labels": ["Process"],
                "properties": {"name": "효율 분석"},
            },
            headers=headers,
        )
        assert create2.status_code == 200

        summary = await ac.get("/api/v1/ontology/cases/case-live-1/ontology/summary", headers=headers)
        assert summary.status_code == 200
        assert summary.json()["success"] is True

        graph_search = await ac.post(
            "/api/v1/graph/search",
            json={"query": "효율", "case_id": "case-live-1"},
            headers=headers,
        )
        assert graph_search.status_code == 200
        assert graph_search.json()["success"] is True

        ontology_path = await ac.post(
            "/api/v1/graph/ontology-path",
            json={"case_id": "case-live-1", "query": "효율", "max_depth": 4},
            headers=headers,
        )
        assert ontology_path.status_code == 200
        assert ontology_path.json()["data"]["case_id"] == "case-live-1"

        stats = await ac.get("/api/v1/graph/stats", headers=headers)
        assert stats.status_code == 200
        assert stats.json()["success"] is True
    finally:
        synapse_gateway_service.base_url = original_base
