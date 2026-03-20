import re
import uuid
import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger()
_ALNUM_UNDERSCORE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# ── 유효한 온톨로지 레이어 목록 (5-Layer: driver 추가) ──
VALID_LAYERS = {"kpi", "measure", "process", "resource", "driver"}

# ── 허용된 Neo4j 관계 타입 (Cypher injection 방지) ──
ALLOWED_REL_TYPES = {
    "DERIVED_FROM", "OBSERVED_IN", "PRECEDES", "SUPPORTS", "USES",
    "CAUSES", "INFLUENCES", "RELATED_TO",
    "CONTAINS", "OPERATES", "GENERATES", "BELONGS_TO", "MONITORS", "TRIGGERS",
    "MEASURED_AS", "EXECUTES", "PRODUCES", "USED_WHEN",
    "UPDATED_BY", "PREDICTED_BY", "LAGS", "TRACEABLE_TO",
    "READS_FIELD", "PREDICTS_FIELD", "HAS_BEHAVIOR",
    "DEFINES", "PARTICIPATES_IN",
}

# ── 유효한 관계 방향 ──
VALID_DIRECTIONS = {"positive", "negative"}

# ── 유효한 분석 방법 ──
VALID_METHODS = {"granger", "correlation", "decomposition", "manual", "partial", "composite"}


def _safe_graph_name(value: str, default: str) -> str:
    candidate = (value or "").strip()
    return candidate if _ALNUM_UNDERSCORE.match(candidate) else default


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_falsy_safe(payload: dict, properties: dict, key: str) -> Any:
    """
    falsy-value 안전 추출 (0.0, 0 허용).
    CRITICAL: payload.get("weight") or properties.get("weight") 패턴은
    0.0을 무시하므로 'in' 연산자로 명시적 존재 검사를 수행한다.
    """
    if key in payload:
        return payload[key]
    if key in properties:
        return properties[key]
    return None


