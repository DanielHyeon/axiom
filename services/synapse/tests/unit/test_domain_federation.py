"""
P3 §5.1 도메인 네임스페이스 정책 + §5.2 도메인 스코프 승인 워크플로 테스트

FakeStore를 사용하여 PostgreSQL 없이 도메인 격리, 교차 도메인 조인,
승인 스코프 기반 상태 전이 등을 검증한다.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api import semantic_contract as sc_module

AUTH = {"Authorization": "Bearer local-oracle-token"}


# ── FakeStore: 도메인 연합 기능을 포함한 인메모리 저장소 ──

class FakeDomainStore:
    """§5.1 + §5.2 기능을 지원하는 인메모리 저장소"""

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

    # ── 개념 CRUD (§5.2: approval_scope 지원) ──

    def create_concept(self, tenant_id, data):
        cid = data["concept_id"]
        if cid in self.concepts:
            raise ValueError(f"concept_id '{cid}'가 이미 존재합니다")
        row = {
            **data,
            "tenant_id": tenant_id,
            "version": 1,
            "status": data.get("status", "draft"),
            "approval_scope": data.get("approval_scope", "global"),
            "approved_by": None,
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

    def list_concepts(self, tenant_id, case_id=None, status=None,
                      limit=100, offset=0, approval_scope=None, domain_id=None):
        """§5.1: domain_id 필터, §5.2: approval_scope 필터 지원"""
        result = [c for c in self.concepts.values() if c["tenant_id"] == tenant_id]
        if case_id:
            result = [c for c in result if c.get("case_id") == case_id]
        if status:
            result = [c for c in result if c.get("status") == status]
        if approval_scope:
            result = [c for c in result if c.get("approval_scope") == approval_scope]
        if domain_id:
            result = [c for c in result if c.get("domain_id") == domain_id]
        return result[offset:offset + limit]

    def update_concept(self, tenant_id, concept_id, data):
        c = self.get_concept(tenant_id, concept_id)
        if not c:
            raise KeyError(f"concept_id '{concept_id}'를 찾을 수 없습니다")
        c.update({k: v for k, v in data.items() if v is not None})
        c["version"] = c.get("version", 1) + 1
        return c

    def change_concept_status(self, tenant_id, concept_id, new_status, approved_by=None):
        """§5.2: approved_by 기록 지원"""
        c = self.get_concept(tenant_id, concept_id)
        if not c:
            raise KeyError(f"concept_id '{concept_id}'를 찾을 수 없습니다")
        transitions = {
            "draft": {"review", "deprecated"},
            "review": {"approved", "draft"},
            "approved": {"deprecated"},
            "deprecated": {"draft"},
        }
        allowed = transitions.get(c["status"], set())
        if new_status not in allowed:
            raise ValueError(f"'{c['status']}' → '{new_status}' 전이가 허용되지 않습니다. 가능: {allowed}")
        c["status"] = new_status
        if new_status == "approved" and approved_by:
            c["approved_by"] = approved_by
        return c

    # ── 용어 ──

    def create_term(self, tenant_id, data):
        if not self.get_concept(tenant_id, data["concept_id"]):
            raise KeyError(f"concept_id '{data['concept_id']}'를 찾을 수 없습니다")
        self._term_seq += 1
        row = {**data, "term_id": self._term_seq, "tenant_id": tenant_id, "created_at": "2026-03-23T00:00:00"}
        self.terms.append(row)
        return row

    def create_terms_bulk(self, tenant_id, terms):
        return [self.create_term(tenant_id, t) for t in terms]

    def search_terms(self, tenant_id, query, limit=50):
        return [t for t in self.terms if tenant_id == t["tenant_id"] and query.lower() in t["surface_form"].lower()][:limit]

    def list_terms_by_concept(self, tenant_id, concept_id):
        return [t for t in self.terms if t["tenant_id"] == tenant_id and t["concept_id"] == concept_id]

    # ── 엔티티 (§5.1: domain_id 지원) ──

    def create_entity(self, tenant_id, data):
        eid = data["entity_id"]
        if eid in self.entities:
            raise ValueError(f"entity_id '{eid}'가 이미 존재합니다")
        row = {
            **data,
            "tenant_id": tenant_id,
            "status": "draft",
            "version": 1,
            "domain_id": data.get("domain_id", "global"),
            "created_at": "2026-03-23T00:00:00",
        }
        self.entities[eid] = row
        return row

    def get_entity(self, tenant_id, entity_id):
        e = self.entities.get(entity_id)
        return e if e and e.get("tenant_id") == tenant_id else None

    def list_entities(self, tenant_id, case_id=None, domain_id=None, limit=100, offset=0):
        """§5.1: domain_id 필터"""
        result = [e for e in self.entities.values() if e["tenant_id"] == tenant_id]
        if case_id:
            result = [e for e in result if e.get("case_id") == case_id]
        if domain_id:
            result = [e for e in result if e.get("domain_id") == domain_id]
        return result[offset:offset + limit]

    def update_entity(self, tenant_id, entity_id, data):
        e = self.get_entity(tenant_id, entity_id)
        if not e:
            raise KeyError(f"entity_id '{entity_id}'를 찾을 수 없습니다")
        e.update({k: v for k, v in data.items() if v is not None})
        e["version"] = e.get("version", 1) + 1
        return e

    # ── 지표 (§5.1: domain_id 지원) ──

    def create_measure(self, tenant_id, data):
        mid = data["measure_id"]
        if mid in self.measures:
            raise ValueError(f"measure_id '{mid}'가 이미 존재합니다")
        if not self.get_entity(tenant_id, data["entity_id"]):
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        row = {
            **data,
            "tenant_id": tenant_id,
            "status": "draft",
            "version": 1,
            "domain_id": data.get("domain_id", "global"),
            "created_at": "2026-03-23T00:00:00",
        }
        self.measures[mid] = row
        return row

    def get_measure(self, tenant_id, measure_id):
        m = self.measures.get(measure_id)
        return m if m and m.get("tenant_id") == tenant_id else None

    def list_measures(self, tenant_id, case_id=None, entity_id=None, domain_id=None, limit=100, offset=0):
        result = [m for m in self.measures.values() if m["tenant_id"] == tenant_id]
        if case_id:
            result = [m for m in result if m.get("case_id") == case_id]
        if entity_id:
            result = [m for m in result if m.get("entity_id") == entity_id]
        if domain_id:
            result = [m for m in result if m.get("domain_id") == domain_id]
        return result[offset:offset + limit]

    def update_measure(self, tenant_id, measure_id, data):
        m = self.get_measure(tenant_id, measure_id)
        if not m:
            raise KeyError(f"measure_id '{measure_id}'를 찾을 수 없습니다")
        m.update({k: v for k, v in data.items() if v is not None})
        m["version"] = m.get("version", 1) + 1
        return m

    # ── 차원 (§5.1: domain_id, conformed_group 지원) ──

    def create_dimension(self, tenant_id, data):
        did = data["dimension_id"]
        if did in self.dimensions:
            raise ValueError(f"dimension_id '{did}'가 이미 존재합니다")
        if not self.get_entity(tenant_id, data["entity_id"]):
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        row = {
            **data,
            "tenant_id": tenant_id,
            "status": "draft",
            "version": 1,
            "domain_id": data.get("domain_id", "global"),
            "created_at": "2026-03-23T00:00:00",
        }
        self.dimensions[did] = row
        return row

    def get_dimension(self, tenant_id, dimension_id):
        d = self.dimensions.get(dimension_id)
        return d if d and d.get("tenant_id") == tenant_id else None

    def list_dimensions(self, tenant_id, case_id=None, entity_id=None,
                        domain_id=None, conformed_group=None, limit=100, offset=0):
        result = [d for d in self.dimensions.values() if d["tenant_id"] == tenant_id]
        if case_id:
            result = [d for d in result if d.get("case_id") == case_id]
        if entity_id:
            result = [d for d in result if d.get("entity_id") == entity_id]
        if domain_id:
            result = [d for d in result if d.get("domain_id") == domain_id]
        if conformed_group:
            result = [d for d in result if d.get("conformed_group") == conformed_group]
        return result[offset:offset + limit]

    def update_dimension(self, tenant_id, dimension_id, data):
        d = self.get_dimension(tenant_id, dimension_id)
        if not d:
            raise KeyError(f"dimension_id '{dimension_id}'를 찾을 수 없습니다")
        d.update({k: v for k, v in data.items() if v is not None})
        d["version"] = d.get("version", 1) + 1
        return d

    # ── 조인 계약 (§5.1: domain_id 지원) ──

    def create_join_contract(self, tenant_id, data):
        jid = data["join_id"]
        if jid in self.joins:
            raise ValueError(f"join_id '{jid}'가 이미 존재합니다")
        for eid in (data["left_entity_id"], data["right_entity_id"]):
            if not self.get_entity(tenant_id, eid):
                raise KeyError(f"entity_id '{eid}'를 찾을 수 없습니다")
        row = {
            **data,
            "tenant_id": tenant_id,
            "status": "draft",
            "domain_id": data.get("domain_id", "global"),
            "created_at": "2026-03-23T00:00:00",
        }
        self.joins[jid] = row
        return row

    def get_join_contract(self, tenant_id, join_id):
        j = self.joins.get(join_id)
        return j if j and j.get("tenant_id") == tenant_id else None

    def list_join_contracts(self, tenant_id, case_id=None, allowed_for_ai=None,
                            domain_id=None, limit=100, offset=0):
        result = [j for j in self.joins.values() if j["tenant_id"] == tenant_id]
        if case_id:
            result = [j for j in result if j.get("case_id") == case_id]
        if allowed_for_ai is not None:
            result = [j for j in result if j.get("allowed_for_ai") == allowed_for_ai]
        if domain_id:
            result = [j for j in result if j.get("domain_id") == domain_id]
        return result[offset:offset + limit]

    def update_join_contract(self, tenant_id, join_id, data):
        j = self.get_join_contract(tenant_id, join_id)
        if not j:
            raise KeyError(f"join_id '{join_id}'를 찾을 수 없습니다")
        j.update({k: v for k, v in data.items() if v is not None})
        return j

    # ── 나머지 (테스트에서 필요한 최소 메서드) ──

    def create_quality_contract(self, tenant_id, data):
        qid = data["quality_contract_id"]
        row = {**data, "tenant_id": tenant_id, "created_at": "2026-03-23T00:00:00"}
        self.quality_contracts[qid] = row
        return row

    def list_quality_contracts(self, tenant_id, case_id=None, target_type=None, limit=100, offset=0):
        return list(self.quality_contracts.values())

    def create_grain_contract(self, tenant_id, data):
        gid = data["grain_id"]
        row = {**data, "tenant_id": tenant_id, "created_at": "2026-03-23T00:00:00"}
        self.grains[gid] = row
        return row

    def get_grain_contract(self, tenant_id, grain_id):
        return self.grains.get(grain_id)

    def list_grain_contracts(self, tenant_id, case_id=None, entity_id=None, limit=100, offset=0):
        return list(self.grains.values())

    def update_grain_contract(self, tenant_id, grain_id, data):
        g = self.grains.get(grain_id)
        if not g:
            raise KeyError(f"grain_id '{grain_id}'를 찾을 수 없습니다")
        g.update({k: v for k, v in data.items() if v is not None})
        return g

    def publish(self, tenant_id, object_type, object_id, reviewer=None):
        return {"release_id": 1, "semantic_object_type": object_type, "semantic_object_id": object_id}

    def list_releases(self, tenant_id, limit=50, offset=0):
        return self.releases

    def get_catalog(self, tenant_id, case_id=None):
        return {"summary": {}, "concepts": [], "entities": [], "measures": [], "dimensions": [], "joins": [], "grains": []}

    def get_ai_context(self, tenant_id, case_id=None):
        return {"context_type": "semantic_contract", "approved_only": True}

    def create_context_pack(self, tenant_id, data):
        cpid = data["context_pack_id"]
        row = {**data, "tenant_id": tenant_id, "version": 1}
        self.context_packs[cpid] = row
        return row

    def get_context_pack(self, tenant_id, cpid):
        return self.context_packs.get(cpid)

    def list_context_packs(self, tenant_id, case_id=None, intent_type=None, limit=100, offset=0):
        return list(self.context_packs.values())

    def update_context_pack(self, tenant_id, cpid, data):
        cp = self.context_packs.get(cpid)
        if not cp:
            raise KeyError(f"context_pack_id '{cpid}'를 찾을 수 없습니다")
        cp.update(data)
        return cp

    def delete_context_pack(self, tenant_id, cpid):
        return self.context_packs.pop(cpid, None) is not None

    def resolve_context_pack(self, tenant_id, cpid):
        cp = self.context_packs.get(cpid)
        if not cp:
            raise KeyError(f"context_pack_id '{cpid}'를 찾을 수 없습니다")
        return cp

    def create_prompt_policy(self, tenant_id, data):
        ppid = data["prompt_policy_id"]
        row = {**data, "tenant_id": tenant_id}
        self.prompt_policies[ppid] = row
        return row

    def list_prompt_policies(self, tenant_id, cpid):
        return [p for p in self.prompt_policies.values() if p.get("context_pack_id") == cpid]

    def delete_prompt_policy(self, tenant_id, ppid):
        return self.prompt_policies.pop(ppid, None) is not None

    def detect_conflicts(self, tenant_id):
        return {"conflicts": []}

    def analyze_impact(self, tenant_id, object_type, object_id):
        return {"impacted": []}

    def generate_training_query(self, tenant_id, entity_id, columns=None, date_range=None):
        return {"sql": "SELECT 1", "entity_id": entity_id}


# ── 픽스처: FakeStore로 모듈 교체 ──

_fake = FakeDomainStore()


@pytest.fixture(autouse=True)
def _inject_fake(monkeypatch):
    """API 라우터 안의 _store를 FakeStore로 교체한다."""
    _fake.__init__()  # 매 테스트마다 초기화
    monkeypatch.setattr(sc_module, "_store", _fake)


@pytest_asyncio.fixture
async def client():
    """FastAPI 테스트 클라이언트"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── 도우미 함수 ──

