"""Phase V1 Analytics API v3 계약·에러 코드 검증."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def client():
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "mock_token"},
    )


@pytest.mark.asyncio
async def test_summary_200(client):
    r = await client.get("/api/v3/analytics/summary")
    assert r.status_code == 200
    j = r.json()
    assert "period" in j and "kpis" in j and "computed_at" in j
    assert "total_cases" in j["kpis"] and "active_cases" in j["kpis"]


@pytest.mark.asyncio
async def test_summary_invalid_period_400(client):
    r = await client.get("/api/v3/analytics/summary", params={"period": "INVALID"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_PERIOD"
    assert "유효하지 않은 기간" in r.json()["detail"]["message"]


@pytest.mark.asyncio
async def test_stakeholders_distribution_missing_400(client):
    r = await client.get("/api/v3/analytics/stakeholders/distribution")
    assert r.status_code == 400  # distribution_by missing → INVALID_DISTRIBUTION_BY


@pytest.mark.asyncio
async def test_stakeholders_distribution_invalid_400(client):
    r = await client.get(
        "/api/v3/analytics/stakeholders/distribution",
        params={"distribution_by": "invalid_kind"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_DISTRIBUTION_BY"


@pytest.mark.asyncio
async def test_stakeholders_distribution_valid_200(client):
    r = await client.get(
        "/api/v3/analytics/stakeholders/distribution",
        params={"distribution_by": "stakeholder_type"},
    )
    assert r.status_code == 200
    assert "distribution_by" in r.json() and "segments" in r.json()


@pytest.mark.asyncio
async def test_financial_summary_not_found_404(client):
    r = await client.get(
        "/api/v3/analytics/cases/00000000-0000-0000-0000-000000000000/financial-summary"
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "CASE_NOT_FOUND"
    assert "사건을 찾을 수 없습니다" in r.json()["detail"]["message"]


@pytest.mark.asyncio
async def test_cases_trend_200(client):
    r = await client.get("/api/v3/analytics/cases/trend")
    assert r.status_code == 200
    assert "granularity" in r.json() and "series" in r.json()


@pytest.mark.asyncio
async def test_performance_trend_200(client):
    r = await client.get("/api/v3/analytics/performance/trend")
    assert r.status_code == 200
    assert "granularity" in r.json() and "series" in r.json()


@pytest.mark.asyncio
async def test_dashboards_200(client):
    r = await client.get("/api/v3/analytics/dashboards")
    assert r.status_code == 200
    assert "dashboards" in r.json()
