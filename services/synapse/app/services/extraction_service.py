import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


TARGET_ENTITY_TYPES = [
    "COMPANY",
    "PERSON",
    "DEPARTMENT",
    "AMOUNT",
    "DATE",
    "ASSET_TYPE",
    "PROCESS_STEP",
    "METRIC",
    "CONTRACT",
    "FINANCIAL_METRIC",
    "REFERENCE",
]


class ExtractionDomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_value(seed: str, idx: int, low: float = 0.4, high: float = 0.99) -> float:
    digest = hashlib.sha256(f"{seed}:{idx}".encode()).hexdigest()
    num = int(digest[:8], 16) / 0xFFFFFFFF
    return round(low + (high - low) * num, 3)


@dataclass
class ExtractionDocState:
    tenant_id: str
    case_id: str
    doc_id: str
    task_id: str
    status: str
    options: dict[str, Any]
    created_at: str
    started_at: str
    updated_at: str
    steps: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    attempts: int
    auto_commit_threshold: float


class ExtractionService:
    def __init__(self) -> None:
        self._docs: dict[str, ExtractionDocState] = {}
        self._entity_to_doc: dict[str, str] = {}

    def clear(self) -> None:
        self._docs.clear()
        self._entity_to_doc.clear()

    def _key(self, tenant_id: str, doc_id: str) -> str:
        return f"{tenant_id}:{doc_id}"

    def _get(self, tenant_id: str, doc_id: str) -> ExtractionDocState:
        item = self._docs.get(self._key(tenant_id, doc_id))
        if not item:
            raise ExtractionDomainError(404, "DOCUMENT_NOT_FOUND", "document extraction not found")
        return item

    def _validate_options(self, options: dict[str, Any]) -> None:
        threshold = float(options.get("auto_commit_threshold", 0.75))
        if threshold < 0 or threshold > 1:
            raise ExtractionDomainError(400, "INVALID_THRESHOLD", "auto_commit_threshold must be in [0,1]")
        types = options.get("target_entity_types", TARGET_ENTITY_TYPES)
        if not isinstance(types, list) or not types:
            raise ExtractionDomainError(400, "INVALID_ENTITY_TYPES", "target_entity_types must be non-empty list")
        for item in types:
            if item not in TARGET_ENTITY_TYPES:
                raise ExtractionDomainError(400, "INVALID_ENTITY_TYPES", f"unsupported type: {item}")

    def _generate_entities_and_relations(
        self, doc_id: str, threshold: float, target_types: list[str]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        entities: list[dict[str, Any]] = []
        for idx, ent_type in enumerate(target_types[:6]):
            confidence = _stable_value(doc_id, idx)
            entity_id = f"entity-{uuid.uuid4()}"
            status = "committed" if confidence >= threshold else "pending_review"
            entity = {
                "id": entity_id,
                "text": f"{ent_type}-{idx}",
                "entity_type": ent_type,
                "normalized_value": f"{ent_type}-normalized-{idx}",
                "confidence": confidence,
                "ontology_mapping": (
                    {
                        "layer": "resource" if ent_type in {"COMPANY", "PERSON", "DEPARTMENT"} else "measure",
                        "label": f"{ent_type}:Node",
                        "neo4j_node_id": f"node-{uuid.uuid4()}",
                    }
                    if status == "committed"
                    else None
                ),
                "status": status,
                "source_chunk": idx + 1,
                "context": f"document {doc_id} context chunk {idx + 1}",
                "review_reason": None,
            }
            entities.append(entity)
            self._entity_to_doc[entity_id] = doc_id

        relations: list[dict[str, Any]] = []
        for idx in range(max(0, len(entities) - 1)):
            confidence = _stable_value(doc_id + "-rel", idx)
            status = "committed" if confidence >= threshold else "pending_review"
            relations.append(
                {
                    "id": f"rel-{uuid.uuid4()}",
                    "subject": entities[idx]["id"],
                    "predicate": "RELATED_TO",
                    "object": entities[idx + 1]["id"],
                    "confidence": confidence,
                    "ontology_mapping": {
                        "relation_type": "LINKED",
                        "source_layer": "resource",
                        "target_layer": "process",
                    },
                    "status": status,
                    "evidence": f"{entities[idx]['text']} -> {entities[idx + 1]['text']}",
                }
            )
        return entities, relations

    def start_extraction(self, tenant_id: str, doc_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        case_id = payload.get("case_id")
        if not case_id:
            raise ExtractionDomainError(400, "MISSING_CASE_ID", "case_id is required")
        options = payload.get("options", {})
        self._validate_options(options)
        auto_threshold = float(options.get("auto_commit_threshold", 0.75))
        target_types = options.get("target_entity_types", TARGET_ENTITY_TYPES)

        task_id = f"task-{uuid.uuid4()}"
        now = _utcnow()
        entities, relations = self._generate_entities_and_relations(doc_id, auto_threshold, target_types)
        steps = [
            {"name": "text_extraction", "status": "completed", "duration_ms": 1200},
            {"name": "chunking", "status": "completed", "duration_ms": 150, "chunk_count": max(1, len(entities))},
            {"name": "ner_extraction", "status": "completed", "progress": "done"},
            {"name": "relation_extraction", "status": "completed"},
            {"name": "ontology_mapping", "status": "completed"},
            {"name": "neo4j_commit", "status": "completed"},
            {"name": "hitl_queue", "status": "completed"},
        ]

        state = ExtractionDocState(
            tenant_id=tenant_id,
            case_id=str(case_id),
            doc_id=doc_id,
            task_id=task_id,
            status="completed",
            options=options,
            created_at=now,
            started_at=now,
            updated_at=now,
            steps=steps,
            entities=entities,
            relations=relations,
            attempts=1,
            auto_commit_threshold=auto_threshold,
        )
        self._docs[self._key(tenant_id, doc_id)] = state
        return {
            "task_id": task_id,
            "doc_id": doc_id,
            "case_id": state.case_id,
            "status": "queued",
            "created_at": now,
            "estimated_duration_seconds": 120,
        }

    def get_status(self, tenant_id: str, doc_id: str) -> dict[str, Any]:
        state = self._get(tenant_id, doc_id)
        return {
            "task_id": state.task_id,
            "doc_id": state.doc_id,
            "status": state.status,
            "progress": {"current_step": "hitl_queue", "steps": state.steps},
            "started_at": state.started_at,
            "updated_at": state.updated_at,
        }

    def get_result(
        self,
        tenant_id: str,
        doc_id: str,
        min_confidence: float = 0.0,
        include_rejected: bool = False,
        status: str = "all",
    ) -> dict[str, Any]:
        state = self._get(tenant_id, doc_id)
        if min_confidence < 0 or min_confidence > 1:
            raise ExtractionDomainError(400, "INVALID_CONFIDENCE", "min_confidence must be in [0,1]")
        status_filter = status
        if status_filter not in {"all", "committed", "pending_review", "rejected", "reverted"}:
            raise ExtractionDomainError(400, "INVALID_STATUS_FILTER", "unsupported status filter")

        entities = []
        for item in state.entities:
            if item["confidence"] < min_confidence:
                continue
            if status_filter != "all" and item["status"] != status_filter:
                continue
            if not include_rejected and item["status"] == "rejected":
                continue
            entities.append(item)

        relations = []
        valid_ids = {entity["id"] for entity in entities}
        for rel in state.relations:
            if rel["confidence"] < min_confidence:
                continue
            if rel["subject"] not in valid_ids or rel["object"] not in valid_ids:
                continue
            if status_filter != "all" and rel["status"] != status_filter:
                continue
            if not include_rejected and rel["status"] == "rejected":
                continue
            relations.append(rel)

        summary = {
            "total_entities": len(state.entities),
            "total_relations": len(state.relations),
            "auto_committed": sum(1 for e in state.entities if e["status"] == "committed"),
            "pending_review": sum(1 for e in state.entities if e["status"] == "pending_review"),
            "rejected": sum(1 for e in state.entities if e["status"] == "rejected"),
            "average_confidence": round(
                sum(item["confidence"] for item in state.entities) / max(1, len(state.entities)), 3
            ),
        }
        return {
            "task_id": state.task_id,
            "doc_id": state.doc_id,
            "extraction_summary": summary,
            "entities": entities,
            "relations": relations,
        }

    def _find_entity(self, tenant_id: str, entity_id: str) -> tuple[ExtractionDocState, dict[str, Any]]:
        doc_id = self._entity_to_doc.get(entity_id)
        if not doc_id:
            raise ExtractionDomainError(404, "ENTITY_NOT_FOUND", "entity not found")
        state = self._get(tenant_id, doc_id)
        for entity in state.entities:
            if entity["id"] == entity_id:
                return state, entity
        raise ExtractionDomainError(404, "ENTITY_NOT_FOUND", "entity not found")

    def confirm_entity(self, tenant_id: str, entity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        action = payload.get("action")
        reviewer_id = payload.get("reviewer_id")
        if action not in {"approve", "modify", "reject"}:
            raise ExtractionDomainError(400, "INVALID_ACTION", "action must be approve|modify|reject")
        if not reviewer_id:
            raise ExtractionDomainError(400, "MISSING_REVIEWER", "reviewer_id is required")
        if action == "reject" and not payload.get("reason"):
            raise ExtractionDomainError(400, "MISSING_REASON", "reason is required for reject")
        if action == "modify" and not payload.get("modifications"):
            raise ExtractionDomainError(400, "MISSING_MODIFICATIONS", "modifications is required for modify")

        state, entity = self._find_entity(tenant_id, entity_id)
        if action == "approve":
            entity["status"] = "committed"
        elif action == "modify":
            mods = payload["modifications"]
            for key in ["entity_type", "normalized_value", "ontology_mapping"]:
                if key in mods:
                    entity[key] = mods[key]
            entity["status"] = "committed"
        else:
            entity["status"] = "rejected"
            entity["review_reason"] = payload.get("reason")
        state.updated_at = _utcnow()
        return {
            "entity_id": entity_id,
            "action": action,
            "status": entity["status"],
            "neo4j_node_id": entity.get("ontology_mapping", {}).get("neo4j_node_id")
            if entity.get("ontology_mapping")
            else None,
            "reviewed_at": state.updated_at,
            "reviewer_id": reviewer_id,
        }

    def batch_review(self, tenant_id: str, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        reviews = payload.get("reviews")
        reviewer_id = payload.get("reviewer_id")
        if not isinstance(reviews, list) or not reviews:
            raise ExtractionDomainError(400, "MISSING_REVIEWS", "reviews is required")
        if not reviewer_id:
            raise ExtractionDomainError(400, "MISSING_REVIEWER", "reviewer_id is required")

        results = []
        for review in reviews:
            entity_id = review.get("entity_id")
            if not entity_id:
                raise ExtractionDomainError(400, "MISSING_ENTITY_ID", "entity_id is required")
            state, _ = self._find_entity(tenant_id, entity_id)
            if state.case_id != case_id:
                raise ExtractionDomainError(404, "ENTITY_NOT_IN_CASE", "entity is not in case")
            merged = dict(review)
            merged["reviewer_id"] = reviewer_id
            results.append(self.confirm_entity(tenant_id, entity_id, merged))

        return {
            "case_id": case_id,
            "reviewer_id": reviewer_id,
            "processed_count": len(results),
            "results": results,
        }

    def review_queue(self, tenant_id: str, case_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        pending = []
        for item in self._docs.values():
            if item.tenant_id != tenant_id or item.case_id != case_id:
                continue
            for entity in item.entities:
                if entity["status"] == "pending_review":
                    pending.append(
                        {
                            "doc_id": item.doc_id,
                            "entity_id": entity["id"],
                            "entity_type": entity["entity_type"],
                            "text": entity["text"],
                            "confidence": entity["confidence"],
                            "context": entity["context"],
                        }
                    )
        pending.sort(key=lambda x: x["confidence"])
        safe_limit = min(max(limit, 1), 200)
        safe_offset = max(offset, 0)
        return {
            "case_id": case_id,
            "total": len(pending),
            "items": pending[safe_offset : safe_offset + safe_limit],
        }

    def retry(self, tenant_id: str, doc_id: str) -> dict[str, Any]:
        state = self._get(tenant_id, doc_id)
        state.attempts += 1
        state.task_id = f"task-{uuid.uuid4()}"
        state.status = "completed"
        state.updated_at = _utcnow()
        return {
            "task_id": state.task_id,
            "doc_id": doc_id,
            "status": "queued",
            "attempt": state.attempts,
            "created_at": state.updated_at,
        }

    def revert(self, tenant_id: str, doc_id: str) -> dict[str, Any]:
        state = self._get(tenant_id, doc_id)
        reverted_entities = 0
        reverted_relations = 0
        for entity in state.entities:
            if entity["status"] != "reverted":
                entity["status"] = "reverted"
                reverted_entities += 1
        for relation in state.relations:
            if relation["status"] != "reverted":
                relation["status"] = "reverted"
                reverted_relations += 1
        state.status = "completed"
        state.updated_at = _utcnow()
        return {
            "doc_id": doc_id,
            "status": "reverted",
            "reverted": {
                "entities": reverted_entities,
                "relations": reverted_relations,
            },
            "reverted_at": state.updated_at,
        }


extraction_service = ExtractionService()