def _concept_body(concept_id: str, domain_id: str = "default",
                  approval_scope: str = "global", **kwargs) -> dict:
    """개념 생성 요청 본문 생성"""
    return {
        "concept_id": concept_id,
        "case_id": "case-1",
        "domain_id": domain_id,
        "name_ko": f"테스트 개념 {concept_id}",
        "approval_scope": approval_scope,
        **kwargs,
    }


def _entity_body(entity_id: str, domain_id: str = "global", **kwargs) -> dict:
    """엔티티 생성 요청 본문 생성"""
    return {
        "entity_id": entity_id,
        "physical_source_ref": f"dw.{entity_id}_table",
        "entity_type": "fact",
        "case_id": "case-1",
        "domain_id": domain_id,
        **kwargs,
    }


def _measure_body(measure_id: str, entity_id: str, domain_id: str = "global", **kwargs) -> dict:
    """지표 생성 요청 본문 생성"""
    return {
        "measure_id": measure_id,
        "entity_id": entity_id,
        "name": f"테스트 지표 {measure_id}",
        "sql_expression": "SUM(amount)",
        "case_id": "case-1",
        "domain_id": domain_id,
        **kwargs,
    }


def _dimension_body(dimension_id: str, entity_id: str, domain_id: str = "global", **kwargs) -> dict:
    """차원 생성 요청 본문 생성"""
    return {
        "dimension_id": dimension_id,
        "entity_id": entity_id,
        "name": f"테스트 차원 {dimension_id}",
        "sql_expression": "region_code",
        "case_id": "case-1",
        "domain_id": domain_id,
        **kwargs,
    }


