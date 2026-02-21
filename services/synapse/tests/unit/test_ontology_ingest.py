import pytest

from app.graph.ontology_ingest import OntologyIngestor


@pytest.mark.asyncio
async def test_ontology_ingest_supported_event():
    ingestor = OntologyIngestor()
    out = await ingestor.process_event("case.process.started", {"case_id": "c1", "proc_inst_id": "p1"})
    assert out["accepted"] is True
    assert out["case_id"] == "c1"
    assert len(out["entities"]) == 2
    assert out["relations"][0]["type"] == "HAS_PROCESS"


@pytest.mark.asyncio
async def test_ontology_ingest_unsupported_event():
    ingestor = OntologyIngestor()
    out = await ingestor.process_event("case.unknown", {"case_id": "c1"})
    assert out["accepted"] is False
    assert out["reason"] == "unsupported_event_type"
