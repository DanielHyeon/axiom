"""
시멘틱 스냅샷 서비스 단위 테스트

PostgreSQL 없이 동작하도록 FakeSnapshotBuilder/FakeSnapshotRegistry로
모듈 싱글턴을 교체하여 API 엔드포인트를 검증한다.
"""
import json
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api import semantic_contract as sc_module
from app.services.semantic_snapshot_service import (
    _compute_content_hash,
    SNAPSHOT_BUILDING,
    SNAPSHOT_READY,
    SNAPSHOT_ACTIVE,
    SNAPSHOT_INVALIDATED,
    LEASE_ACTIVE,
    LEASE_RELEASED,
    ARTIFACT_CONTRACT_INDEX,
    ARTIFACT_JOIN_GRAPH,
    ARTIFACT_CONTEXT_PACKS,
    ARTIFACT_SYNONYM_MAP,
)

AUTH = {"Authorization": "Bearer local-oracle-token"}


# ── Fake 구현체 — DB 없이 인메모리 동작 ──

class FakeSemanticStore:
    """get_ai_context()만 제공하는 최소 Fake"""

    def __init__(self):
        self._ai_context = {
            "context_type": "semantic_contract",
            "approved_only": True,
            "summary": {"concepts": 2, "entities": 1, "measures": 3, "dimensions": 2},
            "concepts": [
                {"concept_id": "c1", "name_ko": "매출"},
                {"concept_id": "c2", "name_ko": "비용"},
            ],
            "entities": [{"entity_id": "e1", "physical_source_ref": "sales"}],
            "measures": [
                {"measure_id": "m1", "name": "총매출", "sql_expression": "SUM(amount)", "entity_id": "e1"},
            ],
            "dimensions": [
                {"dimension_id": "d1", "name": "지역", "sql_expression": "region", "entity_id": "e1"},
            ],
            "allowed_joins": [],
            "banned_joins": [],
            "synonym_map": {"매출액": "c1", "수익": "c1"},
            "quality_contracts": [],
        }

    def ensure_schema(self):
        pass

    def get_ai_context(self, tenant_id, case_id=None):
        return self._ai_context


class FakeSnapshotBuilder:
    """SnapshotBuilder의 인메모리 Fake — DB 없이 빌드 결과를 메모리에 저장"""

    def __init__(self, store):
        self._store = store
        self._snapshots = {}  # version → snapshot dict
        self._seq = 0

    def build_from_release(self, tenant_id, release_id=None, release_version=None, created_by="system"):
        ai_context = self._store.get_ai_context(tenant_id)
        content_hash = _compute_content_hash(ai_context)
        self._seq += 1
        now = datetime.now(timezone.utc)
        version = f"snap-test-{self._seq:04d}-{content_hash[:8]}"
        snapshot_id = f"fake-id-{self._seq}"

        manifest = {
            "summary": ai_context.get("summary", {}),
            "context_type": ai_context.get("context_type"),
            "tenant_id": tenant_id,
        }

        snapshot = {
            "snapshot_id": snapshot_id,
            "snapshot_version": version,
            "release_id": release_id or "",
            "release_version": release_version or "",
            "status": SNAPSHOT_READY,
            "content_hash": content_hash,
            "manifest": manifest,
            "artifact_count": 4,
            "built_at": now.isoformat(),
            "tenant_id": tenant_id,
        }
        self._snapshots[version] = snapshot
        return snapshot