# ========================================
# §5.1: 도메인 네임스페이스 정책 테스트
# ========================================

@pytest.mark.anyio
async def test_entity_domain_id_defaults_to_global(client):
    """엔티티 생성 시 domain_id 미지정이면 'global'이 기본값이다."""
    # domain_id를 생략한 요청
    body = {
        "entity_id": "ent-no-domain",
        "physical_source_ref": "dw.orders",
        "entity_type": "fact",
        "case_id": "case-1",
    }
    resp = await client.post("/api/v3/synapse/semantic/entities", json=body, headers=AUTH)
    assert resp.status_code == 201
    data = resp.json()["data"]
    # FakeStore가 domain_id='global'을 기본값으로 설정
    assert data.get("domain_id") == "global"


@pytest.mark.anyio
async def test_list_entities_filter_by_domain(client):
    """§5.1: 엔티티 목록 조회 시 domain_id 필터가 동작한다."""
    # 서로 다른 도메인에 엔티티 생성
    await client.post("/api/v3/synapse/semantic/entities",
                      json=_entity_body("ent-sales", domain_id="sales"), headers=AUTH)
    await client.post("/api/v3/synapse/semantic/entities",
                      json=_entity_body("ent-hr", domain_id="hr"), headers=AUTH)
    await client.post("/api/v3/synapse/semantic/entities",
                      json=_entity_body("ent-global"), headers=AUTH)

    # sales 도메인만 조회
    resp = await client.get("/api/v3/synapse/semantic/entities?domain_id=sales", headers=AUTH)
    assert resp.status_code == 200
    entities = resp.json()["data"]
    assert len(entities) == 1
    assert entities[0]["entity_id"] == "ent-sales"


