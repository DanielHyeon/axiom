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
    "PROCESS_INITIATED": EventContract(
        event_name="PROCESS_INITIATED",
        owner_service="core",
        version="1.0.0",
        payload_schema="core/process_initiated/v1",
        idempotency_key_rule="event_type:aggregate_id",
    ),
    "WORKITEM_COMPLETED": EventContract(
        event_name="WORKITEM_COMPLETED",
        owner_service="core",
        version="1.0.0",
        payload_schema="core/workitem_completed/v1",
        idempotency_key_rule="event_type:aggregate_id",
    ),
    "WORKITEM_SELF_VERIFICATION_FAILED": EventContract(
        event_name="WORKITEM_SELF_VERIFICATION_FAILED",
        owner_service="core",
        version="1.0.0",
        payload_schema="core/workitem_self_verification_failed/v1",
        idempotency_key_rule="event_type:aggregate_id",
    ),
}


def enforce_event_contract(event_type: str, payload: dict[str, Any], aggregate_id: str) -> dict[str, Any]:
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
