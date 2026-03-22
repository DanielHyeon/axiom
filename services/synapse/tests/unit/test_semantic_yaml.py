"""
시멘틱 계약 YAML Export/Import 단위 테스트

P3 §5.4: Metrics as Code — YAML 기반 직렬화/역직렬화 검증.
FakeStore를 사용하여 PostgreSQL 없이 동작한다.
"""
import pytest
import yaml

# FakeStore를 기존 테스트에서 재사용 — 동일 패턴
import sys
import os

# 서비스 루트를 path에 추가 (import 해결)
_SERVICE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _SERVICE_ROOT not in sys.path:
    sys.path.insert(0, _SERVICE_ROOT)

from app.services.semantic_yaml import (
    SemanticYamlExporter,
    SemanticYamlImporter,
    SemanticYamlValidator,
)


# ── FakeStore: PostgreSQL 없이 동작하는 인메모리 저장소 ──

class FakeSemanticStore:
    """시멘틱 계약 인메모리 Fake — YAML 테스트용"""

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
        self._term_seq = 0

    def ensure_schema(self):
        pass

    # 개념 CRUD
    def create_concept(self, tenant_id, data):
        cid = data["concept_id"]
        if cid in self.concepts:
            raise ValueError(f"concept_id '{cid}'가 이미 존재합니다")
        row = {**data, "tenant_id": tenant_id, "version": 1,
               "status": data.get("status", "draft"),
               "created_at": "2026-03-23T00:00:00", "updated_at": "2026-03-23T00:00:00"}
        self.concepts[cid] = row
        return row

    def get_concept(self, tenant_id, concept_id):
        c = self.concepts.get(concept_id)
        return c if c and c.get("tenant_id") == tenant_id else None

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

    # 용어
    def create_term(self, tenant_id, data):
        if not self.get_concept(tenant_id, data["concept_id"]):
            raise KeyError(f"concept_id '{data['concept_id']}'를 찾을 수 없습니다")
        self._term_seq += 1
        row = {**data, "term_id": self._term_seq, "tenant_id": tenant_id,
               "created_at": "2026-03-23T00:00:00"}
        self.terms.append(row)
        return row

    def create_terms_bulk(self, tenant_id, terms):
        return [self.create_term(tenant_id, t) for t in terms]

    def list_terms_by_concept(self, tenant_id, concept_id):
        return [t for t in self.terms
                if t["tenant_id"] == tenant_id and t["concept_id"] == concept_id]

    # 엔티티
    def create_entity(self, tenant_id, data):
        eid = data["entity_id"]
        if eid in self.entities:
            raise ValueError(f"entity_id '{eid}'가 이미 존재합니다")
        row = {**data, "tenant_id": tenant_id, "status": "draft", "version": 1,
               "created_at": "2026-03-23T00:00:00"}
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
        row = {**data, "tenant_id": tenant_id, "status": "draft", "version": 1,
               "created_at": "2026-03-23T00:00:00"}
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
        row = {**data, "tenant_id": tenant_id, "status": "draft", "version": 1,
               "created_at": "2026-03-23T00:00:00"}
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
        row = {**data, "tenant_id": tenant_id, "status": "draft",
               "created_at": "2026-03-23T00:00:00"}
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
        row = {**data, "tenant_id": tenant_id, "created_at": "2026-03-23T00:00:00"}
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
        row = {**data, "tenant_id": tenant_id, "version": 1,
               "created_at": "2026-03-23T00:00:00"}
        self.grains[gid] = row
        return row

    def get_grain_contract(self, tenant_id, grain_id):
        g = self.grains.get(grain_id)
        return g if g and g.get("tenant_id") == grain_id else None

    def list_grain_contracts(self, tenant_id, case_id=None, entity_id=None, limit=100, offset=0):
        result = [g for g in self.grains.values() if g["tenant_id"] == tenant_id]
        if case_id:
            result = [g for g in result if g.get("case_id") == case_id]
        if entity_id:
            result = [g for g in result if g.get("entity_id") == entity_id]
        return result[offset:offset + limit]

    def update_grain_contract(self, tenant_id, grain_id, data):
        g = self.grains.get(grain_id)
        if not g or g.get("tenant_id") != tenant_id:
            raise KeyError(f"grain_id '{grain_id}'를 찾을 수 없습니다")
        g.update({k: v for k, v in data.items() if v is not None})
        return g

    # 컨텍스트 팩
    def create_context_pack(self, tenant_id, data):
        cpid = data["context_pack_id"]
        if cpid in self.context_packs:
            raise ValueError(f"context_pack_id '{cpid}'가 이미 존재합니다")
        row = {**data, "tenant_id": tenant_id, "version": 1,
               "created_at": "2026-03-23T00:00:00", "updated_at": "2026-03-23T00:00:00"}
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


