"""
L4 Reasoning & Governance — 충돌 탐지 + 영향 분석 단위 테스트

FakeSemanticStore를 사용하여 PostgreSQL 없이 API 동작을 검증한다.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api import semantic_contract as sc_module

AUTH = {"Authorization": "Bearer local-oracle-token"}

# FakeStore는 기존 test_semantic_contract_api에서 가져온다
from tests.unit.test_semantic_contract_api import FakeSemanticStore


# ── Fixtures ──

@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def fake_store():
    """테스트마다 FakeStore 주입 → 테스트 간 격리"""
    fake = FakeSemanticStore()
    sc_module._store = fake
    from app.services.semantic_compiler import SemanticCompiler
    sc_module._compiler = SemanticCompiler(fake)
    yield fake


# ========================================
# 충돌 탐지 테스트
# ========================================

@pytest.mark.asyncio
async def test_concept_name_conflict_detected(ac, fake_store):
    """동일 name_ko를 가진 두 개념이 concept_conflicts에 포함된다"""
    fake_store.create_concept("system", {
        "concept_id": "c1", "case_id": "case-1", "name_ko": "활성 고객",
        "description": "정의 A",
    })
    fake_store.create_concept("system", {
        "concept_id": "c2", "case_id": "case-1", "name_ko": "활성 고객",
        "description": "정의 B",
    })

    resp = await ac.get("/api/v3/synapse/semantic/conflicts", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True

    conflicts = body["data"]["concept_conflicts"]
    assert len(conflicts) >= 1

    # name_ko "활성 고객"에 대한 충돌 확인
    ko_conflict = [c for c in conflicts if c["name"] == "활성 고객" and c["field"] == "name_ko"]
    assert len(ko_conflict) == 1
    assert set(ko_conflict[0]["concept_ids"]) == {"c1", "c2"}


@pytest.mark.asyncio
async def test_no_conflict_when_unique(ac, fake_store):
    """이름이 모두 고유하면 충돌이 없다"""
    fake_store.create_concept("system", {
        "concept_id": "a", "case_id": "c", "name_ko": "개념A",
    })
    fake_store.create_concept("system", {
        "concept_id": "b", "case_id": "c", "name_ko": "개념B",
    })

    resp = await ac.get("/api/v3/synapse/semantic/conflicts", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["concept_conflicts"] == []
    assert data["measure_conflicts"] == []
    assert data["term_collisions"] == []


@pytest.mark.asyncio
async def test_measure_name_conflict(ac, fake_store):
    """동일 name을 가진 두 지표가 measure_conflicts에 포함된다"""
    fake_store.create_entity("system", {
        "entity_id": "e1", "case_id": "c", "physical_source_ref": "t1",
    })
    fake_store.create_measure("system", {
        "measure_id": "m1", "entity_id": "e1", "case_id": "c",
        "name": "총매출", "sql_expression": "SUM(amount)",
        "bound_concept_id": None,
    })
    fake_store.create_measure("system", {
        "measure_id": "m2", "entity_id": "e1", "case_id": "c",
        "name": "총매출", "sql_expression": "SUM(total)",
        "bound_concept_id": None,
    })

    resp = await ac.get("/api/v3/synapse/semantic/conflicts", headers=AUTH)
    assert resp.status_code == 200
    mc = resp.json()["data"]["measure_conflicts"]
    assert len(mc) == 1
    assert set(mc[0]["measure_ids"]) == {"m1", "m2"}


@pytest.mark.asyncio
async def test_term_collision(ac, fake_store):
    """동일 surface_form이 서로 다른 concept_id에 매핑되면 term_collisions에 포함된다"""
    fake_store.create_concept("system", {
        "concept_id": "x", "case_id": "c", "name_ko": "X개념",
    })
    fake_store.create_concept("system", {
        "concept_id": "y", "case_id": "c", "name_ko": "Y개념",
    })
    fake_store.create_term("system", {
        "concept_id": "x", "surface_form": "고객", "language": "ko",
    })
    fake_store.create_term("system", {
        "concept_id": "y", "surface_form": "고객", "language": "ko",
    })

    resp = await ac.get("/api/v3/synapse/semantic/conflicts", headers=AUTH)
    assert resp.status_code == 200
    tc = resp.json()["data"]["term_collisions"]
    assert len(tc) == 1
    assert set(tc[0]["concept_ids"]) == {"x", "y"}
    assert tc[0]["surface_form"] == "고객"


# ========================================
# 영향 분석 테스트
# ========================================

@pytest.mark.asyncio
async def test_impact_concept_affects_measures(ac, fake_store):
    """개념 변경 시 바인딩된 지표/차원이 affected에 포함된다"""
    fake_store.create_concept("system", {
        "concept_id": "cust", "case_id": "c", "name_ko": "고객",
    })
    fake_store.create_entity("system", {
        "entity_id": "e_sales", "case_id": "c", "physical_source_ref": "sales",
        "bound_concept_id": "cust",
    })
    fake_store.create_measure("system", {
        "measure_id": "m_rev", "entity_id": "e_sales", "case_id": "c",
        "name": "매출", "sql_expression": "SUM(revenue)",
        "bound_concept_id": "cust",
    })

    resp = await ac.get("/api/v3/synapse/semantic/impact/concept/cust", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["object_type"] == "concept"
    assert body["data"]["object_id"] == "cust"
    assert "m_rev" in body["data"]["affected"]["measures"]
    assert "e_sales" in body["data"]["affected"]["entities"]
    assert body["data"]["total_affected"] >= 2


@pytest.mark.asyncio
async def test_impact_measure_affects_context_packs(ac, fake_store):
    """지표 변경 시 포함된 컨텍스트 팩이 affected에 포함된다"""
    fake_store.create_entity("system", {
        "entity_id": "e1", "case_id": "c", "physical_source_ref": "t1",
    })
    fake_store.create_measure("system", {
        "measure_id": "revenue", "entity_id": "e1", "case_id": "c",
        "name": "매출", "sql_expression": "SUM(amount)",
    })
    fake_store.create_context_pack("system", {
        "context_pack_id": "cp_kpi", "case_id": "c",
        "intent_type": "kpi_query",
        "included_measure_ids": ["revenue"],
    })

    resp = await ac.get("/api/v3/synapse/semantic/impact/measure/revenue", headers=AUTH)
    assert resp.status_code == 200
    affected = resp.json()["data"]["affected"]
    assert "cp_kpi" in affected["context_packs"]
    assert "e1" in affected["entities"]


@pytest.mark.asyncio
async def test_impact_entity_affects_measures_dimensions(ac, fake_store):
    """엔티티 변경 시 바인딩된 지표/차원/조인/그레인이 affected에 포함된다"""
    fake_store.create_entity("system", {
        "entity_id": "e_order", "case_id": "c", "physical_source_ref": "orders",
    })
    fake_store.create_entity("system", {
        "entity_id": "e_customer", "case_id": "c", "physical_source_ref": "customers",
    })
    fake_store.create_measure("system", {
        "measure_id": "m_qty", "entity_id": "e_order", "case_id": "c",
        "name": "주문수량", "sql_expression": "COUNT(*)",
    })
    fake_store.create_dimension("system", {
        "dimension_id": "d_date", "entity_id": "e_order", "case_id": "c",
        "name": "주문일자", "sql_expression": "order_date",
    })
    fake_store.create_join_contract("system", {
        "join_id": "j_oc", "left_entity_id": "e_order", "right_entity_id": "e_customer",
        "case_id": "c", "join_condition": "e_order.cust_id = e_customer.id",
    })
    fake_store.create_grain_contract("system", {
        "grain_id": "g_order", "entity_id": "e_order", "case_id": "c",
        "grain_key_set": ["order_id"],
    })

    resp = await ac.get("/api/v3/synapse/semantic/impact/entity/e_order", headers=AUTH)
    assert resp.status_code == 200
    affected = resp.json()["data"]["affected"]
    assert "m_qty" in affected["measures"]
    assert "d_date" in affected["dimensions"]
    assert "j_oc" in affected["joins"]
    assert "g_order" in affected["grains"]


@pytest.mark.asyncio
async def test_impact_unknown_object_empty(ac, fake_store):
    """존재하지 않는 객체에 대한 영향 분석은 빈 결과를 반환한다"""
    resp = await ac.get("/api/v3/synapse/semantic/impact/concept/nonexistent", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_affected"] == 0
    assert all(len(v) == 0 for v in data["affected"].values())


@pytest.mark.asyncio
async def test_impact_invalid_object_type(ac, fake_store):
    """유효하지 않은 object_type은 400 에러를 반환한다"""
    resp = await ac.get("/api/v3/synapse/semantic/impact/unknown_type/some_id", headers=AUTH)
    assert resp.status_code == 400
    assert "object_type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_impact_join_affects_context_packs(ac, fake_store):
    """조인 변경 시 allowed/banned 컨텍스트 팩이 affected에 포함된다"""
    fake_store.create_entity("system", {
        "entity_id": "e_a", "case_id": "c", "physical_source_ref": "ta",
    })
    fake_store.create_entity("system", {
        "entity_id": "e_b", "case_id": "c", "physical_source_ref": "tb",
    })
    fake_store.create_join_contract("system", {
        "join_id": "j_ab", "left_entity_id": "e_a", "right_entity_id": "e_b",
        "case_id": "c", "join_condition": "a.id = b.a_id",
    })
    fake_store.create_context_pack("system", {
        "context_pack_id": "cp_with_join", "case_id": "c",
        "intent_type": "general",
        "allowed_join_ids": ["j_ab"],
    })

    resp = await ac.get("/api/v3/synapse/semantic/impact/join/j_ab", headers=AUTH)
    assert resp.status_code == 200
    affected = resp.json()["data"]["affected"]
    assert "cp_with_join" in affected["context_packs"]
    assert set(affected["entities"]) == {"e_a", "e_b"}
