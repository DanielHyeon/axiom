from __future__ import annotations

from typing import Any
from app.core.schema import GraphSchema, NodeDefinition, PropertyDefinition


def _label_from_table_name(table_name: str) -> str:
    parts = [x for x in table_name.strip().split("_") if x]
    if not parts:
        return "Unknown"
    return "".join(part.capitalize() for part in parts)


def _normalize_columns(table: dict[str, Any]) -> list[dict[str, Any]]:
    columns = table.get("columns")
    if not isinstance(columns, list):
        return [{"name": "id", "type": "string", "nullable": False}]
    normalized: list[dict[str, Any]] = []
    for col in columns:
        if not isinstance(col, dict):
            continue
        name = str(col.get("name") or "").strip()
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "type": str(col.get("type") or "string"),
                "nullable": bool(col.get("nullable", True)),
            }
        )
    if not normalized:
        return [{"name": "id", "type": "string", "nullable": False}]
    return normalized


class SchemaIntrospector:
    async def introspect(self, extracted_schema: dict[str, Any]) -> GraphSchema:
        """
        Translates raw relational schema definitions (ex. from PostgresAdapter) into 
        formal Axiom Neo4j V2 graph schema nodes and properties.
        """
        tables = extracted_schema.get("tables", [])
        nodes = []
        
        for table in tables:
            if isinstance(table, str):
                table_name = table
                columns = [{"name": "id", "type": "string", "nullable": False}]
            elif isinstance(table, dict):
                table_name = str(table.get("name") or "").strip()
                if not table_name:
                    continue
                columns = _normalize_columns(table)
            else:
                continue
            node = NodeDefinition(
                label=_label_from_table_name(table_name),
                source_table=table_name,
                properties=[
                    PropertyDefinition(
                        name=col["name"],
                        type=col["type"],
                        description=f"{col['name']} field from {table_name}",
                    )
                    for col in columns
                ]
            )
            nodes.append(node)
            
        return GraphSchema(nodes=nodes, edges=[])

schema_introspector = SchemaIntrospector()
