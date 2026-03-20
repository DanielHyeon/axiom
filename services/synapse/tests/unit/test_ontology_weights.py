"""
온톨로지 관계 가중치(weight/lag/confidence) 단위 테스트.

테스트 대상:
- _normalize_relation: falsy-value 안전 추출, 범위 검증, enum 검증
- update_relation: 속성 머지, tenant_id 검증, 존재하지 않는 관계 404
- bulk_update_relations: 일괄 생성/업데이트, compound index 최적화
- _normalize_node: VALID_LAYERS 검증, driver 레이어 지원
- get_case_ontology: min_weight/min_confidence 필터
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.ontology import ontology_service


# ── Fixtures ──────────────────────────────────────────────────

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
CASE_ID = "case-weights-test"
TENANT_ID = "system"  # TenantMiddleware 기본값


async def _create_two_nodes(ac: AsyncClient):
    """테스트용 노드 2개 생성 헬퍼"""
    await ac.post("/api/v3/synapse/ontology/nodes", json={
        "id": "node-src", "case_id": CASE_ID, "layer": "driver",
        "properties": {"name": "원가 지수"},
    }, headers=HEADERS)
    await ac.post("/api/v3/synapse/ontology/nodes", json={
        "id": "node-tgt", "case_id": CASE_ID, "layer": "kpi",
        "properties": {"name": "불량률"},
    }, headers=HEADERS)


# ── _normalize_relation 테스트 ────────────────────────────────


class TestNormalizeRelation:
    """_normalize_relation 메서드의 가중치 추출/검증 테스트"""

    def test_weight_lag_confidence_from_payload(self):
        """최상위 키에서 weight/lag/confidence 추출"""
        rel = ontology_service._normalize_relation("t1", {
            "case_id": "c1", "source_id": "a", "target_id": "b",
            "type": "CAUSES", "weight": 0.75, "lag": 3, "confidence": 0.88,
        })
        assert rel["properties"]["weight"] == 0.75
        assert rel["properties"]["lag"] == 3
        assert rel["properties"]["confidence"] == 0.88

    def test_weight_zero_is_preserved(self):
        """CRITICAL: weight=0.0이 무시되지 않고 정상 저장됨"""
        rel = ontology_service._normalize_relation("t1", {
            "case_id": "c1", "source_id": "a", "target_id": "b",
            "weight": 0.0, "lag": 0, "confidence": 0.0,
        })
        assert rel["properties"]["weight"] == 0.0
        assert rel["properties"]["lag"] == 0
        assert rel["properties"]["confidence"] == 0.0

    def test_weight_from_properties_dict(self):
        """properties dict 내부에서도 가중치 추출"""
        rel = ontology_service._normalize_relation("t1", {
            "case_id": "c1", "source_id": "a", "target_id": "b",
            "properties": {"weight": 0.5, "lag": 2, "confidence": 0.9},
        })
        assert rel["properties"]["weight"] == 0.5
        assert rel["properties"]["lag"] == 2
        assert rel["properties"]["confidence"] == 0.9

    def test_weight_clamped_to_range(self):
        """weight/confidence는 0.0~1.0으로 클램핑"""
        rel = ontology_service._normalize_relation("t1", {
            "case_id": "c1", "source_id": "a", "target_id": "b",
            "weight": 2.5, "confidence": -0.3,
        })
        assert rel["properties"]["weight"] == 1.0
        assert rel["properties"]["confidence"] == 0.0

    def test_lag_clamped_to_non_negative(self):
        """lag는 0 이상으로 클램핑"""
        rel = ontology_service._normalize_relation("t1", {
            "case_id": "c1", "source_id": "a", "target_id": "b",
            "lag": -5,
        })
        assert rel["properties"]["lag"] == 0

    def test_payload_overrides_properties(self):
        """payload 최상위 키가 properties 내부 키보다 우선"""
        rel = ontology_service._normalize_relation("t1", {
            "case_id": "c1", "source_id": "a", "target_id": "b",
            "weight": 0.8,
            "properties": {"weight": 0.3},
        })
        assert rel["properties"]["weight"] == 0.8

    def test_direction_validation(self):
        """direction은 positive/negative만 허용"""
        rel = ontology_service._normalize_relation("t1", {
            "case_id": "c1", "source_id": "a", "target_id": "b",
            "direction": "positive",
        })
        assert rel["properties"]["direction"] == "positive"

        # 잘못된 direction은 저장되지 않음
        rel2 = ontology_service._normalize_relation("t1", {
            "case_id": "c1", "source_id": "a", "target_id": "b",
            "direction": "invalid",
        })
        assert "direction" not in rel2["properties"]

    def test_method_and_layer_metadata(self):
        """method, source_layer, target_layer 등 메타데이터 추출"""
        rel = ontology_service._normalize_relation("t1", {
            "case_id": "c1", "source_id": "a", "target_id": "b",
            "method": "granger", "source_layer": "Driver", "target_layer": "KPI",
            "from_field": "cost_idx", "to_field": "defect_rate",
        })
        assert rel["properties"]["method"] == "granger"
        assert rel["properties"]["source_layer"] == "Driver"
        assert rel["properties"]["target_layer"] == "KPI"
        assert rel["properties"]["from_field"] == "cost_idx"
        assert rel["properties"]["to_field"] == "defect_rate"

    def test_unknown_relation_type_fallback(self):
        """허용되지 않은 관계 타입은 RELATED_TO로 폴백"""
        rel = ontology_service._normalize_relation("t1", {
            "case_id": "c1", "source_id": "a", "target_id": "b",
            "type": "INVALID_TYPE",
        })
        assert rel["type"] == "RELATED_TO"

    def test_allowed_relation_types(self):
        """허용된 관계 타입은 그대로 통과"""
        for allowed_type in ("CAUSES", "INFLUENCES", "DERIVED_FROM", "OBSERVED_IN"):
            rel = ontology_service._normalize_relation("t1", {
                "case_id": "c1", "source_id": "a", "target_id": "b",
                "type": allowed_type,
            })
            assert rel["type"] == allowed_type

    def test_none_weight_not_stored(self):
        """weight가 None이면 properties에 저장하지 않음"""
        rel = ontology_service._normalize_relation("t1", {
            "case_id": "c1", "source_id": "a", "target_id": "b",
        })
        assert "weight" not in rel["properties"]
        assert "lag" not in rel["properties"]
        assert "confidence" not in rel["properties"]


# ── _normalize_node 테스트 ────────────────────────────────────


class TestNormalizeNode:
    """_normalize_node 메서드의 VALID_LAYERS 검증 테스트"""

    def test_driver_layer_accepted(self):
        """driver는 유효한 레이어로 허용됨 (5번째 레이어)"""
        node = ontology_service._normalize_node("t1", {
            "case_id": "c1", "id": "n1", "layer": "driver",
        })
        assert node["layer"] == "driver"

    def test_all_valid_layers(self):
        """모든 유효한 레이어 검증"""
        for layer in ("kpi", "measure", "process", "resource", "driver"):
            node = ontology_service._normalize_node("t1", {
                "case_id": "c1", "id": f"n-{layer}", "layer": layer,
            })
            assert node["layer"] == layer

    def test_invalid_layer_fallback_to_resource(self):
        """유효하지 않은 레이어는 resource로 폴백"""
        node = ontology_service._normalize_node("t1", {
            "case_id": "c1", "id": "n1", "layer": "unknown_layer",
        })
        assert node["layer"] == "resource"

    def test_empty_layer_fallback_to_resource(self):
        """빈 레이어는 resource로 폴백"""
        node = ontology_service._normalize_node("t1", {
            "case_id": "c1", "id": "n1", "layer": "",
        })
        assert node["layer"] == "resource"


# ── update_relation API 테스트 ────────────────────────────────


class TestUpdateRelationAPI:
    """PATCH /relations/{id} 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_update_relation_weight(self, ac: AsyncClient):
        """관계의 weight를 업데이트"""
        await _create_two_nodes(ac)
        # 관계 생성
        resp = await ac.post("/api/v3/synapse/ontology/relations", json={
            "case_id": CASE_ID, "source_id": "node-src", "target_id": "node-tgt",
            "type": "CAUSES", "weight": 0.5,
        }, headers=HEADERS)
        assert resp.status_code == 200
        rel_id = resp.json()["data"]["id"]

        # weight 업데이트
        patch_resp = await ac.patch(f"/api/v3/synapse/ontology/relations/{rel_id}", json={
            "weight": 0.9, "confidence": 0.85,
        }, headers=HEADERS)
        assert patch_resp.status_code == 200
        data = patch_resp.json()["data"]
        assert data["properties"]["weight"] == 0.9
        assert data["properties"]["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_update_relation_not_found(self, ac: AsyncClient):
        """존재하지 않는 관계 업데이트 시 404"""
        resp = await ac.patch("/api/v3/synapse/ontology/relations/nonexistent", json={
            "weight": 0.5,
        }, headers=HEADERS)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_relation_preserves_existing(self, ac: AsyncClient):
        """업데이트 시 기존 속성이 보존됨"""
        await _create_two_nodes(ac)
        resp = await ac.post("/api/v3/synapse/ontology/relations", json={
            "case_id": CASE_ID, "source_id": "node-src", "target_id": "node-tgt",
            "type": "CAUSES", "weight": 0.5, "lag": 3,
        }, headers=HEADERS)
        rel_id = resp.json()["data"]["id"]

        # weight만 업데이트 -> lag 유지
        patch_resp = await ac.patch(f"/api/v3/synapse/ontology/relations/{rel_id}", json={
            "weight": 0.9,
        }, headers=HEADERS)
        data = patch_resp.json()["data"]
        assert data["properties"]["weight"] == 0.9
        assert data["properties"]["lag"] == 3  # 기존 값 유지

    @pytest.mark.asyncio
    async def test_update_relation_zero_weight(self, ac: AsyncClient):
        """CRITICAL: weight=0.0 업데이트가 정상 동작"""
        await _create_two_nodes(ac)
        resp = await ac.post("/api/v3/synapse/ontology/relations", json={
            "case_id": CASE_ID, "source_id": "node-src", "target_id": "node-tgt",
            "type": "CAUSES", "weight": 0.8,
        }, headers=HEADERS)
        rel_id = resp.json()["data"]["id"]

        # weight를 0.0으로 업데이트
        patch_resp = await ac.patch(f"/api/v3/synapse/ontology/relations/{rel_id}", json={
            "weight": 0.0,
        }, headers=HEADERS)
        data = patch_resp.json()["data"]
        assert data["properties"]["weight"] == 0.0


# ── bulk_update_relations API 테스트 ──────────────────────────


class TestBulkUpdateRelationsAPI:
    """PATCH /cases/{case_id}/relations:bulk 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_bulk_create_and_update(self, ac: AsyncClient):
        """일괄 업데이트: 새 관계 생성 + 기존 관계 업데이트"""
        await _create_two_nodes(ac)

        # 기존 관계 하나 생성
        await ac.post("/api/v3/synapse/ontology/relations", json={
            "case_id": CASE_ID, "source_id": "node-src", "target_id": "node-tgt",
            "type": "CAUSES", "weight": 0.3,
        }, headers=HEADERS)

        # 세 번째 노드 추가
        await ac.post("/api/v3/synapse/ontology/nodes", json={
            "id": "node-mid", "case_id": CASE_ID, "layer": "measure",
            "properties": {"name": "중간 지표"},
        }, headers=HEADERS)

        # 일괄 업데이트: 기존 CAUSES 업데이트 + 새 INFLUENCES 생성
        resp = await ac.patch(f"/api/v3/synapse/ontology/cases/{CASE_ID}/relations:bulk", json={
            "updates": [
                {"source_id": "node-src", "target_id": "node-tgt", "type": "CAUSES", "weight": 0.9},
                {"source_id": "node-src", "target_id": "node-mid", "type": "INFLUENCES", "weight": 0.6},
            ],
        }, headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["updated"] == 1
        assert data["created"] == 1
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_bulk_empty_updates(self, ac: AsyncClient):
        """빈 updates 목록은 400 에러"""
        resp = await ac.patch(f"/api/v3/synapse/ontology/cases/{CASE_ID}/relations:bulk", json={
            "updates": [],
        }, headers=HEADERS)
        assert resp.status_code == 400


# ── get_case_ontology 필터 테스트 ─────────────────────────────


class TestOntologyWeightFilter:
    """min_weight/min_confidence 필터 테스트"""

    @pytest.mark.asyncio
    async def test_min_weight_filter(self, ac: AsyncClient):
        """min_weight 필터로 낮은 가중치 관계 제외"""
        await _create_two_nodes(ac)

        # 세 번째 노드 + 관계 2개 (다른 가중치)
        await ac.post("/api/v3/synapse/ontology/nodes", json={
            "id": "node-mid", "case_id": CASE_ID, "layer": "measure",
        }, headers=HEADERS)

        await ac.post("/api/v3/synapse/ontology/relations", json={
            "case_id": CASE_ID, "source_id": "node-src", "target_id": "node-tgt",
            "type": "CAUSES", "weight": 0.9, "confidence": 0.85,
        }, headers=HEADERS)
        await ac.post("/api/v3/synapse/ontology/relations", json={
            "case_id": CASE_ID, "source_id": "node-src", "target_id": "node-mid",
            "type": "INFLUENCES", "weight": 0.2, "confidence": 0.3,
        }, headers=HEADERS)

        # min_weight=0.5 -> weight=0.2 관계 제외
        resp = await ac.get(
            f"/api/v3/synapse/ontology/cases/{CASE_ID}/ontology?min_weight=0.5",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["summary"]["total_relations"] == 1

    @pytest.mark.asyncio
    async def test_min_confidence_filter(self, ac: AsyncClient):
        """min_confidence 필터로 낮은 신뢰도 관계 제외"""
        await _create_two_nodes(ac)
        await ac.post("/api/v3/synapse/ontology/relations", json={
            "case_id": CASE_ID, "source_id": "node-src", "target_id": "node-tgt",
            "type": "CAUSES", "confidence": 0.4,
        }, headers=HEADERS)

        # min_confidence=0.5 -> confidence=0.4 관계 제외
        resp = await ac.get(
            f"/api/v3/synapse/ontology/cases/{CASE_ID}/ontology?min_confidence=0.5",
            headers=HEADERS,
        )
        data = resp.json()["data"]
        assert data["summary"]["total_relations"] == 0

    @pytest.mark.asyncio
    async def test_no_filter_returns_all(self, ac: AsyncClient):
        """필터 없으면 모든 관계 반환"""
        await _create_two_nodes(ac)
        await ac.post("/api/v3/synapse/ontology/relations", json={
            "case_id": CASE_ID, "source_id": "node-src", "target_id": "node-tgt",
            "type": "CAUSES",
        }, headers=HEADERS)

        resp = await ac.get(
            f"/api/v3/synapse/ontology/cases/{CASE_ID}/ontology",
            headers=HEADERS,
        )
        data = resp.json()["data"]
        assert data["summary"]["total_relations"] == 1


# ── 관계 생성 시 가중치 포함 테스트 ───────────────────────────


class TestCreateRelationWithWeights:
    """POST /relations에서 가중치 속성 포함 테스트"""

    @pytest.mark.asyncio
    async def test_create_with_weight(self, ac: AsyncClient):
        """관계 생성 시 weight/lag/confidence 포함"""
        await _create_two_nodes(ac)
        resp = await ac.post("/api/v3/synapse/ontology/relations", json={
            "case_id": CASE_ID, "source_id": "node-src", "target_id": "node-tgt",
            "type": "CAUSES", "weight": 0.75, "lag": 3, "confidence": 0.88,
            "direction": "negative", "method": "granger",
        }, headers=HEADERS)
        assert resp.status_code == 200
        props = resp.json()["data"]["properties"]
        assert props["weight"] == 0.75
        assert props["lag"] == 3
        assert props["confidence"] == 0.88
        assert props["direction"] == "negative"
        assert props["method"] == "granger"

    @pytest.mark.asyncio
    async def test_create_without_weight_backward_compat(self, ac: AsyncClient):
        """가중치 없이 관계 생성 — 하위 호환"""
        await _create_two_nodes(ac)
        resp = await ac.post("/api/v3/synapse/ontology/relations", json={
            "case_id": CASE_ID, "source_id": "node-src", "target_id": "node-tgt",
            "type": "DERIVED_FROM",
        }, headers=HEADERS)
        assert resp.status_code == 200
        props = resp.json()["data"]["properties"]
        assert "weight" not in props
        assert "lag" not in props
        assert "confidence" not in props


# ── driver 레이어 노드 테스트 ─────────────────────────────────


class TestDriverLayer:
    """5번째 레이어 'driver' 지원 테스트"""

    @pytest.mark.asyncio
    async def test_create_driver_node(self, ac: AsyncClient):
        """driver 레이어 노드 생성"""
        resp = await ac.post("/api/v3/synapse/ontology/nodes", json={
            "id": "drv-1", "case_id": CASE_ID, "layer": "driver",
            "properties": {"name": "원가 지수"},
        }, headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["layer"] == "driver"

    @pytest.mark.asyncio
    async def test_driver_layer_in_summary(self, ac: AsyncClient):
        """driver 레이어가 summary에 표시"""
        await ac.post("/api/v3/synapse/ontology/nodes", json={
            "id": "drv-1", "case_id": CASE_ID, "layer": "driver",
        }, headers=HEADERS)
        resp = await ac.get(f"/api/v3/synapse/ontology/cases/{CASE_ID}/ontology", headers=HEADERS)
        by_layer = resp.json()["data"]["summary"]["by_layer"]
        assert by_layer.get("driver") == 1
