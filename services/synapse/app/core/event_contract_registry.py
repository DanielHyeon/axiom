"""Synapse 서비스 이벤트 계약 레지스트리 (DDD-P3-01).

Synapse가 소유(발행)하는 도메인 이벤트 4종의 스키마·버전·멱등성 규칙을 정의한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventContract:
    event_name: str
    owner_service: str
    version: str
    payload_schema: str
    idempotency_key_rule: str


class EventContractError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


EVENT_CONTRACTS: dict[str, EventContract] = {
    "ONTOLOGY_NODE_CREATED": EventContract(
        event_name="ONTOLOGY_NODE_CREATED",
        owner_service="synapse",
        version="1.0.0",
        payload_schema="synapse/ontology_node_created/v1",
        idempotency_key_rule="event_type:aggregate_id:timestamp_ms",
    ),
    "ONTOLOGY_NODE_UPDATED": EventContract(
        event_name="ONTOLOGY_NODE_UPDATED",
        owner_service="synapse",
        version="1.0.0",
        payload_schema="synapse/ontology_node_updated/v1",
        idempotency_key_rule="event_type:aggregate_id:timestamp_ms",
    ),
    "MINING_DISCOVERY_COMPLETED": EventContract(
        event_name="MINING_DISCOVERY_COMPLETED",
        owner_service="synapse",
        version="1.0.0",
        payload_schema="synapse/mining_discovery_completed/v1",
        idempotency_key_rule="event_type:aggregate_id",
    ),
    "CONFORMANCE_CHECK_COMPLETED": EventContract(
        event_name="CONFORMANCE_CHECK_COMPLETED",
        owner_service="synapse",
        version="1.0.0",
        payload_schema="synapse/conformance_check_completed/v1",
        idempotency_key_rule="event_type:aggregate_id",
    ),
}


def enforce_event_contract(event_type: str, payload: dict[str, Any], aggregate_id: str) -> dict[str, Any]:
    """이벤트 페이로드에 계약 메타를 보강하고 버전·멱등키를 검증한다."""
    contract = EVENT_CONTRACTS.get(event_type)
    if contract is None:
        raise EventContractError("EVENT_CONTRACT_NOT_REGISTERED", f"event_type '{event_type}' is not registered")

    requested_version = str(payload.get("event_contract_version") or contract.version)
    if requested_version != contract.version:
        raise EventContractError(
            "EVENT_CONTRACT_VERSION_MISMATCH",
            f"event_type '{event_type}' expects version {contract.version}, got {requested_version}",
        )

    idempotency_key = str(payload.get("idempotency_key") or f"{event_type}:{aggregate_id}").strip()
    if not idempotency_key:
        raise EventContractError("EVENT_IDEMPOTENCY_KEY_REQUIRED", "idempotency_key is required")

    enriched_payload = dict(payload)
    enriched_payload["idempotency_key"] = idempotency_key
    enriched_payload["event_contract"] = {
        "event_name": contract.event_name,
        "owner_service": contract.owner_service,
        "version": contract.version,
        "payload_schema": contract.payload_schema,
        "idempotency_key_rule": contract.idempotency_key_rule,
    }
    return enriched_payload
