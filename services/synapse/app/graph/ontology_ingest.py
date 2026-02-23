from __future__ import annotations

import structlog
from app.core.neo4j_client import neo4j_client

logger = structlog.get_logger()


class OntologyIngestor:
    """
    Subscribes to Redis Streams from Core (events) and auto-generates Neo4j nodes.
    process_event() returns entities/relations; merge_from_ingest_result() writes them to Neo4j.
    """
    async def process_event(self, event_type: str, payload: dict):
        case_id = str((payload or {}).get("case_id") or "").strip()
        if not case_id:
            return {"accepted": False, "reason": "missing_case_id"}

        if event_type in ("case.created", "case.updated"):
            entity = {"id": f"case:{case_id}", "label": "Case", "properties": {"name": payload.get("name", "")}}
            return {"accepted": True, "case_id": case_id, "entities": [entity], "relations": []}

        if event_type == "case.process.started":
            process_id = str(payload.get("proc_inst_id") or "").strip()
            if not process_id:
                return {"accepted": False, "reason": "missing_proc_inst_id", "case_id": case_id}
            return {
                "accepted": True,
                "case_id": case_id,
                "entities": [
                    {"id": f"case:{case_id}", "label": "Case", "properties": {}},
                    {"id": f"process:{process_id}", "label": "Process", "properties": {"status": "STARTED"}},
                ],
                "relations": [{"from": f"case:{case_id}", "to": f"process:{process_id}", "type": "HAS_PROCESS"}],
            }

        if event_type == "case.asset.registered":
            asset_id = str(payload.get("asset_id") or "").strip()
            if not asset_id:
                return {"accepted": False, "reason": "missing_asset_id", "case_id": case_id}
            return {
                "accepted": True,
                "case_id": case_id,
                "entities": [{"id": f"asset:{asset_id}", "label": "Asset", "properties": {"kind": payload.get("kind")}}],
                "relations": [{"from": f"case:{case_id}", "to": f"asset:{asset_id}", "type": "HAS_ASSET"}],
            }

        if event_type == "case.stakeholder.added":
            stakeholder_id = str(payload.get("stakeholder_id") or "").strip()
            if not stakeholder_id:
                return {"accepted": False, "reason": "missing_stakeholder_id", "case_id": case_id}
            return {
                "accepted": True,
                "case_id": case_id,
                "entities": [
                    {"id": f"stakeholder:{stakeholder_id}", "label": "Stakeholder", "properties": {"role": payload.get("role")}}
                ],
                "relations": [{"from": f"case:{case_id}", "to": f"stakeholder:{stakeholder_id}", "type": "HAS_STAKEHOLDER"}],
            }

        if event_type == "case.metric.updated":
            metric_id = str(payload.get("metric_id") or "").strip()
            if not metric_id:
                return {"accepted": False, "reason": "missing_metric_id", "case_id": case_id}
            return {
                "accepted": True,
                "case_id": case_id,
                "entities": [{"id": f"metric:{metric_id}", "label": "Measure", "properties": {"value": payload.get("value")}}],
                "relations": [{"from": f"case:{case_id}", "to": f"metric:{metric_id}", "type": "HAS_METRIC"}],
            }

        return {"accepted": False, "reason": "unsupported_event_type", "event_type": event_type, "case_id": case_id}

    async def merge_from_ingest_result(self, entities: list, relations: list) -> None:
        """Persist entities and relations from process_event result to Neo4j (MERGE upsert)."""
        if not entities and not relations:
            return
        async with neo4j_client.session() as session:
            for e in entities:
                nid = e.get("id") or ""
                label = (e.get("label") or "Node").replace("`", "")
                props = dict(e.get("properties") or {})
                if "id" not in props:
                    props["id"] = nid
                await session.execute_write(lambda tx: _merge_node_tx(tx, label, nid, props))
            for r in relations:
                from_id = r.get("from") or ""
                to_id = r.get("to") or ""
                rel_type = (r.get("type") or "RELATES_TO").replace("`", "")
                await session.execute_write(lambda tx, f=from_id, t=to_id, rt=rel_type: _merge_relation_tx(tx, f, t, rt))
        logger.debug("ontology_ingest_merged", entities=len(entities), relations=len(relations))


def _merge_node_tx(tx, label: str, nid: str, props: dict):
    """Transaction function: MERGE node by id, SET properties."""
    q = f"MERGE (n:{label} {{id: $id}}) SET n += $props"
    tx.run(q, id=nid, props=props)
    return None


def _merge_relation_tx(tx, from_id: str, to_id: str, rel_type: str):
    """Transaction function: MATCH two nodes by id, MERGE relation."""
    q = f"MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) MERGE (a)-[r:{rel_type}]->(b)"
    tx.run(q, from_id=from_id, to_id=to_id)
    return None
