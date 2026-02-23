import asyncio
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.vision_runtime import vision_runtime


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "mock_token_admin"}


@pytest.fixture(autouse=True)
def clear_runtime() -> None:
    vision_runtime.clear()


@pytest.mark.asyncio
async def test_what_if_full_lifecycle_and_analysis_endpoints() -> None:
    case_id = "case-001"
    create_payload = {
        "scenario_name": "base plan",
        "scenario_type": "BASELINE",
        "parameters": {
            "execution_period_years": 10,
            "interest_rate": 4.5,
            "ebitda_growth_rate": 7.5,
            "operating_cost_ratio": 65.0,
        },
        "constraints": [
            {
                "constraint_type": "legal_minimum",
                "description": "general allocation >= 15",
                "value": 15.0,
            }
        ],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_res = await client.post(f"/api/v3/cases/{case_id}/what-if", json=create_payload, headers=_admin_headers())
        assert create_res.status_code == 201
        scenario_id = create_res.json()["id"]

        list_res = await client.get(f"/api/v3/cases/{case_id}/what-if", headers=_admin_headers())
        assert list_res.status_code == 200
        assert list_res.json()["total"] == 1

        detail_res = await client.get(f"/api/v3/cases/{case_id}/what-if/{scenario_id}", headers=_admin_headers())
        assert detail_res.status_code == 200
        assert detail_res.json()["scenario_name"] == "base plan"

        update_res = await client.put(
            f"/api/v3/cases/{case_id}/what-if/{scenario_id}",
            json={"scenario_name": "base plan v2", "parameters": {"interest_rate": 5.0}},
            headers=_admin_headers(),
        )
        assert update_res.status_code == 200
        assert update_res.json()["scenario_name"] == "base plan v2"
        assert update_res.json()["status"] == "DRAFT"

        compute_res = await client.post(
            f"/api/v3/cases/{case_id}/what-if/{scenario_id}/compute",
            json={"force_recompute": False},
            headers=_admin_headers(),
        )
        assert compute_res.status_code == 202
        assert compute_res.json()["status"] == "COMPUTING"

        for _ in range(60):
            status_res = await client.get(f"/api/v3/cases/{case_id}/what-if/{scenario_id}/status", headers=_admin_headers())
            assert status_res.status_code == 200
            if status_res.json()["status"] == "COMPLETED":
                break
            if status_res.json()["status"] == "FAILED":
                pytest.fail("scenario compute failed")
            await asyncio.sleep(0.5)
        assert status_res.json()["status"] == "COMPLETED"
        assert "started_at" in status_res.json()
        assert "elapsed_seconds" in status_res.json()

        result_res = await client.get(f"/api/v3/cases/{case_id}/what-if/{scenario_id}/result", headers=_admin_headers())
        assert result_res.status_code == 200
        result = result_res.json()
        assert result["status"] == "COMPLETED"
        assert "by_year" in result
        assert "by_stakeholder_class" in result
        assert "constraints_met" in result

        second_res = await client.post(
            f"/api/v3/cases/{case_id}/what-if",
            json={**create_payload, "scenario_name": "second plan", "scenario_type": "OPTIMISTIC"},
            headers=_admin_headers(),
        )
        second_id = second_res.json()["id"]
        await client.post(
            f"/api/v3/cases/{case_id}/what-if/{second_id}/compute",
            json={"force_recompute": False},
            headers=_admin_headers(),
        )
        for _ in range(60):
            s2_status = await client.get(f"/api/v3/cases/{case_id}/what-if/{second_id}/status", headers=_admin_headers())
            if s2_status.json().get("status") == "COMPLETED":
                break
            await asyncio.sleep(0.5)

        compare_fail = await client.get(
            f"/api/v3/cases/{case_id}/what-if/compare",
            params={"scenario_ids": scenario_id},
            headers=_admin_headers(),
        )
        assert compare_fail.status_code == 422

        compare_res = await client.get(
            f"/api/v3/cases/{case_id}/what-if/compare",
            params={"scenario_ids": f"{scenario_id},{second_id}"},
            headers=_admin_headers(),
        )
        assert compare_res.status_code == 200
        assert compare_res.json()["total"] == 2

        sensitivity_res = await client.post(
            f"/api/v3/cases/{case_id}/what-if/{scenario_id}/sensitivity",
            json={"parameter": "interest_rate", "delta_pct": 7.0},
            headers=_admin_headers(),
        )
        assert sensitivity_res.status_code == 200
        assert sensitivity_res.json()["parameter"] == "interest_rate"

        breakeven_res = await client.post(
            f"/api/v3/cases/{case_id}/what-if/{scenario_id}/breakeven",
            json={"target_metric": "overall_allocation_rate", "target_value": 0.6},
            headers=_admin_headers(),
        )
        assert breakeven_res.status_code == 200
        assert "breakeven_value" in breakeven_res.json()

        sim_res = await client.post(
            f"/api/v3/cases/{case_id}/what-if/process-simulation",
            json={
                "process_model_id": "log-1",
                "scenario_name": "승인 시간 단축",
                "description": "테스트 시나리오",
                "parameter_changes": [
                    {"activity": "승인", "change_type": "duration", "duration_change": -7200},
                ],
                "sla_threshold_seconds": None,
            },
            headers=_admin_headers(),
        )
        if sim_res.status_code == 200:
            body = sim_res.json()
            assert "original_cycle_time" in body
            assert "simulated_cycle_time" in body
            assert "by_activity" in body
        else:
            assert sim_res.status_code == 502
            assert (sim_res.json().get("detail") or {}).get("code") == "SYNAPSE_UNAVAILABLE"

        delete_res = await client.delete(f"/api/v3/cases/{case_id}/what-if/{second_id}", headers=_admin_headers())
        assert delete_res.status_code == 200
        assert delete_res.json()["deleted"] is True


@pytest.mark.asyncio
async def test_what_if_rejects_viewer_role() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v3/cases/case-001/what-if",
            json={"scenario_name": "x", "scenario_type": "BASELINE", "parameters": {}, "constraints": []},
            headers={"Authorization": "mock_token_viewer"},
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_olap_full_endpoints_contract() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        upload_res = await client.post(
            "/api/v3/cubes/schema/upload",
            files={"file": ("business_analysis_cube.xml", "<Cube name='BusinessAnalysisCube'></Cube>", "application/xml")},
            headers=_admin_headers(),
        )
        assert upload_res.status_code == 201
        cube_name = upload_res.json()["cube_name"]

        cubes_res = await client.get("/api/v3/cubes", headers=_admin_headers())
        assert cubes_res.status_code == 200
        assert cubes_res.json()["cubes"][0]["name"] == cube_name

        cube_res = await client.get(f"/api/v3/cubes/{cube_name}", headers=_admin_headers())
        assert cube_res.status_code == 200
        assert "dimensions" in cube_res.json()
        assert "measures" in cube_res.json()

        pivot_404 = await client.post(
            "/api/v3/pivot/query",
            json={"cube_name": "missing", "rows": ["region"], "measures": ["sales"]},
            headers=_admin_headers(),
        )
        assert pivot_404.status_code == 404

        pivot_res = await client.post(
            "/api/v3/pivot/query",
            json={
                "cube_name": cube_name,
                "rows": ["CaseType.CaseCategory"],
                "columns": ["Time.Year"],
                "measures": ["CaseCount"],
                "filters": [],
            },
            headers=_admin_headers(),
        )
        assert pivot_res.status_code == 200
        assert "aggregations" in pivot_res.json()
        assert "CaseCount_total" in pivot_res.json()["aggregations"]

        nl_res = await client.post(
            "/api/v3/pivot/nl-query",
            json={"query": "show profit by region", "cube_name": cube_name, "include_sql": False},
            headers=_admin_headers(),
        )
        assert nl_res.status_code == 200
        assert "generated_sql" not in nl_res.json()
        assert nl_res.json()["interpreted_as"]["cube_name"] == cube_name

        drill_res = await client.get("/api/v3/pivot/drillthrough", params={"cube_name": cube_name, "limit": 3}, headers=_admin_headers())
        assert drill_res.status_code == 200
        assert drill_res.json()["total_count"] == 3
        assert len(drill_res.json()["records"]) == 3

        analyze_res = await client.post("/api/v3/etl/analyze", json={"source": "dw"}, headers=_admin_headers())
        assert analyze_res.status_code == 200
        assert analyze_res.json()["status"] == "analyzed"

        sync_res = await client.post("/api/v3/etl/sync", json={"source": "dw"}, headers=_admin_headers())
        assert sync_res.status_code == 202
        job_id = sync_res.json().get("job_id") or sync_res.json()["sync_id"]

        for _ in range(30):
            status_res = await client.get("/api/v3/etl/status", params={"job_id": job_id}, headers=_admin_headers())
            assert status_res.status_code == 200
            st = status_res.json().get("status")
            if st in ("COMPLETED", "completed"):
                break
            await asyncio.sleep(0.15)
        assert status_res.json().get("status") in ("COMPLETED", "completed")

        dag_res = await client.post("/api/v3/etl/airflow/trigger-dag", json={"dag_id": "vision_etl"}, headers=_admin_headers())
        assert dag_res.status_code == 200
        assert dag_res.json()["triggered"] is True
