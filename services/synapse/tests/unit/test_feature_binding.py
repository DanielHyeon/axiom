"""
P3 §5.3: ML/Feature Source 바인딩 단위 테스트

feature_source 엔티티의 feature_config, 학습 쿼리 생성,
BI-ML 일관성 검증 API를 FakeStore 기반으로 검증한다.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api import semantic_contract as sc_module

AUTH = {"Authorization": "Bearer local-oracle-token"}


# ── FakeStore 확장: feature binding 메서드 포함 ──

class FakeFeatureStore:
    """feature binding 테스트용 인메모리 저장소

    기존 FakeSemanticStore에 P3 §5.3 메서드를 추가한 경량 버전.
    """

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

    # ── 엔티티 CRUD ──

    def create_entity(self, tenant_id, data):
        eid = data["entity_id"]
        if eid in self.entities:
            raise ValueError(f"entity_id '{eid}'가 이미 존재합니다")
        etype = data.get("entity_type", "fact")
        # feature_config 타입 제약
        feature_config = data.get("feature_config")
        if feature_config and etype != "feature_source":
            raise ValueError("feature_config는 entity_type='feature_source'일 때만 설정할 수 있습니다")
        row = {
            **data,
            "tenant_id": tenant_id,
            "entity_type": etype,
            "status": "draft",
            "version": 1,
            "created_at": "2026-03-23T00:00:00",
        }
        self.entities[eid] = row
        return row

    def get_entity(self, tenant_id, entity_id):
        e = self.entities.get(entity_id)
        return e if e and e.get("tenant_id") == tenant_id else None

    def list_entities(self, tenant_id, case_id=None, domain_id=None, limit=100, offset=0):
        result = [e for e in self.entities.values() if e["tenant_id"] == tenant_id]
        if case_id:
            result = [e for e in result if e.get("case_id") == case_id]
        return result[offset:offset + limit]

    def update_entity(self, tenant_id, entity_id, data):
        e = self.get_entity(tenant_id, entity_id)
        if not e:
            raise KeyError(f"entity_id '{entity_id}'를 찾을 수 없습니다")
        # feature_config 타입 제약
        if "feature_config" in data and data["feature_config"] is not None:
            effective_type = data.get("entity_type", e.get("entity_type"))
            if effective_type != "feature_source":
                raise ValueError("feature_config는 entity_type='feature_source'일 때만 설정할 수 있습니다")
        e.update({k: v for k, v in data.items() if v is not None})
        e["version"] = e.get("version", 1) + 1
        return e

    # ── 지표 CRUD ──

    def create_measure(self, tenant_id, data):
        mid = data["measure_id"]
        if mid in self.measures:
            raise ValueError(f"measure_id '{mid}'가 이미 존재합니다")
        if not self.get_entity(tenant_id, data["entity_id"]):
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        row = {**data, "tenant_id": tenant_id, "status": "draft", "version": 1}
        self.measures[mid] = row
        return row

    def list_measures(self, tenant_id, case_id=None, entity_id=None, limit=100, offset=0):
        result = [m for m in self.measures.values() if m["tenant_id"] == tenant_id]
        if case_id:
            result = [m for m in result if m.get("case_id") == case_id]
        if entity_id:
            result = [m for m in result if m.get("entity_id") == entity_id]
        return result[offset:offset + limit]

    # ── P3 §5.3 Feature Binding ──

    def list_feature_sources(self, tenant_id, case_id=None, limit=100, offset=0):
        """feature_source 타입 엔티티만 조회"""
        result = [
            e for e in self.entities.values()
            if e["tenant_id"] == tenant_id and e.get("entity_type") == "feature_source"
        ]
        if case_id:
            result = [e for e in result if e.get("case_id") == case_id]
        return result[offset:offset + limit]

    def generate_training_query(self, tenant_id, entity_id, columns=None, date_range=None):
        """학습 SQL 생성"""
        entity = self.get_entity(tenant_id, entity_id)
        if not entity:
            raise KeyError(f"entity_id '{entity_id}'를 찾을 수 없습니다")
        if entity.get("entity_type") != "feature_source":
            raise ValueError(f"entity_id '{entity_id}'의 타입이 feature_source가 아닙니다")
        fc = entity.get("feature_config") or {}
        if not fc:
            raise ValueError(f"entity_id '{entity_id}'에 feature_config가 설정되지 않았습니다")

        use_columns = columns or fc.get("feature_columns") or ["*"]
        col_str = ", ".join(use_columns)
        source = entity.get("physical_source_ref", "UNKNOWN_SOURCE")

        date_filter = "1=1"
        if date_range:
            start = date_range.get("start")
            end = date_range.get("end")
            if start and end:
                date_filter = f"created_at >= '{start}' AND created_at <= '{end}'"
            elif start:
                date_filter = f"created_at >= '{start}'"
            elif end:
                date_filter = f"created_at <= '{end}'"

        template = fc.get(
            "training_query_template",
            "SELECT {columns} FROM {entity_source} WHERE {date_filter}",
        )
        sql = template.format(columns=col_str, entity_source=source, date_filter=date_filter)

        return {
            "sql": sql,
            "entity_id": entity_id,
            "columns": use_columns,
            "source": source,
            "date_range": date_range,
        }

    def check_feature_consistency(self, tenant_id, entity_id):
        """BI-ML 일관성 검증"""
        entity = self.get_entity(tenant_id, entity_id)
        if not entity:
            raise KeyError(f"entity_id '{entity_id}'를 찾을 수 없습니다")
        if entity.get("entity_type") != "feature_source":
            raise ValueError(f"entity_id '{entity_id}'의 타입이 feature_source가 아닙니다")

        feature_measures = self.list_measures(tenant_id, entity_id=entity_id)
        all_measures = self.list_measures(tenant_id, limit=500)

        # BI(fact) 지표를 이름으로 매핑
        bi_by_name: dict[str, dict] = {}
        for m in all_measures:
            if m.get("entity_id") == entity_id:
                continue
            mname = m.get("name", "")
            if mname and mname not in bi_by_name:
                bi_by_name[mname] = m

        mismatches = []
        matched = 0
        for fm in feature_measures:
            fname = fm.get("name", "")
            if fname in bi_by_name:
                bi_m = bi_by_name[fname]
                f_sql = (fm.get("sql_expression") or "").strip()
                b_sql = (bi_m.get("sql_expression") or "").strip()
                if f_sql == b_sql:
                    matched += 1
                else:
                    mismatches.append({
                        "measure_name": fname,
                        "feature_measure_id": fm.get("measure_id"),
                        "bi_measure_id": bi_m.get("measure_id"),
                        "feature_sql": f_sql,
                        "bi_sql": b_sql,
                    })

        return {
            "entity_id": entity_id,
            "consistent": len(mismatches) == 0,
            "total_feature_measures": len(feature_measures),
            "matched": matched,
            "mismatches": mismatches,
        }

    # ── 나머지 stub (라우터가 참조하는 것만) ──

    def get_concept(self, *a, **kw):
        return None
    def list_concepts(self, *a, **kw):
        return []
    def create_concept(self, *a, **kw):
        return {}
    def update_concept(self, *a, **kw):
        return {}
    def change_concept_status(self, *a, **kw):
        return {}
    def create_term(self, *a, **kw):
        return {}
    def create_terms_bulk(self, *a, **kw):
        return []
    def search_terms(self, *a, **kw):
        return []
    def list_terms_by_concept(self, *a, **kw):
        return []
    def get_measure(self, *a, **kw):
        return None
    def update_measure(self, *a, **kw):
        return {}
    def create_dimension(self, *a, **kw):
        return {}
    def get_dimension(self, *a, **kw):
        return None
    def list_dimensions(self, *a, **kw):
        return []
    def update_dimension(self, *a, **kw):
        return {}
    def create_join_contract(self, *a, **kw):
        return {}
    def get_join_contract(self, *a, **kw):
        return None
    def list_join_contracts(self, *a, **kw):
        return []
    def update_join_contract(self, *a, **kw):
        return {}
    def create_quality_contract(self, *a, **kw):
        return {}
    def list_quality_contracts(self, *a, **kw):
        return []
    def create_grain_contract(self, *a, **kw):
        return {}
    def get_grain_contract(self, *a, **kw):
        return None
    def list_grain_contracts(self, *a, **kw):
        return []
    def update_grain_contract(self, *a, **kw):
        return {}
    def publish(self, *a, **kw):
        return {}
    def list_releases(self, *a, **kw):
        return []
    def get_catalog(self, *a, **kw):
        return {}
    def get_ai_context(self, *a, **kw):
        return {}
    def create_context_pack(self, *a, **kw):
        return {}
    def get_context_pack(self, *a, **kw):
        return None
    def list_context_packs(self, *a, **kw):
        return []
    def update_context_pack(self, *a, **kw):
        return {}
    def delete_context_pack(self, *a, **kw):
        return False
    def resolve_context_pack(self, *a, **kw):
        return {}
    def create_prompt_policy(self, *a, **kw):
        return {}
    def list_prompt_policies(self, *a, **kw):
        return []
    def delete_prompt_policy(self, *a, **kw):
        return False
    def detect_conflicts(self, *a, **kw):
        return {}
    def analyze_impact(self, *a, **kw):
        return {}


# ── Fixtures ──

@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def _inject_fake(request):
    """테스트마다 FakeFeatureStore 주입 → 격리"""
    fake = FakeFeatureStore()
    sc_module._store = fake
    from app.services.semantic_compiler import SemanticCompiler
    sc_module._compiler = SemanticCompiler(fake)
    return fake


# ========================================
# feature_config 엔티티 생성/수정 테스트
# ========================================

@pytest.mark.asyncio
async def test_create_entity_with_feature_config(ac, _inject_fake):
    """feature_source 타입 엔티티에 feature_config를 설정할 수 있다."""
    resp = await ac.post("/api/v3/synapse/semantic/entities", json={
        "entity_id": "ml_customer_features",
        "physical_source_ref": "ml.customer_features",
        "entity_type": "feature_source",
        "feature_config": {
            "online_source": "redis://features:6379/ml_features",
            "offline_source": "s3://axiom-features/customer/",
            "serving_latency_sla_ms": 50,
            "feature_freshness_hours": 24,
            "feature_columns": ["customer_ltv", "churn_probability", "segment_id"],
            "training_query_template": "SELECT {columns} FROM {entity_source} WHERE {date_filter}",
        },
    }, headers=AUTH)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["entity_type"] == "feature_source"


@pytest.mark.asyncio
async def test_feature_config_only_for_feature_source(ac, _inject_fake):
    """fact 타입 엔티티에 feature_config를 설정하면 400 에러가 발생한다."""
    resp = await ac.post("/api/v3/synapse/semantic/entities", json={
        "entity_id": "regular_fact",
        "physical_source_ref": "dw.sales",
        "entity_type": "fact",
        "feature_config": {"feature_columns": ["amount"]},
    }, headers=AUTH)
    assert resp.status_code == 400
    assert "feature_source" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_feature_config(ac, _inject_fake):
    """feature_source 엔티티의 feature_config를 업데이트할 수 있다."""
    fake = _inject_fake
    fake.create_entity("system", {
        "entity_id": "feat_01",
        "physical_source_ref": "ml.features",
        "entity_type": "feature_source",
        "feature_config": {"feature_columns": ["col_a"]},
        "case_id": "",
    })
    resp = await ac.put("/api/v3/synapse/semantic/entities/feat_01", json={
        "feature_config": {"feature_columns": ["col_a", "col_b"], "serving_latency_sla_ms": 100},
    }, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "col_b" in data["feature_config"]["feature_columns"]
    assert data["version"] == 2


# ========================================
# feature source 목록 조회 테스트
# ========================================

@pytest.mark.asyncio
async def test_list_feature_sources(ac, _inject_fake):
    """feature_source 타입 엔티티만 조회된다."""
    fake = _inject_fake
    # feature_source 2개 + fact 1개 생성
    fake.create_entity("system", {
        "entity_id": "fs_1", "physical_source_ref": "ml.a",
        "entity_type": "feature_source", "case_id": "",
    })
    fake.create_entity("system", {
        "entity_id": "fs_2", "physical_source_ref": "ml.b",
        "entity_type": "feature_source", "case_id": "",
    })
    fake.create_entity("system", {
        "entity_id": "fact_1", "physical_source_ref": "dw.sales",
        "entity_type": "fact", "case_id": "",
    })
    resp = await ac.get("/api/v3/synapse/semantic/features", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    entity_ids = {e["entity_id"] for e in body["data"]}
    assert "fs_1" in entity_ids
    assert "fs_2" in entity_ids
    assert "fact_1" not in entity_ids


# ========================================
# 학습 쿼리 생성 테스트
# ========================================

@pytest.mark.asyncio
async def test_generate_training_query(ac, _inject_fake):
    """feature_source 엔티티에서 학습 SQL이 생성된다."""
    fake = _inject_fake
    fake.create_entity("system", {
        "entity_id": "fs_train", "physical_source_ref": "ml.customer_features",
        "entity_type": "feature_source", "case_id": "",
        "feature_config": {
            "feature_columns": ["customer_ltv", "churn_probability"],
            "training_query_template": "SELECT {columns} FROM {entity_source} WHERE {date_filter}",
        },
    })
    resp = await ac.post("/api/v3/synapse/semantic/features/training-query", json={
        "entity_id": "fs_train",
    }, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "customer_ltv" in data["sql"]
    assert "churn_probability" in data["sql"]
    assert data["source"] == "ml.customer_features"
    assert data["columns"] == ["customer_ltv", "churn_probability"]


@pytest.mark.asyncio
async def test_training_query_with_date_range(ac, _inject_fake):
    """날짜 범위 지정 시 WHERE 조건에 날짜 필터가 포함된다."""
    fake = _inject_fake
    fake.create_entity("system", {
        "entity_id": "fs_dr", "physical_source_ref": "ml.features",
        "entity_type": "feature_source", "case_id": "",
        "feature_config": {
            "feature_columns": ["score"],
        },
    })
    resp = await ac.post("/api/v3/synapse/semantic/features/training-query", json={
        "entity_id": "fs_dr",
        "date_range": {"start": "2025-01-01", "end": "2025-12-31"},
    }, headers=AUTH)
    assert resp.status_code == 200
    sql = resp.json()["data"]["sql"]
    assert "2025-01-01" in sql
    assert "2025-12-31" in sql


@pytest.mark.asyncio
async def test_training_query_custom_columns(ac, _inject_fake):
    """사용자 지정 컬럼이 feature_columns보다 우선한다."""
    fake = _inject_fake
    fake.create_entity("system", {
        "entity_id": "fs_cc", "physical_source_ref": "ml.features",
        "entity_type": "feature_source", "case_id": "",
        "feature_config": {"feature_columns": ["col_a", "col_b"]},
    })
    resp = await ac.post("/api/v3/synapse/semantic/features/training-query", json={
        "entity_id": "fs_cc",
        "columns": ["only_this"],
    }, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["columns"] == ["only_this"]
    assert "only_this" in data["sql"]
    assert "col_a" not in data["sql"]


@pytest.mark.asyncio
async def test_training_query_non_feature_source(ac, _inject_fake):
    """fact 타입 엔티티로 학습 쿼리를 요청하면 400 에러"""
    fake = _inject_fake
    fake.create_entity("system", {
        "entity_id": "fact_nf", "physical_source_ref": "dw.sales",
        "entity_type": "fact", "case_id": "",
    })
    resp = await ac.post("/api/v3/synapse/semantic/features/training-query", json={
        "entity_id": "fact_nf",
    }, headers=AUTH)
    assert resp.status_code == 400
    assert "feature_source" in resp.json()["detail"]


# ========================================
# BI-ML 일관성 검증 테스트
# ========================================

@pytest.mark.asyncio
async def test_feature_consistency_check_match(ac, _inject_fake):
    """동일한 sql_expression을 가진 지표는 consistent=True"""
    fake = _inject_fake
    # fact 엔티티 + 동일 이름 지표
    fake.create_entity("system", {
        "entity_id": "fact_bi", "physical_source_ref": "dw.sales",
        "entity_type": "fact", "case_id": "",
    })
    fake.create_measure("system", {
        "measure_id": "bi_revenue", "entity_id": "fact_bi",
        "name": "revenue", "sql_expression": "SUM(amount)",
        "case_id": "",
    })
    # feature_source 엔티티 + 동일 sql_expression
    fake.create_entity("system", {
        "entity_id": "fs_con", "physical_source_ref": "ml.features",
        "entity_type": "feature_source", "case_id": "",
        "feature_config": {"feature_columns": ["revenue"]},
    })
    fake.create_measure("system", {
        "measure_id": "ml_revenue", "entity_id": "fs_con",
        "name": "revenue", "sql_expression": "SUM(amount)",
        "case_id": "",
    })
    resp = await ac.get("/api/v3/synapse/semantic/features/fs_con/consistency", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["consistent"] is True
    assert data["matched"] == 1
    assert len(data["mismatches"]) == 0


@pytest.mark.asyncio
async def test_feature_consistency_check_mismatch(ac, _inject_fake):
    """다른 sql_expression을 가진 지표는 consistent=False + 불일치 상세"""
    fake = _inject_fake
    fake.create_entity("system", {
        "entity_id": "fact_mm", "physical_source_ref": "dw.sales",
        "entity_type": "fact", "case_id": "",
    })
    fake.create_measure("system", {
        "measure_id": "bi_rev", "entity_id": "fact_mm",
        "name": "revenue", "sql_expression": "SUM(amount)",
        "case_id": "",
    })
    fake.create_entity("system", {
        "entity_id": "fs_mm", "physical_source_ref": "ml.features",
        "entity_type": "feature_source", "case_id": "",
        "feature_config": {"feature_columns": ["revenue"]},
    })
    fake.create_measure("system", {
        "measure_id": "ml_rev", "entity_id": "fs_mm",
        "name": "revenue", "sql_expression": "SUM(net_amount)",
        "case_id": "",
    })
    resp = await ac.get("/api/v3/synapse/semantic/features/fs_mm/consistency", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["consistent"] is False
    assert len(data["mismatches"]) == 1
    mm = data["mismatches"][0]
    assert mm["measure_name"] == "revenue"
    assert mm["feature_sql"] == "SUM(net_amount)"
    assert mm["bi_sql"] == "SUM(amount)"
