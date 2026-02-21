import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.event_log_service import event_log_service
from app.services.process_mining_service import process_mining_service

AUTH = {"Authorization": "Bearer local-oracle-token"}


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def setup_function():
    event_log_service.clear()
    process_mining_service.clear()


@pytest.mark.asyncio
async def test_process_mining_full_routes(ac: AsyncClient):
    export_log = await ac.post(
        "/api/v3/synapse/event-logs/export-bpm",
        json={
            "case_id": "case-1",
            "name": "pm-log",
            "events": [
                {"case_id": "c-1", "activity": "주문 접수", "timestamp": "2024-01-01T09:00:00Z"},
                {"case_id": "c-1", "activity": "결제 확인", "timestamp": "2024-01-01T10:00:00Z"},
                {"case_id": "c-1", "activity": "출하 지시", "timestamp": "2024-01-01T11:00:00Z"},
                {"case_id": "c-2", "activity": "주문 접수", "timestamp": "2024-01-02T09:00:00Z"},
                {"case_id": "c-2", "activity": "결제 확인", "timestamp": "2024-01-02T11:00:00Z"},
                {"case_id": "c-2", "activity": "배송 완료", "timestamp": "2024-01-02T15:00:00Z"},
            ],
        },
        headers=AUTH,
    )
    assert export_log.status_code == 202
    log_id = export_log.json()["data"]["log_id"]

    discover = await ac.post(
        "/api/v3/synapse/process-mining/discover",
        json={"case_id": "case-1", "log_id": log_id, "algorithm": "inductive"},
        headers=AUTH,
    )
    assert discover.status_code == 202
    task_id = discover.json()["data"]["task_id"]

    conformance = await ac.post(
        "/api/v3/synapse/process-mining/conformance",
        json={
            "case_id": "case-1",
            "log_id": log_id,
            "reference_model": {"type": "eventstorming", "model_id": "es-1"},
        },
        headers=AUTH,
    )
    assert conformance.status_code == 202

    bottlenecks_post = await ac.post(
        "/api/v3/synapse/process-mining/bottlenecks",
        json={"case_id": "case-1", "log_id": log_id},
        headers=AUTH,
    )
    assert bottlenecks_post.status_code == 202

    performance_post = await ac.post(
        "/api/v3/synapse/process-mining/performance",
        json={"case_id": "case-1", "log_id": log_id, "options": {"include_bottlenecks": True}},
        headers=AUTH,
    )
    assert performance_post.status_code == 202
    performance_task_id = performance_post.json()["data"]["task_id"]

    variants = await ac.get(
        "/api/v3/synapse/process-mining/variants",
        params={"case_id": "case-1", "log_id": log_id},
        headers=AUTH,
    )
    assert variants.status_code == 200
    assert "variants" in variants.json()["data"]

    bottlenecks_get = await ac.get(
        "/api/v3/synapse/process-mining/bottlenecks",
        params={"case_id": "case-1", "log_id": log_id},
        headers=AUTH,
    )
    assert bottlenecks_get.status_code == 200

    task = await ac.get(f"/api/v3/synapse/process-mining/tasks/{task_id}", headers=AUTH)
    assert task.status_code == 200
    result_id = task.json()["data"]["result_id"]

    task_result = await ac.get(f"/api/v3/synapse/process-mining/tasks/{task_id}/result", headers=AUTH)
    assert task_result.status_code == 200

    result = await ac.get(f"/api/v3/synapse/process-mining/results/{result_id}", headers=AUTH)
    assert result.status_code == 200

    performance_task = await ac.get(f"/api/v3/synapse/process-mining/tasks/{performance_task_id}", headers=AUTH)
    assert performance_task.status_code == 200
    assert performance_task.json()["data"]["task_type"] == "performance"

    performance_result = await ac.get(
        f"/api/v3/synapse/process-mining/tasks/{performance_task_id}/result", headers=AUTH
    )
    assert performance_result.status_code == 200
    assert "overall_performance" in performance_result.json()["data"]["result"]

    result_alias = await ac.get(f"/api/v3/synapse/process-mining/results/{task_id}", headers=AUTH)
    assert result_alias.status_code == 200

    stats = await ac.get(f"/api/v3/synapse/process-mining/statistics/{log_id}", headers=AUTH)
    assert stats.status_code == 200

    export = await ac.post(
        "/api/v3/synapse/process-mining/bpmn/export",
        json={"case_id": "case-1", "source": {"type": "discovered", "result_id": result_id}},
        headers=AUTH,
    )
    assert export.status_code == 200
    assert "xml" in export.json()["data"]

    imported = await ac.post(
        "/api/v3/synapse/process-mining/import-model",
        json={
            "case_id": "case-1",
            "model": {"type": "bpmn", "content": "<definitions><process id='p'/></definitions>"},
            "result_id": result_id,
        },
        headers=AUTH,
    )
    assert imported.status_code == 200
    assert imported.json()["data"]["status"] == "imported"


@pytest.mark.asyncio
async def test_process_mining_validation_errors(ac: AsyncClient):
    invalid = await ac.post(
        "/api/v3/synapse/process-mining/discover",
        json={"case_id": "case-1", "log_id": "missing", "algorithm": "unknown"},
        headers=AUTH,
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"]["code"] == "INVALID_ALGORITHM"

    missing_required = await ac.post(
        "/api/v3/synapse/process-mining/discover",
        json={"log_id": "missing-log"},
        headers=AUTH,
    )
    assert missing_required.status_code == 400
    assert missing_required.json()["detail"]["code"] == "INVALID_REQUEST"

    not_found_task = await ac.get("/api/v3/synapse/process-mining/tasks/task-missing", headers=AUTH)
    assert not_found_task.status_code == 404
    assert not_found_task.json()["detail"]["code"] == "TASK_NOT_FOUND"

    not_found_result = await ac.get("/api/v3/synapse/process-mining/results/result-missing", headers=AUTH)
    assert not_found_result.status_code == 404
    assert not_found_result.json()["detail"]["code"] == "RESULT_NOT_FOUND"

    unauthorized = await ac.get("/api/v3/synapse/process-mining/tasks/task-missing")
    assert unauthorized.status_code == 401
