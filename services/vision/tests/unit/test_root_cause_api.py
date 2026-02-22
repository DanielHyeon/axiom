import pytest
from httpx import ASGITransport, AsyncClient
import os

from app.main import app
from app.services.vision_runtime import VisionRuntimeError, vision_runtime


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": token}


@pytest.fixture(autouse=True)
def clear_runtime() -> None:
    vision_runtime.clear()


@pytest.mark.asyncio
async def test_root_cause_minimum_lifecycle() -> None:
    case_id = "case-rca-001"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing_status = await client.get(
            f"/api/v3/cases/{case_id}/root-cause-analysis/status",
            headers=_headers("mock_token_viewer"),
        )
        assert missing_status.status_code == 404

        forbidden_run = await client.post(
            f"/api/v3/cases/{case_id}/root-cause-analysis",
            json={"analysis_depth": "full", "max_root_causes": 3},
            headers=_headers("mock_token_viewer"),
        )
        assert forbidden_run.status_code == 403

        run_res = await client.post(
            f"/api/v3/cases/{case_id}/root-cause-analysis",
            json={
                "analysis_depth": "full",
                "max_root_causes": 3,
                "include_counterfactuals": True,
                "include_explanation": True,
                "language": "ko",
            },
            headers=_headers("mock_token_staff"),
        )
        assert run_res.status_code == 202
        assert run_res.json()["status"] == "ANALYZING"

        not_ready_res = await client.get(
            f"/api/v3/cases/{case_id}/root-causes",
            headers=_headers("mock_token_viewer"),
        )
        assert not_ready_res.status_code == 409

        status_res = await client.get(
            f"/api/v3/cases/{case_id}/root-cause-analysis/status",
            headers=_headers("mock_token_viewer"),
        )
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "COMPLETED"
        assert status_res.json()["progress"]["pct"] == 100

        causes_res = await client.get(
            f"/api/v3/cases/{case_id}/root-causes",
            headers=_headers("mock_token_viewer"),
        )
        assert causes_res.status_code == 200
        assert len(causes_res.json()["root_causes"]) == 3
        assert causes_res.json()["overall_confidence"] > 0
        assert causes_res.json()["confidence_basis"]["model"] == "deterministic-risk-engine-v1"

        counterfactual_res = await client.post(
            f"/api/v3/cases/{case_id}/counterfactual",
            json={
                "variable": "debt_ratio",
                "actual_value": 1.5,
                "counterfactual_value": 1.0,
                "question": "부채비율이 낮았다면 실패를 줄일 수 있는가?",
            },
            headers=_headers("mock_token_admin"),
        )
        assert counterfactual_res.status_code == 200
        assert counterfactual_res.json()["risk_reduction_pct"] >= 0
        assert counterfactual_res.json()["confidence_basis"]["method"] == "variable-sensitivity-table-v1"

        timeline_res = await client.get(
            f"/api/v3/cases/{case_id}/causal-timeline",
            headers=_headers("mock_token_viewer"),
        )
        assert timeline_res.status_code == 200
        assert len(timeline_res.json()["timeline"]) >= 1

        impact_res = await client.get(
            f"/api/v3/cases/{case_id}/root-cause-impact",
            headers=_headers("mock_token_viewer"),
        )
        assert impact_res.status_code == 200
        assert len(impact_res.json()["contributions"]) >= 1
        assert impact_res.json()["confidence_basis"]["model"] == "deterministic-risk-engine-v1"

        graph_res = await client.get(
            f"/api/v3/cases/{case_id}/causal-graph",
            headers=_headers("mock_token_viewer"),
        )
        assert graph_res.status_code == 200
        assert len(graph_res.json()["nodes"]) >= 2