# ── 공통 fixture ──

TENANT = "test-tenant"


@pytest.fixture
def store():
    """깨끗한 FakeStore를 반환한다."""
    return FakeSemanticStore()


@pytest.fixture
def exporter(store):
    return SemanticYamlExporter(store)


@pytest.fixture
def importer(store):
    return SemanticYamlImporter(store)


@pytest.fixture
def validator():
    return SemanticYamlValidator()


def _seed_concept(store, concept_id="concept.test", name_ko="테스트 개념"):
    """테스트용 개념을 등록한다."""
    store.create_concept(TENANT, {
        "concept_id": concept_id,
        "case_id": "case-1",
        "domain_id": "sales",
        "name_ko": name_ko,
        "name_en": "Test Concept",
        "business_definition": "테스트 목적의 개념",
        "status": "approved",
        "owner_team": "data-eng",
    })


def _seed_entity(store, entity_id="mart_test", physical_source="mart.test_table"):
    """테스트용 엔티티를 등록한다."""
    store.create_entity(TENANT, {
        "entity_id": entity_id,
        "physical_source_ref": physical_source,
        "entity_type": "fact",
        "case_id": "case-1",
    })


def _seed_measure(store, measure_id="measure_test", entity_id="mart_test"):
    """테스트용 지표를 등록한다."""
    store.create_measure(TENANT, {
        "measure_id": measure_id,
        "entity_id": entity_id,
        "name": "Test Measure",
        "sql_expression": "SUM(amount)",
        "measure_type": "sum",
        "case_id": "case-1",
    })


# ========================================
# 테스트 케이스
# ========================================


class TestExportEmptyCatalog:
    """빈 카탈로그 내보내기"""

    def test_export_empty_catalog(self, exporter):
        """데이터가 없는 카탈로그를 내보내면 기본 헤더만 있는 YAML이 생성된다."""
        result = exporter.export(TENANT)
        assert "axiom_semantic_version" in result
        assert "1.0" in result
        # 빈 카탈로그이므로 concepts/entities 등의 섹션이 없어야 함
        parsed = yaml.safe_load(result)
        assert parsed["axiom_semantic_version"] == "1.0"
        assert "concepts" not in parsed
        assert "entities" not in parsed


class TestExportWithConceptsAndMeasures:
    """개념과 지표가 있는 카탈로그 내보내기"""

    def test_export_with_concepts_and_measures(self, store, exporter):
        """개념 + 엔티티 + 지표가 있는 카탈로그를 올바르게 내보낸다."""
        _seed_concept(store)
        _seed_entity(store)
        _seed_measure(store)

        result = exporter.export(TENANT)
        parsed = yaml.safe_load(result)

        assert len(parsed["concepts"]) == 1
        assert parsed["concepts"][0]["concept_id"] == "concept.test"
        assert parsed["concepts"][0]["name_ko"] == "테스트 개념"

        assert len(parsed["entities"]) == 1
        assert parsed["entities"][0]["entity_id"] == "mart_test"

        assert len(parsed["measures"]) == 1
        assert parsed["measures"][0]["measure_id"] == "measure_test"
        assert parsed["measures"][0]["sql_expression"] == "SUM(amount)"


