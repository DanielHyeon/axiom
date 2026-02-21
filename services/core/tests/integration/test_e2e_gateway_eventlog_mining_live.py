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
async def test_gateway_eventlog_and_process_mining_live_http(ac: AsyncClient, synapse_live_base_url: str):
    original_base = synapse_gateway_service.base_url
    synapse_gateway_service.base_url = synapse_live_base_url.rstrip("/")

    headers = {"X-Tenant-Id": "acme-corp", "Authorization": "Bearer local-oracle-token"}
    case_id = "case-live-pm-1"
    try:
        export = await ac.post(
            "/api/v1/event-logs/export-bpm",
            json={
                "case_id": case_id,
                "name": "live-pm-log",
                "events": [
                    {"case_id": "c-1", "activity": "접수", "timestamp": "2024-01-01T09:00:00Z"},
                    {"case_id": "c-1", "activity": "심사", "timestamp": "2024-01-01T10:00:00Z"},
                    {"case_id": "c-1", "activity": "승인", "timestamp": "2024-01-01T11:00:00Z"},
                    {"case_id": "c-2", "activity": "접수", "timestamp": "2024-01-02T09:00:00Z"},
                    {"case_id": "c-2", "activity": "심사", "timestamp": "2024-01-02T11:30:00Z"},
                    {"case_id": "c-2", "activity": "반려", "timestamp": "2024-01-02T12:00:00Z"},
                ],
            },
            headers=headers,
        )
        assert export.status_code == 202
        log_id = export.json()["data"]["log_id"]

        listed = await ac.get("/api/v1/event-logs", params={"case_id": case_id}, headers=headers)
        assert listed.status_code == 200
        assert listed.json()["success"] is True

        discover = await ac.post(
            "/api/v1/process-mining/discover",
            json={"case_id": case_id, "log_id": log_id, "algorithm": "inductive"},
            headers=headers,
        )
        assert discover.status_code == 202
        discover_task_id = discover.json()["data"]["task_id"]

        discover_task = await ac.get(f"/api/v1/process-mining/tasks/{discover_task_id}", headers=headers)
        assert discover_task.status_code == 200
        assert discover_task.json()["success"] is True

        discover_result = await ac.get(
            f"/api/v1/process-mining/tasks/{discover_task_id}/result",
            headers=headers,
        )
        assert discover_result.status_code == 200
        assert discover_result.json()["data"]["task_type"] == "discover"

        performance = await ac.post(
            "/api/v1/process-mining/performance",
            json={"case_id": case_id, "log_id": log_id, "options": {"include_bottlenecks": True}},
            headers=headers,
        )
        assert performance.status_code == 202
        performance_task_id = performance.json()["data"]["task_id"]

        performance_task = await ac.get(f"/api/v1/process-mining/tasks/{performance_task_id}", headers=headers)
        assert performance_task.status_code == 200
        assert performance_task.json()["data"]["task_type"] == "performance"

        performance_result = await ac.get(
            f"/api/v1/process-mining/tasks/{performance_task_id}/result",
            headers=headers,
        )
        assert performance_result.status_code == 200
        result_payload = performance_result.json()["data"]["result"]
        assert "overall_performance" in result_payload
        assert "activity_performance" in result_payload
    finally:
        synapse_gateway_service.base_url = original_base
