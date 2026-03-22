"""
온톨로지 규칙(OntologyRule) + 정책(OntologyPolicy) API 단위 테스트

FakeSemanticStore를 재활용하여 PostgreSQL 없이 API 동작을 검증한다.
10+ 테스트: 규칙 CRUD, 정책 CRUD, 유효성 검증, 필터링
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api import semantic_contract as sc_module

AUTH = {"Authorization": "Bearer local-oracle-token"}
BASE = "/api/v3/synapse/semantic"


# ── Fixtures: 기존 test_semantic_contract_api.py의 FakeStore를 재활용 ──

from tests.unit.test_semantic_contract_api import FakeSemanticStore


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def _inject_fake_store():
    """테스트마다 FakeStore 주입 → 테스트 간 격리"""
    fake = FakeSemanticStore()
    sc_module._store = fake
    from app.services.semantic_compiler import SemanticCompiler
    sc_module._compiler = SemanticCompiler(fake)
    yield fake


async def _create_concept(ac):
    """테스트 헬퍼: 규칙/정책 바인딩용 개념 생성"""
    resp = await ac.post(f"{BASE}/concepts", json={
        "concept_id": "cust.active",
        "case_id": "case-1",
        "name_ko": "활성 고객",
    }, headers=AUTH)
    assert resp.status_code == 201
    return resp.json()


# ========================================
# 온톨로지 규칙 테스트
# ========================================

@pytest.mark.asyncio
async def test_create_rule(ac, _inject_fake_store):
    """규칙 생성 → 201 + 올바른 필드 반환"""
    await _create_concept(ac)
    resp = await ac.post(f"{BASE}/rules", json={
        "rule_id": "rule-001",
        "concept_id": "cust.active",
        "rule_type": "definition",
        "rule_expression": "status = 'active' AND last_login > NOW() - INTERVAL '90 days'",
        "expression_lang": "sql",
        "severity": "error",
        "description": "활성 고객 정의: 90일 이내 로그인 이력",
    }, headers=AUTH)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["rule_id"] == "rule-001"
    assert data["rule_type"] == "definition"
    assert data["expression_lang"] == "sql"


@pytest.mark.asyncio
async def test_list_rules_by_concept(ac, _inject_fake_store):
    """개념별 규칙 필터링"""
    await _create_concept(ac)
    # 규칙 2개 생성
    await ac.post(f"{BASE}/rules", json={
        "rule_id": "rule-a", "concept_id": "cust.active",
        "rule_type": "definition", "rule_expression": "x = 1",
    }, headers=AUTH)
    await ac.post(f"{BASE}/rules", json={
        "rule_id": "rule-b", "concept_id": "cust.active",
        "rule_type": "eligibility", "rule_expression": "age >= 18",
    }, headers=AUTH)
    resp = await ac.get(f"{BASE}/rules", params={"concept_id": "cust.active"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


@pytest.mark.asyncio
async def test_list_rules_by_type(ac, _inject_fake_store):
    """rule_type 필터로 규칙 조회"""
    await _create_concept(ac)
    await ac.post(f"{BASE}/rules", json={
        "rule_id": "rule-def", "concept_id": "cust.active",
        "rule_type": "definition", "rule_expression": "x = 1",
    }, headers=AUTH)
    await ac.post(f"{BASE}/rules", json={
        "rule_id": "rule-exc", "concept_id": "cust.active",
        "rule_type": "exclusion", "rule_expression": "blacklisted = true",
    }, headers=AUTH)
    resp = await ac.get(f"{BASE}/rules", params={"rule_type": "exclusion"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
    assert resp.json()["data"][0]["rule_id"] == "rule-exc"


@pytest.mark.asyncio
async def test_update_rule(ac, _inject_fake_store):
    """규칙 수정 → 변경된 필드 반영"""
    await _create_concept(ac)
    await ac.post(f"{BASE}/rules", json={
        "rule_id": "rule-upd", "concept_id": "cust.active",
        "rule_type": "definition", "rule_expression": "x = 1",
    }, headers=AUTH)
    resp = await ac.put(f"{BASE}/rules/rule-upd", json={
        "severity": "critical",
        "description": "수정된 설명",
    }, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["severity"] == "critical"
    assert data["description"] == "수정된 설명"


@pytest.mark.asyncio
async def test_delete_rule(ac, _inject_fake_store):
    """규칙 삭제 → 이후 조회 시 404"""
    await _create_concept(ac)
    await ac.post(f"{BASE}/rules", json={
        "rule_id": "rule-del", "concept_id": "cust.active",
        "rule_type": "policy", "rule_expression": "y > 0",
    }, headers=AUTH)
    resp = await ac.delete(f"{BASE}/rules/rule-del", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    # 조회 시 404
    resp2 = await ac.get(f"{BASE}/rules/rule-del", headers=AUTH)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_create_rule_invalid_type(ac, _inject_fake_store):
    """잘못된 rule_type → 400"""
    await _create_concept(ac)
    resp = await ac.post(f"{BASE}/rules", json={
        "rule_id": "rule-bad", "concept_id": "cust.active",
        "rule_type": "INVALID_TYPE", "rule_expression": "x = 1",
    }, headers=AUTH)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_rule_invalid_lang(ac, _inject_fake_store):
    """잘못된 expression_lang → 400"""
    await _create_concept(ac)
    resp = await ac.post(f"{BASE}/rules", json={
        "rule_id": "rule-lang", "concept_id": "cust.active",
        "rule_type": "definition", "rule_expression": "x = 1",
        "expression_lang": "rust",
    }, headers=AUTH)
    assert resp.status_code == 400


# ========================================
# 온톨로지 정책 테스트
# ========================================

@pytest.mark.asyncio
async def test_create_policy(ac, _inject_fake_store):
    """정책 생성 → 201 + 올바른 필드 반환"""
    await _create_concept(ac)
    resp = await ac.post(f"{BASE}/policies", json={
        "policy_id": "pol-001",
        "concept_id": "cust.active",
        "policy_type": "pii",
        "policy_expression": "MASK(email, '***@***')",
        "description": "고객 이메일 PII 마스킹 정책",
    }, headers=AUTH)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["policy_id"] == "pol-001"
    assert data["policy_type"] == "pii"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_active_policies(ac, _inject_fake_store):
    """is_active 필터로 활성 정책만 조회"""
    await _create_concept(ac)
    # 활성 정책 1개
    await ac.post(f"{BASE}/policies", json={
        "policy_id": "pol-active", "concept_id": "cust.active",
        "policy_type": "access", "policy_expression": "role IN ('admin','analyst')",
        "is_active": True,
    }, headers=AUTH)
    # 비활성 정책 1개
    await ac.post(f"{BASE}/policies", json={
        "policy_id": "pol-inactive", "concept_id": "cust.active",
        "policy_type": "retention", "policy_expression": "retain_days <= 365",
        "is_active": False,
    }, headers=AUTH)
    # 활성만 조회
    resp = await ac.get(f"{BASE}/policies", params={"is_active": "true"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
    assert resp.json()["data"][0]["policy_id"] == "pol-active"


@pytest.mark.asyncio
async def test_deactivate_policy(ac, _inject_fake_store):
    """정책 비활성화 (is_active=False로 업데이트)"""
    await _create_concept(ac)
    await ac.post(f"{BASE}/policies", json={
        "policy_id": "pol-deact", "concept_id": "cust.active",
        "policy_type": "aggregation", "policy_expression": "MIN_GROUP_SIZE >= 5",
    }, headers=AUTH)
    resp = await ac.put(f"{BASE}/policies/pol-deact", json={
        "is_active": False,
    }, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_create_policy_invalid_type(ac, _inject_fake_store):
    """잘못된 policy_type → 400"""
    await _create_concept(ac)
    resp = await ac.post(f"{BASE}/policies", json={
        "policy_id": "pol-bad", "concept_id": "cust.active",
        "policy_type": "NONEXISTENT", "policy_expression": "x > 0",
    }, headers=AUTH)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_policy(ac, _inject_fake_store):
    """정책 삭제"""
    await _create_concept(ac)
    await ac.post(f"{BASE}/policies", json={
        "policy_id": "pol-del", "concept_id": "cust.active",
        "policy_type": "residency", "policy_expression": "region = 'KR'",
    }, headers=AUTH)
    resp = await ac.delete(f"{BASE}/policies/pol-del", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_rule_not_found(ac):
    """존재하지 않는 규칙 조회 → 404"""
    resp = await ac.get(f"{BASE}/rules/nonexistent", headers=AUTH)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_policy_not_found(ac):
    """존재하지 않는 정책 조회 → 404"""
    resp = await ac.get(f"{BASE}/policies/nonexistent", headers=AUTH)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rule_no_concept(ac):
    """존재하지 않는 개념에 규칙 바인딩 시도 → 404"""
    resp = await ac.post(f"{BASE}/rules", json={
        "rule_id": "rule-orphan", "concept_id": "no.such.concept",
        "rule_type": "definition", "rule_expression": "x = 1",
    }, headers=AUTH)
    assert resp.status_code == 404