class TestExportIncludesTerms:
    """내보내기에 용어가 포함되는지 검증"""

    def test_export_includes_terms(self, store, exporter):
        """개념에 바인딩된 용어가 YAML에 포함된다."""
        _seed_concept(store)
        store.create_terms_bulk(TENANT, [
            {"concept_id": "concept.test", "surface_form": "테스트개념",
             "language": "ko", "term_type": "primary"},
            {"concept_id": "concept.test", "surface_form": "test concept",
             "language": "en", "term_type": "synonym"},
        ])

        result = exporter.export(TENANT)
        parsed = yaml.safe_load(result)

        concept = parsed["concepts"][0]
        assert "terms" in concept
        assert len(concept["terms"]) == 2
        forms = {t["surface_form"] for t in concept["terms"]}
        assert "테스트개념" in forms
        assert "test concept" in forms


class TestImportCreatesNewConcepts:
    """새로운 개념 import"""

    def test_import_creates_new_concepts(self, store, importer):
        """YAML에서 새 개념을 가져오면 store에 생성된다."""
        yaml_content = yaml.dump({
            "axiom_semantic_version": "1.0",
            "concepts": [
                {
                    "concept_id": "new.concept",
                    "name_ko": "새 개념",
                    "name_en": "New Concept",
                    "domain_id": "analytics",
                    "status": "draft",
                }
            ],
        })

        result = importer.import_yaml(TENANT, yaml_content, case_id="case-1")

        assert result["errors"] == []
        assert result["created"]["concepts"] == 1
        # store에 실제 생성 확인
        concept = store.get_concept(TENANT, "new.concept")
        assert concept is not None
        assert concept["name_ko"] == "새 개념"


class TestImportUpdatesExisting:
    """기존 엔티티 업데이트"""

    def test_import_updates_existing(self, store, importer):
        """이미 존재하는 엔티티의 필드를 YAML import로 업데이트한다."""
        _seed_entity(store)
        original = store.get_entity(TENANT, "mart_test")
        assert original["physical_source_ref"] == "mart.test_table"

        yaml_content = yaml.dump({
            "axiom_semantic_version": "1.0",
            "entities": [
                {
                    "entity_id": "mart_test",
                    "physical_source_ref": "mart.updated_table",
                    "entity_type": "dimension",
                }
            ],
        })

        result = importer.import_yaml(TENANT, yaml_content, case_id="case-1")

        assert result["errors"] == []
        assert result["updated"]["entities"] == 1
        updated = store.get_entity(TENANT, "mart_test")
        assert updated["physical_source_ref"] == "mart.updated_table"
        assert updated["entity_type"] == "dimension"


class TestImportDryRunNoChanges:
    """dry_run 모드에서 DB 변경 없음"""

    def test_import_dry_run_no_changes(self, store, importer):
        """dry_run=True이면 검증만 하고 DB에 아무것도 생성하지 않는다."""
        yaml_content = yaml.dump({
            "axiom_semantic_version": "1.0",
            "concepts": [
                {"concept_id": "dry.run.test", "name_ko": "드라이런"}
            ],
        })

        result = importer.import_yaml(TENANT, yaml_content, dry_run=True)

        assert result["dry_run"] is True
        assert result["errors"] == []
        assert result["created"]["concepts"] == 1  # 미리보기 수치
        # 실제 store에는 생성되지 않음
        assert store.get_concept(TENANT, "dry.run.test") is None


class TestImportValidationErrorMissingFields:
    """필수 필드 누락 검증"""

    def test_import_validation_error_missing_fields(self, store, importer):
        """필수 필드가 누락된 YAML은 검증 오류를 반환한다."""
        yaml_content = yaml.dump({
            "axiom_semantic_version": "1.0",
            "measures": [
                {
                    "measure_id": "bad_measure",
                    # entity_id, name, sql_expression 누락
                }
            ],
        })

        result = importer.import_yaml(TENANT, yaml_content)

        assert len(result["errors"]) > 0
        # entity_id, name, sql_expression 3개 필수 필드 누락
        error_text = " ".join(result["errors"])
        assert "entity_id" in error_text
        assert "name" in error_text
        assert "sql_expression" in error_text


