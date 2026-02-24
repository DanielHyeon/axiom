"""Core SynapseACL 단위 테스트.

Synapse API 응답 형식이 변경되어도 Core 내부 모델이 안정적으로 유지되는지 검증한다.
"""
import pytest

from app.infrastructure.external.synapse_acl import (
    IngestResult,
    OntologySearchResult,
    ProcessModelInfo,
    SynapseACL,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def acl():
    return SynapseACL(base_url="http://fake-synapse:8003")


# ---------------------------------------------------------------------------
# search_ontology 변환 테스트
# ---------------------------------------------------------------------------


class TestTranslateSearchResults:
    """Synapse 그래프 검색 응답 → OntologySearchResult 변환 검증."""

    def test_standard_response(self, acl: SynapseACL):
        raw = {
            "data": {
                "results": [
                    {
                        "id": "node-1",
                        "type": "Table",
                        "name": "creditors",
                        "score": 0.92,
                        "row_count": 1500,
                    },
                    {
                        "id": "node-2",
                        "type": "Column",
                        "label": "amount",
                        "score": 0.85,
                    },
                ]
            }
        }
        results = acl._translate_search_results(raw)

        assert len(results) == 2
        assert isinstance(results[0], OntologySearchResult)
        assert results[0].entity_id == "node-1"
        assert results[0].entity_type == "Table"
        assert results[0].label == "creditors"
        assert results[0].relevance_score == 0.92
        assert results[0].properties["row_count"] == 1500

        assert results[1].label == "amount"  # falls back to "label" key

    def test_nodes_key_fallback(self, acl: SynapseACL):
        """Synapse가 'results' 대신 'nodes' 키를 사용하는 경우."""
        raw = {
            "nodes": [
                {"id": "n1", "type": "Entity", "name": "test", "score": 0.5}
            ]
        }
        results = acl._translate_search_results(raw)
        assert len(results) == 1
        assert results[0].entity_id == "n1"

    def test_empty_response(self, acl: SynapseACL):
        assert acl._translate_search_results({}) == []
        assert acl._translate_search_results({"data": {}}) == []
        assert acl._translate_search_results({"data": {"results": []}}) == []

    def test_missing_id_skipped(self, acl: SynapseACL):
        """id가 없는 항목은 무시."""
        raw = {"data": {"results": [{"type": "Table", "name": "no_id"}]}}
        results = acl._translate_search_results(raw)
        assert len(results) == 0

    def test_non_dict_items_skipped(self, acl: SynapseACL):
        raw = {"data": {"results": ["string_item", None, 42]}}
        results = acl._translate_search_results(raw)
        assert len(results) == 0

    def test_default_values(self, acl: SynapseACL):
        raw = {"data": {"results": [{"id": "x"}]}}
        results = acl._translate_search_results(raw)
        assert results[0].entity_type == "unknown"
        assert results[0].label == ""
        assert results[0].relevance_score == 0.0


# ---------------------------------------------------------------------------
# get_process_model 변환 테스트
# ---------------------------------------------------------------------------


class TestTranslateProcessModel:
    """Synapse mining 모델 → ProcessModelInfo 변환 검증."""

    def test_standard_response(self, acl: SynapseACL):
        raw = {
            "data": {
                "id": "model-1",
                "activities": ["Start", "Review", "Approve", "End"],
                "transitions": [
                    {"source": "Start", "target": "Review", "count": 100},
                    {"source": "Review", "target": "Approve", "count": 85},
                ],
            }
        }
        result = acl._translate_process_model(raw)

        assert isinstance(result, ProcessModelInfo)
        assert result.model_id == "model-1"
        assert len(result.activities) == 4
        assert len(result.transitions) == 2
        assert result.transitions[0]["from"] == "Start"
        assert result.transitions[0]["to"] == "Review"
        assert result.transitions[0]["frequency"] == 100

    def test_edges_key_fallback(self, acl: SynapseACL):
        """Synapse가 'transitions' 대신 'edges' 키를 사용하는 경우."""
        raw = {
            "id": "model-2",
            "activities": ["A", "B"],
            "edges": [{"from": "A", "to": "B", "frequency": 50}],
        }
        result = acl._translate_process_model(raw)
        assert result.model_id == "model-2"
        assert result.transitions[0]["from"] == "A"
        assert result.transitions[0]["frequency"] == 50

    def test_empty_model(self, acl: SynapseACL):
        raw = {"data": {"id": "empty"}}
        result = acl._translate_process_model(raw)
        assert result.model_id == "empty"
        assert result.activities == []
        assert result.transitions == []


# ---------------------------------------------------------------------------
# ingest_event_log 변환 테스트
# ---------------------------------------------------------------------------


class TestTranslateIngestResult:
    """Synapse ingest 응답 → IngestResult 변환 검증."""

    def test_standard_response(self, acl: SynapseACL):
        raw = {
            "data": {
                "log_id": "log-abc",
                "status": "accepted",
                "message": "42 events ingested",
            }
        }
        result = acl._translate_ingest_result(raw)
        assert isinstance(result, IngestResult)
        assert result.log_id == "log-abc"
        assert result.status == "accepted"
        assert result.message == "42 events ingested"

    def test_id_key_fallback(self, acl: SynapseACL):
        raw = {"id": "log-xyz", "status": "ok"}
        result = acl._translate_ingest_result(raw)
        assert result.log_id == "log-xyz"

    def test_empty_response(self, acl: SynapseACL):
        result = acl._translate_ingest_result({})
        assert result.log_id == ""
        assert result.status == "accepted"  # default
