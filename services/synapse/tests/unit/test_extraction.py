import pytest
import pytest_asyncio
from app.extraction.ner_extractor import ExtractedAmount, ExtractedCompany
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.event_log_service import event_log_service
from app.services.process_mining_service import process_mining_service


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def setup_function():
    event_log_service.clear()
    process_mining_service.clear()

def test_amount_normalization():
    # Test valid korean strings parsed properly within pydantic
    amount = ExtractedAmount(raw_text="100억원", normalized_amount="10000000000", confidence=0.99)
    assert amount.normalized_amount == 10000000000

    amount2 = ExtractedAmount(raw_text="50만원", normalized_amount="500000", confidence=0.88)
    assert amount2.normalized_amount == 500000

def test_company_boundary():
    company = ExtractedCompany(name="Axiom Corp", confidence=0.75)
    assert company.confidence == 0.75
    assert company.type == "COMPANY"

@pytest.mark.asyncio
async def test_mining_api_conformance_check_queued(ac: AsyncClient):
    exported = await ac.post(
        "/api/v3/synapse/event-logs/export-bpm",
        json={
            "case_id": "case-1",
            "events": [
                {"case_id": "c-1", "activity": "A", "timestamp": "2024-01-01T00:00:00Z"},
                {"case_id": "c-1", "activity": "B", "timestamp": "2024-01-01T01:00:00Z"},
            ],
        },
        headers={"Authorization": "Bearer local-oracle-token"},
    )
    assert exported.status_code == 202
    log_id = exported.json()["data"]["log_id"]

    res = await ac.post(
        "/api/v3/synapse/process-mining/conformance",
        json={
            "case_id": "case-1",
            "log_id": log_id,
            "reference_model": {"type": "eventstorming", "model_id": "es-1"},
        },
        headers={"Authorization": "Bearer local-oracle-token"},
    )
    assert res.status_code == 202
    assert "task_id" in res.json()["data"]
    assert res.json()["data"]["status"] == "queued"
