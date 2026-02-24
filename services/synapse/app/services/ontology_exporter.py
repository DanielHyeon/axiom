"""O5-1: OWL/RDF Export — Turtle (.ttl) and JSON-LD formats."""
from typing import Any

import structlog

logger = structlog.get_logger()


class OntologyExporter:
    """온톨로지 그래프를 RDF 형식으로 export."""

    def __init__(self, ontology_service) -> None:
        self._ontology = ontology_service

    async def _load_graph(self, case_id: str):
        """Fetch ontology data and build an rdflib Graph."""
        from rdflib import Graph, Namespace, Literal, RDF, RDFS  # type: ignore

        g = Graph()
        AX = Namespace("http://axiom.ai/ontology/")
        g.bind("ax", AX)
        g.bind("rdfs", RDFS)

        data = await self._ontology.get_case_ontology(case_id=case_id, limit=10000)
        nodes: list[dict[str, Any]] = data.get("nodes", [])
        relations: list[dict[str, Any]] = data.get("relations", [])

        for node in nodes:
            node_id = node.get("id", "unknown")
            uri = AX[f"node/{node_id}"]
            layer = node.get("layer", "Entity")
            g.add((uri, RDF.type, AX[layer.capitalize()]))

            props = node.get("properties") or {}
            name = props.get("name", node_id)
            g.add((uri, RDFS.label, Literal(name)))

            if props.get("description"):
                g.add((uri, AX["description"], Literal(props["description"])))
            if props.get("verified") is not None:
                g.add((uri, AX["verified"], Literal(bool(props["verified"]))))

        for rel in relations:
            src = AX[f"node/{rel['source_id']}"]
            tgt = AX[f"node/{rel['target_id']}"]
            rel_type = rel.get("type", "RELATED_TO")
            g.add((src, AX[rel_type], tgt))

        logger.info(
            "ontology_export_graph_built",
            case_id=case_id,
            nodes=len(nodes),
            relations=len(relations),
        )
        return g

    async def export_turtle(self, case_id: str, tenant_id: str) -> str:
        """Turtle (.ttl) 형식으로 export."""
        _ = tenant_id  # reserved for future ACL
        g = await self._load_graph(case_id)
        return g.serialize(format="turtle")

    async def export_jsonld(self, case_id: str, tenant_id: str) -> str:
        """JSON-LD 형식으로 export."""
        _ = tenant_id
        g = await self._load_graph(case_id)
        return g.serialize(format="json-ld")
