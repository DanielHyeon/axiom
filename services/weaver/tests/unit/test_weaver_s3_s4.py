import pytest
from app.core.schema_introspection import schema_introspector
from app.core.metadata_enrichment import metadata_enricher
from app.core.schema import GraphSchema, NodeDefinition, PropertyDefinition

@pytest.mark.asyncio
async def test_schema_introspector_mapping():
    raw_schema = {"tables": ["users", "orders"]}
    graph = await schema_introspector.introspect(raw_schema)
    
    assert len(graph.nodes) == 2
    assert graph.nodes[0].label == "Users"
    assert graph.nodes[0].source_table == "users"
    assert graph.nodes[0].properties[0].name == "id"


@pytest.mark.asyncio
async def test_schema_introspector_mapping_with_columns():
    raw_schema = {
        "tables": [
            {
                "name": "user_orders",
                "columns": [
                    {"name": "id", "type": "uuid", "nullable": False},
                    {"name": "order_total", "type": "numeric", "nullable": False},
                ],
            }
        ]
    }
    graph = await schema_introspector.introspect(raw_schema)

    assert len(graph.nodes) == 1
    assert graph.nodes[0].label == "UserOrders"
    assert graph.nodes[0].source_table == "user_orders"
    assert [p.name for p in graph.nodes[0].properties] == ["id", "order_total"]

@pytest.mark.asyncio
async def test_metadata_enrichment_llm_tags():
    node = NodeDefinition(
        label="Product",
        properties=[PropertyDefinition(name="price", type="float")],
        source_table="products",
    )
    schema = GraphSchema(nodes=[node], edges=[])
    
    enriched = await metadata_enricher.enrich(schema)
    assert len(enriched.nodes) == 1
    
    # Assert tag injection
    props = enriched.nodes[0].properties
    assert any(type(p) is dict and p.get("name") == "_semantic_tag" for p in props)
    
    # Assert description additions
    price_prop = next(p for p in props if type(p) is not dict and p.name == "price")
    assert "AI Inferred" in price_prop.description
