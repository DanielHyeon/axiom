"""Vision 서비스 이벤트 계약 레지스트리 (DDD-P3-01).

Vision이 소유(발행)하는 도메인 이벤트 2종의 스키마·버전·멱등성 규칙을 정의한다.
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
    "WHATIF_SIMULATION_COMPLETED": EventContract(
        event_name="WHATIF_SIMULATION_COMPLETED",
        owner_service="vision",
        version="1.0.0",
        payload_schema="vision/whatif_simulation_completed/v1",
        idempotency_key_rule="event_type:aggregate_id",
    ),
    "ROOT_CAUSE_DETECTED": EventContract(
        event_name="ROOT_CAUSE_DETECTED",
        owner_service="vision",
        version="1.0.0",
        payload_schema="vision/root_cause_detected/v1",
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