@pytest.mark.asyncio
async def test_process_bottleneck_requires_synapse_when_configured() -> None:
    case_id = "case-rca-002"
    old_synapse = os.environ.get("SYNAPSE_BASE_URL")
    os.environ["SYNAPSE_BASE_URL"] = "http://127.0.0.1:65535"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            run_res = await client.post(
                f"/api/v3/cases/{case_id}/root-cause-analysis",
                json={"analysis_depth": "full", "max_root_causes": 3},
                headers=_headers("mock_token_staff"),
            )
            assert run_res.status_code == 202
            status_res = await client.get(
                f"/api/v3/cases/{case_id}/root-cause-analysis/status",
                headers=_headers("mock_token_viewer"),
            )
            assert status_res.status_code == 200

            bottleneck_res = await client.get(
                f"/api/v3/cases/{case_id}/root-cause/process-bottleneck",
                params={"process_id": "pm-1"},
                headers=_headers("mock_token_viewer"),
            )
            assert bottleneck_res.status_code == 502
            assert bottleneck_res.json()["detail"]["code"] == "SYNAPSE_UNAVAILABLE"
    finally:
        if old_synapse is None:
            os.environ.pop("SYNAPSE_BASE_URL", None)
        else:
            os.environ["SYNAPSE_BASE_URL"] = old_synapse


@pytest.mark.asyncio
async def test_root_cause_engine_is_deterministic_and_case_sensitive() -> None:
    case_a = "case-rca-diff-a"
    case_b = "case-rca-diff-b"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for case_id in (case_a, case_b):
            run_res = await client.post(
                f"/api/v3/cases/{case_id}/root-cause-analysis",
                json={"analysis_depth": "full", "max_root_causes": 3},
                headers=_headers("mock_token_staff"),
            )
            assert run_res.status_code == 202
            await client.get(
                f"/api/v3/cases/{case_id}/root-cause-analysis/status",
                headers=_headers("mock_token_viewer"),
            )

        first_a = await client.get(f"/api/v3/cases/{case_a}/root-causes", headers=_headers("mock_token_viewer"))
        second_a = await client.get(f"/api/v3/cases/{case_a}/root-causes", headers=_headers("mock_token_viewer"))
        result_b = await client.get(f"/api/v3/cases/{case_b}/root-causes", headers=_headers("mock_token_viewer"))

        assert first_a.status_code == 200
        assert second_a.status_code == 200
        assert result_b.status_code == 200

        vars_first_a = [item["variable"] for item in first_a.json()["root_causes"]]
        vars_second_a = [item["variable"] for item in second_a.json()["root_causes"]]
        vars_b = [item["variable"] for item in result_b.json()["root_causes"]]
        assert vars_first_a == vars_second_a
        assert vars_first_a != vars_b


@pytest.mark.asyncio
async def test_root_cause_operational_metrics_exposed() -> None:
    case_id = "case-rca-metrics"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ready_before = await client.get("/health/ready")
        assert ready_before.status_code == 200
        assert ready_before.json()["root_cause_operational"]["calls_total"] == 0

        missing = await client.get(
            f"/api/v3/cases/{case_id}/root-causes",
            headers=_headers("mock_token_viewer"),
        )
        assert missing.status_code == 404

        run_res = await client.post(
            f"/api/v3/cases/{case_id}/root-cause-analysis",
            json={"analysis_depth": "full", "max_root_causes": 3},
            headers=_headers("mock_token_staff"),
        )
        assert run_res.status_code == 202
        await client.get(f"/api/v3/cases/{case_id}/root-cause-analysis/status", headers=_headers("mock_token_viewer"))
        await client.get(f"/api/v3/cases/{case_id}/root-cause-impact", headers=_headers("mock_token_viewer"))

        ready_after = await client.get("/health/ready")
        assert ready_after.status_code == 200
        root_metrics = ready_after.json()["root_cause_operational"]
        assert root_metrics["calls_total"] == 4
        assert root_metrics["error_total"] == 1
        assert root_metrics["failure_rate"] > 0
        assert root_metrics["avg_latency_ms"] >= 0

        metrics_res = await client.get("/metrics")
        assert metrics_res.status_code == 200
        body = metrics_res.text
        assert "vision_root_cause_calls_total 4" in body
        assert "vision_root_cause_errors_total 1" in body
        assert 'vision_root_cause_operation_calls_total{operation="list_root_causes"} 1' in body


