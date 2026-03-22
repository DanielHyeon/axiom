"""
§5.2 L2 계약 확장 테스트 — SemanticSegment, TimeContract, AccessPolicy

FakeStore를 사용하여 PostgreSQL 없이 API 동작을 검증한다.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api import semantic_contract as sc_module

AUTH = {"Authorization": "Bearer local-oracle-token"}

# ── 테스트용 헬퍼: 엔티티를 미리 생성하는 공통 셋업 ──

BASE = "/api/v3/synapse/semantic"


# ── FakeStore에 세그먼트/시간계약/접근정책 메서드 추가를 위한 패치 ──

class FakeStoreL2:
    """기존 FakeSemanticStore에 §5.2 L2 계약 3종 메서드를 추가하는 래퍼.

    test_semantic_contract_api.py의 FakeSemanticStore 전체를 복사하지 않고,
    _inject_fake_store에서 기존 FakeStore 인스턴스에 동적으로 바인딩한다.
    """

    def __init__(self):
        self.segments: dict[str, dict] = {}
        self.time_contracts: dict[str, dict] = {}
        self.access_policies: dict[str, dict] = {}

    # ── 세그먼트 ──

    def create_segment(self, tenant_id, data):
        sid = data["segment_id"]
        if sid in self.segments:
            raise ValueError(f"segment_id '{sid}'가 이미 존재합니다")
        if not self._parent.get_entity(tenant_id, data["entity_id"]):
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        from app.models.semantic_models import VALID_SEGMENT_TYPES
        if data.get("segment_type", "static") not in VALID_SEGMENT_TYPES:
            raise ValueError(f"segment_type은 {VALID_SEGMENT_TYPES} 중 하나여야 합니다")
        row = {**data, "tenant_id": tenant_id, "version": 1,
               "created_at": "2026-03-23T00:00:00", "updated_at": "2026-03-23T00:00:00"}
        self.segments[sid] = row
        return row

    def get_segment(self, tenant_id, segment_id):
        s = self.segments.get(segment_id)
        return s if s and s.get("tenant_id") == tenant_id else None

    def list_segments(self, tenant_id, entity_id=None, limit=100, offset=0):
        result = [s for s in self.segments.values() if s["tenant_id"] == tenant_id]
        if entity_id:
            result = [s for s in result if s.get("entity_id") == entity_id]
        return result[offset:offset + limit]

    def update_segment(self, tenant_id, segment_id, data):
        s = self.get_segment(tenant_id, segment_id)
        if not s:
            raise KeyError(f"segment_id '{segment_id}'를 찾을 수 없습니다")
        from app.models.semantic_models import VALID_SEGMENT_TYPES
        if "segment_type" in data and data["segment_type"] not in VALID_SEGMENT_TYPES:
            raise ValueError(f"segment_type 유효하지 않음: {data['segment_type']}")
        s.update({k: v for k, v in data.items() if v is not None})
        s["version"] = s.get("version", 1) + 1
        return s

    def delete_segment(self, tenant_id, segment_id):
        if segment_id in self.segments and self.segments[segment_id].get("tenant_id") == tenant_id:
            del self.segments[segment_id]
            return True
        return False

    # ── 시간 계약 ──

    def create_time_contract(self, tenant_id, data):
        tid = data["time_contract_id"]
        if tid in self.time_contracts:
            raise ValueError(f"time_contract_id '{tid}'가 이미 존재합니다")
        if not self._parent.get_entity(tenant_id, data["entity_id"]):
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        from app.models.semantic_models import VALID_TIME_CONTRACT_GRAINS
        if data.get("time_grain", "") not in VALID_TIME_CONTRACT_GRAINS:
            raise ValueError(f"time_grain은 {VALID_TIME_CONTRACT_GRAINS} 중 하나여야 합니다")
        row = {**data, "tenant_id": tenant_id, "version": 1,
               "created_at": "2026-03-23T00:00:00", "updated_at": "2026-03-23T00:00:00"}
        self.time_contracts[tid] = row
        return row

    def get_time_contract(self, tenant_id, time_contract_id):
        t = self.time_contracts.get(time_contract_id)
        return t if t and t.get("tenant_id") == tenant_id else None

    def list_time_contracts(self, tenant_id, entity_id=None, limit=100, offset=0):
        result = [t for t in self.time_contracts.values() if t["tenant_id"] == tenant_id]
        if entity_id:
            result = [t for t in result if t.get("entity_id") == entity_id]
        return result[offset:offset + limit]

    def update_time_contract(self, tenant_id, time_contract_id, data):
        t = self.get_time_contract(tenant_id, time_contract_id)
        if not t:
            raise KeyError(f"time_contract_id '{time_contract_id}'를 찾을 수 없습니다")
        from app.models.semantic_models import VALID_TIME_CONTRACT_GRAINS
        if "time_grain" in data and data["time_grain"] not in VALID_TIME_CONTRACT_GRAINS:
            raise ValueError(f"time_grain 유효하지 않음: {data['time_grain']}")
        t.update({k: v for k, v in data.items() if v is not None})
        t["version"] = t.get("version", 1) + 1
        return t

    def delete_time_contract(self, tenant_id, time_contract_id):
        if time_contract_id in self.time_contracts and self.time_contracts[time_contract_id].get("tenant_id") == tenant_id:
            del self.time_contracts[time_contract_id]
            return True
        return False

    # ── 접근 정책 ──

    def create_access_policy(self, tenant_id, data):
        aid = data["access_policy_id"]
        if aid in self.access_policies:
            raise ValueError(f"access_policy_id '{aid}'가 이미 존재합니다")
        if not self._parent.get_entity(tenant_id, data["entity_id"]):
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        from app.models.semantic_models import VALID_ACCESS_POLICY_TYPES
        if data.get("policy_type", "") not in VALID_ACCESS_POLICY_TYPES:
            raise ValueError(f"policy_type은 {VALID_ACCESS_POLICY_TYPES} 중 하나여야 합니다")
        row = {**data, "tenant_id": tenant_id, "version": 1, "is_active": data.get("is_active", True),
               "created_at": "2026-03-23T00:00:00", "updated_at": "2026-03-23T00:00:00"}
        self.access_policies[aid] = row
        return row

    def get_access_policy(self, tenant_id, access_policy_id):
        a = self.access_policies.get(access_policy_id)
        return a if a and a.get("tenant_id") == tenant_id else None

    def list_access_policies(self, tenant_id, entity_id=None, is_active=None, limit=100, offset=0):
        result = [a for a in self.access_policies.values() if a["tenant_id"] == tenant_id]
        if entity_id:
            result = [a for a in result if a.get("entity_id") == entity_id]
        if is_active is not None:
            result = [a for a in result if a.get("is_active") == is_active]
        return result[offset:offset + limit]

    def update_access_policy(self, tenant_id, access_policy_id, data):
        a = self.get_access_policy(tenant_id, access_policy_id)
        if not a:
            raise KeyError(f"access_policy_id '{access_policy_id}'를 찾을 수 없습니다")
        from app.models.semantic_models import VALID_ACCESS_POLICY_TYPES
        if "policy_type" in data and data["policy_type"] not in VALID_ACCESS_POLICY_TYPES:
            raise ValueError(f"policy_type 유효하지 않음: {data['policy_type']}")
        a.update({k: v for k, v in data.items() if v is not None})
        a["version"] = a.get("version", 1) + 1
        return a

    def delete_access_policy(self, tenant_id, access_policy_id):
        if access_policy_id in self.access_policies and self.access_policies[access_policy_id].get("tenant_id") == tenant_id:
            del self.access_policies[access_policy_id]
            return True
        return False


# ── Fixtures ──

@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def _inject_fake_store():
    """테스트마다 FakeStore 주입 + L2 계약 메서드 동적 바인딩"""
    # 기존 test_semantic_contract_api.py의 FakeSemanticStore를 가져와 사용
    from tests.unit.test_semantic_contract_api import FakeSemanticStore
    fake = FakeSemanticStore()

    # L2 확장 메서드 바인딩
    l2 = FakeStoreL2()
    l2._parent = fake  # 엔티티 조회를 위한 참조

    # 세그먼트 메서드 바인딩
    fake.segments = l2.segments
    fake.create_segment = l2.create_segment
    fake.get_segment = l2.get_segment
    fake.list_segments = l2.list_segments
    fake.update_segment = l2.update_segment
    fake.delete_segment = l2.delete_segment

    # 시간 계약 메서드 바인딩
    fake.time_contracts = l2.time_contracts
    fake.create_time_contract = l2.create_time_contract
    fake.get_time_contract = l2.get_time_contract
    fake.list_time_contracts = l2.list_time_contracts
    fake.update_time_contract = l2.update_time_contract
    fake.delete_time_contract = l2.delete_time_contract

    # 접근 정책 메서드 바인딩
    fake.access_policies = l2.access_policies
    fake.create_access_policy = l2.create_access_policy
    fake.get_access_policy = l2.get_access_policy
    fake.list_access_policies = l2.list_access_policies
    fake.update_access_policy = l2.update_access_policy
    fake.delete_access_policy = l2.delete_access_policy

    sc_module._store = fake
    from app.services.semantic_compiler import SemanticCompiler
    sc_module._compiler = SemanticCompiler(fake)
    yield fake


# ── 공통: 테스트용 엔티티 생성 헬퍼 ──

async def _create_entity(ac, entity_id="ent-1"):
    """테스트 전 시멘틱 엔티티를 생성한다"""
    resp = await ac.post(f"{BASE}/entities", json={
        "entity_id": entity_id,
        "physical_source_ref": "dw.orders",
        "entity_type": "fact",
        "case_id": "case-l2",
    }, headers=AUTH)
    assert resp.status_code == 201
    return resp.json()["data"]


# ========================================
# 시멘틱 세그먼트 테스트
# ========================================

@pytest.mark.asyncio
async def test_create_segment(ac):
    """세그먼트 등록 — 정상 케이스"""
    await _create_entity(ac)
    resp = await ac.post(f"{BASE}/segments", json={
        "segment_id": "seg-vip",
        "entity_id": "ent-1",
        "name": "VIP 고객",
        "filter_expression": "tier = 'VIP'",
        "segment_type": "static",
    }, headers=AUTH)
    assert resp.status_code == 201
    assert resp.json()["data"]["segment_id"] == "seg-vip"


@pytest.mark.asyncio
async def test_list_segments_by_entity(ac):
    """세그먼트 목록 — entity_id 필터 검증"""
    await _create_entity(ac)
    await ac.post(f"{BASE}/segments", json={
        "segment_id": "seg-a", "entity_id": "ent-1",
        "name": "A군", "filter_expression": "grade = 'A'",
    }, headers=AUTH)
    await ac.post(f"{BASE}/segments", json={
        "segment_id": "seg-b", "entity_id": "ent-1",
        "name": "B군", "filter_expression": "grade = 'B'",
    }, headers=AUTH)
    resp = await ac.get(f"{BASE}/segments", params={"entity_id": "ent-1"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


@pytest.mark.asyncio
async def test_update_segment(ac):
    """세그먼트 수정 — 이름 변경"""
    await _create_entity(ac)
    await ac.post(f"{BASE}/segments", json={
        "segment_id": "seg-up", "entity_id": "ent-1",
        "name": "원래이름", "filter_expression": "x > 1",
    }, headers=AUTH)
    resp = await ac.put(f"{BASE}/segments/seg-up", json={
        "name": "변경된이름",
    }, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "변경된이름"


@pytest.mark.asyncio
async def test_segment_invalid_type(ac):
    """세그먼트 등록 — 유효하지 않은 segment_type"""
    await _create_entity(ac)
    resp = await ac.post(f"{BASE}/segments", json={
        "segment_id": "seg-bad", "entity_id": "ent-1",
        "name": "잘못된", "filter_expression": "x > 0",
        "segment_type": "unknown_type",
    }, headers=AUTH)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_segment(ac):
    """세그먼트 삭제 — 정상 케이스"""
    await _create_entity(ac)
    await ac.post(f"{BASE}/segments", json={
        "segment_id": "seg-del", "entity_id": "ent-1",
        "name": "삭제용", "filter_expression": "x = 0",
    }, headers=AUTH)
    resp = await ac.delete(f"{BASE}/segments/seg-del", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    # 삭제 후 조회 불가
    resp2 = await ac.get(f"{BASE}/segments/seg-del", headers=AUTH)
    assert resp2.status_code == 404


# ========================================
# 시간 계약 테스트
# ========================================

@pytest.mark.asyncio
async def test_create_time_contract(ac):
    """시간 계약 등록 — 정상 케이스"""
    await _create_entity(ac)
    resp = await ac.post(f"{BASE}/time-contracts", json={
        "time_contract_id": "tc-1",
        "entity_id": "ent-1",
        "time_column": "order_date",
        "time_grain": "day",
    }, headers=AUTH)
    assert resp.status_code == 201
    assert resp.json()["data"]["time_contract_id"] == "tc-1"


@pytest.mark.asyncio
async def test_list_time_contracts(ac):
    """시간 계약 목록 조회"""
    await _create_entity(ac)
    await ac.post(f"{BASE}/time-contracts", json={
        "time_contract_id": "tc-list-1", "entity_id": "ent-1",
        "time_column": "created_at", "time_grain": "hour",
    }, headers=AUTH)
    resp = await ac.get(f"{BASE}/time-contracts", params={"entity_id": "ent-1"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


@pytest.mark.asyncio
async def test_update_time_contract_grain(ac):
    """시간 계약 수정 — time_grain 변경"""
    await _create_entity(ac)
    await ac.post(f"{BASE}/time-contracts", json={
        "time_contract_id": "tc-upd", "entity_id": "ent-1",
        "time_column": "ts", "time_grain": "day",
    }, headers=AUTH)
    resp = await ac.put(f"{BASE}/time-contracts/tc-upd", json={
        "time_grain": "month",
    }, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["time_grain"] == "month"


@pytest.mark.asyncio
async def test_time_contract_default_lookback(ac):
    """시간 계약 — 기본 lookback 검증"""
    await _create_entity(ac)
    resp = await ac.post(f"{BASE}/time-contracts", json={
        "time_contract_id": "tc-lb", "entity_id": "ent-1",
        "time_column": "event_ts", "time_grain": "hour",
        "default_lookback_days": 30,
    }, headers=AUTH)
    assert resp.status_code == 201
    # 단건 조회로 default_lookback_days 확인
    resp2 = await ac.get(f"{BASE}/time-contracts/tc-lb", headers=AUTH)
    assert resp2.status_code == 200
    assert resp2.json()["data"]["default_lookback_days"] == 30


# ========================================
# 접근 정책 테스트
# ========================================

@pytest.mark.asyncio
async def test_create_access_policy(ac):
    """접근 정책 등록 — 정상 케이스"""
    await _create_entity(ac)
    resp = await ac.post(f"{BASE}/access-policies", json={
        "access_policy_id": "ap-1",
        "entity_id": "ent-1",
        "policy_type": "row_filter",
        "condition_expression": "region = 'KR'",
        "target_roles": ["analyst", "viewer"],
    }, headers=AUTH)
    assert resp.status_code == 201
    assert resp.json()["data"]["access_policy_id"] == "ap-1"


@pytest.mark.asyncio
async def test_list_active_policies(ac):
    """접근 정책 목록 — is_active 필터"""
    await _create_entity(ac)
    await ac.post(f"{BASE}/access-policies", json={
        "access_policy_id": "ap-act", "entity_id": "ent-1",
        "policy_type": "row_filter", "condition_expression": "x > 0",
        "is_active": True,
    }, headers=AUTH)
    await ac.post(f"{BASE}/access-policies", json={
        "access_policy_id": "ap-inact", "entity_id": "ent-1",
        "policy_type": "column_mask", "condition_expression": "y = 1",
        "is_active": False,
    }, headers=AUTH)
    # 활성 정책만 조회
    resp = await ac.get(f"{BASE}/access-policies", params={"is_active": True}, headers=AUTH)
    assert resp.status_code == 200
    ids = [p["access_policy_id"] for p in resp.json()["data"]]
    assert "ap-act" in ids
    assert "ap-inact" not in ids


@pytest.mark.asyncio
async def test_deactivate_access_policy(ac):
    """접근 정책 비활성화 — is_active를 False로 수정"""
    await _create_entity(ac)
    await ac.post(f"{BASE}/access-policies", json={
        "access_policy_id": "ap-deact", "entity_id": "ent-1",
        "policy_type": "field_redact", "condition_expression": "role != 'admin'",
    }, headers=AUTH)
    resp = await ac.put(f"{BASE}/access-policies/ap-deact", json={
        "is_active": False,
    }, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_invalid_policy_type(ac):
    """접근 정책 등록 — 유효하지 않은 policy_type"""
    await _create_entity(ac)
    resp = await ac.post(f"{BASE}/access-policies", json={
        "access_policy_id": "ap-bad", "entity_id": "ent-1",
        "policy_type": "nonexistent_type",
        "condition_expression": "1=1",
    }, headers=AUTH)
    assert resp.status_code == 400
