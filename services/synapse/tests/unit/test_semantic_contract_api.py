"""
시멘틱 계약 API 단위 테스트

SemanticStore를 FakeStore로 교체하여 PostgreSQL 없이 API 동작을 검증한다.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api import semantic_contract as sc_module

AUTH = {"Authorization": "Bearer local-oracle-token"}

# ── FakeStore: PostgreSQL 없이 동작하는 인메모리 저장소 ──

class FakeSemanticStore:
    """시멘틱 계약 인메모리 Fake — API 라우터 테스트용"""

    def __init__(self):
        self.concepts: dict[str, dict] = {}
        self.terms: list[dict] = []
        self.entities: dict[str, dict] = {}
        self.measures: dict[str, dict] = {}
        self.dimensions: dict[str, dict] = {}
        self.joins: dict[str, dict] = {}
        self.quality_contracts: dict[str, dict] = {}
        self.grains: dict[str, dict] = {}
        self.context_packs: dict[str, dict] = {}
        self.prompt_policies: dict[str, dict] = {}
        self.releases: list[dict] = []
        self._term_seq = 0

    def ensure_schema(self):
        pass

    # 개념 CRUD
    def create_concept(self, tenant_id, data):
        cid = data["concept_id"]
        if cid in self.concepts:
            raise ValueError(f"concept_id '{cid}'가 이미 존재합니다")
        row = {**data, "tenant_id": tenant_id, "version": 1, "status": data.get("status", "draft"),
               "created_at": "2026-03-22T00:00:00", "updated_at": "2026-03-22T00:00:00"}
        self.concepts[cid] = row
        return row

    def get_concept(self, tenant_id, concept_id):
        c = self.concepts.get(concept_id)
        if c and c.get("tenant_id") == tenant_id:
            return c
        return None

    def list_concepts(self, tenant_id, case_id=None, status=None, limit=100, offset=0):
        result = [c for c in self.concepts.values() if c["tenant_id"] == tenant_id]
        if case_id:
            result = [c for c in result if c.get("case_id") == case_id]
        if status:
            result = [c for c in result if c.get("status") == status]
        return result[offset:offset + limit]

    def update_concept(self, tenant_id, concept_id, data):
        c = self.get_concept(tenant_id, concept_id)
        if not c:
            raise KeyError(f"concept_id '{concept_id}'를 찾을 수 없습니다")
        c.update({k: v for k, v in data.items() if v is not None})
        c["version"] = c.get("version", 1) + 1
        return c

    def change_concept_status(self, tenant_id, concept_id, new_status):
        c = self.get_concept(tenant_id, concept_id)
        if not c:
            raise KeyError(f"concept_id '{concept_id}'를 찾을 수 없습니다")
        transitions = {"draft": {"review", "deprecated"}, "review": {"approved", "draft"}, "approved": {"deprecated"}, "deprecated": {"draft"}}
        allowed = transitions.get(c["status"], set())
        if new_status not in allowed:
            raise ValueError(f"'{c['status']}' → '{new_status}' 전이가 허용되지 않습니다. 가능: {allowed}")
        c["status"] = new_status
        return c

    # 용어
    def create_term(self, tenant_id, data):
        if not self.get_concept(tenant_id, data["concept_id"]):
            raise KeyError(f"concept_id '{data['concept_id']}'를 찾을 수 없습니다")
        self._term_seq += 1
        row = {**data, "term_id": self._term_seq, "tenant_id": tenant_id, "created_at": "2026-03-22T00:00:00"}
        self.terms.append(row)
        return row

    def create_terms_bulk(self, tenant_id, terms):
        return [self.create_term(tenant_id, t) for t in terms]

    def search_terms(self, tenant_id, query, limit=50):
        return [t for t in self.terms if tenant_id == t["tenant_id"] and query.lower() in t["surface_form"].lower()][:limit]

    def list_terms_by_concept(self, tenant_id, concept_id):
        return [t for t in self.terms if t["tenant_id"] == tenant_id and t["concept_id"] == concept_id]

    # 엔티티
    def create_entity(self, tenant_id, data):
        eid = data["entity_id"]
        if eid in self.entities:
            raise ValueError(f"entity_id '{eid}'가 이미 존재합니다")
        row = {**data, "tenant_id": tenant_id, "status": "draft", "version": 1, "created_at": "2026-03-22T00:00:00"}
        self.entities[eid] = row
        return row

    def get_entity(self, tenant_id, entity_id):
        e = self.entities.get(entity_id)
        return e if e and e.get("tenant_id") == tenant_id else None

    def list_entities(self, tenant_id, case_id=None, limit=100, offset=0):
        result = [e for e in self.entities.values() if e["tenant_id"] == tenant_id]
        if case_id:
            result = [e for e in result if e.get("case_id") == case_id]
        return result[offset:offset + limit]

    def update_entity(self, tenant_id, entity_id, data):
        e = self.get_entity(tenant_id, entity_id)
        if not e:
            raise KeyError(f"entity_id '{entity_id}'를 찾을 수 없습니다")
        e.update({k: v for k, v in data.items() if v is not None})
        e["version"] = e.get("version", 1) + 1
        return e

    # 지표
    def create_measure(self, tenant_id, data):
        mid = data["measure_id"]
        if mid in self.measures:
            raise ValueError(f"measure_id '{mid}'가 이미 존재합니다")
        if not self.get_entity(tenant_id, data["entity_id"]):
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        row = {**data, "tenant_id": tenant_id, "status": "draft", "version": 1, "created_at": "2026-03-22T00:00:00"}
        self.measures[mid] = row
        return row

    def get_measure(self, tenant_id, measure_id):
        m = self.measures.get(measure_id)
        return m if m and m.get("tenant_id") == tenant_id else None

    def list_measures(self, tenant_id, case_id=None, entity_id=None, limit=100, offset=0):
        result = [m for m in self.measures.values() if m["tenant_id"] == tenant_id]
        if case_id:
            result = [m for m in result if m.get("case_id") == case_id]
        if entity_id:
            result = [m for m in result if m.get("entity_id") == entity_id]
        return result[offset:offset + limit]

    def update_measure(self, tenant_id, measure_id, data):
        m = self.get_measure(tenant_id, measure_id)
        if not m:
            raise KeyError(f"measure_id '{measure_id}'를 찾을 수 없습니다")
        m.update({k: v for k, v in data.items() if v is not None})
        m["version"] = m.get("version", 1) + 1
        return m

    # 차원
    def create_dimension(self, tenant_id, data):
        did = data["dimension_id"]
        if did in self.dimensions:
            raise ValueError(f"dimension_id '{did}'가 이미 존재합니다")
        if not self.get_entity(tenant_id, data["entity_id"]):
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        row = {**data, "tenant_id": tenant_id, "status": "draft", "version": 1, "created_at": "2026-03-22T00:00:00"}
        self.dimensions[did] = row
        return row

    def get_dimension(self, tenant_id, dimension_id):
        d = self.dimensions.get(dimension_id)
        return d if d and d.get("tenant_id") == tenant_id else None

    def list_dimensions(self, tenant_id, case_id=None, entity_id=None, limit=100, offset=0):
        result = [d for d in self.dimensions.values() if d["tenant_id"] == tenant_id]
        if case_id:
            result = [d for d in result if d.get("case_id") == case_id]
        if entity_id:
            result = [d for d in result if d.get("entity_id") == entity_id]
        return result[offset:offset + limit]

    def update_dimension(self, tenant_id, dimension_id, data):
        d = self.get_dimension(tenant_id, dimension_id)
        if not d:
            raise KeyError(f"dimension_id '{dimension_id}'를 찾을 수 없습니다")
        d.update({k: v for k, v in data.items() if v is not None})
        d["version"] = d.get("version", 1) + 1
        return d

    # 조인 계약
    def create_join_contract(self, tenant_id, data):
        jid = data["join_id"]
        if jid in self.joins:
            raise ValueError(f"join_id '{jid}'가 이미 존재합니다")
        for eid in (data["left_entity_id"], data["right_entity_id"]):
            if not self.get_entity(tenant_id, eid):
                raise KeyError(f"entity_id '{eid}'를 찾을 수 없습니다")
        row = {**data, "tenant_id": tenant_id, "status": "draft", "created_at": "2026-03-22T00:00:00"}
        self.joins[jid] = row
        return row

    def get_join_contract(self, tenant_id, join_id):
        j = self.joins.get(join_id)
        return j if j and j.get("tenant_id") == tenant_id else None

    def list_join_contracts(self, tenant_id, case_id=None, allowed_for_ai=None, limit=100, offset=0):
        result = [j for j in self.joins.values() if j["tenant_id"] == tenant_id]
        if case_id:
            result = [j for j in result if j.get("case_id") == case_id]
        if allowed_for_ai is not None:
            result = [j for j in result if j.get("allowed_for_ai") == allowed_for_ai]
        return result[offset:offset + limit]

    def update_join_contract(self, tenant_id, join_id, data):
        j = self.get_join_contract(tenant_id, join_id)
        if not j:
            raise KeyError(f"join_id '{join_id}'를 찾을 수 없습니다")
        j.update({k: v for k, v in data.items() if v is not None})
        return j

    # 품질 계약
    def create_quality_contract(self, tenant_id, data):
        qid = data["quality_contract_id"]
        if qid in self.quality_contracts:
            raise ValueError(f"quality_contract_id '{qid}'가 이미 존재합니다")
        row = {**data, "tenant_id": tenant_id, "created_at": "2026-03-22T00:00:00"}
        self.quality_contracts[qid] = row
        return row

    def list_quality_contracts(self, tenant_id, case_id=None, target_type=None, limit=100, offset=0):
        result = [q for q in self.quality_contracts.values() if q["tenant_id"] == tenant_id]
        if case_id:
            result = [q for q in result if q.get("case_id") == case_id]
        if target_type:
            result = [q for q in result if q.get("target_type") == target_type]
        return result[offset:offset + limit]

    # 그레인 계약
    def create_grain_contract(self, tenant_id, data):
        gid = data["grain_id"]
        if gid in self.grains:
            raise ValueError(f"grain_id '{gid}'가 이미 존재합니다")
        if not self.get_entity(tenant_id, data["entity_id"]):
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        row = {**data, "tenant_id": tenant_id, "version": 1, "created_at": "2026-03-22T00:00:00"}
        self.grains[gid] = row
        return row

    def get_grain_contract(self, tenant_id, grain_id):
        g = self.grains.get(grain_id)
        return g if g and g.get("tenant_id") == tenant_id else None

    def list_grain_contracts(self, tenant_id, case_id=None, entity_id=None, limit=100, offset=0):
        result = [g for g in self.grains.values() if g["tenant_id"] == tenant_id]
        if case_id:
            result = [g for g in result if g.get("case_id") == case_id]
        if entity_id:
            result = [g for g in result if g.get("entity_id") == entity_id]
        return result[offset:offset + limit]

    def update_grain_contract(self, tenant_id, grain_id, data):
        g = self.get_grain_contract(tenant_id, grain_id)
        if not g:
            raise KeyError(f"grain_id '{grain_id}'를 찾을 수 없습니다")
        g.update({k: v for k, v in data.items() if v is not None})
        return g

    # 컨텍스트 팩
    def create_context_pack(self, tenant_id, data):
        cpid = data["context_pack_id"]
        if cpid in self.context_packs:
            raise ValueError(f"context_pack_id '{cpid}'가 이미 존재합니다")
        row = {**data, "tenant_id": tenant_id, "version": 1, "created_at": "2026-03-22T00:00:00", "updated_at": "2026-03-22T00:00:00"}
        self.context_packs[cpid] = row
        return row

    def get_context_pack(self, tenant_id, context_pack_id):
        cp = self.context_packs.get(context_pack_id)
        return cp if cp and cp.get("tenant_id") == tenant_id else None

    def list_context_packs(self, tenant_id, case_id=None, intent_type=None, limit=100, offset=0):
        result = [cp for cp in self.context_packs.values() if cp["tenant_id"] == tenant_id]
        if case_id:
            result = [cp for cp in result if cp.get("case_id") == case_id]
        if intent_type:
            result = [cp for cp in result if cp.get("intent_type") == intent_type]
        return result[offset:offset + limit]

    def update_context_pack(self, tenant_id, context_pack_id, data):
        cp = self.get_context_pack(tenant_id, context_pack_id)
        if not cp:
            raise KeyError(f"context_pack_id '{context_pack_id}'를 찾을 수 없습니다")
        cp.update({k: v for k, v in data.items() if v is not None})
        cp["version"] = cp.get("version", 1) + 1
        return cp

    def delete_context_pack(self, tenant_id, context_pack_id):
        if context_pack_id in self.context_packs and self.context_packs[context_pack_id].get("tenant_id") == tenant_id:
            del self.context_packs[context_pack_id]
            # CASCADE: 연관 정책도 삭제
            self.prompt_policies = {k: v for k, v in self.prompt_policies.items() if v.get("context_pack_id") != context_pack_id}
            return True
        return False

    # 프롬프트 정책
    def create_prompt_policy(self, tenant_id, data):
        ppid = data["prompt_policy_id"]
        if ppid in self.prompt_policies:
            raise ValueError(f"prompt_policy_id '{ppid}'가 이미 존재합니다")
        if not self.get_context_pack(tenant_id, data["context_pack_id"]):
            raise KeyError(f"context_pack_id '{data['context_pack_id']}'를 찾을 수 없습니다")
        row = {**data, "tenant_id": tenant_id, "created_at": "2026-03-22T00:00:00"}
        self.prompt_policies[ppid] = row
        return row

    def list_prompt_policies(self, tenant_id, context_pack_id):
        return [p for p in self.prompt_policies.values()
                if p["tenant_id"] == tenant_id and p.get("context_pack_id") == context_pack_id]

    def delete_prompt_policy(self, tenant_id, prompt_policy_id):
        if prompt_policy_id in self.prompt_policies and self.prompt_policies[prompt_policy_id].get("tenant_id") == tenant_id:
            del self.prompt_policies[prompt_policy_id]
            return True
        return False

    def resolve_context_pack(self, tenant_id, context_pack_id):
        cp = self.get_context_pack(tenant_id, context_pack_id)
        if not cp:
            raise KeyError(f"context_pack_id '{context_pack_id}'를 찾을 수 없습니다")
        policies = self.list_prompt_policies(tenant_id, context_pack_id)
        return {
            "context_pack_id": context_pack_id,
            "intent_type": cp.get("intent_type", "general"),
            "quality_gate_min_score": cp.get("quality_gate_min_score", 0),
            "concepts": [], "measures": [], "dimensions": [],
            "allowed_joins": [], "banned_joins": [],
            "synonym_map": {}, "answer_guardrails": cp.get("answer_guardrails", []),
            "temporal_rules": cp.get("temporal_rules", {}),
            "prompt_policies": [{"rule_type": p["rule_type"], "rule_text": p["rule_text"], "priority": p.get("priority", 0)} for p in policies],
        }

    # 배포
    def publish(self, tenant_id, object_type, object_id, reviewer=None):
        release = {
            "release_id": len(self.releases) + 1,
            "semantic_object_type": object_type,
            "semantic_object_id": object_id,
            "version": 1,
            "review_status": "approved",
            "deployed_at": "2026-03-22T00:00:00",
        }
        self.releases.append(release)
        return release

    def list_releases(self, tenant_id, limit=50, offset=0):
        return self.releases[offset:offset + limit]

    # 카탈로그
    def get_catalog(self, tenant_id, case_id=None):
        grains = self.grains
        return {
            "summary": {
                "concepts": len(self.concepts),
                "entities": len(self.entities),
                "measures": len(self.measures),
                "dimensions": len(self.dimensions),
                "joins": len(self.joins),
                "grains": len(grains),
            },
            "concepts": list(self.concepts.values()),
            "entities": list(self.entities.values()),
            "measures": list(self.measures.values()),
            "dimensions": list(self.dimensions.values()),
            "joins": list(self.joins.values()),
        }


# ── Fixtures ──

@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def _inject_fake_store():
    """테스트마다 FakeStore 주입 → 테스트 간 격리"""
    fake = FakeSemanticStore()
    sc_module._store = fake
    # Compiler도 같은 fake store를 참조하도록 교체
    from app.services.semantic_compiler import SemanticCompiler
    sc_module._compiler = SemanticCompiler(fake)
    yield fake


# ========================================
# 온톨로지 개념 테스트
# ========================================

@pytest.mark.asyncio
async def test_create_concept(ac):
    resp = await ac.post("/api/v3/synapse/semantic/concepts", json={
        "concept_id": "customer.active",
        "case_id": "case-1",
        "name_ko": "활성 고객",
        "name_en": "Active Customer",
        "owner_team": "growth",
    }, headers=AUTH)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["concept_id"] == "customer.active"
    assert body["data"]["version"] == 1


@pytest.mark.asyncio
async def test_create_concept_duplicate(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_concept("system", {"concept_id": "dup", "case_id": "c", "name_ko": "중복"})
    resp = await ac.post("/api/v3/synapse/semantic/concepts", json={
        "concept_id": "dup", "case_id": "c", "name_ko": "중복2",
    }, headers=AUTH)
    assert resp.status_code == 400
    assert "이미 존재" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_concepts(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_concept("system", {"concept_id": "a", "case_id": "c1", "name_ko": "A"})
    fake.create_concept("system", {"concept_id": "b", "case_id": "c1", "name_ko": "B"})
    resp = await ac.get("/api/v3/synapse/semantic/concepts?case_id=c1", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


@pytest.mark.asyncio
async def test_get_concept_with_terms(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_concept("system", {"concept_id": "cust", "case_id": "c", "name_ko": "고객"})
    fake.create_term("system", {"concept_id": "cust", "surface_form": "customer", "language": "en"})
    fake.create_term("system", {"concept_id": "cust", "surface_form": "고객", "language": "ko"})
    resp = await ac.get("/api/v3/synapse/semantic/concepts/cust", headers=AUTH)
    assert resp.status_code == 200
    assert len(resp.json()["data"]["terms"]) == 2


@pytest.mark.asyncio
async def test_concept_not_found(ac):
    resp = await ac.get("/api/v3/synapse/semantic/concepts/nonexistent", headers=AUTH)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_concept_version_increment(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_concept("system", {"concept_id": "x", "case_id": "c", "name_ko": "X"})
    resp = await ac.put("/api/v3/synapse/semantic/concepts/x", json={"name_en": "X-en"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["version"] == 2


@pytest.mark.asyncio
async def test_concept_status_transition(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_concept("system", {"concept_id": "s", "case_id": "c", "name_ko": "S", "status": "draft"})
    # draft → review (허용)
    resp = await ac.patch("/api/v3/synapse/semantic/concepts/s/status", json={"status": "review"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "review"
    # review → approved (허용)
    resp = await ac.patch("/api/v3/synapse/semantic/concepts/s/status", json={"status": "approved"}, headers=AUTH)
    assert resp.status_code == 200
    # approved → draft (비허용)
    resp = await ac.patch("/api/v3/synapse/semantic/concepts/s/status", json={"status": "draft"}, headers=AUTH)
    assert resp.status_code == 400
    assert "허용되지 않습니다" in resp.json()["detail"]


# ========================================
# 용어 테스트
# ========================================

@pytest.mark.asyncio
async def test_create_term(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_concept("system", {"concept_id": "c1", "case_id": "c", "name_ko": "개념1"})
    resp = await ac.post("/api/v3/synapse/semantic/terms", json={
        "concept_id": "c1", "surface_form": "활성고객", "term_type": "synonym",
    }, headers=AUTH)
    assert resp.status_code == 201
    assert resp.json()["data"]["term_id"] == 1


@pytest.mark.asyncio
async def test_create_term_no_concept(ac):
    resp = await ac.post("/api/v3/synapse/semantic/terms", json={
        "concept_id": "no-exist", "surface_form": "없음",
    }, headers=AUTH)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bulk_terms(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_concept("system", {"concept_id": "c1", "case_id": "c", "name_ko": "개념1"})
    resp = await ac.post("/api/v3/synapse/semantic/terms/bulk", json={
        "terms": [
            {"concept_id": "c1", "surface_form": "활성 고객"},
            {"concept_id": "c1", "surface_form": "active customer", "language": "en"},
        ],
    }, headers=AUTH)
    assert resp.status_code == 201
    assert resp.json()["count"] == 2


@pytest.mark.asyncio
async def test_search_terms(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_concept("system", {"concept_id": "c1", "case_id": "c", "name_ko": "개념1"})
    fake.create_term("system", {"concept_id": "c1", "surface_form": "활성 고객"})
    fake.create_term("system", {"concept_id": "c1", "surface_form": "비활성 고객"})
    resp = await ac.get("/api/v3/synapse/semantic/terms/search?q=활성", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


# ========================================
# 시멘틱 엔티티 테스트
# ========================================

@pytest.mark.asyncio
async def test_entity_crud(ac, _inject_fake_store):
    # 생성
    resp = await ac.post("/api/v3/synapse/semantic/entities", json={
        "entity_id": "mart_customer_daily",
        "physical_source_ref": "public.customer_activity_daily",
        "entity_type": "fact",
        "grain_definition": "1 row = 1 일별 고객 활동",
        "case_id": "c1",
    }, headers=AUTH)
    assert resp.status_code == 201

    # 조회
    resp = await ac.get("/api/v3/synapse/semantic/entities/mart_customer_daily", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["entity_id"] == "mart_customer_daily"

    # 목록
    resp = await ac.get("/api/v3/synapse/semantic/entities", headers=AUTH)
    assert resp.json()["count"] == 1

    # 수정
    resp = await ac.put("/api/v3/synapse/semantic/entities/mart_customer_daily", json={
        "grain_definition": "1 row = 1 일별 고객 거래",
    }, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["version"] == 2


# ========================================
# 시멘틱 지표 테스트
# ========================================

@pytest.mark.asyncio
async def test_measure_crud(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_entity("system", {"entity_id": "e1", "physical_source_ref": "t1", "case_id": "c"})
    # 생성
    resp = await ac.post("/api/v3/synapse/semantic/measures", json={
        "measure_id": "sales.mac",
        "entity_id": "e1",
        "name": "월간 활성 고객",
        "measure_type": "distinct_count",
        "sql_expression": "COUNT(DISTINCT customer_id)",
        "additive_type": "non_additive",
        "case_id": "c",
    }, headers=AUTH)
    assert resp.status_code == 201

    # 조회
    resp = await ac.get("/api/v3/synapse/semantic/measures/sales.mac", headers=AUTH)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_measure_no_entity(ac):
    resp = await ac.post("/api/v3/synapse/semantic/measures", json={
        "measure_id": "m1", "entity_id": "no-exist", "name": "X", "sql_expression": "1",
    }, headers=AUTH)
    assert resp.status_code == 404


# ========================================
# 시멘틱 차원 테스트
# ========================================

@pytest.mark.asyncio
async def test_dimension_crud(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_entity("system", {"entity_id": "e1", "physical_source_ref": "t1", "case_id": "c"})
    resp = await ac.post("/api/v3/synapse/semantic/dimensions", json={
        "dimension_id": "dim.month",
        "entity_id": "e1",
        "name": "월",
        "sql_expression": "DATE_TRUNC('month', order_date)",
        "value_type": "temporal",
        "hierarchy_path": "year > quarter > month",
        "case_id": "c",
    }, headers=AUTH)
    assert resp.status_code == 201
    resp = await ac.get("/api/v3/synapse/semantic/dimensions/dim.month", headers=AUTH)
    assert resp.status_code == 200


# ========================================
# 조인 계약 테스트
# ========================================

@pytest.mark.asyncio
async def test_join_contract_crud(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_entity("system", {"entity_id": "e1", "physical_source_ref": "t1", "case_id": "c"})
    fake.create_entity("system", {"entity_id": "e2", "physical_source_ref": "t2", "case_id": "c"})
    resp = await ac.post("/api/v3/synapse/semantic/joins", json={
        "join_id": "j1",
        "left_entity_id": "e1",
        "right_entity_id": "e2",
        "join_condition": "e1.customer_id = e2.customer_id",
        "relationship_type": "1:N",
        "allowed_for_ai": True,
        "case_id": "c",
    }, headers=AUTH)
    assert resp.status_code == 201

    resp = await ac.get("/api/v3/synapse/semantic/joins?allowed_for_ai=true", headers=AUTH)
    assert resp.json()["count"] == 1


@pytest.mark.asyncio
async def test_join_contract_missing_entity(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_entity("system", {"entity_id": "e1", "physical_source_ref": "t1", "case_id": "c"})
    resp = await ac.post("/api/v3/synapse/semantic/joins", json={
        "join_id": "j2",
        "left_entity_id": "e1",
        "right_entity_id": "no-exist",
        "join_condition": "x = y",
    }, headers=AUTH)
    assert resp.status_code == 404


# ========================================
# 품질 계약 테스트
# ========================================

@pytest.mark.asyncio
async def test_quality_contract(ac):
    resp = await ac.post("/api/v3/synapse/semantic/quality-contracts", json={
        "quality_contract_id": "qc1",
        "target_type": "measure",
        "target_id": "sales.mac",
        "freshness_sla_minutes": 60,
        "completeness_threshold": 98.0,
    }, headers=AUTH)
    assert resp.status_code == 201
    resp = await ac.get("/api/v3/synapse/semantic/quality-contracts?target_type=measure", headers=AUTH)
    assert resp.json()["count"] == 1


# ========================================
# 배포 + 카탈로그 테스트
# ========================================

@pytest.mark.asyncio
async def test_publish_and_releases(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_entity("system", {"entity_id": "e1", "physical_source_ref": "t1", "case_id": "c"})
    resp = await ac.post("/api/v3/synapse/semantic/publish", json={
        "semantic_object_type": "entity",
        "semantic_object_id": "e1",
    }, headers=AUTH)
    assert resp.status_code == 201
    assert resp.json()["data"]["review_status"] == "approved"

    resp = await ac.get("/api/v3/synapse/semantic/releases", headers=AUTH)
    assert resp.json()["count"] == 1


@pytest.mark.asyncio
async def test_catalog(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_concept("system", {"concept_id": "c1", "case_id": "c", "name_ko": "개념"})
    fake.create_entity("system", {"entity_id": "e1", "physical_source_ref": "t1", "case_id": "c"})
    resp = await ac.get("/api/v3/synapse/semantic/catalog", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["summary"]["concepts"] == 1
    assert data["summary"]["entities"] == 1


# ========================================
# P2: 그레인 계약 테스트
# ========================================

@pytest.mark.asyncio
async def test_grain_contract_crud(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_entity("system", {"entity_id": "e1", "physical_source_ref": "t1", "case_id": "c"})
    # 생성
    resp = await ac.post("/api/v3/synapse/semantic/grains", json={
        "grain_id": "g1",
        "entity_id": "e1",
        "grain_key_set": ["customer_id", "date"],
        "time_grain": "daily",
        "duplicate_resolution_rule": "latest_wins",
        "case_id": "c",
    }, headers=AUTH)
    assert resp.status_code == 201
    assert resp.json()["data"]["grain_id"] == "g1"

    # 조회
    resp = await ac.get("/api/v3/synapse/semantic/grains/g1", headers=AUTH)
    assert resp.status_code == 200

    # 목록
    resp = await ac.get("/api/v3/synapse/semantic/grains?entity_id=e1", headers=AUTH)
    assert resp.json()["count"] == 1

    # 수정
    resp = await ac.put("/api/v3/synapse/semantic/grains/g1", json={
        "time_grain": "monthly",
    }, headers=AUTH)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_grain_contract_missing_entity(ac):
    resp = await ac.post("/api/v3/synapse/semantic/grains", json={
        "grain_id": "g2",
        "entity_id": "no-exist",
        "grain_key_set": ["id"],
    }, headers=AUTH)
    assert resp.status_code == 404


# ========================================
# P2: Semantic Compiler 테스트
# ========================================

@pytest.mark.asyncio
async def test_compile_entity_valid(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_concept("system", {"concept_id": "c1", "case_id": "c", "name_ko": "고객"})
    fake.create_entity("system", {
        "entity_id": "e1", "physical_source_ref": "public.customer_daily",
        "bound_concept_id": "c1", "case_id": "c",
    })
    fake.create_measure("system", {
        "measure_id": "m1", "entity_id": "e1", "name": "활성고객",
        "measure_type": "distinct_count", "sql_expression": "customer_id",
        "bound_concept_id": "c1", "case_id": "c",
    })
    fake.create_grain_contract("system", {
        "grain_id": "g1", "entity_id": "e1",
        "grain_key_set": ["customer_id", "date"], "case_id": "c",
    })
    resp = await ac.post("/api/v3/synapse/semantic/compile/entity/e1", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["valid"] is True
    assert data["sql_template"] is not None
    assert "customer_id" in data["sql_template"]
    assert data["metadata"]["measure_count"] == 1


@pytest.mark.asyncio
async def test_compile_entity_missing_grain_warning(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_entity("system", {
        "entity_id": "e1", "physical_source_ref": "t1", "case_id": "c",
    })
    fake.create_measure("system", {
        "measure_id": "m1", "entity_id": "e1", "name": "X",
        "measure_type": "sum", "sql_expression": "amount", "case_id": "c",
    })
    resp = await ac.post("/api/v3/synapse/semantic/compile/entity/e1", headers=AUTH)
    data = resp.json()["data"]
    # 그레인 없으면 warning, 에러는 아니므로 valid=True
    assert data["valid"] is True
    codes = [i["code"] for i in data["issues"]]
    assert "NO_GRAIN" in codes
    assert "MISSING_BINDING" in codes  # 엔티티에 bound_concept_id 없음


@pytest.mark.asyncio
async def test_compile_entity_not_found(ac):
    resp = await ac.post("/api/v3/synapse/semantic/compile/entity/no-exist", headers=AUTH)
    data = resp.json()["data"]
    assert data["valid"] is False
    assert data["issues"][0]["code"] == "ENTITY_NOT_FOUND"


@pytest.mark.asyncio
async def test_compile_measure_valid(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_entity("system", {
        "entity_id": "e1", "physical_source_ref": "public.orders", "case_id": "c",
    })
    fake.create_measure("system", {
        "measure_id": "sales.total", "entity_id": "e1", "name": "총매출",
        "measure_type": "sum", "sql_expression": "amount",
        "filter_expression": "status = 'COMPLETED'",
        "bound_concept_id": None, "case_id": "c",
    })
    resp = await ac.post("/api/v3/synapse/semantic/compile/measure/sales.total", headers=AUTH)
    data = resp.json()["data"]
    assert data["valid"] is True
    assert "SUM(amount)" in data["sql_template"]
    assert "COMPLETED" in data["sql_template"]


@pytest.mark.asyncio
async def test_compile_measure_ratio_missing_parts(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_entity("system", {"entity_id": "e1", "physical_source_ref": "t1", "case_id": "c"})
    fake.create_measure("system", {
        "measure_id": "bad_ratio", "entity_id": "e1", "name": "비율",
        "measure_type": "ratio", "sql_expression": "x/y", "case_id": "c",
    })
    resp = await ac.post("/api/v3/synapse/semantic/compile/measure/bad_ratio", headers=AUTH)
    data = resp.json()["data"]
    assert data["valid"] is False
    codes = [i["code"] for i in data["issues"]]
    assert "RATIO_MISSING_PARTS" in codes


# ========================================
# P4: ContextPack + PromptPolicy 테스트
# ========================================

@pytest.mark.asyncio
async def test_context_pack_crud(ac, _inject_fake_store):
    # 생성
    resp = await ac.post("/api/v3/synapse/semantic/context-packs", json={
        "context_pack_id": "cp-kpi",
        "intent_type": "kpi_query",
        "description": "KPI 조회 전용 컨텍스트",
        "included_measure_ids": ["sales.mac", "sales.total"],
        "answer_guardrails": ["항상 transaction_date 기준으로 설명할 것"],
        "quality_gate_min_score": 80.0,
        "case_id": "c1",
    }, headers=AUTH)
    assert resp.status_code == 201
    assert resp.json()["data"]["intent_type"] == "kpi_query"

    # 목록
    resp = await ac.get("/api/v3/synapse/semantic/context-packs?intent_type=kpi_query", headers=AUTH)
    assert resp.json()["count"] == 1

    # 단건
    resp = await ac.get("/api/v3/synapse/semantic/context-packs/cp-kpi", headers=AUTH)
    assert resp.status_code == 200

    # 수정
    resp = await ac.put("/api/v3/synapse/semantic/context-packs/cp-kpi", json={
        "quality_gate_min_score": 90.0,
    }, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["version"] == 2


@pytest.mark.asyncio
async def test_context_pack_not_found(ac):
    resp = await ac.get("/api/v3/synapse/semantic/context-packs/no-exist", headers=AUTH)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_context_pack_delete(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_context_pack("system", {"context_pack_id": "cp-del", "intent_type": "general", "case_id": "c"})
    resp = await ac.delete("/api/v3/synapse/semantic/context-packs/cp-del", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    # 삭제 확인
    resp = await ac.get("/api/v3/synapse/semantic/context-packs/cp-del", headers=AUTH)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_prompt_policy_crud(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_context_pack("system", {"context_pack_id": "cp1", "intent_type": "kpi_query", "case_id": "c"})
    # 정책 생성
    resp = await ac.post("/api/v3/synapse/semantic/prompt-policies", json={
        "prompt_policy_id": "pp1",
        "context_pack_id": "cp1",
        "rule_type": "must_use_metric",
        "rule_text": "반드시 승인된 지표 정의의 sql_expression을 사용할 것",
        "priority": 10,
    }, headers=AUTH)
    assert resp.status_code == 201

    # 목록
    resp = await ac.get("/api/v3/synapse/semantic/prompt-policies?context_pack_id=cp1", headers=AUTH)
    assert resp.json()["count"] == 1

    # 삭제
    resp = await ac.delete("/api/v3/synapse/semantic/prompt-policies/pp1", headers=AUTH)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_prompt_policy_no_pack(ac):
    resp = await ac.post("/api/v3/synapse/semantic/prompt-policies", json={
        "prompt_policy_id": "pp2",
        "context_pack_id": "no-exist",
        "rule_type": "must_use_metric",
        "rule_text": "test",
    }, headers=AUTH)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resolve_context_pack(ac, _inject_fake_store):
    fake = _inject_fake_store
    fake.create_context_pack("system", {
        "context_pack_id": "cp-resolve",
        "intent_type": "root_cause",
        "answer_guardrails": ["원인 분석 시 Granger 검증 결과 인용"],
        "quality_gate_min_score": 75.0,
        "case_id": "c",
    })
    fake.create_prompt_policy("system", {
        "prompt_policy_id": "pp-r1",
        "context_pack_id": "cp-resolve",
        "rule_type": "must_cite_quality",
        "rule_text": "품질 점수가 80 미만이면 경고를 먼저 표시",
        "priority": 5,
    })
    resp = await ac.get("/api/v3/synapse/semantic/context-packs/cp-resolve/resolve", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["intent_type"] == "root_cause"
    assert data["quality_gate_min_score"] == 75.0
    assert len(data["prompt_policies"]) == 1
    assert "품질 점수" in data["prompt_policies"][0]["rule_text"]
    assert "원인 분석" in data["answer_guardrails"][0]
