"""DDD-P3-01: Unit tests for expanded EventContractRegistry.

Tests all 8 Core events are registered with correct metadata.
"""
import pytest

from app.core.event_contract_registry import (
    EVENT_CONTRACTS,
    EventContract,
    EventContractError,
    enforce_event_contract,
)


# ── Registry Completeness Tests ──────────────────────────

class TestRegistryCompleteness:
    EXPECTED_EVENTS = [
        "PROCESS_INITIATED",
        "WORKITEM_COMPLETED",
        "WORKITEM_SELF_VERIFICATION_FAILED",
        "SAGA_COMPENSATION_COMPLETED",
        "WORKITEM_CREATED",
        "WORKITEM_CANCELLED",
        "CASE_STATUS_CHANGED",
        "WATCH_ALERT_TRIGGERED",
    ]

    def test_all_8_events_registered(self):
        assert len(EVENT_CONTRACTS) == 8

    @pytest.mark.parametrize("event_name", EXPECTED_EVENTS)
    def test_event_exists(self, event_name):
        assert event_name in EVENT_CONTRACTS

    @pytest.mark.parametrize("event_name", EXPECTED_EVENTS)
    def test_event_has_correct_owner(self, event_name):
        assert EVENT_CONTRACTS[event_name].owner_service == "core"

    @pytest.mark.parametrize("event_name", EXPECTED_EVENTS)
    def test_event_has_version(self, event_name):
        assert EVENT_CONTRACTS[event_name].version == "1.0.0"

    @pytest.mark.parametrize("event_name", EXPECTED_EVENTS)
    def test_event_has_payload_schema(self, event_name):
        contract = EVENT_CONTRACTS[event_name]
        assert contract.payload_schema.startswith("core/")
        assert "/v1" in contract.payload_schema

    @pytest.mark.parametrize("event_name", EXPECTED_EVENTS)
    def test_event_has_idempotency_key_rule(self, event_name):
        contract = EVENT_CONTRACTS[event_name]
        assert "event_type" in contract.idempotency_key_rule
        assert "aggregate_id" in contract.idempotency_key_rule


# ── P3-01 New Events Specific Tests ─────────────────────

class TestNewCoreEvents:
    def test_workitem_created_contract(self):
        c = EVENT_CONTRACTS["WORKITEM_CREATED"]
        assert c.payload_schema == "core/workitem_created/v1"
        assert c.idempotency_key_rule == "event_type:aggregate_id"

    def test_workitem_cancelled_contract(self):
        c = EVENT_CONTRACTS["WORKITEM_CANCELLED"]
        assert c.payload_schema == "core/workitem_cancelled/v1"
        assert c.idempotency_key_rule == "event_type:aggregate_id"

    def test_case_status_changed_contract(self):
        c = EVENT_CONTRACTS["CASE_STATUS_CHANGED"]
        assert c.payload_schema == "core/case_status_changed/v1"
        assert c.idempotency_key_rule == "event_type:aggregate_id:timestamp_ms"

    def test_watch_alert_triggered_contract(self):
        c = EVENT_CONTRACTS["WATCH_ALERT_TRIGGERED"]
        assert c.payload_schema == "core/watch_alert_triggered/v1"
        assert c.idempotency_key_rule == "event_type:aggregate_id:timestamp_ms"


# ── enforce_event_contract Tests ─────────────────────────

class TestEnforceEventContract:
    def test_enforce_enriches_payload(self):
        result = enforce_event_contract(
            event_type="PROCESS_INITIATED",
            payload={"proc_inst_id": "p1"},
            aggregate_id="agg-1",
        )
        assert "idempotency_key" in result
        assert "event_contract" in result
        ec = result["event_contract"]
        assert ec["event_name"] == "PROCESS_INITIATED"
        assert ec["owner_service"] == "core"
        assert ec["version"] == "1.0.0"

    def test_enforce_unregistered_event_raises(self):
        with pytest.raises(EventContractError) as exc_info:
            enforce_event_contract("NONEXISTENT", {}, "agg-1")
        assert exc_info.value.code == "EVENT_CONTRACT_NOT_REGISTERED"

    def test_enforce_version_mismatch_raises(self):
        with pytest.raises(EventContractError) as exc_info:
            enforce_event_contract(
                "PROCESS_INITIATED",
                {"event_contract_version": "2.0.0"},
                "agg-1",
            )
        assert exc_info.value.code == "EVENT_CONTRACT_VERSION_MISMATCH"

    def test_enforce_preserves_existing_idempotency_key(self):
        result = enforce_event_contract(
            "PROCESS_INITIATED",
            {"idempotency_key": "custom-key"},
            "agg-1",
        )
        assert result["idempotency_key"] == "custom-key"

    def test_enforce_generates_idempotency_key_if_missing(self):
        result = enforce_event_contract(
            "PROCESS_INITIATED",
            {},
            "agg-1",
        )
        assert result["idempotency_key"] == "PROCESS_INITIATED:agg-1"

    @pytest.mark.parametrize("event_name", [
        "WORKITEM_CREATED",
        "WORKITEM_CANCELLED",
        "CASE_STATUS_CHANGED",
        "WATCH_ALERT_TRIGGERED",
    ])
    def test_enforce_new_events(self, event_name):
        result = enforce_event_contract(
            event_type=event_name,
            payload={},
            aggregate_id="agg-test",
        )
        assert result["event_contract"]["event_name"] == event_name
