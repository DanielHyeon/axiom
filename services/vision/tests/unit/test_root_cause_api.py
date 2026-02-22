import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.vision_runtime import vision_runtime


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