class FakeSnapshotRegistry:
    """SnapshotRegistry의 인메모리 Fake"""

    def __init__(self):
        self._snapshots = {}  # version → dict
        self._bindings = {}   # (consumer_name, instance_id) → dict
        self._leases = {}     # (request_id, consumer_name) → dict

    def ensure_schema(self):
        pass

    def _add_snapshot(self, version, tenant_id, status=SNAPSHOT_READY, **kw):
        """테스트 헬퍼 — 스냅샷 직접 등록"""
        snap = {
            "id": f"id-{version}",
            "snapshot_version": version,
            "tenant_id": tenant_id,
            "status": status,
            "content_hash": "abcd1234",
            "manifest_json": {},
            "release_id": "",
            "release_version": "",
            "built_at": datetime.now(timezone.utc).isoformat(),
            "activated_at": None,
            "invalidated_at": None,
            "invalidation_reason": None,
            "created_by": "system",
            "artifacts": [],
            **kw,
        }
        self._snapshots[version] = snap
        return snap

    def get_snapshot(self, snapshot_version):
        return self._snapshots.get(snapshot_version)

    def find_active(self, tenant_id, consumer_name=None):
        # 소비자 바인딩 확인
        if consumer_name:
            for (cn, _), binding in self._bindings.items():
                if cn == consumer_name:
                    ver = binding["bound_snapshot_version"]
                    snap = self._snapshots.get(ver)
                    if snap and snap["status"] == SNAPSHOT_ACTIVE and snap["tenant_id"] == tenant_id:
                        return snap
        # 최신 ACTIVE
        active = [s for s in self._snapshots.values()
                  if s["status"] == SNAPSHOT_ACTIVE and s["tenant_id"] == tenant_id]
        return active[-1] if active else None

    def list_snapshots(self, tenant_id, limit=20, offset=0):
        result = [s for s in self._snapshots.values() if s["tenant_id"] == tenant_id]
        result.sort(key=lambda x: x["built_at"], reverse=True)
        return result[offset:offset + limit]

    def activate(self, snapshot_version, tenant_id):
        snap = self._snapshots.get(snapshot_version)
        if not snap or snap["tenant_id"] != tenant_id:
            raise KeyError(f"snapshot_version '{snapshot_version}'를 찾을 수 없습니다")
        if snap["status"] == SNAPSHOT_INVALIDATED:
            raise ValueError("무효화된 스냅샷은 활성화할 수 없습니다")
        # 기존 ACTIVE → READY 강등
        for s in self._snapshots.values():
            if s["status"] == SNAPSHOT_ACTIVE and s["tenant_id"] == tenant_id:
                s["status"] = SNAPSHOT_READY
        snap["status"] = SNAPSHOT_ACTIVE
        snap["activated_at"] = datetime.now(timezone.utc).isoformat()
        return snap

    def invalidate(self, snapshot_version, tenant_id, reason=""):
        snap = self._snapshots.get(snapshot_version)
        if not snap or snap["tenant_id"] != tenant_id:
            raise KeyError(f"snapshot_version '{snapshot_version}'를 찾을 수 없습니다")
        snap["status"] = SNAPSHOT_INVALIDATED
        snap["invalidated_at"] = datetime.now(timezone.utc).isoformat()
        snap["invalidation_reason"] = reason
        return snap

    def register_binding(self, consumer_name, instance_id, snapshot_version, mode="AUTO"):
        now = datetime.now(timezone.utc).isoformat()
        binding = {
            "consumer_name": consumer_name,
            "consumer_instance_id": instance_id,
            "bound_snapshot_version": snapshot_version,
            "binding_mode": mode,
            "last_seen_at": now,
            "updated_at": now,
        }
        self._bindings[(consumer_name, instance_id)] = binding
        return binding

    def list_bindings(self, consumer_name=None):
        if consumer_name:
            return [b for (cn, _), b in self._bindings.items() if cn == consumer_name]
        return list(self._bindings.values())

    def acquire_lease(self, request_id, consumer_name, snapshot_version, ttl_minutes=30):
        now = datetime.now(timezone.utc)
        lease = {
            "request_id": request_id,
            "consumer_name": consumer_name,
            "snapshot_version": snapshot_version,
            "acquired_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=ttl_minutes)).isoformat(),
            "status": LEASE_ACTIVE,
            "released_at": None,
        }
        self._leases[(request_id, consumer_name)] = lease
        return lease

    def release_lease(self, request_id, consumer_name):
        key = (request_id, consumer_name)
        if key in self._leases:
            self._leases[key]["status"] = LEASE_RELEASED
            self._leases[key]["released_at"] = datetime.now(timezone.utc).isoformat()


# ── Fixtures ──

@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def _inject_fakes():
    """테스트마다 Fake 주입 → 테스트 간 격리"""
    fake_store = FakeSemanticStore()
    fake_builder = FakeSnapshotBuilder(fake_store)
    fake_registry = FakeSnapshotRegistry()

    # 모듈 싱글턴 교체
    original_builder = sc_module._snapshot_builder
    original_registry = sc_module._snapshot_registry
    sc_module._snapshot_builder = fake_builder
    sc_module._snapshot_registry = fake_registry

    yield fake_store, fake_builder, fake_registry

    # 복원
    sc_module._snapshot_builder = original_builder
    sc_module._snapshot_registry = original_registry


# ========================================
# 스냅샷 빌드 테스트
# ========================================

