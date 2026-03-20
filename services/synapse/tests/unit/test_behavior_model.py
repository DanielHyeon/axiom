"""
BehaviorModel CRUD 및 model-graph API 단위 테스트.

테스트 대상:
- POST /cases/{case_id}/behavior-models: BehaviorModel 생성 + READS/PREDICTS 링크
- GET /cases/{case_id}/behavior-models: 모델 목록 조회
- GET /cases/{case_id}/model-graph: 시뮬레이션용 DAG 구조 반환
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.ontology import ontology_service


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def reset_state():
    """매 테스트마다 인메모리 상태 초기화"""
    ontology_service.clear()
    yield
    ontology_service.clear()


HEADERS = {"Authorization": "Bearer local-oracle-token"}
CASE_ID = "case-bm-test"


async def _setup_ontology_nodes(ac: AsyncClient):
    """테스트용 온톨로지 노드 3개 생성"""
    for node in [
        {"id": "node-costs", "case_id": CASE_ID, "layer": "driver", "properties": {"name": "원가 지수"}},
        {"id": "node-quality", "case_id": CASE_ID, "layer": "kpi", "properties": {"name": "품질 지표"}},
        {"id": "node-temp", "case_id": CASE_ID, "layer": "measure", "properties": {"name": "온도"}},
    ]:
        resp = await ac.post("/api/v3/synapse/ontology/nodes", json=node, headers=HEADERS)
        assert resp.status_code == 200


class TestBehaviorModelCreate:
    """POST /cases/{case_id}/behavior-models 테스트"""

    @pytest.mark.asyncio
    async def test_create_behavior_model(self, ac: AsyncClient):
        """기본 BehaviorModel 생성"""
        await _setup_ontology_nodes(ac)
        resp = await ac.post(f"/api/v3/synapse/ontology/cases/{CASE_ID}/behavior-models", json={
            "name": "불량률 예측",
            "model_type": "RandomForest",
            "status": "trained",
            "reads": [
                {"source_node_id": "node-costs", "field": "cost_index", "lag": 0},
                {"source_node_id": "node-temp", "field": "temperature", "lag": 3},
            ],
            "predicts": [
                {"target_node_id": "node-quality", "field": "defect_rate", "confidence": 0.85},
            ],
        }, headers=HEADERS)

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "불량률 예측"
        assert data["model_type"] == "RandomForest"
        assert data["status"] == "trained"
        assert data["behavior_type"] == "Model"
        # 링크 생성 확인
        links = data["links"]
        reads = [l for l in links if l["link_type"] == "READS_FIELD"]
        predicts = [l for l in links if l["link_type"] == "PREDICTS_FIELD"]
        assert len(reads) == 2
        assert len(predicts) == 1
        assert predicts[0]["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_create_model_minimal(self, ac: AsyncClient):
        """최소 필드로 모델 생성 (reads/predicts 없음)"""
        resp = await ac.post(f"/api/v3/synapse/ontology/cases/{CASE_ID}/behavior-models", json={
            "name": "빈 모델",
        }, headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "빈 모델"
        assert data["status"] == "pending"
        assert data["links"] == []


class TestBehaviorModelList:
    """GET /cases/{case_id}/behavior-models 테스트"""

    @pytest.mark.asyncio
    async def test_list_empty(self, ac: AsyncClient):
        """모델이 없을 때 빈 목록 반환"""
        resp = await ac.get(f"/api/v3/synapse/ontology/cases/{CASE_ID}/behavior-models", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_list_multiple_models(self, ac: AsyncClient):
        """여러 모델 생성 후 목록 조회"""
        await _setup_ontology_nodes(ac)
        for name in ["모델A", "모델B", "모델C"]:
            await ac.post(f"/api/v3/synapse/ontology/cases/{CASE_ID}/behavior-models", json={
                "name": name,
            }, headers=HEADERS)

        resp = await ac.get(f"/api/v3/synapse/ontology/cases/{CASE_ID}/behavior-models", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["total"] == 3


class TestModelGraph:
    """GET /cases/{case_id}/model-graph 테스트"""

    @pytest.mark.asyncio
    async def test_model_graph_structure(self, ac: AsyncClient):
        """model-graph가 올바른 구조(models, reads, predicts)를 반환"""
        await _setup_ontology_nodes(ac)
        await ac.post(f"/api/v3/synapse/ontology/cases/{CASE_ID}/behavior-models", json={
            "name": "불량률 예측",
            "model_type": "RandomForest",
            "status": "trained",
            "reads": [
                {"source_node_id": "node-costs", "field": "cost_index", "lag": 0},
                {"source_node_id": "node-temp", "field": "temperature", "lag": 3},
            ],
            "predicts": [
                {"target_node_id": "node-quality", "field": "defect_rate", "confidence": 0.85},
            ],
        }, headers=HEADERS)

        resp = await ac.get(f"/api/v3/synapse/ontology/cases/{CASE_ID}/model-graph", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()["data"]

        # 구조 검증
        assert "models" in data
        assert "reads" in data
        assert "predicts" in data

        # 모델 1개
        assert len(data["models"]) == 1
        model = data["models"][0]
        assert model["name"] == "불량률 예측"
        assert model["status"] == "trained"

        # reads 2개
        assert len(data["reads"]) == 2
        reads_fields = {r["field"] for r in data["reads"]}
        assert reads_fields == {"cost_index", "temperature"}

        # predicts 1개
        assert len(data["predicts"]) == 1
        pred = data["predicts"][0]
        assert pred["field"] == "defect_rate"
        assert pred["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_model_graph_empty(self, ac: AsyncClient):
        """모델이 없을 때 빈 그래프 반환"""
        resp = await ac.get(f"/api/v3/synapse/ontology/cases/{CASE_ID}/model-graph", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["models"] == []
        assert data["reads"] == []
        assert data["predicts"] == []

    @pytest.mark.asyncio
    async def test_model_graph_multiple_models(self, ac: AsyncClient):
        """여러 모델이 있을 때 모든 모델과 링크 반환"""
        await _setup_ontology_nodes(ac)

        # 모델 1: costs -> quality
        await ac.post(f"/api/v3/synapse/ontology/cases/{CASE_ID}/behavior-models", json={
            "name": "모델1",
            "reads": [{"source_node_id": "node-costs", "field": "cost_index"}],
            "predicts": [{"target_node_id": "node-quality", "field": "defect_rate", "confidence": 0.8}],
        }, headers=HEADERS)

        # 모델 2: temp -> quality
        await ac.post(f"/api/v3/synapse/ontology/cases/{CASE_ID}/behavior-models", json={
            "name": "모델2",
            "reads": [{"source_node_id": "node-temp", "field": "temperature", "lag": 2}],
            "predicts": [{"target_node_id": "node-quality", "field": "quality_score", "confidence": 0.7}],
        }, headers=HEADERS)

        resp = await ac.get(f"/api/v3/synapse/ontology/cases/{CASE_ID}/model-graph", headers=HEADERS)
        data = resp.json()["data"]
        assert len(data["models"]) == 2
        assert len(data["reads"]) == 2
        assert len(data["predicts"]) == 2


class TestBehaviorModelService:
    """OntologyService의 BehaviorModel 메서드 직접 테스트"""

    @pytest.mark.asyncio
    async def test_create_and_list(self):
        """서비스 레벨에서 생성 + 목록 조회"""
        result = await ontology_service.create_behavior_model(
            tenant_id="t1", case_id="c1",
            model_data={"name": "test_model", "model_type": "LinearRegression"},
        )
        assert result["name"] == "test_model"
        assert result["behavior_type"] == "Model"

        models = await ontology_service.list_behavior_models("c1")
        assert len(models) == 1
        assert models[0]["name"] == "test_model"

    @pytest.mark.asyncio
    async def test_model_graph_from_memory(self):
        """인메모리에서 모델 그래프 빌드"""
        await ontology_service.create_behavior_model(
            tenant_id="t1", case_id="c1",
            model_data={
                "name": "pred_model",
                "reads": [{"source_node_id": "n1", "field": "x1", "lag": 0}],
                "predicts": [{"target_node_id": "n2", "field": "y1", "confidence": 0.9}],
            },
        )
        graph = ontology_service._build_model_graph_from_memory("c1")
        assert len(graph["models"]) == 1
        assert len(graph["reads"]) == 1
        assert len(graph["predicts"]) == 1
        assert graph["reads"][0]["field"] == "x1"
        assert graph["predicts"][0]["confidence"] == 0.9