class TestImportSqlInjectionBlocked:
    """SQL injection 차단"""

    def test_import_sql_injection_blocked(self, store, importer):
        """위험한 SQL 표현식이 포함된 YAML은 import를 차단한다."""
        yaml_content = yaml.dump({
            "axiom_semantic_version": "1.0",
            "measures": [
                {
                    "measure_id": "evil_measure",
                    "entity_id": "mart_test",
                    "name": "Evil Measure",
                    "sql_expression": "SUM(amount); DROP TABLE users",
                }
            ],
        })

        result = importer.import_yaml(TENANT, yaml_content)

        assert len(result["errors"]) > 0
        error_text = " ".join(result["errors"])
        assert "세미콜론" in error_text or "위험한" in error_text


class TestImportSqlCommentBlocked:
    """SQL 코멘트(프롬프트 주입) 차단"""

    def test_import_sql_comment_blocked(self, store, importer):
        """SQL 코멘트가 포함된 SQL 표현식을 차단한다."""
        yaml_content = yaml.dump({
            "axiom_semantic_version": "1.0",
            "dimensions": [
                {
                    "dimension_id": "dim_evil",
                    "entity_id": "mart_test",
                    "name": "Evil Dim",
                    "sql_expression": "channel_group -- ignore this",
                }
            ],
        })

        result = importer.import_yaml(TENANT, yaml_content)

        assert len(result["errors"]) > 0
        error_text = " ".join(result["errors"])
        assert "코멘트" in error_text


class TestImportWithGitSha:
    """git_commit_sha 기록"""

    def test_import_with_git_sha(self, store, importer):
        """git_commit_sha가 전달되면 결과에 포함된다."""
        yaml_content = yaml.dump({
            "axiom_semantic_version": "1.0",
            "concepts": [
                {"concept_id": "git.test", "name_ko": "깃 테스트", "case_id": "c-1"}
            ],
        })

        result = importer.import_yaml(
            TENANT, yaml_content, git_sha="abc123def456", case_id="c-1",
        )

        assert result["errors"] == []
        assert result["git_commit_sha"] == "abc123def456"


class TestRoundtripExportImport:
    """export → import 왕복 검증"""

    def test_roundtrip_export_import(self, store, exporter, importer):
        """export한 YAML을 다시 import하면 동일한 데이터가 복원된다."""
        # 1) 데이터 시드
        _seed_concept(store)
        store.create_terms_bulk(TENANT, [
            {"concept_id": "concept.test", "surface_form": "테스트",
             "language": "ko", "term_type": "primary"},
        ])
        _seed_entity(store)
        _seed_measure(store)

        # 2) export
        yaml_content = exporter.export(TENANT)

        # 3) 새로운 store에 import
        new_store = FakeSemanticStore()
        new_importer = SemanticYamlImporter(new_store)
        result = new_importer.import_yaml(TENANT, yaml_content, case_id="case-1")

        assert result["errors"] == []
        assert result["created"].get("concepts", 0) == 1
        assert result["created"].get("entities", 0) == 1
        assert result["created"].get("measures", 0) == 1

        # 4) 데이터 일치 검증
        concept = new_store.get_concept(TENANT, "concept.test")
        assert concept is not None
        assert concept["name_ko"] == "테스트 개념"

        entity = new_store.get_entity(TENANT, "mart_test")
        assert entity is not None

        measure = new_store.get_measure(TENANT, "measure_test")
        assert measure is not None
        assert measure["sql_expression"] == "SUM(amount)"


class TestImportUnsupportedVersion:
    """지원하지 않는 YAML 버전"""

    def test_import_unsupported_version(self, store, importer):
        """지원하지 않는 axiom_semantic_version은 검증 오류를 반환한다."""
        yaml_content = yaml.dump({
            "axiom_semantic_version": "99.0",
            "concepts": [],
        })

        result = importer.import_yaml(TENANT, yaml_content)

        assert len(result["errors"]) > 0
        assert "99.0" in result["errors"][0]


