import asyncio
import pathlib
import subprocess
import random

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.synapse_client import synapse_client
from app.main import app


async def _terminate_process(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()


async def _wait_health_or_fail_with_logs(
    url: str,
    proc: asyncio.subprocess.Process,
    name: str,
    attempts: int = 80,
    sleep_s: float = 0.25,
) -> None:
    async with httpx.AsyncClient(timeout=1.0) as client:
        for _ in range(attempts):
            if proc.returncode is not None:
                stderr = b""
                if proc.stderr:
                    stderr = await proc.stderr.read()
                pytest.fail(
                    f"{name} exited before healthy. rc={proc.returncode}, stderr={stderr.decode(errors='ignore')[:500]}"
                )
            try:
                res = await client.get(url)
                if res.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(sleep_s)
    pytest.fail(f"service not healthy: {url}")


def _random_test_port() -> int:
    return random.randint(20000, 40000)


@pytest_asyncio.fixture(scope="module")
async def live_core_and_synapse():
    repo_root = pathlib.Path(__file__).resolve().parents[4]
    core_dir = repo_root / "services" / "core"
    synapse_dir = repo_root / "services" / "synapse"
    synapse_py = synapse_dir / "venv" / "bin" / "python"

    core_port = _random_test_port()
    synapse_port = _random_test_port()
    if synapse_port == core_port:
        synapse_port = core_port + 1
    core_base = f"http://127.0.0.1:{core_port}"
    synapse_base = f"http://127.0.0.1:{synapse_port}"

    core_proc = await asyncio.create_subprocess_exec(
        "python3",
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(core_port),
        cwd=str(core_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    synapse_proc = await asyncio.create_subprocess_exec(
        str(synapse_py),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(synapse_port),
        cwd=str(synapse_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    try:
        await _wait_health_or_fail_with_logs(f"{core_base}/api/v1/health/live", core_proc, "core")
        await _wait_health_or_fail_with_logs(f"{synapse_base}/health/live", synapse_proc, "synapse")
        yield {"core_base": core_base, "synapse_base": synapse_base}
    finally:
        await _terminate_process(core_proc)
        await _terminate_process(synapse_proc)


@pytest.mark.asyncio
async def test_oracle_core_synapse_live_contract(live_core_and_synapse):
    old_core = settings.CORE_API_URL
    old_synapse = settings.SYNAPSE_API_URL
    old_synapse_client = synapse_client.base_url
    try:
        settings.CORE_API_URL = live_core_and_synapse["core_base"]
        settings.SYNAPSE_API_URL = live_core_and_synapse["synapse_base"]
        synapse_client.base_url = live_core_and_synapse["synapse_base"]

        headers = {"Authorization": "Bearer admin-live-token"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            meta_tables = await ac.get("/text2sql/meta/tables", params={"datasource_id": "ds_business_main"}, headers=headers)
            assert meta_tables.status_code == 200
            meta_body = meta_tables.json()
            assert meta_body["success"] is True
            assert len(meta_body["data"]["tables"]) >= 1

            scheduler_start = await ac.post("/text2sql/events/scheduler/start", headers=headers)
            assert scheduler_start.status_code == 200
            assert scheduler_start.json()["success"] is True

            scheduler_status = await ac.get("/text2sql/events/scheduler/status", headers=headers)
            assert scheduler_status.status_code == 200
            assert scheduler_status.json()["success"] is True
            assert scheduler_status.json()["data"]["running"] is True

            watch_chat = await ac.post(
                "/text2sql/watch-agent/chat",
                json={"message": "알림 룰 추천", "datasource_id": "ds_business_main", "session_id": "s1"},
                headers=headers,
            )
            assert watch_chat.status_code == 200
            watch_body = watch_chat.json()
            assert watch_body["success"] is True
            assert watch_body["data"]["action_required"] == "confirm"
    finally:
        settings.CORE_API_URL = old_core
        settings.SYNAPSE_API_URL = old_synapse
        synapse_client.base_url = old_synapse_client
