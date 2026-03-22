"""온톨로지 피드백 & 스키마 개선 단위 테스트.

테스트 대상:
- SchemaRefiner: 구조화된 피드백 적용 + LLM 자연어 피드백
- FeedbackItem: 데이터 모델
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.schema_refiner import SchemaRefiner, FeedbackItem, FeedbackResult


class MockOntologyService:
    """테스트용 OntologyService 모의 객체."""

    def __init__(self):
        self.created_nodes: list[dict] = []
        self.updated_nodes: list[dict] = []
        self.deleted_nodes: list[str] = []
        self.created_relations: list[dict] = []
        self.deleted_relations: list[str] = []

    async def create_node(self, tenant_id, payload):
        self.created_nodes.append(payload)

    async def update_node(self, tenant_id, node_id, payload):
        self.updated_nodes.append({"node_id": node_id, **payload})

    async def delete_node(self, node_id, tenant_id):
        self.deleted_nodes.append(node_id)

    async def create_relation(self, tenant_id, payload):
        self.created_relations.append(payload)

    async def delete_relation(self, relation_id, tenant_id):
        self.deleted_relations.append(relation_id)

    async def get_case_ontology(self, case_id, limit=50):
        return {
            "nodes": [
                {"id": "node-1", "properties": {"name": "OEE"}},
                {"id": "node-2", "properties": {"name": "Throughput"}},
            ],
            "summary": {"total_nodes": 2},
        }


class TestSchemaRefiner:
    """SchemaRefiner 피드백 적용 테스트."""

    @pytest.fixture
    def mock_ontology(self):
        return MockOntologyService()

    @pytest.fixture
    def refiner(self, mock_ontology):
        return SchemaRefiner(ontology_service=mock_ontology)

    @pytest.mark.asyncio
    async def test_add_node(self, refiner, mock_ontology):
        """노드 추가 피드백."""
        result = await refiner.apply_feedback(
            case_id="case-1",
            tenant_id="tenant-1",
            feedback_items=[{
                "type": "add_node",
                "content": {
                    "id": "new-kpi",
                    "layer": "kpi",
                    "properties": {"name": "Energy Efficiency"},
                },
            }],
        )
        assert len(result.applied) == 1
        assert result.applied[0]["type"] == "add_node"
        assert len(mock_ontology.created_nodes) == 1

    @pytest.mark.asyncio
    async def test_update_node(self, refiner, mock_ontology):
        """노드 수정 피드백."""
        result = await refiner.apply_feedback(
            case_id="case-1",
            tenant_id="tenant-1",
            feedback_items=[{
                "type": "update_node",
                "target_id": "node-1",
                "content": {"properties": {"name": "Updated OEE"}},
            }],
        )
        assert len(result.applied) == 1
        assert mock_ontology.updated_nodes[0]["node_id"] == "node-1"

    @pytest.mark.asyncio
    async def test_delete_node(self, refiner, mock_ontology):
        """노드 삭제 피드백."""
        result = await refiner.apply_feedback(
            case_id="case-1",
            tenant_id="tenant-1",
            feedback_items=[{
                "type": "delete_node",
                "target_id": "node-2",
            }],
        )
        assert len(result.applied) == 1
        assert "node-2" in mock_ontology.deleted_nodes

    @pytest.mark.asyncio
    async def test_add_relation(self, refiner, mock_ontology):
        """관계 추가 피드백."""
        result = await refiner.apply_feedback(
            case_id="case-1",
            tenant_id="tenant-1",
            feedback_items=[{
                "type": "add_relation",
                "content": {
                    "source_id": "node-1",
                    "target_id": "node-2",
                    "relation_type": "DERIVED_FROM",
                },
            }],
        )
        assert len(result.applied) == 1
        assert len(mock_ontology.created_relations) == 1

    @pytest.mark.asyncio
    async def test_move_layer(self, refiner, mock_ontology):
        """레이어 이동 피드백."""
        result = await refiner.apply_feedback(
            case_id="case-1",
            tenant_id="tenant-1",
            feedback_items=[{
                "type": "move_layer",
                "target_id": "node-1",
                "content": {"layer": "driver"},
            }],
        )
        assert len(result.applied) == 1
        assert result.applied[0]["new_layer"] == "driver"

    @pytest.mark.asyncio
    async def test_mixed_feedback(self, refiner, mock_ontology):
        """여러 타입의 피드백 동시 적용."""
        result = await refiner.apply_feedback(
            case_id="case-1",
            tenant_id="tenant-1",
            feedback_items=[
                {"type": "add_node", "content": {"id": "n1", "layer": "kpi", "properties": {"name": "New"}}},
                {"type": "update_node", "target_id": "node-1", "content": {"properties": {"name": "Modified"}}},
                {"type": "delete_node", "target_id": "node-2"},
            ],
        )
        assert len(result.applied) == 3
        assert len(result.rejected) == 0

    @pytest.mark.asyncio
    async def test_invalid_type_rejected(self, refiner):
        """알 수 없는 피드백 타입은 거부."""
        result = await refiner.apply_feedback(
            case_id="case-1",
            tenant_id="tenant-1",
            feedback_items=[{"type": "invalid_type"}],
        )
        assert len(result.rejected) == 1
        assert "알 수 없는" in result.rejected[0]["error"]

    @pytest.mark.asyncio
    async def test_add_relation_missing_ids_rejected(self, refiner):
        """source_id/target_id 없는 관계 추가는 거부."""
        result = await refiner.apply_feedback(
            case_id="case-1",
            tenant_id="tenant-1",
            feedback_items=[{
                "type": "add_relation",
                "content": {"relation_type": "USES"},
            }],
        )
        assert len(result.rejected) == 1

    @pytest.mark.asyncio
    async def test_no_ontology_service_raises(self):
        """OntologyService 없이 피드백 적용 시 rejected."""
        refiner = SchemaRefiner(ontology_service=None)
        result = await refiner.apply_feedback(
            case_id="case-1",
            tenant_id="tenant-1",
            feedback_items=[{"type": "add_node", "content": {"id": "x", "layer": "kpi", "properties": {}}}],
        )
        assert len(result.rejected) == 1

    @pytest.mark.asyncio
    async def test_version_id_generated(self, refiner):
        """피드백 결과에 새 버전 ID가 생성된다."""
        result = await refiner.apply_feedback(
            case_id="case-1",
            tenant_id="tenant-1",
            feedback_items=[],
        )
        assert result.new_version  # UUID 형태

    @pytest.mark.asyncio
    async def test_llm_refine_no_llm(self, mock_ontology):
        """LLM 없이 자연어 피드백은 거부."""
        refiner = SchemaRefiner(ontology_service=mock_ontology, llm_generate_fn=None)
        result = await refiner.refine_with_llm(
            case_id="case-1",
            tenant_id="tenant-1",
            natural_feedback="OEE에 에너지 지표 추가",
        )
        assert len(result.rejected) == 1
        assert "LLM" in result.rejected[0]["error"]