class TestImportMalformedYaml:
    """잘못된 YAML 형식"""

    def test_import_malformed_yaml(self, store, importer):
        """파싱할 수 없는 YAML은 오류를 반환한다."""
        # 탭+콜론 혼합은 실제 YAML 파싱 오류를 유발
        result = importer.import_yaml(TENANT, "\t: {invalid:\n\t- [\n")

        assert len(result["errors"]) > 0
        # YAML 파싱 오류 또는 루트 타입 오류 등
        assert any("파싱 오류" in e or "딕셔너리" in e for e in result["errors"])


class TestImportSelfJoinBlocked:
    """self-join 차단 검증"""

    def test_import_self_join_blocked(self, store, importer):
        """left_entity_id == right_entity_id인 조인은 차단된다."""
        yaml_content = yaml.dump({
            "axiom_semantic_version": "1.0",
            "joins": [
                {
                    "join_id": "self_join",
                    "left_entity_id": "mart_test",
                    "right_entity_id": "mart_test",
                    "join_condition": "a.id = b.id",
                }
            ],
        })

        result = importer.import_yaml(TENANT, yaml_content)

        assert len(result["errors"]) > 0
        assert "self-join" in result["errors"][0]


class TestValidatorDirectly:
    """SemanticYamlValidator 직접 검증"""

    def test_validate_missing_version(self, validator):
        """axiom_semantic_version이 없으면 오류"""
        errors = validator.validate({"concepts": []})
        assert any("axiom_semantic_version" in e for e in errors)

    def test_validate_ddl_in_sql(self, validator):
        """DDL 키워드가 SQL 표현식에 있으면 오류"""
        errors = validator.validate({
            "axiom_semantic_version": "1.0",
            "measures": [
                {
                    "measure_id": "m1",
                    "entity_id": "e1",
                    "name": "M",
                    "sql_expression": "DROP TABLE users",
                }
            ],
        })
        assert any("위험한 SQL" in e for e in errors)

    def test_validate_valid_document(self, validator):
        """올바른 YAML 문서는 오류가 없다."""
        errors = validator.validate({
            "axiom_semantic_version": "1.0",
            "concepts": [
                {"concept_id": "c1", "name_ko": "테스트"}
            ],
            "measures": [
                {
                    "measure_id": "m1",
                    "entity_id": "e1",
                    "name": "M",
                    "sql_expression": "SUM(amount)",
                }
            ],
        })
        assert errors == []


class TestExportDomainFilter:
    """도메인 필터 내보내기"""

    def test_export_filters_by_domain(self, store, exporter):
        """domain_id 필터를 적용하면 해당 도메인 개념만 내보낸다."""
        _seed_concept(store, concept_id="sales.metric", name_ko="매출 지표")
        store.create_concept(TENANT, {
            "concept_id": "hr.metric",
            "case_id": "case-1",
            "domain_id": "hr",
            "name_ko": "HR 지표",
        })

        result = exporter.export(TENANT, domain_id="sales")
        parsed = yaml.safe_load(result)

        assert len(parsed["concepts"]) == 1
        assert parsed["concepts"][0]["concept_id"] == "sales.metric"


class TestExportExcludesInternalFields:
    """내보내기에서 내부 필드 제외"""

    def test_export_excludes_tenant_id(self, store, exporter):
        """tenant_id, case_id 등 내부 필드가 YAML에 포함되지 않는다."""
        _seed_concept(store)
        _seed_entity(store)

        result = exporter.export(TENANT)
        parsed = yaml.safe_load(result)

        concept = parsed["concepts"][0]
        assert "tenant_id" not in concept
        assert "created_at" not in concept
        assert "updated_at" not in concept

        entity = parsed["entities"][0]
        assert "tenant_id" not in entity