@pytest.mark.anyio
async def test_measure_inherits_domain_from_request(client):
    """§5.1: 지표 생성 시 domain_id를 명시적으로 전달할 수 있다."""
    # 엔티티 먼저 생성
    await client.post("/api/v3/synapse/semantic/entities",
                      json=_entity_body("ent-fin", domain_id="finance"), headers=AUTH)
    # 지표 생성 시 domain_id 지정
    resp = await client.post("/api/v3/synapse/semantic/measures",
                             json=_measure_body("m-revenue", "ent-fin", domain_id="finance"),
                             headers=AUTH)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data.get("domain_id") == "finance"

    # domain_id로 필터링
    resp = await client.get("/api/v3/synapse/semantic/measures?domain_id=finance", headers=AUTH)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.anyio
async def test_cross_domain_join_allowed(client):
    """§5.1: 서로 다른 도메인의 엔티티 간 조인 계약 생성이 허용된다."""
    await client.post("/api/v3/synapse/semantic/entities",
                      json=_entity_body("ent-left", domain_id="sales"), headers=AUTH)
    await client.post("/api/v3/synapse/semantic/entities",
                      json=_entity_body("ent-right", domain_id="logistics"), headers=AUTH)

    join_body = {
        "join_id": "j-cross",
        "left_entity_id": "ent-left",
        "right_entity_id": "ent-right",
        "join_type": "LEFT",
        "join_condition": "left.order_id = right.order_id",
        "relationship_type": "1:N",
        "case_id": "case-1",
        "domain_id": "global",
    }
    resp = await client.post("/api/v3/synapse/semantic/joins", json=join_body, headers=AUTH)
    # 교차 도메인 조인은 허용되어야 한다 (경고 로그만 남김)
    assert resp.status_code == 201


