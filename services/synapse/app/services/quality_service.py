"""O5-2: Ontology Data Quality Service — orphan detection, confidence metrics, coverage analysis."""
from typing import Any

import structlog

logger = structlog.get_logger()


class OntologyQualityService:
    """온톨로지 품질 리포트 생성."""

    def __init__(self, ontology_service) -> None:
        self._ontology = ontology_service

    async def generate_report(self, case_id: str) -> dict[str, Any]:
        data = await self._ontology.get_case_ontology(case_id=case_id, limit=10000)
        nodes: list[dict[str, Any]] = data.get("nodes", [])
        relations: list[dict[str, Any]] = data.get("relations", [])

        # Build adjacency set of connected node IDs
        connected: set[str] = set()
        for r in relations:
            connected.add(r["source_id"])
            connected.add(r["target_id"])

        orphans = [n for n in nodes if n["id"] not in connected]
        unverified = [
            n for n in nodes if not n.get("properties", {}).get("verified")
        ]
        no_desc = [
            n for n in nodes if not n.get("properties", {}).get("description")
        ]

        # Duplicate name detection
        name_counts: dict[str, int] = {}
        for n in nodes:
            name = n.get("properties", {}).get("name", "")
            if name:
                name_counts[name] = name_counts.get(name, 0) + 1
        duplicates = {k: v for k, v in name_counts.items() if v > 1}

        # Coverage by layer
        layers: dict[str, dict[str, int]] = {}
        for n in nodes:
            layer = n.get("layer", "unknown")
            if layer not in layers:
                layers[layer] = {"total": 0, "verified": 0, "orphan": 0}
            layers[layer]["total"] += 1
            if n.get("properties", {}).get("verified"):
                layers[layer]["verified"] += 1
            if n["id"] not in connected:
                layers[layer]["orphan"] += 1

        report = {
            "orphan_count": len(orphans),
            "low_confidence_count": len(unverified),
            "missing_description": len(no_desc),
            "duplicate_names": len(duplicates),
            "duplicate_details": duplicates,
            "total_nodes": len(nodes),
            "total_relations": len(relations),
            "coverage_by_layer": layers,
        }

        logger.info("quality_report_generated", case_id=case_id, **{
            k: v for k, v in report.items() if k != "coverage_by_layer" and k != "duplicate_details"
        })
        return report