class OntologyService:
    def __init__(self, neo4j_client):
        self._neo4j = neo4j_client
        self._case_nodes: dict[str, dict[str, dict[str, Any]]] = {}
        self._case_relations: dict[str, dict[str, dict[str, Any]]] = {}
        self._node_case_index: dict[str, str] = {}
        self._relation_case_index: dict[str, str] = {}

    def clear(self) -> None:
        self._case_nodes.clear()
        self._case_relations.clear()
        self._node_case_index.clear()
        self._relation_case_index.clear()

    def get_case_id_for_node(self, node_id: str) -> str | None:
        """노드가 속한 case_id를 반환 — API 레이어에서 사용"""
        return self._node_case_index.get(node_id)

    def _nodes(self, case_id: str) -> dict[str, dict[str, Any]]:
        return self._case_nodes.setdefault(case_id, {})

    def _relations(self, case_id: str) -> dict[str, dict[str, Any]]:
        return self._case_relations.setdefault(case_id, {})

    # ── Neo4j 동기화 ────────────────────────────────────────────

    # Neo4j 노드 라벨 허용 목록
    ALLOWED_LABELS = {"Kpi", "Measure", "Process", "Resource", "Driver", "Entity"}
    # properties에서 제거할 예약 키 (MERGE 키와 충돌 방지)
    _RESERVED_PROPERTY_KEYS = {"case_id", "node_id", "model_id", "id"}

    async def _run_neo4j_query(
        self,
        query: str,
        params: dict[str, Any],
        *,
        timeout: float = 0.8,
        error_context: str = "neo4j_query",
    ) -> None:
        """Neo4j 세션에서 쿼리를 실행한다. 실패 시 경고 로그만 남긴다."""
        try:
            async with self._neo4j.session() as session:
                await asyncio.wait_for(
                    session.run(query, **params),
                    timeout=timeout,
                )
        except Exception as exc:
            logger.warning(f"{error_context}_failed", error=str(exc), **{
                k: v for k, v in params.items()
                if k in ("case_id", "node_id", "relation_id", "model_id", "link_id")
            })

    async def _sync_node_to_neo4j(self, case_id: str, node: dict[str, Any]) -> None:
        """온톨로지 노드를 Neo4j에 동기화한다."""
        label = _safe_graph_name(str(node.get("labels", ["Entity"])[0]), "Entity")
        # 라벨 허용 목록 검증 — 미허용 시 Entity로 폴백
        if label not in self.ALLOWED_LABELS:
            label = "Entity"
        properties = {
            k: v for k, v in (node.get("properties") or {}).items()
            if k not in self._RESERVED_PROPERTY_KEYS
        }
        await self._run_neo4j_query(
            f"""
            MERGE (n:{label} {{case_id: $case_id, node_id: $node_id}})
            SET n += $properties
            """,
            {"case_id": case_id, "node_id": node["id"], "properties": properties},
            error_context="ontology_node_sync",
        )

    async def _sync_relation_to_neo4j(self, case_id: str, rel: dict[str, Any]) -> None:
        """
        관계를 Neo4j에 동기화.
        properties dict에 weight/lag/confidence 등이 포함되어 있으면
        SET r += $properties 로 자동 반영된다.
        """
        rel_type = _safe_graph_name(str(rel.get("type") or "RELATED_TO"), "RELATED_TO")
        # 허용되지 않은 관계 타입은 RELATED_TO로 폴백 (Cypher injection 방지)
        if rel_type not in ALLOWED_REL_TYPES:
            rel_type = "RELATED_TO"
        properties = dict(rel.get("properties") or {})
        await self._run_neo4j_query(
            f"""
            MATCH (a {{case_id: $case_id, node_id: $source_id}})
            MATCH (b {{case_id: $case_id, node_id: $target_id}})
            MERGE (a)-[r:{rel_type} {{id: $relation_id}}]->(b)
            SET r += $properties
            """,
            {
                "case_id": case_id,
                "source_id": rel["source_id"],
                "target_id": rel["target_id"],
                "relation_id": rel["id"],
                "properties": properties,
            },
            error_context="ontology_relation_sync",
        )

    async def _sync_behavior_model_to_neo4j(self, case_id: str, model: dict[str, Any]) -> None:
        """BehaviorModel 노드를 Neo4j에 :OntologyBehavior:Model 멀티레이블로 동기화"""
        properties = {k: v for k, v in model.items() if k not in ("id", "case_id")}
        await self._run_neo4j_query(
            """
            MERGE (m:OntologyBehavior:Model {case_id: $case_id, model_id: $model_id})
            SET m += $properties
            """,
            {"case_id": case_id, "model_id": model["id"], "properties": properties},
            error_context="behavior_model_sync",
        )

    async def _sync_field_link_to_neo4j(self, case_id: str, link: dict[str, Any]) -> None:
        """READS_FIELD / PREDICTS_FIELD 관계를 Neo4j에 동기화"""
        link_type = link.get("link_type", "READS_FIELD")
        if link_type not in ("READS_FIELD", "PREDICTS_FIELD"):
            link_type = "READS_FIELD"
        # READS_FIELD: source_node -> model, PREDICTS_FIELD: model -> target_node
        props = {k: v for k, v in link.items() if k not in ("id", "source_id", "target_id", "link_type")}
        await self._run_neo4j_query(
            f"""
            MATCH (a {{case_id: $case_id}})
            WHERE a.node_id = $source_id OR a.model_id = $source_id
            MATCH (b {{case_id: $case_id}})
            WHERE b.node_id = $target_id OR b.model_id = $target_id
            MERGE (a)-[r:{link_type} {{id: $link_id}}]->(b)
            SET r += $properties
            """,
            {
                "case_id": case_id,
                "source_id": link["source_id"],
                "target_id": link["target_id"],
                "link_id": link["id"],
                "properties": props,
            },
            error_context="field_link_sync",
        )

    # ── 정규화 ────────────────────────────────────────────────

    def _normalize_node(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        node_id = str(payload.get("id") or payload.get("node_id") or f"node-{uuid.uuid4()}").strip()
        if not case_id:
            raise ValueError("case_id is required")
        if not node_id:
            raise ValueError("node_id is required")
        layer = str(payload.get("layer") or "resource").lower()
        # 유효하지 않은 layer는 "resource"로 폴백
        if layer not in VALID_LAYERS:
            layer = "resource"
        labels = payload.get("labels") if isinstance(payload.get("labels"), list) else [layer.capitalize()]
        properties = payload.get("properties") if isinstance(payload.get("properties"), dict) else {}
        properties.setdefault("updated_at", _iso_now())
        properties.setdefault("verified", False)
        properties.setdefault("tenant_id", tenant_id)
        return {
            "id": node_id,
            "case_id": case_id,
            "layer": layer,
            "labels": [str(item) for item in labels if str(item).strip()],
            "properties": properties,
        }

    def _normalize_relation(self, tenant_id: str, payload: dict[str, Any], relation_id: str | None = None) -> dict[str, Any]:
        """
        관계 정규화 -- weight/lag/confidence 등 가중치 속성을 properties에 저장.

        CRITICAL: falsy-value 안전 추출 사용.
        0.0이나 0 같은 유효한 값이 무시되지 않도록 'in' 연산자로 존재 검사한다.
        """
        case_id = str(payload.get("case_id") or "").strip()
        source_id = str(payload.get("source_id") or payload.get("from") or payload.get("source") or "").strip()
        target_id = str(payload.get("target_id") or payload.get("to") or payload.get("target") or "").strip()

        # 관계 타입 추출 + enum 검증
        raw_type = _safe_graph_name(str(payload.get("type") or "RELATED_TO"), "RELATED_TO")
        rel_type = raw_type if raw_type in ALLOWED_REL_TYPES else "RELATED_TO"

        if not case_id:
            raise ValueError("case_id is required")
        if not source_id or not target_id:
            raise ValueError("source_id and target_id are required")

        properties = payload.get("properties") if isinstance(payload.get("properties"), dict) else {}

        # ── 가중치/지연/신뢰도 추출 (falsy-value 안전) ──
        weight = _extract_falsy_safe(payload, properties, "weight")
        lag = _extract_falsy_safe(payload, properties, "lag")
        confidence = _extract_falsy_safe(payload, properties, "confidence")

        # 유효성 검증 후 properties에 저장
        if weight is not None:
            properties["weight"] = max(0.0, min(1.0, float(weight)))
        if lag is not None:
            properties["lag"] = max(0, int(lag))
        if confidence is not None:
            properties["confidence"] = max(0.0, min(1.0, float(confidence)))

        # ── 레이어/필드 메타데이터 추출 ──
        for str_key in ("source_layer", "target_layer", "from_field", "to_field"):
            val = _extract_falsy_safe(payload, properties, str_key)
            if val is not None and str(val).strip():
                properties[str_key] = str(val).strip()

        # 분석 방법 (granger, correlation, decomposition, manual 등)
        method = _extract_falsy_safe(payload, properties, "method")
        if method is not None and str(method).strip() in VALID_METHODS:
            properties["method"] = str(method).strip()

        # 영향 방향 (positive / negative)
        direction = _extract_falsy_safe(payload, properties, "direction")
        if direction is not None and str(direction).strip() in VALID_DIRECTIONS:
            properties["direction"] = str(direction).strip()

        properties.setdefault("updated_at", _iso_now())
        properties.setdefault("tenant_id", tenant_id)

        return {
            "id": relation_id or str(payload.get("id") or f"rel-{uuid.uuid4()}"),
            "case_id": case_id,
            "source_id": source_id,
            "target_id": target_id,
            "type": rel_type,
            "properties": properties,
        }

    # ── 노드 CRUD ────────────────────────────────────────────

    async def extract_ontology(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        entities = payload.get("entities") or []
        relations = payload.get("relations") or []
        if not case_id:
            raise ValueError("case_id is required")
        if not isinstance(entities, list) or not isinstance(relations, list):
            raise ValueError("entities/relations must be list")

        task_id = f"onto-{uuid.uuid4()}"
        created_nodes = 0
        created_relations = 0

        for entity in entities:
            if not isinstance(entity, dict):
                continue
            node_payload = {
                "id": entity.get("id") or entity.get("node_id"),
                "case_id": case_id,
                "layer": entity.get("layer") or entity.get("label") or "resource",
                "labels": [entity.get("label")] if entity.get("label") else entity.get("labels"),
                "properties": entity.get("properties") or {},
            }
            node = await self.create_node(tenant_id=tenant_id, payload=node_payload)
            if node:
                created_nodes += 1

        for rel in relations:
            if not isinstance(rel, dict):
                continue
            rel_payload = {
                "case_id": case_id,
                "source_id": rel.get("source_id") or rel.get("from") or rel.get("source"),
                "target_id": rel.get("target_id") or rel.get("to") or rel.get("target"),
                "type": rel.get("type") or "RELATED_TO",
                "properties": rel.get("properties") or {},
            }
            # 가중치 속성 전달
            for wk in ("weight", "lag", "confidence", "source_layer", "target_layer",
                        "from_field", "to_field", "method", "direction"):
                if wk in rel:
                    rel_payload[wk] = rel[wk]
            relation = await self.create_relation(tenant_id=tenant_id, payload=rel_payload)
            if relation:
                created_relations += 1

        return {
            "task_id": task_id,
            "status": "completed",
            "case_id": case_id,
            "stats": {"nodes": created_nodes, "relations": created_relations},
        }

    async def create_node(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        node = self._normalize_node(tenant_id=tenant_id, payload=payload)
        nodes = self._nodes(node["case_id"])
        existing = nodes.get(node["id"])
        if existing:
            existing["layer"] = node["layer"]
            existing["labels"] = node["labels"]
            existing["properties"].update(node["properties"])
            await self._sync_node_to_neo4j(case_id=node["case_id"], node=existing)
            return existing
        nodes[node["id"]] = node
        self._node_case_index[node["id"]] = node["case_id"]
        await self._sync_node_to_neo4j(case_id=node["case_id"], node=node)
        return node

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        case_id = self._node_case_index.get(node_id)
        if not case_id:
            return None
        return self._nodes(case_id).get(node_id)

    async def update_node(self, tenant_id: str, node_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.get_node(node_id)
        if not current:
            raise KeyError("node not found")
        merged = {
            "id": node_id,
            "case_id": current["case_id"],
            "layer": payload.get("layer", current["layer"]),
            "labels": payload.get("labels", current["labels"]),
            "properties": {**current["properties"], **(payload.get("properties") or {})},
        }
        node = self._normalize_node(tenant_id=tenant_id, payload=merged)
        self._nodes(current["case_id"])[node_id] = node
        await self._sync_node_to_neo4j(case_id=current["case_id"], node=node)
        return node

    async def delete_node(self, node_id: str, tenant_id: str = "system") -> dict[str, Any]:
        """노드 삭제 — tenant_id 검증 + Neo4j 동기화 포함"""
        case_id = self._node_case_index.get(node_id)
        if not case_id:
            raise KeyError("node not found")
        nodes = self._nodes(case_id)
        node = nodes.get(node_id)

        # tenant_id 검증
        if node and tenant_id != "system":
            node_tenant = node.get("properties", {}).get("tenant_id")
            if node_tenant and node_tenant != tenant_id:
                raise PermissionError("다른 테넌트의 노드를 삭제할 수 없습니다")

        del nodes[node_id]
        del self._node_case_index[node_id]
        relations = self._relations(case_id)
        stale_ids = [
            rel_id
            for rel_id, rel in relations.items()
            if rel["source_id"] == node_id or rel["target_id"] == node_id
        ]
        for rel_id in stale_ids:
            del relations[rel_id]
            self._relation_case_index.pop(rel_id, None)

        # Neo4j에서도 삭제 (DETACH DELETE로 연결된 관계도 제거)
        await self._run_neo4j_query(
            "MATCH (n {case_id: $case_id, node_id: $node_id}) DETACH DELETE n",
            {"case_id": case_id, "node_id": node_id},
            error_context="ontology_node_delete_sync",
        )

        return {"deleted": True, "node_id": node_id, "deleted_relations": len(stale_ids)}

    # ── 관계 CRUD ────────────────────────────────────────────

    async def create_relation(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        relation = self._normalize_relation(tenant_id=tenant_id, payload=payload)
        nodes = self._nodes(relation["case_id"])
        if relation["source_id"] not in nodes or relation["target_id"] not in nodes:
            raise ValueError("source/target node not found in case")
        relations = self._relations(relation["case_id"])
        relations[relation["id"]] = relation
        self._relation_case_index[relation["id"]] = relation["case_id"]
        await self._sync_relation_to_neo4j(case_id=relation["case_id"], rel=relation)
        return relation

    async def update_relation(self, tenant_id: str, relation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        기존 관계의 속성(weight, lag, confidence 등)을 수정.
        tenant_id 검증을 통해 다른 테넌트의 관계 수정을 방지한다.
        """
        case_id = self._relation_case_index.get(relation_id)
        if not case_id:
            raise KeyError("relation not found")
        current = self._relations(case_id).get(relation_id)
        if not current:
            raise KeyError("relation not found")

        # tenant_id 검증: 관계 소유자와 요청자가 다르면 거부
        current_tenant = current.get("properties", {}).get("tenant_id")
        if current_tenant and current_tenant != tenant_id and tenant_id != "system":
            raise PermissionError("tenant_id mismatch: 다른 테넌트의 관계를 수정할 수 없습니다")

        # 속성 머지 -- 기존 properties를 기반으로 새 값 덮어쓰기
        merged_properties = {**current.get("properties", {})}

        # 가중치 관련 속성: falsy-safe 업데이트
        for key in ("weight", "lag", "confidence", "source_layer", "target_layer",
                     "from_field", "to_field", "method", "direction"):
            if key in payload:
                merged_properties[key] = payload[key]

        # payload.properties가 있으면 추가 머지
        if isinstance(payload.get("properties"), dict):
            merged_properties.update(payload["properties"])

        # 유효성 검증
        if "weight" in merged_properties and merged_properties["weight"] is not None:
            merged_properties["weight"] = max(0.0, min(1.0, float(merged_properties["weight"])))
        if "lag" in merged_properties and merged_properties["lag"] is not None:
            merged_properties["lag"] = max(0, int(merged_properties["lag"]))
        if "confidence" in merged_properties and merged_properties["confidence"] is not None:
            merged_properties["confidence"] = max(0.0, min(1.0, float(merged_properties["confidence"])))
        if "direction" in merged_properties and merged_properties["direction"] not in VALID_DIRECTIONS:
            del merged_properties["direction"]

        merged_properties["updated_at"] = _iso_now()
        current["properties"] = merged_properties

        # 관계 타입 변경 (선택적)
        if "type" in payload:
            new_type = _safe_graph_name(str(payload["type"]), current["type"])
            current["type"] = new_type if new_type in ALLOWED_REL_TYPES else current["type"]

        await self._sync_relation_to_neo4j(case_id=case_id, rel=current)
        return current

    async def bulk_update_relations(
        self, tenant_id: str, case_id: str,
        updates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        상관 분석 결과를 관계에 일괄 반영 (EdgeCandidate -> relation properties).
        MAJOR 최적화: compound index를 사전 구축하여 O(n+m) 성능을 보장한다.
        (기존 O(n*m) 대비 대규모 그래프에서 큰 성능 차이)
        """
        updated = 0
        created = 0
        errors: list[str] = []

        # compound index 사전 구축: (source_id, target_id, type) -> relation
        rel_index: dict[tuple[str, str, str], dict[str, Any]] = {}
        for rel in self._relations(case_id).values():
            key = (rel["source_id"], rel["target_id"], rel["type"])
            rel_index[key] = rel

        for idx, item in enumerate(updates):
            try:
                source_id = str(item.get("source_id", "")).strip()
                target_id = str(item.get("target_id", "")).strip()
                rel_type = str(item.get("type", "CAUSES")).strip()
                if not source_id or not target_id:
                    errors.append(f"[{idx}] source_id/target_id 누락")
                    continue

                # compound index로 O(1) 조회
                lookup_key = (source_id, target_id, rel_type)
                existing_rel = rel_index.get(lookup_key)

                if existing_rel:
                    # 기존 관계 업데이트
                    await self.update_relation(tenant_id, existing_rel["id"], item)
                    updated += 1
                else:
                    # 새 관계 생성
                    create_payload = {**item, "case_id": case_id}
                    new_rel = await self.create_relation(tenant_id=tenant_id, payload=create_payload)
                    # 새로 생성된 관계도 인덱스에 추가 (후속 항목 중복 방지)
                    rel_index[(source_id, target_id, rel_type)] = new_rel
                    created += 1
            except (ValueError, KeyError, PermissionError) as exc:
                errors.append(f"[{idx}] {str(exc)}")

        result: dict[str, Any] = {"updated": updated, "created": created, "total": updated + created}
        if errors:
            result["errors"] = errors
        return result

    async def delete_relation(self, relation_id: str, tenant_id: str = "system") -> dict[str, Any]:
        """관계 삭제 — tenant_id 검증 + Neo4j 동기화 포함"""
        case_id = self._relation_case_index.get(relation_id)
        if not case_id:
            raise KeyError("relation not found")
        relations = self._relations(case_id)
        rel = relations.get(relation_id)

        # tenant_id 검증
        if rel and tenant_id != "system":
            rel_tenant = rel.get("properties", {}).get("tenant_id")
            if rel_tenant and rel_tenant != tenant_id:
                raise PermissionError("다른 테넌트의 관계를 삭제할 수 없습니다")

        del relations[relation_id]
        del self._relation_case_index[relation_id]

        # Neo4j에서도 삭제
        await self._run_neo4j_query(
            "MATCH ()-[r {id: $relation_id}]-() DELETE r",
            {"relation_id": relation_id},
            error_context="ontology_relation_delete_sync",
        )

        return {"deleted": True, "relation_id": relation_id}

    # ── 온톨로지 조회 ────────────────────────────────────────

    async def get_case_ontology(
        self,
        case_id: str,
        layer: str = "all",
        include_relations: bool = True,
        verified_only: bool = False,
        min_weight: float | None = None,
        min_confidence: float | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> dict[str, Any]:
        nodes = list(self._nodes(case_id).values())
        if layer != "all":
            nodes = [n for n in nodes if n["layer"] == layer]
        if verified_only:
            nodes = [n for n in nodes if bool(n["properties"].get("verified", False))]

        total = len(nodes)
        safe_limit = min(max(limit, 1), 1000)
        safe_offset = max(offset, 0)
        paged_nodes = nodes[safe_offset : safe_offset + safe_limit]
        node_ids = {n["id"] for n in paged_nodes}

        rel_items: list[dict[str, Any]] = []
        if include_relations:
            for rel in self._relations(case_id).values():
                if rel["source_id"] in node_ids and rel["target_id"] in node_ids:
                    # 가중치/신뢰도 필터 적용
                    props = rel.get("properties", {})
                    if min_weight is not None:
                        w = props.get("weight")
                        if w is None or float(w) < min_weight:
                            continue
                    if min_confidence is not None:
                        c = props.get("confidence")
                        if c is None or float(c) < min_confidence:
                            continue
                    rel_items.append(rel)

        by_layer: dict[str, int] = {}
        for item in nodes:
            by_layer[item["layer"]] = by_layer.get(item["layer"], 0) + 1

        return {
            "case_id": case_id,
            "summary": {
                "total_nodes": len(nodes),
                "total_relations": len(rel_items),
                "by_layer": by_layer,
            },
            "nodes": paged_nodes,
            "relations": rel_items,
            "pagination": {
                "total": total,
                "limit": safe_limit,
                "offset": safe_offset,
                "has_more": (safe_offset + safe_limit) < total,
            },
        }

    async def get_case_summary(self, case_id: str) -> dict[str, Any]:
        nodes = list(self._nodes(case_id).values())
        relations = list(self._relations(case_id).values())

        node_counts: dict[str, dict[str, Any]] = {}
        verification = {"verified": 0, "unverified": 0, "pending_review": 0}
        for node in nodes:
            layer = node["layer"]
            node_counts.setdefault(layer, {"total": 0, "by_type": {}})
            node_counts[layer]["total"] += 1
            typ = node["labels"][0] if node["labels"] else "Entity"
            node_counts[layer]["by_type"][typ] = node_counts[layer]["by_type"].get(typ, 0) + 1
            verified = node["properties"].get("verified")
            if verified is True:
                verification["verified"] += 1
            elif verified == "pending_review":
                verification["pending_review"] += 1
            else:
                verification["unverified"] += 1

        rel_counts: dict[str, int] = {}
        for rel in relations:
            rel_counts[rel["type"]] = rel_counts.get(rel["type"], 0) + 1

        return {
            "case_id": case_id,
            "node_counts": node_counts,
            "relation_counts": rel_counts,
            "verification_status": verification,
            "last_updated": _iso_now(),
        }

    async def get_neighbors(self, node_id: str, limit: int = 100) -> dict[str, Any]:
        case_id = self._node_case_index.get(node_id)
        if not case_id:
            raise KeyError("node not found")
        rels = self._relations(case_id).values()
        neighbors: list[dict[str, Any]] = []
        for rel in rels:
            if rel["source_id"] == node_id:
                neighbor = self.get_node(rel["target_id"])
                if neighbor:
                    neighbors.append({"relation": rel, "node": neighbor})
            elif rel["target_id"] == node_id:
                neighbor = self.get_node(rel["source_id"])
                if neighbor:
                    neighbors.append({"relation": rel, "node": neighbor})
            if len(neighbors) >= limit:
                break
        return {"node_id": node_id, "neighbors": neighbors, "total": len(neighbors)}

    # ── BehaviorModel CRUD ────────────────────────────────────

    async def create_behavior_model(self, tenant_id: str, case_id: str, model_data: dict[str, Any]) -> dict[str, Any]:
        """
        BehaviorModel(ML 예측 모델) 노드를 생성하고 READS_FIELD/PREDICTS_FIELD 링크를 설정.

        model_data 구조:
        {
            "name": "불량률 예측",
            "model_type": "RandomForest",
            "status": "pending",
            "reads": [{"source_node_id": "...", "field": "cost_index", "lag": 0}],
            "predicts": [{"target_node_id": "...", "field": "defect_rate", "confidence": 0.85}]
        }
        """
        model_id = str(model_data.get("id") or f"model_{uuid.uuid4().hex[:12]}")
        model = {
            "id": model_id,
            "case_id": case_id,
            "name": str(model_data.get("name", "unnamed_model")),
            "behavior_type": "Model",
            "model_type": str(model_data.get("model_type", "unknown")),
            "status": str(model_data.get("status", "pending")),
            "metrics_json": str(model_data.get("metrics_json", "{}")),
            "feature_view_sql": str(model_data.get("feature_view_sql", "")),
            "train_data_rows": int(model_data.get("train_data_rows", 0)),
            "trained_at": model_data.get("trained_at", ""),
            "version": int(model_data.get("version", 1)),
            "tenant_id": tenant_id,
            "created_at": _iso_now(),
            "updated_at": _iso_now(),
        }

        # 인메모리 저장 (behavior_models는 별도 namespace로 관리)
        bm_store = self._case_nodes.setdefault(f"__bm__{case_id}", {})
        bm_store[model_id] = model
        await self._sync_behavior_model_to_neo4j(case_id, model)

        # READS_FIELD 링크 생성
        reads = model_data.get("reads") or []
        created_links: list[dict[str, Any]] = []
        for read_spec in reads:
            link = {
                "id": f"rf-{uuid.uuid4().hex[:8]}",
                "source_id": str(read_spec.get("source_node_id", "")),
                "target_id": model_id,
                "link_type": "READS_FIELD",
                "field": str(read_spec.get("field", "")),
                "lag": int(read_spec.get("lag", 0)),
                "feature_name": str(read_spec.get("feature_name", read_spec.get("field", ""))),
                "importance": read_spec.get("importance"),
                "correlation_score": read_spec.get("correlation_score"),
                "granger_p_value": read_spec.get("granger_p_value"),
            }
            link_store = self._case_nodes.setdefault(f"__links__{case_id}", {})
            link_store[link["id"]] = link
            await self._sync_field_link_to_neo4j(case_id, link)
            created_links.append(link)

        # PREDICTS_FIELD 링크 생성
        predicts = model_data.get("predicts") or []
        for pred_spec in predicts:
            link = {
                "id": f"pf-{uuid.uuid4().hex[:8]}",
                "source_id": model_id,
                "target_id": str(pred_spec.get("target_node_id", "")),
                "link_type": "PREDICTS_FIELD",
                "field": str(pred_spec.get("field", "")),
                "confidence": pred_spec.get("confidence"),
            }
            link_store = self._case_nodes.setdefault(f"__links__{case_id}", {})
            link_store[link["id"]] = link
            await self._sync_field_link_to_neo4j(case_id, link)
            created_links.append(link)

        return {**model, "links": created_links}

    async def list_behavior_models(self, case_id: str) -> list[dict[str, Any]]:
        """해당 case의 모든 BehaviorModel 목록 반환"""
        bm_store = self._case_nodes.get(f"__bm__{case_id}", {})
        return list(bm_store.values())

    async def get_model_graph(self, case_id: str) -> dict[str, Any]:
        """
        시뮬레이션용 모델 DAG 구조를 반환.
        Neo4j에서 직접 로딩을 시도하고, 실패 시 인메모리 캐시에서 구성한다.

        Returns:
            {
                "models": [{id, name, status, model_type, ...}],
                "reads": [{model_id, source_node_id, field, lag, feature_name, ...}],
                "predicts": [{model_id, target_node_id, field, confidence}],
            }
        """
        # Neo4j에서 직접 로딩 시도
        try:
            return await self._load_model_graph_from_neo4j(case_id)
        except Exception as exc:
            logger.warning("model_graph_neo4j_load_failed", error=str(exc), case_id=case_id)

        # 폴백: 인메모리에서 구성
        return self._build_model_graph_from_memory(case_id)

    async def _load_model_graph_from_neo4j(self, case_id: str) -> dict[str, Any]:
        """Neo4j에서 BehaviorModel + READS_FIELD + PREDICTS_FIELD 로딩"""
        models = []
        reads = []
        predicts = []

        async with self._neo4j.session() as session:
            result = await asyncio.wait_for(
                session.run(
                    """
                    MATCH (m:OntologyBehavior:Model {case_id: $case_id})
                    OPTIONAL MATCH (src)-[r:READS_FIELD]->(m)
                    OPTIONAL MATCH (m)-[p:PREDICTS_FIELD]->(tgt)
                    RETURN m, collect(DISTINCT {
                        source_node_id: src.node_id,
                        field: r.field,
                        lag: r.lag,
                        feature_name: r.feature_name,
                        importance: r.importance,
                        correlation_score: r.correlation_score,
                        granger_p_value: r.granger_p_value,
                        link_id: r.id
                    }) AS reads_list, collect(DISTINCT {
                        target_node_id: tgt.node_id,
                        field: p.field,
                        confidence: p.confidence,
                        link_id: p.id
                    }) AS predicts_list
                    """,
                    case_id=case_id,
                ),
                timeout=2.0,
            )

            seen_model_ids = set()
            async for record in result:
                m = dict(record["m"])
                model_id = m.get("model_id", "")
                if model_id in seen_model_ids:
                    continue
                seen_model_ids.add(model_id)

                models.append({
                    "id": model_id,
                    "name": m.get("name", ""),
                    "status": m.get("status", "pending"),
                    "model_type": m.get("model_type", ""),
                    "metrics_json": m.get("metrics_json", "{}"),
                })

                for r in record["reads_list"]:
                    if r.get("source_node_id") and r.get("link_id"):
                        reads.append({
                            "model_id": model_id,
                            "source_node_id": r["source_node_id"],
                            "field": r.get("field", ""),
                            "lag": r.get("lag", 0),
                            "feature_name": r.get("feature_name", ""),
                            "importance": r.get("importance"),
                            "correlation_score": r.get("correlation_score"),
                            "granger_p_value": r.get("granger_p_value"),
                        })

                for p in record["predicts_list"]:
                    if p.get("target_node_id") and p.get("link_id"):
                        predicts.append({
                            "model_id": model_id,
                            "target_node_id": p["target_node_id"],
                            "field": p.get("field", ""),
                            "confidence": p.get("confidence"),
                        })

        return {"models": models, "reads": reads, "predicts": predicts}

    def _build_model_graph_from_memory(self, case_id: str) -> dict[str, Any]:
        """인메모리 캐시에서 모델 그래프 구성 (Neo4j 폴백용)"""
        bm_store = self._case_nodes.get(f"__bm__{case_id}", {})
        link_store = self._case_nodes.get(f"__links__{case_id}", {})

        models = []
        for m in bm_store.values():
            models.append({
                "id": m["id"],
                "name": m.get("name", ""),
                "status": m.get("status", "pending"),
                "model_type": m.get("model_type", ""),
                "metrics_json": m.get("metrics_json", "{}"),
            })

        reads = []
        predicts = []
        for link in link_store.values():
            if link.get("link_type") == "READS_FIELD":
                reads.append({
                    "model_id": link["target_id"],
                    "source_node_id": link["source_id"],
                    "field": link.get("field", ""),
                    "lag": link.get("lag", 0),
                    "feature_name": link.get("feature_name", ""),
                    "importance": link.get("importance"),
                    "correlation_score": link.get("correlation_score"),
                    "granger_p_value": link.get("granger_p_value"),
                })
            elif link.get("link_type") == "PREDICTS_FIELD":
                predicts.append({
                    "model_id": link["source_id"],
                    "target_node_id": link["target_id"],
                    "field": link.get("field", ""),
                    "confidence": link.get("confidence"),
                })

        return {"models": models, "reads": reads, "predicts": predicts}

    # ── O5-5: GlossaryTerm <-> Ontology Bridge ────────────────

    async def suggest_glossary_matches(self, term_name: str, case_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Fulltext search for ontology nodes matching a glossary term name."""
        try:
            async with self._neo4j.session() as session:
                result = await session.run(
                    """
                    CALL db.index.fulltext.queryNodes('ontology_fulltext', $term)
                    YIELD node, score
                    WHERE score > 0.5 AND node.case_id = $case_id
                    RETURN node.id AS id, node.name AS name, labels(node)[0] AS layer, score
                    ORDER BY score DESC
                    LIMIT $limit
                    """,
                    term=term_name,
                    case_id=case_id,
                    limit=limit,
                )
                return [dict(r) async for r in result]
        except Exception as exc:
            logger.warning("glossary_suggest_failed", error=str(exc), term=term_name, case_id=case_id)
            return []

    async def create_glossary_link(self, term_id: str, node_id: str, case_id: str) -> dict[str, Any]:
        """Create DEFINES relationship between GlossaryTerm and OntologyNode."""
        try:
            async with self._neo4j.session() as session:
                await session.run(
                    """
                    MATCH (t {id: $term_id})
                    MATCH (n {case_id: $case_id, node_id: $node_id})
                    MERGE (t)-[r:DEFINES]->(n)
                    SET r.created_at = datetime()
                    RETURN r
                    """,
                    term_id=term_id,
                    node_id=node_id,
                    case_id=case_id,
                )
        except Exception as exc:
            logger.warning("glossary_link_failed", error=str(exc), term_id=term_id, node_id=node_id)
            raise
        return {"term_id": term_id, "node_id": node_id, "case_id": case_id}

    async def path_to(self, source_id: str, target_id: str, max_depth: int = 6) -> dict[str, Any]:
        case_id = self._node_case_index.get(source_id)
        if not case_id or self._node_case_index.get(target_id) != case_id:
            raise KeyError("source or target node not found")
        graph: dict[str, list[tuple[str, str]]] = {}
        for rel in self._relations(case_id).values():
            graph.setdefault(rel["source_id"], []).append((rel["target_id"], rel["id"]))
            graph.setdefault(rel["target_id"], []).append((rel["source_id"], rel["id"]))

        queue = deque([(source_id, [source_id], [])])
        visited = {source_id}
        while queue:
            current, path_nodes, path_rels = queue.popleft()
            if current == target_id:
                return {"source_id": source_id, "target_id": target_id, "path": path_nodes, "relations": path_rels}
            if len(path_nodes) > max_depth:
                continue
            for neighbor, rel_id in graph.get(current, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, [*path_nodes, neighbor], [*path_rels, rel_id]))
        return {"source_id": source_id, "target_id": target_id, "path": [], "relations": []}
