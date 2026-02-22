from __future__ import annotations

from typing import Any


class IngestionContractError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def validate_4source_ingestion_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("ingestion_metadata")
    if not isinstance(metadata, dict):
        raise IngestionContractError(
            "INGESTION_LINEAGE_REQUIRED",
            "ingestion_metadata is required",
        )

    source_origin = str(metadata.get("source_origin") or "").strip()
    lineage_path = metadata.get("lineage_path")
    idempotency_key = str(metadata.get("idempotency_key") or "").strip()

    if not source_origin:
        raise IngestionContractError("INGESTION_LINEAGE_REQUIRED", "source_origin is required")
    if not isinstance(lineage_path, list) or not lineage_path or not all(str(item).strip() for item in lineage_path):
        raise IngestionContractError("INGESTION_LINEAGE_REQUIRED", "lineage_path must be a non-empty string array")
    if not idempotency_key:
        raise IngestionContractError("INGESTION_LINEAGE_REQUIRED", "idempotency_key is required")

    return {
        "source_origin": source_origin,
        "lineage_path": [str(item).strip() for item in lineage_path],
        "idempotency_key": idempotency_key,
        "source_family": str(metadata.get("source_family") or "").strip() or None,
        "source_ref": str(metadata.get("source_ref") or "").strip() or None,
    }
