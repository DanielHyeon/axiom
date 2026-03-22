"""O5-4: Ontology Version Management — Snapshot creation and diff."""
import json
import uuid
from typing import Any

import structlog

logger = structlog.get_logger()


class SnapshotService:
    """온톨로지 스냅샷 생성 및 버전 비교."""

    def __init__(self, neo4j_client, ontology_service) -> None:
        self._neo4j = neo4j_client
        self._ontology = ontology_service

    async def create_snapshot(self, case_id: str, tenant_id: str) -> dict[str, Any]:
        """Serialize current ontology state into an OntologySnapshot node in Neo4j."""
        data = await self._ontology.get_case_ontology(case_id=case_id, limit=10000)
        nodes = data.get("nodes", [])
        relations = data.get("relations", [])

        snapshot_id = str(uuid.uuid4())
        snapshot_data = json.dumps({"nodes": nodes, "relations": relations}, default=str)

        try:
            async with self._neo4j.session() as session:
                await session.run(
                    """
                    CREATE (s:OntologySnapshot {
                        id: $id,
                        case_id: $case_id,
                        tenant_id: $tenant_id,
                        created_at: datetime(),
                        node_count: $nc,
                        relation_count: $rc,
                        snapshot_data: $data
                    })
                    """,
                    id=snapshot_id,
                    case_id=case_id,
                    tenant_id=tenant_id,
                    nc=len(nodes),
                    rc=len(relations),
                    data=snapshot_data,
                )
        except Exception as exc:
            logger.error("snapshot_create_failed", error=str(exc), case_id=case_id)
            raise

        logger.info(
            "snapshot_created",
            snapshot_id=snapshot_id,
            case_id=case_id,
            nodes=len(nodes),
            relations=len(relations),
        )
        return {
            "snapshot_id": snapshot_id,
            "case_id": case_id,
            "node_count": len(nodes),
            "relation_count": len(relations),
        }

    async def list_snapshots(self, case_id: str) -> list[dict[str, Any]]:
        """List snapshots for a case (without snapshot_data to save bandwidth)."""
        try:
            async with self._neo4j.session() as session:
                result = await session.run(
                    """
                    MATCH (s:OntologySnapshot {case_id: $case_id})
                    RETURN s.id AS id, s.case_id AS case_id, s.tenant_id AS tenant_id,
                           s.created_at AS created_at, s.node_count AS node_count,
                           s.relation_count AS relation_count
                    ORDER BY s.created_at DESC
                    """,
                    case_id=case_id,
                )
                return [dict(r) async for r in result]
        except Exception as exc:
            logger.error("snapshot_list_failed", error=str(exc), case_id=case_id)
            return []

    async def _load_snapshot_data(self, snapshot_id: str) -> dict[str, Any]:
        """Load snapshot_data JSON from Neo4j."""
        async with self._neo4j.session() as session:
            result = await session.run(
                "MATCH (s:OntologySnapshot {id: $id}) RETURN s.snapshot_data AS data",
                id=snapshot_id,
            )
            record = await result.single()
            if not record:
                raise KeyError(f"Snapshot {snapshot_id} not found")
            return json.loads(record["data"])

    async def activate_snapshot(self, case_id: str, snapshot_id: str) -> dict[str, Any]:
        """스냅샷을 활성 버전으로 설정 — 현재 온톨로지를 해당 스냅샷으로 복원한다.

        1. 스냅샷 데이터 로드
        2. 현재 온톨로지 클리어
        3. 스냅샷의 노드/관계 복원
        4. 복원 요약 반환
        """
        # 1) 스냅샷 데이터 로드
        snapshot_data = await self._load_snapshot_data(snapshot_id)
        nodes = snapshot_data.get("nodes", [])
        relations = snapshot_data.get("relations", [])

        # 2) 현재 온톨로지 노드/관계 전부 삭제
        try:
            async with self._neo4j.session() as session:
                await session.run(
                    """
                    MATCH (n:OntologyNode {case_id: $case_id})
                    DETACH DELETE n
                    """,
                    case_id=case_id,
                )
        except Exception as exc:
            logger.error("snapshot_activate_clear_failed", error=str(exc), case_id=case_id)
            raise

        # 3) 스냅샷 노드 복원
        restored_nodes = 0
        restored_relations = 0

        try:
            async with self._neo4j.session() as session:
                for node in nodes:
                    node_id = node.get("id")
                    if not node_id:
                        continue
                    # 노드의 기본 속성 추출
                    props = {k: v for k, v in node.items() if v is not None}
                    props["case_id"] = case_id
                    await session.run(
                        """
                        CREATE (n:OntologyNode)
                        SET n = $props
                        """,
                        props=props,
                    )
                    restored_nodes += 1

                # 4) 스냅샷 관계 복원
                for rel in relations:
                    source_id = rel.get("source") or rel.get("source_id")
                    target_id = rel.get("target") or rel.get("target_id")
                    rel_type = rel.get("type", "RELATED_TO")
                    if not source_id or not target_id:
                        continue
                    # 관계 속성 (type, source, target 제외)
                    rel_props = {
                        k: v for k, v in rel.items()
                        if k not in ("source", "target", "source_id", "target_id", "type") and v is not None
                    }
                    # 안전한 관계 타입만 허용
                    safe_type = rel_type if rel_type.replace("_", "").isalpha() else "RELATED_TO"
                    await session.run(
                        f"""
                        MATCH (a:OntologyNode {{id: $source_id}})
                        MATCH (b:OntologyNode {{id: $target_id}})
                        CREATE (a)-[r:{safe_type}]->(b)
                        SET r = $props
                        """,
                        source_id=source_id,
                        target_id=target_id,
                        props=rel_props,
                    )
                    restored_relations += 1
        except Exception as exc:
            logger.error("snapshot_activate_restore_failed", error=str(exc), case_id=case_id)
            raise

        # 5) 스냅샷을 활성으로 표시
        try:
            async with self._neo4j.session() as session:
                # 기존 활성 플래그 제거
                await session.run(
                    """
                    MATCH (s:OntologySnapshot {case_id: $case_id})
                    SET s.is_active = false
                    """,
                    case_id=case_id,
                )
                # 현재 스냅샷 활성화
                await session.run(
                    """
                    MATCH (s:OntologySnapshot {id: $snapshot_id})
                    SET s.is_active = true, s.activated_at = datetime()
                    """,
                    snapshot_id=snapshot_id,
                )
        except Exception as exc:
            logger.error("snapshot_activate_flag_failed", error=str(exc), snapshot_id=snapshot_id)
            raise

        # 인메모리 캐시 무효화
        if hasattr(self._ontology, "_case_nodes") and case_id in self._ontology._case_nodes:
            del self._ontology._case_nodes[case_id]
        if hasattr(self._ontology, "_case_relations") and case_id in self._ontology._case_relations:
            del self._ontology._case_relations[case_id]

        logger.info(
            "snapshot_activated",
            snapshot_id=snapshot_id,
            case_id=case_id,
            restored_nodes=restored_nodes,
            restored_relations=restored_relations,
        )
        return {
            "snapshot_id": snapshot_id,
            "case_id": case_id,
            "restored_nodes": restored_nodes,
            "restored_relations": restored_relations,
            "status": "activated",
        }

    async def diff_snapshots(self, snapshot_a: str, snapshot_b: str) -> dict[str, Any]:
        """Compare two snapshots → added/removed/modified nodes and relations."""
        data_a = await self._load_snapshot_data(snapshot_a)
        data_b = await self._load_snapshot_data(snapshot_b)

        nodes_a = {n["id"]: n for n in data_a.get("nodes", [])}
        nodes_b = {n["id"]: n for n in data_b.get("nodes", [])}

        rels_a = {r["id"]: r for r in data_a.get("relations", [])}
        rels_b = {r["id"]: r for r in data_b.get("relations", [])}

        added_nodes = [nodes_b[nid] for nid in nodes_b if nid not in nodes_a]
        removed_nodes = [nodes_a[nid] for nid in nodes_a if nid not in nodes_b]
        modified_nodes = [
            {"before": nodes_a[nid], "after": nodes_b[nid]}
            for nid in nodes_a
            if nid in nodes_b and nodes_a[nid] != nodes_b[nid]
        ]

        added_relations = [rels_b[rid] for rid in rels_b if rid not in rels_a]
        removed_relations = [rels_a[rid] for rid in rels_a if rid not in rels_b]

        diff = {
            "snapshot_a": snapshot_a,
            "snapshot_b": snapshot_b,
            "added_nodes": added_nodes,
            "removed_nodes": removed_nodes,
            "modified_nodes": modified_nodes,
            "added_relations": added_relations,
            "removed_relations": removed_relations,
            "summary": {
                "nodes_added": len(added_nodes),
                "nodes_removed": len(removed_nodes),
                "nodes_modified": len(modified_nodes),
                "relations_added": len(added_relations),
                "relations_removed": len(removed_relations),
            },
        }
        logger.info("snapshot_diff_computed", **diff["summary"])
        return diff