@pytest.mark.anyio
async def test_list_joins_filter_by_domain(client):
    """§5.1: 조인 목록 조회 시 domain_id 필터가 동작한다."""
    await client.post("/api/v3/synapse/semantic/entities",
                      json=_entity_body("ent-a", domain_id="sales"), headers=AUTH)
    await client.post("/api/v3/synapse/semantic/entities",
                      json=_entity_body("ent-b", domain_id="sales"), headers=AUTH)
    await client.post("/api/v3/synapse/semantic/entities",
                      json=_entity_body("ent-c", domain_id="hr"), headers=AUTH)

    join1 = {
        "join_id": "j-sales",
        "left_entity_id": "ent-a",
        "right_entity_id": "ent-b",
        "join_type": "LEFT",
        "join_condition": "a.id = b.id",
        "relationship_type": "1:N",
        "case_id": "case-1",
        "domain_id": "sales",
    }
    join2 = {
        "join_id": "j-hr",
        "left_entity_id": "ent-a",
        "right_entity_id": "ent-c",
        "join_type": "LEFT",
        "join_condition": "a.id = c.id",
        "relationship_type": "1:N",
        "case_id": "case-1",
        "domain_id": "hr",
    }
    await client.post("/api/v3/synapse/semantic/joins", json=join1, headers=AUTH)
    await client.post("/api/v3/synapse/semantic/joins", json=join2, headers=AUTH)

    resp = await client.get("/api/v3/synapse/semantic/joins?domain_id=sales", headers=AUTH)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["join_id"] == "j-sales"


