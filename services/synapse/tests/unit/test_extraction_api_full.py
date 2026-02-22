import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.extraction_service import extraction_service

AUTH = {"Authorization": "Bearer local-oracle-token"}

INGESTION_META = {
    "ingestion_metadata": {
        "source_origin": "git://repo/commit/abc123",
        "lineage_path": ["S2", "docs", "doc-1"],
        "idempotency_key": "ingest-doc-1-v1",
        "source_family": "legacy_code",
        "source_ref": "doc-1",
    }
}


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def setup_function():
    extraction_service.clear()


@pytest.mark.asyncio
async def test_extraction_full_flow(ac: AsyncClient):
    payload = {
        "case_id": "case-100",
        **INGESTION_META,
        "options": {
            "extract_entities": True,
            "extract_relations": True,
            "auto_map_ontology": True,
            "auto_commit_threshold": 0.75,
            "target_entity_types": ["COMPANY", "PERSON", "DEPARTMENT", "AMOUNT"],
        },
    }
    start = await ac.post(
        "/api/v3/synapse/extraction/documents/doc-1/extract-ontology",
        json=payload,
        headers=AUTH,
    )
    assert start.status_code == 202
    assert start.json()["data"]["status"] == "queued"

    status_resp = await ac.get("/api/v3/synapse/extraction/documents/doc-1/ontology-status", headers=AUTH)
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["status"] == "completed"

    result_resp = await ac.get(
        "/api/v3/synapse/extraction/documents/doc-1/ontology-result",
        params={"min_confidence": 0.0},
        headers=AUTH,
    )
    assert result_resp.status_code == 200
    result_data = result_resp.json()["data"]
    assert result_data["extraction_summary"]["total_entities"] > 0
    assert len(result_data["entities"]) > 0

    queue = await ac.get("/api/v3/synapse/extraction/cases/case-100/review-queue", headers=AUTH)
    assert queue.status_code == 200
    assert "items" in queue.json()["data"]

    pending = None
    for item in result_data["entities"]:
        if item["status"] == "pending_review":
            pending = item
            break
    assert pending is not None

    reject = await ac.put(
        f"/api/v3/synapse/extraction/ontology/{pending['id']}/confirm",
        json={"action": "reject", "reason": "오인식", "reviewer_id": "reviewer-1"},
        headers=AUTH,
    )
    assert reject.status_code == 200
    assert reject.json()["data"]["status"] == "rejected"

    result_with_rejected = await ac.get(
        "/api/v3/synapse/extraction/documents/doc-1/ontology-result",
        params={"include_rejected": "true"},
        headers=AUTH,
    )
    assert result_with_rejected.status_code == 200
    rejected_ids = {
        ent["id"] for ent in result_with_rejected.json()["data"]["entities"] if ent["status"] == "rejected"
    }
    assert pending["id"] in rejected_ids

    batch_payload = {
        "reviews": [{"entity_id": pending["id"], "action": "approve"}],
        "reviewer_id": "reviewer-2",
    }
    batch = await ac.post(
        "/api/v3/synapse/extraction/cases/case-100/ontology/review",
        json=batch_payload,
        headers=AUTH,
    )
    assert batch.status_code == 200
    assert batch.json()["data"]["processed_count"] == 1

    retry = await ac.post("/api/v3/synapse/extraction/documents/doc-1/retry", headers=AUTH)
    assert retry.status_code == 202
    assert retry.json()["data"]["status"] == "queued"

    revert = await ac.post("/api/v3/synapse/extraction/documents/doc-1/revert-extraction", headers=AUTH)
    assert revert.status_code == 200
    assert revert.json()["data"]["status"] == "reverted"


@pytest.mark.asyncio
async def test_extraction_validation_errors(ac: AsyncClient):
    bad_start = await ac.post(
        "/api/v3/synapse/extraction/documents/doc-2/extract-ontology",
        json={"options": {"auto_commit_threshold": 0.75}},
        headers=AUTH,
    )
    assert bad_start.status_code == 400
    assert bad_start.json()["detail"]["code"] == "MISSING_CASE_ID"

    start = await ac.post(
        "/api/v3/synapse/extraction/documents/doc-2/extract-ontology",
        json={
            "case_id": "case-200",
            **INGESTION_META,
            "options": {"auto_commit_threshold": 0.75},
        },
        headers=AUTH,
    )
    assert start.status_code == 202

    missing_lineage = await ac.post(
        "/api/v3/synapse/extraction/documents/doc-3/extract-ontology",
        json={"case_id": "case-201", "options": {"auto_commit_threshold": 0.75}},
        headers=AUTH,
    )
    assert missing_lineage.status_code == 422
    assert missing_lineage.json()["detail"]["code"] == "INGESTION_LINEAGE_REQUIRED"

    result = await ac.get(
        "/api/v3/synapse/extraction/documents/doc-2/ontology-result",
        params={"status": "unknown"},
        headers=AUTH,
    )
    assert result.status_code == 400
    assert result.json()["detail"]["code"] == "INVALID_STATUS_FILTER"