@pytest.mark.asyncio
async def test_process_bottleneck_maps_synapse_domain_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    case_id = "case-rca-003"
    old_synapse = os.environ.get("SYNAPSE_BASE_URL")
    os.environ["SYNAPSE_BASE_URL"] = "http://synapse"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run_res = await client.post(
            f"/api/v3/cases/{case_id}/root-cause-analysis",
            json={"analysis_depth": "full", "max_root_causes": 3},
            headers=_headers("mock_token_staff"),
        )
        assert run_res.status_code == 202
        await client.get(
            f"/api/v3/cases/{case_id}/root-cause-analysis/status",
            headers=_headers("mock_token_viewer"),
        )

        def _raise_not_found(*_: object, **__: object) -> dict[str, object]:
            raise VisionRuntimeError("PROCESS_MODEL_NOT_FOUND", "process model not found")

        monkeypatch.setattr(vision_runtime, "_fetch_synapse_process_context", _raise_not_found)
        not_found_res = await client.get(
            f"/api/v3/cases/{case_id}/root-cause/process-bottleneck",
            params={"process_id": "pm-missing"},
            headers=_headers("mock_token_viewer"),
        )
        assert not_found_res.status_code == 404
        assert not_found_res.json()["detail"]["code"] == "PROCESS_MODEL_NOT_FOUND"

        def _raise_insufficient(*_: object, **__: object) -> dict[str, object]:
            raise VisionRuntimeError("INSUFFICIENT_PROCESS_DATA", "insufficient process data")

        monkeypatch.setattr(vision_runtime, "_fetch_synapse_process_context", _raise_insufficient)
        data_res = await client.get(
            f"/api/v3/cases/{case_id}/root-cause/process-bottleneck",
            params={"process_id": "pm-empty"},
            headers=_headers("mock_token_viewer"),
        )
        assert data_res.status_code == 422
        assert data_res.json()["detail"]["code"] == "INSUFFICIENT_PROCESS_DATA"

    if old_synapse is None:
        os.environ.pop("SYNAPSE_BASE_URL", None)
    else:
        os.environ["SYNAPSE_BASE_URL"] = old_synapse


@pytest.mark.asyncio
async def test_process_bottleneck_uses_synapse_payload_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    case_id = "case-rca-004"
    old_synapse = os.environ.get("SYNAPSE_BASE_URL")
    os.environ["SYNAPSE_BASE_URL"] = "http://synapse"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            run_res = await client.post(
                f"/api/v3/cases/{case_id}/root-cause-analysis",
                json={"analysis_depth": "full", "max_root_causes": 3},
                headers=_headers("mock_token_staff"),
            )
            assert run_res.status_code == 202
            await client.get(
                f"/api/v3/cases/{case_id}/root-cause-analysis/status",
                headers=_headers("mock_token_viewer"),
            )

            def _mock_synapse(*_: object, **__: object) -> dict[str, object]:
                return {
                    "source_log_id": "log-42",
                    "bottleneck_activity": "심사",
                    "bottleneck_score": 0.91,
                    "data_range": {"from": "2025-01-01", "to": "2025-01-31"},
                    "case_count": 37,
                }

            monkeypatch.setattr(vision_runtime, "_fetch_synapse_process_context", _mock_synapse)
            response = await client.get(
                f"/api/v3/cases/{case_id}/root-cause/process-bottleneck",
                params={"process_id": "pm-42"},
                headers=_headers("mock_token_viewer"),
            )
            assert response.status_code == 200
            body = response.json()
            assert body["synapse_status"] == "connected"
            assert body["source_log_id"] == "log-42"
            assert body["bottleneck_activity"] == "심사"
            assert body["bottleneck_score"] == 0.91
            assert body["case_count"] == 37
            assert body["data_range"] == {"from": "2025-01-01", "to": "2025-01-31"}
    finally:
        if old_synapse is None:
            os.environ.pop("SYNAPSE_BASE_URL", None)
        else:
            os.environ["SYNAPSE_BASE_URL"] = old_synapse
