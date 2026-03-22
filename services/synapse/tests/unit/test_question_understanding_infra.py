"""
Sprint 4: 질문 이해 인프라 단위 테스트

별칭 그룹, 확장 규칙, 의도 모델, 추론 로그, 질문 피드백의
API CRUD 동작과 라이프사이클(activate/deprecate/resolve)을 검증한다.
FakeStore를 주입하여 PostgreSQL 없이 API 동작을 검증한다.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api import semantic_contract as sc_module

AUTH = {"Authorization": "Bearer local-oracle-token"}
BASE = "/api/v3/synapse/semantic"


# ── FakeStore 확장: Sprint 4 질문 이해 인프라 메서드 추가 ──
# 기존 FakeSemanticStore를 가져와서 확장하는 대신, 필요한 메서드만 가진 Fake를 생성한다.

class FakeQuestionStore:
    """Sprint 4 질문 이해 인프라용 인메모리 Fake Store"""

    def __init__(self):
        # 기존 시멘틱 계약 데이터
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
        self.segments: dict[str, dict] = {}
        self.time_contracts: dict[str, dict] = {}
        self.access_policies: dict[str, dict] = {}
        self.rules: dict[str, dict] = {}
        self.policies: dict[str, dict] = {}
        self.relations: dict[str, dict] = {}
        self._term_seq = 0

        # Sprint 4 신규 데이터
        self.alias_groups: dict[str, dict] = {}
        self.expansion_rules: dict[str, dict] = {}
        self.intent_models: dict[str, dict] = {}
        self.inference_logs: list[dict] = []
        self.question_feedback: dict[str, dict] = {}

    def ensure_schema(self):
        pass

    # ── 기존 메서드 스텁 (API 라우터가 필요로 하는 것들) ──
    def create_concept(self, tenant_id, data):
        cid = data["concept_id"]
        row = {**data, "tenant_id": tenant_id, "version": 1, "status": "draft"}
        self.concepts[cid] = row
        return row

    def get_concept(self, tenant_id, concept_id):
        c = self.concepts.get(concept_id)
        return c if c and c.get("tenant_id") == tenant_id else None

    def list_concepts(self, tenant_id, **kwargs):
        return [c for c in self.concepts.values() if c["tenant_id"] == tenant_id]

    def get_entity(self, tenant_id, entity_id):
        e = self.entities.get(entity_id)
        return e if e and e.get("tenant_id") == tenant_id else None

    def get_catalog(self, tenant_id, case_id=None):
        return {"summary": {}, "concepts": [], "entities": [], "measures": [], "dimensions": [], "joins": []}

    def detect_conflicts(self, tenant_id):
        return {"concept_conflicts": [], "measure_conflicts": [], "term_collisions": []}

    # ── Sprint 4: 별칭 그룹 ──

    def create_alias_group(self, tenant_id, data):
        """별칭 그룹 생성 — 인메모리"""
        gid = data["id"]
        if gid in self.alias_groups:
            raise ValueError(f"alias_group id '{gid}'가 이미 존재합니다")
        from app.models.semantic_models import VALID_ALIAS_GROUP_STATUSES
        status = data.get("status", "ACTIVE")
        if status not in VALID_ALIAS_GROUP_STATUSES:
            raise ValueError(f"status는 {VALID_ALIAS_GROUP_STATUSES} 중 하나여야 합니다: {status}")
        row = {
            **data, "tenant_id": tenant_id, "status": status,
            "created_at": "2026-03-23T00:00:00", "updated_at": "2026-03-23T00:00:00",
        }
        self.alias_groups[gid] = row
        return row

    def list_alias_groups(self, tenant_id, domain_id=None, status=None, limit=100, offset=0):
        """별칭 그룹 목록 조회"""
        result = [g for g in self.alias_groups.values() if g["tenant_id"] == tenant_id]
        if domain_id:
            result = [g for g in result if g.get("domain_id") == domain_id]
        if status:
            result = [g for g in result if g.get("status") == status]
        return result[offset:offset + limit]

    def get_alias_group(self, tenant_id, group_id):
        """별칭 그룹 단건 조회"""
        g = self.alias_groups.get(group_id)
        return g if g and g.get("tenant_id") == tenant_id else None

    # ── Sprint 4: 확장 규칙 ──

    def create_expansion_rule(self, tenant_id, data):
        """확장 규칙 생성"""
        rid = data["id"]
        if rid in self.expansion_rules:
            raise ValueError(f"expansion_rule id '{rid}'가 이미 존재합니다")
        from app.models.semantic_models import VALID_EXPANSION_RULE_TYPES
        rule_type = data.get("rule_type", "")
        if rule_type not in VALID_EXPANSION_RULE_TYPES:
            raise ValueError(f"rule_type은 {VALID_EXPANSION_RULE_TYPES} 중 하나여야 합니다: {rule_type}")
        # 별칭 그룹 존재 확인
        if not self.get_alias_group(tenant_id, data["alias_group_id"]):
            raise KeyError(f"alias_group_id '{data['alias_group_id']}'를 찾을 수 없습니다")
        row = {
            **data, "tenant_id": tenant_id,
            "status": data.get("status", "ACTIVE"),
            "created_at": "2026-03-23T00:00:00",
        }
        self.expansion_rules[rid] = row
        return row

    def list_expansion_rules(self, tenant_id, alias_group_id=None, rule_type=None, status=None, limit=100, offset=0):
        """확장 규칙 목록"""
        result = [r for r in self.expansion_rules.values() if r["tenant_id"] == tenant_id]
        if alias_group_id:
            result = [r for r in result if r.get("alias_group_id") == alias_group_id]
        if rule_type:
            result = [r for r in result if r.get("rule_type") == rule_type]
        if status:
            result = [r for r in result if r.get("status") == status]
        return result[offset:offset + limit]

    def update_expansion_rule(self, tenant_id, rule_id, data):
        """확장 규칙 수정"""
        r = self.expansion_rules.get(rule_id)
        if not r or r.get("tenant_id") != tenant_id:
            raise KeyError(f"expansion_rule id '{rule_id}'를 찾을 수 없습니다")
        from app.models.semantic_models import VALID_EXPANSION_RULE_TYPES
        if "rule_type" in data and data["rule_type"] not in VALID_EXPANSION_RULE_TYPES:
            raise ValueError(f"rule_type 유효하지 않음: {data['rule_type']}")
        r.update({k: v for k, v in data.items() if v is not None})
        return r

    def activate_rule(self, tenant_id, rule_id):
        """확장 규칙 활성화"""
        r = self.expansion_rules.get(rule_id)
        if not r or r.get("tenant_id") != tenant_id:
            raise KeyError(f"expansion_rule id '{rule_id}'를 찾을 수 없습니다")
        r["status"] = "ACTIVE"
        return r

    def deprecate_rule(self, tenant_id, rule_id):
        """확장 규칙 비활성화"""
        r = self.expansion_rules.get(rule_id)
        if not r or r.get("tenant_id") != tenant_id:
            raise KeyError(f"expansion_rule id '{rule_id}'를 찾을 수 없습니다")
        r["status"] = "DEPRECATED"
        return r

    # ── Sprint 4: 의도 모델 ──

    def create_intent_model(self, tenant_id, data):
        """의도 모델 등록"""
        mid = data["id"]
        if mid in self.intent_models:
            raise ValueError(f"intent_model id '{mid}'가 이미 존재합니다")
        from app.models.semantic_models import VALID_INTENT_MODEL_TYPES
        model_type = data.get("model_type", "keyword")
        if model_type not in VALID_INTENT_MODEL_TYPES:
            raise ValueError(f"model_type은 {VALID_INTENT_MODEL_TYPES} 중 하나여야 합니다: {model_type}")
        row = {**data, "tenant_id": tenant_id, "created_at": "2026-03-23T00:00:00"}
        self.intent_models[mid] = row
        return row

    def list_intent_models(self, tenant_id, status=None, limit=100, offset=0):
        """의도 모델 목록"""
        result = [m for m in self.intent_models.values() if m["tenant_id"] == tenant_id]
        if status:
            result = [m for m in result if m.get("status") == status]
        return result[offset:offset + limit]

    # ── Sprint 4: 추론 로그 ──

    def create_inference_log(self, tenant_id, data):
        """추론 로그 기록"""
        row = {**data, "tenant_id": tenant_id, "created_at": "2026-03-23T00:00:00"}
        self.inference_logs.append(row)
        return row

    def list_inference_logs(self, tenant_id, limit=50, offset=0):
        """추론 로그 목록"""
        result = [l for l in self.inference_logs if l["tenant_id"] == tenant_id]
        return result[offset:offset + limit]

    # ── Sprint 4: 질문 피드백 ──

    def create_question_feedback(self, tenant_id, data):
        """피드백 등록"""
        fid = data["id"]
        if fid in self.question_feedback:
            raise ValueError(f"feedback id '{fid}'가 이미 존재합니다")
        from app.models.semantic_models import VALID_FEEDBACK_ISSUE_TYPES
        issue_type = data.get("issue_type", "")
        if issue_type not in VALID_FEEDBACK_ISSUE_TYPES:
            raise ValueError(f"issue_type은 {VALID_FEEDBACK_ISSUE_TYPES} 중 하나여야 합니다: {issue_type}")
        row = {**data, "tenant_id": tenant_id, "resolved": False, "created_at": "2026-03-23T00:00:00"}
        self.question_feedback[fid] = row
        return row

    def list_question_feedback(self, tenant_id, resolved=None, limit=50, offset=0):
        """피드백 목록"""
        result = [f for f in self.question_feedback.values() if f["tenant_id"] == tenant_id]
        if resolved is not None:
            result = [f for f in result if f.get("resolved") == resolved]
        return result[offset:offset + limit]

    def resolve_feedback(self, tenant_id, feedback_id):
        """피드백 해결"""
        f = self.question_feedback.get(feedback_id)
        if not f or f.get("tenant_id") != tenant_id:
            raise KeyError(f"feedback id '{feedback_id}'를 찾을 수 없습니다")
        f["resolved"] = True
        return f

    # ── 기존 패턴 호환을 위한 더미 메서드들 ──
    def publish(self, *a, **kw):
        return {}

    def list_releases(self, *a, **kw):
        return []

    def resolve_context_pack(self, *a, **kw):
        return {}

    def analyze_impact(self, *a, **kw):
        return {"affected": {}, "total_affected": 0}


# ── Fixtures ──

@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def _inject_fake_store():
    """테스트마다 FakeStore 주입 → 테스트 간 격리"""
    fake = FakeQuestionStore()
    sc_module._store = fake
    # Compiler도 같은 fake store를 참조하도록 교체
    from app.services.semantic_compiler import SemanticCompiler
    sc_module._compiler = SemanticCompiler(fake)
    yield fake


# ========================================
# 별칭 그룹 테스트
# ========================================

@pytest.mark.asyncio
async def test_create_alias_group(ac):
    """별칭 그룹을 정상적으로 생성한다"""
    resp = await ac.post(f"{BASE}/ontology/alias-groups", json={
        "id": "ag-001",
        "canonical_term_id": "term-active-customer",
        "group_name": "활성 고객 별칭",
        "language_code": "ko",
        "domain_id": "crm",
    }, headers=AUTH)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["id"] == "ag-001"
    assert body["data"]["group_name"] == "활성 고객 별칭"
    assert body["data"]["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_create_alias_group_duplicate(ac, _inject_fake_store):
    """중복 별칭 그룹 생성 시 400 에러를 반환한다"""
    fake = _inject_fake_store
    fake.create_alias_group("system", {
        "id": "ag-dup", "canonical_term_id": "t1",
        "group_name": "중복", "domain_id": "global",
    })
    resp = await ac.post(f"{BASE}/ontology/alias-groups", json={
        "id": "ag-dup", "canonical_term_id": "t2",
        "group_name": "중복2",
    }, headers=AUTH)
    assert resp.status_code == 400
    assert "이미 존재" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_alias_groups(ac, _inject_fake_store):
    """별칭 그룹 목록을 조회하고 도메인 필터를 적용한다"""
    fake = _inject_fake_store
    fake.create_alias_group("system", {"id": "ag-1", "canonical_term_id": "t1", "group_name": "G1", "domain_id": "crm"})
    fake.create_alias_group("system", {"id": "ag-2", "canonical_term_id": "t2", "group_name": "G2", "domain_id": "hr"})
    # 전체 조회
    resp = await ac.get(f"{BASE}/ontology/alias-groups", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["count"] == 2
    # 도메인 필터
    resp = await ac.get(f"{BASE}/ontology/alias-groups?domain_id=crm", headers=AUTH)
    assert resp.json()["count"] == 1
    assert resp.json()["data"][0]["id"] == "ag-1"


# ========================================
# 확장 규칙 테스트
# ========================================

@pytest.mark.asyncio
async def test_expansion_rule_crud_and_lifecycle(ac, _inject_fake_store):
    """확장 규칙의 CRUD + activate/deprecate 라이프사이클을 검증한다"""
    fake = _inject_fake_store
    # 선행: 별칭 그룹 생성
    fake.create_alias_group("system", {"id": "ag-x", "canonical_term_id": "t1", "group_name": "테스트"})

    # 1) 생성
    resp = await ac.post(f"{BASE}/ontology/expansion-rules", json={
        "id": "er-001",
        "alias_group_id": "ag-x",
        "rule_type": "EXACT",
        "match_pattern": "활성고객",
        "boost": 1.5,
        "priority": 200,
    }, headers=AUTH)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["rule_type"] == "EXACT"
    assert data["status"] == "ACTIVE"

    # 2) 목록 조회
    resp = await ac.get(f"{BASE}/ontology/expansion-rules?alias_group_id=ag-x", headers=AUTH)
    assert resp.json()["count"] == 1

    # 3) 수정
    resp = await ac.patch(f"{BASE}/ontology/expansion-rules/er-001", json={
        "boost": 2.0,
    }, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["boost"] == 2.0

    # 4) 비활성화
    resp = await ac.post(f"{BASE}/ontology/expansion-rules/er-001/deprecate", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "DEPRECATED"

    # 5) 재활성화
    resp = await ac.post(f"{BASE}/ontology/expansion-rules/er-001/activate", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_expansion_rule_missing_group(ac):
    """존재하지 않는 별칭 그룹으로 확장 규칙 생성 시 404 에러"""
    resp = await ac.post(f"{BASE}/ontology/expansion-rules", json={
        "id": "er-bad",
        "alias_group_id": "nonexistent",
        "rule_type": "EXACT",
        "match_pattern": "테스트",
    }, headers=AUTH)
    assert resp.status_code == 404
    assert "찾을 수 없습니다" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_expansion_rule_invalid_type(ac, _inject_fake_store):
    """유효하지 않은 rule_type으로 생성 시 400 에러"""
    fake = _inject_fake_store
    fake.create_alias_group("system", {"id": "ag-v", "canonical_term_id": "t1", "group_name": "V"})
    resp = await ac.post(f"{BASE}/ontology/expansion-rules", json={
        "id": "er-bad-type",
        "alias_group_id": "ag-v",
        "rule_type": "INVALID_TYPE",
        "match_pattern": "테스트",
    }, headers=AUTH)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_expansion_rule_filter_by_status(ac, _inject_fake_store):
    """확장 규칙을 상태별로 필터링한다"""
    fake = _inject_fake_store
    fake.create_alias_group("system", {"id": "ag-f", "canonical_term_id": "t1", "group_name": "F"})
    fake.create_expansion_rule("system", {
        "id": "er-active", "alias_group_id": "ag-f",
        "rule_type": "EXACT", "match_pattern": "활성", "status": "ACTIVE",
    })
    fake.create_expansion_rule("system", {
        "id": "er-dep", "alias_group_id": "ag-f",
        "rule_type": "REGEX", "match_pattern": ".*", "status": "DEPRECATED",
    })
    resp = await ac.get(f"{BASE}/ontology/expansion-rules?status=ACTIVE", headers=AUTH)
    assert resp.json()["count"] == 1
    assert resp.json()["data"][0]["id"] == "er-active"


# ========================================
# 의도 모델 테스트
# ========================================

@pytest.mark.asyncio
async def test_intent_model_crud(ac):
    """의도 분류 모델 등록과 목록 조회를 검증한다"""
    # 생성
    resp = await ac.post(f"{BASE}/runtime/intent-models", json={
        "id": "im-001",
        "model_key": "intent_classifier_v2",
        "model_version": "2.1.0",
        "model_type": "keyword",
        "config_json": {"threshold": 0.7},
    }, headers=AUTH)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["model_key"] == "intent_classifier_v2"
    assert data["model_type"] == "keyword"

    # 목록
    resp = await ac.get(f"{BASE}/runtime/intent-models", headers=AUTH)
    assert resp.json()["count"] == 1


@pytest.mark.asyncio
async def test_intent_model_invalid_type(ac):
    """유효하지 않은 model_type으로 생성 시 400 에러"""
    resp = await ac.post(f"{BASE}/runtime/intent-models", json={
        "id": "im-bad",
        "model_key": "bad",
        "model_version": "1.0",
        "model_type": "invalid_type",
    }, headers=AUTH)
    assert resp.status_code == 400


# ========================================
# 추론 로그 테스트
# ========================================

@pytest.mark.asyncio
async def test_inference_log_creation(ac):
    """추론 로그를 기록하고 조회한다"""
    # 생성
    resp = await ac.post(f"{BASE}/runtime/inference-logs", json={
        "id": "il-001",
        "request_id": "req-abc-123",
        "user_question": "지난 달 활성 고객 수는?",
        "normalized_question": "지난달 활성고객수",
        "top_intent": "kpi_query",
        "confidence": 0.92,
        "ambiguity_score": 0.15,
        "feature_json": {"tokens": ["활성", "고객", "수"]},
        "candidate_json": {"kpi_query": 0.92, "trend": 0.05},
    }, headers=AUTH)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["request_id"] == "req-abc-123"
    assert data["top_intent"] == "kpi_query"

    # 목록
    resp = await ac.get(f"{BASE}/runtime/inference-logs", headers=AUTH)
    assert resp.json()["count"] == 1


# ========================================
# 질문 피드백 테스트
# ========================================

@pytest.mark.asyncio
async def test_question_feedback_crud_and_resolve(ac):
    """피드백 CRUD + 해결 완료 전환을 검증한다"""
    # 1) 생성
    resp = await ac.post(f"{BASE}/runtime/question-feedback", json={
        "id": "fb-001",
        "request_id": "req-abc-123",
        "issue_type": "wrong_intent",
        "expected_intent": "trend",
        "feedback_note": "실제로는 추세 질문이었음",
    }, headers=AUTH)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["issue_type"] == "wrong_intent"
    assert data["resolved"] is False

    # 2) 미해결 목록
    resp = await ac.get(f"{BASE}/runtime/question-feedback?resolved=false", headers=AUTH)
    assert resp.json()["count"] == 1

    # 3) 해결 완료
    resp = await ac.post(f"{BASE}/runtime/question-feedback/fb-001/resolve", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["data"]["resolved"] is True

    # 4) 해결 후 미해결 목록 비어 있음
    resp = await ac.get(f"{BASE}/runtime/question-feedback?resolved=false", headers=AUTH)
    assert resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_question_feedback_invalid_issue_type(ac):
    """유효하지 않은 issue_type으로 피드백 생성 시 400 에러"""
    resp = await ac.post(f"{BASE}/runtime/question-feedback", json={
        "id": "fb-bad",
        "request_id": "req-xxx",
        "issue_type": "invalid_issue",
    }, headers=AUTH)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_resolve_nonexistent_feedback(ac):
    """존재하지 않는 피드백 해결 시 404 에러"""
    resp = await ac.post(f"{BASE}/runtime/question-feedback/nonexistent/resolve", headers=AUTH)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_with_filters(ac, _inject_fake_store):
    """여러 필터 조합으로 목록 조회가 정상 동작하는지 검증한다"""
    fake = _inject_fake_store

    # 별칭 그룹 + 확장 규칙 with 다양한 도메인
    fake.create_alias_group("system", {"id": "ag-a", "canonical_term_id": "t1", "group_name": "A", "domain_id": "sales"})
    fake.create_alias_group("system", {"id": "ag-b", "canonical_term_id": "t2", "group_name": "B", "domain_id": "hr"})
    fake.create_alias_group("system", {"id": "ag-c", "canonical_term_id": "t3", "group_name": "C", "domain_id": "sales", "status": "DEPRECATED"})

    # 의도 모델 다수 등록
    fake.create_intent_model("system", {"id": "im-a", "model_key": "k1", "model_version": "1.0", "model_type": "keyword", "status": "ACTIVE"})
    fake.create_intent_model("system", {"id": "im-b", "model_key": "k2", "model_version": "1.0", "model_type": "llm", "status": "ACTIVE"})

    # 피드백 resolved/unresolved 혼합
    fake.create_question_feedback("system", {"id": "fb-1", "request_id": "r1", "issue_type": "wrong_intent"})
    fake.create_question_feedback("system", {"id": "fb-2", "request_id": "r2", "issue_type": "missing_synonym"})
    fake.resolve_feedback("system", "fb-2")

    # 별칭 그룹: 도메인 sales + ACTIVE만
    resp = await ac.get(f"{BASE}/ontology/alias-groups?domain_id=sales&status=ACTIVE", headers=AUTH)
    assert resp.json()["count"] == 1
    assert resp.json()["data"][0]["id"] == "ag-a"

    # 의도 모델: 상태 필터
    resp = await ac.get(f"{BASE}/runtime/intent-models?status=ACTIVE", headers=AUTH)
    assert resp.json()["count"] == 2

    # 피드백: resolved=true
    resp = await ac.get(f"{BASE}/runtime/question-feedback?resolved=true", headers=AUTH)
    assert resp.json()["count"] == 1
    assert resp.json()["data"][0]["id"] == "fb-2"