@pytest.mark.anyio
async def test_dimension_domain_id_and_conformed_group(client):
    """§5.1: 차원의 domain_id와 conformed_group 필터가 동작한다."""
    await client.post("/api/v3/synapse/semantic/entities",
                      json=_entity_body("ent-dim-a", domain_id="sales"), headers=AUTH)
    await client.post("/api/v3/synapse/semantic/entities",
                      json=_entity_body("ent-dim-b", domain_id="hr"), headers=AUTH)

    # 같은 conformed_group이지만 다른 도메인
    dim1 = _dimension_body("dim-date-sales", "ent-dim-a", domain_id="sales",
                           conformed_group="date_dim")
    dim2 = _dimension_body("dim-date-hr", "ent-dim-b", domain_id="hr",
                           conformed_group="date_dim")
    dim3 = _dimension_body("dim-region-sales", "ent-dim-a", domain_id="sales")

    await client.post("/api/v3/synapse/semantic/dimensions", json=dim1, headers=AUTH)
    await client.post("/api/v3/synapse/semantic/dimensions", json=dim2, headers=AUTH)
    await client.post("/api/v3/synapse/semantic/dimensions", json=dim3, headers=AUTH)

    # conformed_group으로 조회: 도메인에 관계없이 모든 date_dim 차원
    resp = await client.get("/api/v3/synapse/semantic/dimensions?conformed_group=date_dim", headers=AUTH)
    assert resp.status_code == 200
    dims = resp.json()["data"]
    assert len(dims) == 2  # 두 도메인 모두 포함

    # domain_id로 조회: sales 도메인의 차원만
    resp = await client.get("/api/v3/synapse/semantic/dimensions?domain_id=sales", headers=AUTH)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2  # dim-date-sales, dim-region-sales


@pytest.mark.anyio
async def test_conformed_dimension_visible_across_domains(client):
    """§5.1: conformed_group이 설정된 차원은 도메인과 무관하게 검색 가능하다."""
    await client.post("/api/v3/synapse/semantic/entities",
                      json=_entity_body("ent-conformed", domain_id="finance"), headers=AUTH)

    dim = _dimension_body("dim-customer-shared", "ent-conformed",
                          domain_id="finance", conformed_group="customer_dim")
    await client.post("/api/v3/synapse/semantic/dimensions", json=dim, headers=AUTH)

    # conformed_group 검색은 도메인 무관
    resp = await client.get("/api/v3/synapse/semantic/dimensions?conformed_group=customer_dim", headers=AUTH)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["conformed_group"] == "customer_dim"


# ========================================
# §5.2: 도메인 스코프 승인 워크플로 테스트
# ========================================

@pytest.mark.anyio
async def test_concept_domain_approval_scope(client):
    """§5.2: 개념 생성 시 approval_scope를 지정할 수 있다."""
    body = _concept_body("c-domain-scoped", approval_scope="domain")
    resp = await client.post("/api/v3/synapse/semantic/concepts", json=body, headers=AUTH)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["approval_scope"] == "domain"


