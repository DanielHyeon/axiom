import pytest
from app.extraction.ner_extractor import ExtractedAmount, ExtractedCompany, ExtractedPerson
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

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

def test_mining_api_conformance_check_queued():
    # Pass service token to bypass tenant check
    res = client.post(
        "/api/v3/synapse/process-mining/conformance",
        json={"log_id": "test-log-123", "reference_model": {}},
        headers={"Authorization": "Bearer local-oracle-token"}
    )
    assert res.status_code == 200
    assert "task_id" in res.json()["data"]
    assert res.json()["data"]["status"] == "queued"