@pytest.mark.asyncio
async def test_build_snapshot_creates_record(ac, _inject_fakes):
    """빌드 API 호출 시 READY 상태 스냅샷이 생성된다"""
    resp = await ac.post(
        "/api/v3/synapse/semantic/snapshots/build",
        json={"release_id": "rel-001", "release_version": "v1.0"},
        headers=AUTH,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["status"] == SNAPSHOT_READY
    assert data["release_id"] == "rel-001"
    assert data["release_version"] == "v1.0"
    assert data["content_hash"]  # 해시가 비어있지 않음
    assert data["artifact_count"] == 4


@pytest.mark.asyncio
async def test_build_snapshot_without_release(ac, _inject_fakes):
    """release_id 없이 빌드해도 현재 데이터 기반으로 생성된다"""
    resp = await ac.post(
        "/api/v3/synapse/semantic/snapshots/build",
        json={},
        headers=AUTH,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["release_id"] == ""
    assert data["status"] == SNAPSHOT_READY


# ========================================
# 스냅샷 활성화 테스트
# ========================================

@pytest.mark.asyncio
async def test_activate_snapshot(ac, _inject_fakes):
    """READY 스냅샷을 ACTIVE로 전환할 수 있다"""
    _, _, registry = _inject_fakes
    registry._add_snapshot("snap-v1", "system", status=SNAPSHOT_READY)

    resp = await ac.post(
        "/api/v3/synapse/semantic/snapshots/snap-v1/activate",
        headers=AUTH,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == SNAPSHOT_ACTIVE
    assert data["activated_at"] is not None


@pytest.mark.asyncio
async def test_activate_demotes_previous_active(ac, _inject_fakes):
    """새 스냅샷 활성화 시 기존 ACTIVE 스냅샷이 READY로 강등된다"""
    _, _, registry = _inject_fakes
    registry._add_snapshot("snap-v1", "system", status=SNAPSHOT_ACTIVE)
    registry._add_snapshot("snap-v2", "system", status=SNAPSHOT_READY)

    resp = await ac.post(
        "/api/v3/synapse/semantic/snapshots/snap-v2/activate",
        headers=AUTH,
    )
    assert resp.status_code == 200
    # 이전 활성 스냅샷 확인
    assert registry._snapshots["snap-v1"]["status"] == SNAPSHOT_READY
    assert registry._snapshots["snap-v2"]["status"] == SNAPSHOT_ACTIVE


# ========================================
# 스냅샷 무효화 테스트
# ========================================

@pytest.mark.asyncio
async def test_invalidate_snapshot(ac, _inject_fakes):
    """스냅샷을 무효화하면 INVALIDATED 상태가 된다"""
    _, _, registry = _inject_fakes
    registry._add_snapshot("snap-v1", "system", status=SNAPSHOT_READY)

    resp = await ac.post(
        "/api/v3/synapse/semantic/snapshots/snap-v1/invalidate",
        json={"reason": "스키마 변경"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == SNAPSHOT_INVALIDATED
    assert data["invalidation_reason"] == "스키마 변경"


@pytest.mark.asyncio
async def test_activate_invalidated_snapshot_fails(ac, _inject_fakes):
    """무효화된 스냅샷은 활성화할 수 없다"""
    _, _, registry = _inject_fakes
    registry._add_snapshot("snap-v1", "system", status=SNAPSHOT_INVALIDATED)

    resp = await ac.post(
        "/api/v3/synapse/semantic/snapshots/snap-v1/activate",
        headers=AUTH,
    )
    assert resp.status_code == 400
    assert "무효화" in resp.json()["detail"]


# ========================================
# 스냅샷 조회 테스트
# ========================================

@pytest.mark.asyncio
async def test_find_active_snapshot(ac, _inject_fakes):
    """활성 스냅샷이 있으면 반환, 없으면 404"""
    _, _, registry = _inject_fakes

    # 활성 스냅샷 없으면 404
    resp = await ac.get("/api/v3/synapse/semantic/snapshots/active", headers=AUTH)
    assert resp.status_code == 404

    # 활성 스냅샷 추가 후 조회
    registry._add_snapshot("snap-v1", "system", status=SNAPSHOT_ACTIVE)
    resp = await ac.get("/api/v3/synapse/semantic/snapshots/active", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["snapshot_version"] == "snap-v1"


@pytest.mark.asyncio
async def test_list_snapshots(ac, _inject_fakes):
    """스냅샷 목록 조회"""
    _, _, registry = _inject_fakes
    registry._add_snapshot("snap-v1", "system")
    registry._add_snapshot("snap-v2", "system")
    registry._add_snapshot("snap-v3", "system")

    resp = await ac.get("/api/v3/synapse/semantic/snapshots?limit=2", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2  # limit 적용


@pytest.mark.asyncio
async def test_get_snapshot_detail(ac, _inject_fakes):
    """특정 스냅샷 상세 조회"""
    _, _, registry = _inject_fakes
    registry._add_snapshot("snap-v1", "system")

    resp = await ac.get("/api/v3/synapse/semantic/snapshots/snap-v1", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["snapshot_version"] == "snap-v1"

    # 존재하지 않는 버전
    resp = await ac.get("/api/v3/synapse/semantic/snapshots/nonexist", headers=AUTH)
    assert resp.status_code == 404


# ========================================
# 소비자 바인딩 테스트
# ========================================

@pytest.mark.asyncio
async def test_register_binding(ac, _inject_fakes):
    """소비자 바인딩 하트비트 등록"""
    resp = await ac.post(
        "/api/v3/synapse/semantic/consumers/bindings/heartbeat",
        json={
            "consumer_name": "oracle",
            "consumer_instance_id": "oracle-01",
            "snapshot_version": "snap-v1",
            "binding_mode": "AUTO",
        },
        headers=AUTH,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["consumer_name"] == "oracle"
    assert data["bound_snapshot_version"] == "snap-v1"


# ========================================
# 임대 테스트 (순수 단위 테스트 — API가 아닌 Fake 직접 호출)
# ========================================

def test_acquire_lease(_inject_fakes):
    """임대 획득/해제 정상 동작"""
    _, _, registry = _inject_fakes
    lease = registry.acquire_lease("req-001", "oracle", "snap-v1")
    assert lease["status"] == LEASE_ACTIVE
    assert lease["request_id"] == "req-001"

    # 해제
    registry.release_lease("req-001", "oracle")
    assert registry._leases[("req-001", "oracle")]["status"] == LEASE_RELEASED


def test_release_lease(_inject_fakes):
    """임대 해제 후 상태가 RELEASED"""
    _, _, registry = _inject_fakes
    registry.acquire_lease("req-002", "canvas", "snap-v2")
    registry.release_lease("req-002", "canvas")
    lease = registry._leases[("req-002", "canvas")]
    assert lease["status"] == LEASE_RELEASED
    assert lease["released_at"] is not None


# ========================================
# content_hash 결정론적 테스트
# ========================================

def test_content_hash_deterministic():
    """동일 데이터에 대해 항상 동일한 해시가 생성된다"""
    data1 = {"measures": [{"id": "m1"}], "entities": [{"id": "e1"}]}
    data2 = {"measures": [{"id": "m1"}], "entities": [{"id": "e1"}]}
    assert _compute_content_hash(data1) == _compute_content_hash(data2)

    # 키 순서가 달라도 동일 (sort_keys=True)
    data3 = {"entities": [{"id": "e1"}], "measures": [{"id": "m1"}]}
    assert _compute_content_hash(data1) == _compute_content_hash(data3)


def test_content_hash_changes_on_different_data():
    """다른 데이터면 다른 해시"""
    data1 = {"measures": [{"id": "m1"}]}
    data2 = {"measures": [{"id": "m2"}]}
    assert _compute_content_hash(data1) != _compute_content_hash(data2)


# ========================================
# 빌드 아티팩트 포함 테스트
# ========================================

def test_build_includes_artifacts(_inject_fakes):
    """빌드 결과에 4종 아티팩트가 포함된다"""
    _, builder, _ = _inject_fakes
    result = builder.build_from_release("system")
    assert result["artifact_count"] == 4
    assert result["status"] == SNAPSHOT_READY
    assert result["content_hash"]  # 빈 문자열이 아님


# ========================================
# SnapshotBuilder._split_artifacts 직접 테스트
# ========================================

def test_split_artifacts_produces_four_types():
    """_split_artifacts가 4종 아티팩트를 올바르게 분리한다"""
    from app.services.semantic_snapshot_service import SnapshotBuilder

    fake_store = FakeSemanticStore()
    # SnapshotBuilder를 직접 생성하되 DB 연결은 안 함
    builder = SnapshotBuilder.__new__(SnapshotBuilder)
    builder._store = fake_store

    ai_context = fake_store.get_ai_context("system")
    artifacts = builder._split_artifacts("snap-id-1", ai_context)

    assert len(artifacts) == 4
    types = {a["artifact_type"] for a in artifacts}
    assert types == {ARTIFACT_CONTRACT_INDEX, ARTIFACT_JOIN_GRAPH, ARTIFACT_CONTEXT_PACKS, ARTIFACT_SYNONYM_MAP}

    # CONTRACT_INDEX 내용 확인
    contract = next(a for a in artifacts if a["artifact_type"] == ARTIFACT_CONTRACT_INDEX)
    assert len(contract["artifact_json"]["entities"]) == 1
    assert len(contract["artifact_json"]["measures"]) == 1

    # SYNONYM_MAP 내용 확인
    syn = next(a for a in artifacts if a["artifact_type"] == ARTIFACT_SYNONYM_MAP)
    assert syn["artifact_json"]["synonyms"]["매출액"] == "c1"