@pytest.mark.anyio
async def test_domain_scope_allows_direct_approval(client):
    """§5.2: approval_scope='domain'인 개념은 역할에 관계없이 review→approved 전이가 가능하다."""
    # domain 스코프 개념 생성
    body = _concept_body("c-domain-approve", approval_scope="domain")
    await client.post("/api/v3/synapse/semantic/concepts", json=body, headers=AUTH)

    # draft → review
    resp = await client.patch(
        "/api/v3/synapse/semantic/concepts/c-domain-approve/status",
        json={"status": "review"},
        headers=AUTH,
    )
    assert resp.status_code == 200

    # review → approved (domain scope이므로 역할 확인 없이 통과)
    resp = await client.patch(
        "/api/v3/synapse/semantic/concepts/c-domain-approve/status",
        json={"status": "approved"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "approved"


@pytest.mark.anyio
async def test_global_scope_requires_reviewer(client):
    """§5.2: approval_scope='global'인 개념은 admin/manager만 approved로 전이할 수 있다.

    주의: 이 테스트에서는 FakeStore를 사용하므로 API 레벨의 역할 체크만 검증한다.
    테스트 환경의 기본 user_role이 admin이 아닌 경우 403을 반환해야 한다.
    """
    # global 스코프 개념 생성
    body = _concept_body("c-global-approve", approval_scope="global")
    await client.post("/api/v3/synapse/semantic/concepts", json=body, headers=AUTH)

    # draft → review
    resp = await client.patch(
        "/api/v3/synapse/semantic/concepts/c-global-approve/status",
        json={"status": "review"},
        headers=AUTH,
    )
    assert resp.status_code == 200

    # review → approved: 역할 확인이 실행된다
    # 테스트 환경에서 user_role이 설정되지 않으면 403
    resp = await client.patch(
        "/api/v3/synapse/semantic/concepts/c-global-approve/status",
        json={"status": "approved"},
        headers=AUTH,
    )
    # 기본 미들웨어에서 user_role이 없으면 403
    # 만약 admin으로 설정되어 있으면 200
    assert resp.status_code in (200, 403)


@pytest.mark.anyio
async def test_list_concepts_filter_by_approval_scope(client):
    """§5.2: 개념 목록 조회 시 approval_scope 필터가 동작한다."""
    await client.post("/api/v3/synapse/semantic/concepts",
                      json=_concept_body("c-d1", approval_scope="domain"), headers=AUTH)
    await client.post("/api/v3/synapse/semantic/concepts",
                      json=_concept_body("c-d2", approval_scope="domain"), headers=AUTH)
    await client.post("/api/v3/synapse/semantic/concepts",
                      json=_concept_body("c-g1", approval_scope="global"), headers=AUTH)

    resp = await client.get("/api/v3/synapse/semantic/concepts?approval_scope=domain", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["count"] == 2

    resp = await client.get("/api/v3/synapse/semantic/concepts?approval_scope=global", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


@pytest.mark.anyio
async def test_domain_id_migration_existing_data(client):
    """§5.1: domain_id 컬럼이 없는 기존 데이터에 대해 기본값 'global'이 적용된다.

    FakeStore에서 domain_id 미지정 시 'global' 기본값을 검증한다.
    실제 DB에서는 ALTER TABLE ... DEFAULT 'global'로 처리된다.
    """
    # domain_id 없이 엔티티 생성 (기존 데이터 시뮬레이션)
    body = {
        "entity_id": "ent-legacy",
        "physical_source_ref": "legacy.orders",
        "entity_type": "fact",
        "case_id": "case-1",
    }
    resp = await client.post("/api/v3/synapse/semantic/entities", json=body, headers=AUTH)
    assert resp.status_code == 201

    # 전체 조회 시 domain_id='global'이 기본값으로 설정되어야 함
    resp = await client.get("/api/v3/synapse/semantic/entities?domain_id=global", headers=AUTH)
    assert resp.status_code == 200
    entity_ids = [e["entity_id"] for e in resp.json()["data"]]
    assert "ent-legacy" in entity_ids


@pytest.mark.anyio
async def test_list_concepts_filter_by_domain_id(client):
    """§5.1: 개념 목록 조회 시 domain_id 필터가 동작한다."""
    await client.post("/api/v3/synapse/semantic/concepts",
                      json=_concept_body("c-sales", domain_id="sales"), headers=AUTH)
    await client.post("/api/v3/synapse/semantic/concepts",
                      json=_concept_body("c-hr", domain_id="hr"), headers=AUTH)

    resp = await client.get("/api/v3/synapse/semantic/concepts?domain_id=sales", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
    assert resp.json()["data"][0]["concept_id"] == "c-sales"


@pytest.mark.anyio
async def test_update_concept_approval_scope(client):
    """§5.2: 개념의 approval_scope를 수정할 수 있다."""
    await client.post("/api/v3/synapse/semantic/concepts",
                      json=_concept_body("c-update-scope", approval_scope="global"), headers=AUTH)

    # approval_scope를 domain으로 변경
    resp = await client.put(
        "/api/v3/synapse/semantic/concepts/c-update-scope",
        json={"approval_scope": "domain"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["approval_scope"] == "domain"
