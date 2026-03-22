"""
온톨로지 관계 API 단위 테스트

FakeStore에 관계(relation) CRUD 메서드를 추가하여
PostgreSQL 없이 API 동작을 검증한다.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api import semantic_contract as sc_module

AUTH = {"Authorization": "Bearer local-oracle-token"}


# ── FakeStore: 기존 FakeSemanticStore에 relation 메서드 추가 ──

class FakeRelationStore:
    """온톨로지 관계 테스트용 인메모리 Fake Store

    기존 FakeSemanticStore의 개념(concept) CRUD + 관계(relation) CRUD만 구현.
    나머지 메서드는 호출되지 않으므로 __getattr__로 빈 함수를 반환한다.
    """

    VALID_PREDICATE_TYPES = {
        "is_a", "part_of", "relates_to", "derives_from",
        "equivalent_to", "owned_by", "constrained_by",
    }
    VALID_CARDINALITIES = {"1:1", "1:N", "N:1", "N:N"}
    VALID_DIRECTIONALITIES = {"unidirectional", "bidirectional"}

    def __init__(self):
        self.concepts: dict[str, dict] = {}
        self.relations: dict[str, dict] = {}

    def __getattr__(self, name):
        """테스트에서 사용하지 않는 메서드 호출 시 빈 동작 반환"""
        def noop(*args, **kwargs):
            return None
        return noop

    def ensure_schema(self):
        pass

    # ── 개념 CRUD (관계 테스트에 필요한 최소 구현) ──

    def create_concept(self, tenant_id, data):
        cid = data["concept_id"]
        if cid in self.concepts:
            raise ValueError(f"concept_id '{cid}'가 이미 존재합니다")
        row = {
            **data, "tenant_id": tenant_id, "version": 1,
            "status": data.get("status", "draft"),
            "approval_scope": data.get("approval_scope", "global"),
            "created_at": "2026-03-23T00:00:00",
            "updated_at": "2026-03-23T00:00:00",
        }
        self.concepts[cid] = row
        return row

    def get_concept(self, tenant_id, concept_id):
        c = self.concepts.get(concept_id)
        if c and c.get("tenant_id") == tenant_id:
            return c
        return None

    # ── 관계 CRUD ──

    def create_relation(self, tenant_id, data):
        # 술어 타입 검증
        pred = data.get("predicate_type", "")
        if pred not in self.VALID_PREDICATE_TYPES:
            raise ValueError(f"predicate_type은 {self.VALID_PREDICATE_TYPES} 중 하나여야 합니다: {pred}")
        # 기수성 검증
        card = data.get("cardinality", "1:N")
        if card not in self.VALID_CARDINALITIES:
            raise ValueError(f"cardinality는 {self.VALID_CARDINALITIES} 중 하나여야 합니다: {card}")
        # 방향성 검증
        dirn = data.get("directionality", "unidirectional")
        if dirn not in self.VALID_DIRECTIONALITIES:
            raise ValueError(f"directionality는 {self.VALID_DIRECTIONALITIES} 중 하나여야 합니다: {dirn}")
        # 자기참조 방지
        subj = data["subject_concept_id"]
        obj = data["object_concept_id"]
        if subj == obj:
            raise ValueError("subject_concept_id와 object_concept_id가 동일합니다 (자기참조 금지)")
        # 개념 존재 확인
        if not self.get_concept(tenant_id, subj):
            raise KeyError(f"subject concept_id '{subj}'를 찾을 수 없습니다")
        if not self.get_concept(tenant_id, obj):
            raise KeyError(f"object concept_id '{obj}'를 찾을 수 없습니다")
        # 중복 확인
        rid = data["relation_id"]
        if rid in self.relations:
            raise ValueError(f"relation_id '{rid}'가 이미 존재합니다")
        row = {
            **data, "tenant_id": tenant_id,
            "cardinality": card, "directionality": dirn,
            "weight": data.get("weight", 1.0),
            "confidence": data.get("confidence", 1.0),
            "created_at": "2026-03-23T00:00:00",
            "updated_at": "2026-03-23T00:00:00",
        }
        self.relations[rid] = row
        return row

    def get_relation(self, tenant_id, relation_id):
        r = self.relations.get(relation_id)
        if r and r.get("tenant_id") == tenant_id:
            return r
        return None

    def list_relations(self, tenant_id, subject_id=None, object_id=None,
                       predicate_type=None, limit=100, offset=0):
        result = [r for r in self.relations.values() if r["tenant_id"] == tenant_id]
        if subject_id:
            result = [r for r in result if r.get("subject_concept_id") == subject_id]
        if object_id:
            result = [r for r in result if r.get("object_concept_id") == object_id]
        if predicate_type:
            result = [r for r in result if r.get("predicate_type") == predicate_type]
        return result[offset:offset + limit]

    def update_relation(self, tenant_id, relation_id, data):
        r = self.get_relation(tenant_id, relation_id)
        if not r:
            raise KeyError(f"relation_id '{relation_id}'를 찾을 수 없습니다")
        # 유효성 검증
        if "predicate_type" in data and data["predicate_type"] not in self.VALID_PREDICATE_TYPES:
            raise ValueError(f"predicate_type 유효하지 않음: {data['predicate_type']}")
        if "cardinality" in data and data["cardinality"] not in self.VALID_CARDINALITIES:
            raise ValueError(f"cardinality 유효하지 않음: {data['cardinality']}")
        if "directionality" in data and data["directionality"] not in self.VALID_DIRECTIONALITIES:
            raise ValueError(f"directionality 유효하지 않음: {data['directionality']}")
        r.update({k: v for k, v in data.items() if v is not None})
        return r

    def delete_relation(self, tenant_id, relation_id):
        if relation_id in self.relations and self.relations[relation_id].get("tenant_id") == tenant_id:
            del self.relations[relation_id]
            return True
        return False


# ── Fixtures ──

@pytest.fixture(autouse=True)
def _patch_store(monkeypatch):
    """모든 테스트에서 _store를 FakeRelationStore로 교체한다."""
    fake = FakeRelationStore()
    monkeypatch.setattr(sc_module, "_store", fake)
    return fake


@pytest.fixture
def store(_patch_store):
    return _patch_store


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── 헬퍼: 두 개념을 미리 생성 ──

def _seed_concepts(store):
    """테스트용 개념 2개를 등록한다 (tenant_id='system' — 서비스 토큰 미들웨어 기준)."""
    store.create_concept("system", {
        "concept_id": "concept-a", "case_id": "c1",
        "name_ko": "개념A", "domain_id": "default",
    })
    store.create_concept("system", {
        "concept_id": "concept-b", "case_id": "c1",
        "name_ko": "개념B", "domain_id": "default",
    })


# ========================================
# 테스트 케이스
# ========================================

@pytest.mark.asyncio
async def test_create_relation(client, store):
    """관계 생성 → 201 응답 + 반환 데이터 확인"""
    _seed_concepts(store)
    resp = await client.post(
        "/api/v3/synapse/semantic/relations",
        json={
            "relation_id": "rel-1",
            "subject_concept_id": "concept-a",
            "predicate_type": "is_a",
            "object_concept_id": "concept-b",
        },
        headers=AUTH,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["relation_id"] == "rel-1"
    assert body["data"]["predicate_type"] == "is_a"
    assert body["data"]["cardinality"] == "1:N"  # 기본값
    assert body["data"]["directionality"] == "unidirectional"  # 기본값


@pytest.mark.asyncio
async def test_get_relation(client, store):
    """관계 단건 조회 → 200"""
    _seed_concepts(store)
    store.create_relation("system", {
        "relation_id": "rel-2",
        "subject_concept_id": "concept-a",
        "predicate_type": "part_of",
        "object_concept_id": "concept-b",
    })
    resp = await client.get(
        "/api/v3/synapse/semantic/relations/rel-2",
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["predicate_type"] == "part_of"


@pytest.mark.asyncio
async def test_get_relation_not_found(client, store):
    """존재하지 않는 관계 조회 → 404"""
    resp = await client.get(
        "/api/v3/synapse/semantic/relations/nonexistent",
        headers=AUTH,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_by_subject(client, store):
    """주체(subject) 기준 관계 목록 필터"""
    _seed_concepts(store)
    store.create_relation("system", {
        "relation_id": "rel-s1",
        "subject_concept_id": "concept-a",
        "predicate_type": "is_a",
        "object_concept_id": "concept-b",
    })
    store.create_relation("system", {
        "relation_id": "rel-s2",
        "subject_concept_id": "concept-b",
        "predicate_type": "derives_from",
        "object_concept_id": "concept-a",
    })
    resp = await client.get(
        "/api/v3/synapse/semantic/relations?subject_concept_id=concept-a",
        headers=AUTH,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["relation_id"] == "rel-s1"


@pytest.mark.asyncio
async def test_list_by_predicate(client, store):
    """술어(predicate) 기준 관계 목록 필터"""
    _seed_concepts(store)
    store.create_relation("system", {
        "relation_id": "rel-p1",
        "subject_concept_id": "concept-a",
        "predicate_type": "owned_by",
        "object_concept_id": "concept-b",
    })
    store.create_relation("system", {
        "relation_id": "rel-p2",
        "subject_concept_id": "concept-b",
        "predicate_type": "is_a",
        "object_concept_id": "concept-a",
    })
    resp = await client.get(
        "/api/v3/synapse/semantic/relations?predicate_type=owned_by",
        headers=AUTH,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["predicate_type"] == "owned_by"


@pytest.mark.asyncio
async def test_update_relation(client, store):
    """관계 수정 → 200 + 변경 확인"""
    _seed_concepts(store)
    store.create_relation("system", {
        "relation_id": "rel-u1",
        "subject_concept_id": "concept-a",
        "predicate_type": "relates_to",
        "object_concept_id": "concept-b",
        "weight": 0.5,
    })
    resp = await client.put(
        "/api/v3/synapse/semantic/relations/rel-u1",
        json={"predicate_type": "derives_from", "weight": 0.9},
        headers=AUTH,
    )
    assert resp.status_code == 200
    d = resp.json()["data"]
    assert d["predicate_type"] == "derives_from"
    assert d["weight"] == 0.9


@pytest.mark.asyncio
async def test_delete_relation(client, store):
    """관계 삭제 → 200 + 재조회 시 404"""
    _seed_concepts(store)
    store.create_relation("system", {
        "relation_id": "rel-d1",
        "subject_concept_id": "concept-a",
        "predicate_type": "is_a",
        "object_concept_id": "concept-b",
    })
    resp = await client.delete(
        "/api/v3/synapse/semantic/relations/rel-d1",
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    # 재조회 → 404
    resp2 = await client.get(
        "/api/v3/synapse/semantic/relations/rel-d1",
        headers=AUTH,
    )
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_invalid_predicate_type(client, store):
    """유효하지 않은 술어 타입 → 400"""
    _seed_concepts(store)
    resp = await client.post(
        "/api/v3/synapse/semantic/relations",
        json={
            "relation_id": "rel-bad",
            "subject_concept_id": "concept-a",
            "predicate_type": "INVALID_TYPE",
            "object_concept_id": "concept-b",
        },
        headers=AUTH,
    )
    assert resp.status_code == 400
    assert "predicate_type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_self_relation_prevented(client, store):
    """자기참조 관계 → 400"""
    _seed_concepts(store)
    resp = await client.post(
        "/api/v3/synapse/semantic/relations",
        json={
            "relation_id": "rel-self",
            "subject_concept_id": "concept-a",
            "predicate_type": "is_a",
            "object_concept_id": "concept-a",
        },
        headers=AUTH,
    )
    assert resp.status_code == 400
    assert "자기참조" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_missing_concept_returns_404(client, store):
    """존재하지 않는 개념을 참조하면 404"""
    store.create_concept("system", {
        "concept_id": "concept-only",
        "case_id": "c1",
        "name_ko": "혼자개념",
        "domain_id": "default",
    })
    resp = await client.post(
        "/api/v3/synapse/semantic/relations",
        json={
            "relation_id": "rel-miss",
            "subject_concept_id": "concept-only",
            "predicate_type": "is_a",
            "object_concept_id": "concept-nonexistent",
        },
        headers=AUTH,
    )
    assert resp.status_code == 404
    assert "concept_id" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_404(client, store):
    """존재하지 않는 관계 삭제 → 404"""
    resp = await client.delete(
        "/api/v3/synapse/semantic/relations/nope",
        headers=AUTH,
    )
    assert resp.status_code == 404
