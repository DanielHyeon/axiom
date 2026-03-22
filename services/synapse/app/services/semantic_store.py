"""
시멘틱 계약 PostgreSQL 저장소 — Control Plane 메타스토어

SchemaEditStore 패턴을 따라 psycopg2 직접 SQL 사용.
synapse 스키마에 ontology_concepts, ontology_terms,
semantic_entities, semantic_measures, semantic_dimensions,
join_contracts, quality_contracts, semantic_releases 테이블을 관리한다.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

import structlog

from app.core.config import settings
from app.models.semantic_models import (
    VALID_CONCEPT_STATUSES,
    VALID_ENTITY_TYPES,
    VALID_MEASURE_TYPES,
    VALID_ADDITIVE_TYPES,
    VALID_VALUE_TYPES,
    VALID_JOIN_TYPES,
    VALID_RELATIONSHIP_TYPES,
    VALID_SENSITIVITY_LEVELS,
    VALID_TERM_TYPES,
    VALID_SEMANTIC_OBJECT_TYPES,
    VALID_DUPLICATE_RESOLUTION,
    VALID_TIME_GRAINS,
    VALID_INTENT_TYPES,
    VALID_PROMPT_RULE_TYPES,
    VALID_APPROVAL_SCOPES,
    VALID_PREDICATE_TYPES,
    VALID_CARDINALITIES,
    VALID_DIRECTIONALITIES,
    VALID_RULE_TYPES,
    VALID_EXPRESSION_LANGS,
    VALID_POLICY_TYPES,
    VALID_EXPANSION_RULE_TYPES,
    VALID_FEEDBACK_ISSUE_TYPES,
    VALID_INTENT_MODEL_TYPES,
    VALID_ALIAS_GROUP_STATUSES,
    VALID_EXPANSION_RULE_STATUSES,
    VALID_SEGMENT_TYPES,
    VALID_TIME_CONTRACT_GRAINS,
    VALID_ACCESS_POLICY_TYPES,
)

logger = structlog.get_logger()

# ── SQL 프래그먼트 안전성 검증 (방어적 심층 방어) ──
import re

_DANGEROUS_SQL_KEYWORDS = re.compile(
    r"\b(DROP|ALTER|TRUNCATE|DELETE|INSERT|UPDATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)
_STATEMENT_TERMINATOR = re.compile(r";")  # 세미콜론 자체를 금지
_SQL_COMMENT_PATTERN = re.compile(r"(--|/\*)")  # SQL 코멘트 금지 (프롬프트 주입 방어)
_MAX_SQL_FRAGMENT_LEN = 4096


def _validate_sql_fragment(value: str, field_name: str) -> None:
    """SQL 프래그먼트에 위험한 구문이 없는지 검증한다 (방어적 심층 방어).

    허용: SELECT 표현식, 집계 함수, WHERE 조건, 컬럼 참조, 리터럴
    차단: DDL/DML 키워드, 세미콜론, SQL 코멘트 (-- , /* */)
    """
    if not value:
        return
    if len(value) > _MAX_SQL_FRAGMENT_LEN:
        raise ValueError(f"{field_name}이 최대 길이({_MAX_SQL_FRAGMENT_LEN})를 초과합니다")
    if _STATEMENT_TERMINATOR.search(value):
        raise ValueError(f"{field_name}에 세미콜론(;)이 포함되어 있습니다")
    if _SQL_COMMENT_PATTERN.search(value):
        raise ValueError(f"{field_name}에 SQL 코멘트(--, /* */)가 포함되어 있습니다")
    if _DANGEROUS_SQL_KEYWORDS.search(value):
        raise ValueError(f"{field_name}에 위험한 SQL 키워드가 포함되어 있습니다")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _import_psycopg2():
    """psycopg2 동적 임포트 — 경로 문제 방어"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2, RealDictCursor
    except Exception:
        for path in ("/usr/lib/python3/dist-packages", "/home/daniel/.local/lib/python3.12/site-packages"):
            if path not in sys.path:
                sys.path.append(path)
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2, RealDictCursor


# ── 상태 전이 규칙 ──
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"review", "deprecated"},
    "review": {"approved", "draft"},
    "approved": {"deprecated"},
    "deprecated": {"draft"},
}

# ── 업데이트 가능 컬럼 화이트리스트 (SQL injection 방어) ──
_CONCEPT_UPDATABLE = {
    "domain_id", "name_ko", "name_en", "description", "business_definition",
    "owner_team", "steward_user", "sensitivity_level", "default_time_semantics",
    "default_unit", "version", "updated_at",
    "approval_scope",  # §5.2: 도메인 스코프 승인 워크플로
}
_ENTITY_UPDATABLE = {
    "bound_concept_id", "physical_source_ref", "entity_type", "grain_definition",
    "primary_key_spec", "default_filters", "freshness_sla_minutes", "version", "updated_at",
    "domain_id",  # §5.1: 도메인 네임스페이스
    "feature_config",  # P3 §5.3: ML/Feature Source 바인딩
}
_MEASURE_UPDATABLE = {
    "bound_concept_id", "entity_id", "name", "description", "measure_type",
    "sql_expression", "filter_expression", "numerator_measure_id", "denominator_measure_id",
    "additive_type", "default_agg_window", "owner_team", "version", "updated_at",
    "domain_id",  # §5.1: 도메인 네임스페이스
}
_DIMENSION_UPDATABLE = {
    "bound_concept_id", "entity_id", "name", "sql_expression", "value_type",
    "hierarchy_path", "conformed_group", "version", "updated_at",
    "domain_id",  # §5.1: 도메인 네임스페이스
}
_JOIN_UPDATABLE = {
    "join_type", "join_condition", "relationship_type", "allowed_for_ai",
    "fanout_risk_score", "updated_at",
    "domain_id",  # §5.1: 도메인 네임스페이스
}
_GRAIN_UPDATABLE = {
    "grain_key_set", "time_grain", "uniqueness_test", "duplicate_resolution_rule", "version", "updated_at",
}
_CONTEXT_PACK_UPDATABLE = {
    "domain_id", "intent_type", "description", "included_concept_ids", "included_measure_ids",
    "included_dimension_ids", "allowed_join_ids", "banned_join_ids", "temporal_rules",
    "answer_guardrails", "quality_gate_min_score", "version", "updated_at",
}
_PROMPT_POLICY_UPDATABLE = {
    "rule_type", "rule_text", "priority", "updated_at",
}
_RELATION_UPDATABLE = {
    "predicate_type", "cardinality", "directionality", "weight",
    "confidence", "effective_from", "effective_to", "updated_at",
}
_ONTOLOGY_RULE_UPDATABLE = {
    "rule_type", "rule_expression", "expression_lang", "severity", "description", "updated_at",
}
_ONTOLOGY_POLICY_UPDATABLE = {
    "policy_type", "policy_expression", "description", "is_active", "updated_at",
}
# §5.2: 시멘틱 세그먼트 / 시간 계약 / 접근 정책
_SEGMENT_UPDATABLE = {
    "name", "filter_expression", "segment_type", "description", "version", "updated_at",
}
_TIME_CONTRACT_UPDATABLE = {
    "time_column", "time_grain", "timezone", "fiscal_calendar_offset",
    "default_lookback_days", "description", "version", "updated_at",
}
_ACCESS_POLICY_UPDATABLE = {
    "policy_type", "condition_expression", "target_roles", "is_active",
    "description", "version", "updated_at",
}


class SemanticStore:
    """시멘틱 계약 계층 PostgreSQL 저장소 (Control Plane)"""

    _DB_SCHEMA = "synapse"

    def __init__(self, database_url: str | None = None) -> None:
        self._database_url = database_url or settings.SCHEMA_EDIT_DATABASE_URL
        self._schema_ready = False

    # ── 연결 관리 ──

    def _connect(self):
        psycopg2, _ = _import_psycopg2()
        conn = psycopg2.connect(self._database_url)
        cur = conn.cursor()
        cur.execute(f"SET search_path TO {self._DB_SCHEMA}, public")
        cur.close()
        return conn

    def _dict_cursor(self):
        _, RealDictCursor = _import_psycopg2()
        return RealDictCursor

    class _Cursor:
        """커넥션 누수 방지용 컨텍스트 매니저"""
        def __init__(self, store, dict_cursor=False):
            self._store = store
            self._dict = dict_cursor
            self.conn = None
            self.cur = None
        def __enter__(self):
            self.conn = self._store._connect()
            factory = self._store._dict_cursor() if self._dict else None
            self.cur = self.conn.cursor(cursor_factory=factory)
            return self.conn, self.cur
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.cur:
                self.cur.close()
            if self.conn:
                if exc_type:
                    self.conn.rollback()
                self.conn.close()
            return False

    def _cursor(self, dict_cursor=False):
        return self._Cursor(self, dict_cursor)

    # ── 스키마 초기화 (멱등) ──

    def ensure_schema(self) -> None:
        """synapse 스키마와 시멘틱 계약 테이블을 생성한다 (CREATE IF NOT EXISTS)."""
        if self._schema_ready:
            return
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self._DB_SCHEMA}")
        conn.commit()

        # L3: 온톨로지 개념 거버넌스 확장
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ontology_concepts (
                concept_id    VARCHAR PRIMARY KEY,
                case_id       VARCHAR NOT NULL,
                domain_id     VARCHAR NOT NULL DEFAULT 'default',
                name_ko       VARCHAR NOT NULL,
                name_en       VARCHAR,
                description   TEXT,
                business_definition TEXT,
                status        VARCHAR NOT NULL DEFAULT 'draft',
                owner_team    VARCHAR,
                steward_user  VARCHAR,
                sensitivity_level VARCHAR DEFAULT 'internal',
                default_time_semantics VARCHAR,
                default_unit  VARCHAR,
                version       INTEGER NOT NULL DEFAULT 1,
                tenant_id     VARCHAR NOT NULL,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ontology_concepts_tenant
                ON ontology_concepts(tenant_id, case_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ontology_concepts_status
                ON ontology_concepts(tenant_id, status)
        """)

        # L3: 온톨로지 용어
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ontology_terms (
                term_id       BIGSERIAL PRIMARY KEY,
                concept_id    VARCHAR NOT NULL REFERENCES ontology_concepts(concept_id) ON DELETE CASCADE,
                surface_form  VARCHAR NOT NULL,
                language      VARCHAR NOT NULL DEFAULT 'ko',
                term_type     VARCHAR NOT NULL DEFAULT 'primary',
                confidence    NUMERIC(5,2) DEFAULT 1.0,
                tenant_id     VARCHAR NOT NULL,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ontology_terms_concept
                ON ontology_terms(concept_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ontology_terms_search
                ON ontology_terms(tenant_id, surface_form)
        """)

        # L2: 시멘틱 엔티티
        cur.execute("""
            CREATE TABLE IF NOT EXISTS semantic_entities (
                entity_id             VARCHAR PRIMARY KEY,
                bound_concept_id      VARCHAR REFERENCES ontology_concepts(concept_id),
                physical_source_ref   VARCHAR NOT NULL,
                entity_type           VARCHAR NOT NULL DEFAULT 'fact',
                grain_definition      TEXT,
                primary_key_spec      VARCHAR,
                default_filters       JSONB,
                freshness_sla_minutes INTEGER,
                feature_config        JSONB DEFAULT NULL,
                tenant_id             VARCHAR NOT NULL,
                case_id               VARCHAR NOT NULL,
                status                VARCHAR NOT NULL DEFAULT 'draft',
                version               INTEGER NOT NULL DEFAULT 1,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        # P3 §5.3: 기존 테이블에 feature_config 컬럼 추가 (멱등 마이그레이션)
        cur.execute("""
            ALTER TABLE semantic_entities
            ADD COLUMN IF NOT EXISTS feature_config JSONB DEFAULT NULL
        """)

        # L2: 시멘틱 지표
        cur.execute("""
            CREATE TABLE IF NOT EXISTS semantic_measures (
                measure_id            VARCHAR PRIMARY KEY,
                bound_concept_id      VARCHAR REFERENCES ontology_concepts(concept_id),
                entity_id             VARCHAR NOT NULL REFERENCES semantic_entities(entity_id),
                name                  VARCHAR NOT NULL,
                description           TEXT,
                measure_type          VARCHAR NOT NULL DEFAULT 'sum',
                sql_expression        TEXT NOT NULL,
                filter_expression     TEXT,
                numerator_measure_id  VARCHAR,
                denominator_measure_id VARCHAR,
                additive_type         VARCHAR DEFAULT 'additive',
                default_agg_window    VARCHAR,
                owner_team            VARCHAR,
                tenant_id             VARCHAR NOT NULL,
                case_id               VARCHAR NOT NULL,
                status                VARCHAR NOT NULL DEFAULT 'draft',
                version               INTEGER NOT NULL DEFAULT 1,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # L2: 시멘틱 차원
        cur.execute("""
            CREATE TABLE IF NOT EXISTS semantic_dimensions (
                dimension_id          VARCHAR PRIMARY KEY,
                bound_concept_id      VARCHAR REFERENCES ontology_concepts(concept_id),
                entity_id             VARCHAR NOT NULL REFERENCES semantic_entities(entity_id),
                name                  VARCHAR NOT NULL,
                sql_expression        TEXT NOT NULL,
                value_type            VARCHAR DEFAULT 'categorical',
                hierarchy_path        VARCHAR,
                conformed_group       VARCHAR,
                tenant_id             VARCHAR NOT NULL,
                case_id               VARCHAR NOT NULL,
                status                VARCHAR NOT NULL DEFAULT 'draft',
                version               INTEGER NOT NULL DEFAULT 1,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # L2: 조인 계약
        cur.execute("""
            CREATE TABLE IF NOT EXISTS join_contracts (
                join_id               VARCHAR PRIMARY KEY,
                left_entity_id        VARCHAR NOT NULL REFERENCES semantic_entities(entity_id),
                right_entity_id       VARCHAR NOT NULL REFERENCES semantic_entities(entity_id),
                join_type             VARCHAR NOT NULL DEFAULT 'LEFT',
                join_condition        TEXT NOT NULL,
                relationship_type     VARCHAR NOT NULL DEFAULT '1:N',
                allowed_for_ai        BOOLEAN DEFAULT TRUE,
                fanout_risk_score     NUMERIC(3,2) DEFAULT 0.0,
                tenant_id             VARCHAR NOT NULL,
                case_id               VARCHAR NOT NULL,
                status                VARCHAR NOT NULL DEFAULT 'draft',
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # L2: 그레인 계약
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grain_contracts (
                grain_id              VARCHAR PRIMARY KEY,
                entity_id             VARCHAR NOT NULL REFERENCES semantic_entities(entity_id),
                grain_key_set         JSONB NOT NULL,
                time_grain            VARCHAR DEFAULT 'none',
                uniqueness_test       TEXT,
                duplicate_resolution_rule VARCHAR DEFAULT 'fail',
                tenant_id             VARCHAR NOT NULL,
                case_id               VARCHAR NOT NULL,
                version               INTEGER NOT NULL DEFAULT 1,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # L2: 품질 계약
        cur.execute("""
            CREATE TABLE IF NOT EXISTS quality_contracts (
                quality_contract_id   VARCHAR PRIMARY KEY,
                target_type           VARCHAR NOT NULL,
                target_id             VARCHAR NOT NULL,
                freshness_sla_minutes INTEGER,
                completeness_threshold NUMERIC(5,2) DEFAULT 95.0,
                uniqueness_threshold  NUMERIC(5,2) DEFAULT 99.0,
                owner_presence_required BOOLEAN DEFAULT TRUE,
                lineage_required      BOOLEAN DEFAULT TRUE,
                tenant_id             VARCHAR NOT NULL,
                case_id               VARCHAR NOT NULL,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # 배포 이력
        cur.execute("""
            CREATE TABLE IF NOT EXISTS semantic_releases (
                release_id            BIGSERIAL PRIMARY KEY,
                semantic_object_type  VARCHAR NOT NULL,
                semantic_object_id    VARCHAR NOT NULL,
                version               INTEGER NOT NULL,
                review_status         VARCHAR NOT NULL DEFAULT 'pending',
                reviewer              VARCHAR,
                deployed_at           TIMESTAMPTZ,
                tenant_id             VARCHAR NOT NULL,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # L5: AI 컨텍스트 팩
        cur.execute("""
            CREATE TABLE IF NOT EXISTS context_packs (
                context_pack_id       VARCHAR PRIMARY KEY,
                domain_id             VARCHAR NOT NULL DEFAULT 'default',
                intent_type           VARCHAR NOT NULL DEFAULT 'general',
                description           TEXT,
                included_concept_ids  JSONB DEFAULT '[]',
                included_measure_ids  JSONB DEFAULT '[]',
                included_dimension_ids JSONB DEFAULT '[]',
                allowed_join_ids      JSONB DEFAULT '[]',
                banned_join_ids       JSONB DEFAULT '[]',
                temporal_rules        JSONB,
                answer_guardrails     JSONB DEFAULT '[]',
                quality_gate_min_score NUMERIC(5,2) DEFAULT 0.0,
                tenant_id             VARCHAR NOT NULL,
                case_id               VARCHAR NOT NULL,
                version               INTEGER NOT NULL DEFAULT 1,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_context_packs_intent
                ON context_packs(tenant_id, intent_type)
        """)

        # L5: 프롬프트 정책
        cur.execute("""
            CREATE TABLE IF NOT EXISTS prompt_policies (
                prompt_policy_id      VARCHAR PRIMARY KEY,
                context_pack_id       VARCHAR NOT NULL REFERENCES context_packs(context_pack_id) ON DELETE CASCADE,
                rule_type             VARCHAR NOT NULL,
                rule_text             TEXT NOT NULL,
                priority              INTEGER DEFAULT 0,
                tenant_id             VARCHAR NOT NULL,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_prompt_policies_pack
                ON prompt_policies(context_pack_id)
        """)

        # §5.2 L2: 시멘틱 세그먼트 — 엔티티 필터 기반 데이터 분할
        cur.execute("""
            CREATE TABLE IF NOT EXISTS semantic_segments (
                segment_id            VARCHAR PRIMARY KEY,
                entity_id             VARCHAR NOT NULL REFERENCES semantic_entities(entity_id),
                name                  VARCHAR NOT NULL,
                filter_expression     TEXT NOT NULL,
                segment_type          VARCHAR NOT NULL DEFAULT 'static',
                description           TEXT,
                tenant_id             VARCHAR NOT NULL,
                case_id               VARCHAR NOT NULL DEFAULT '',
                version               INTEGER NOT NULL DEFAULT 1,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_semantic_segments_entity
                ON semantic_segments(tenant_id, entity_id)
        """)

        # §5.2 L2: 시간 계약 — 엔티티의 시간 축 의미론
        cur.execute("""
            CREATE TABLE IF NOT EXISTS time_contracts (
                time_contract_id      VARCHAR PRIMARY KEY,
                entity_id             VARCHAR NOT NULL REFERENCES semantic_entities(entity_id),
                time_column           VARCHAR NOT NULL,
                time_grain            VARCHAR NOT NULL,
                timezone              VARCHAR DEFAULT 'UTC',
                fiscal_calendar_offset INTEGER DEFAULT 0,
                default_lookback_days INTEGER DEFAULT 365,
                description           TEXT,
                tenant_id             VARCHAR NOT NULL,
                case_id               VARCHAR NOT NULL DEFAULT '',
                version               INTEGER NOT NULL DEFAULT 1,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_time_contracts_entity
                ON time_contracts(tenant_id, entity_id)
        """)

        # §5.2 L2: 접근 정책 — 행/열 수준 데이터 접근 제어
        cur.execute("""
            CREATE TABLE IF NOT EXISTS access_policies (
                access_policy_id      VARCHAR PRIMARY KEY,
                entity_id             VARCHAR NOT NULL REFERENCES semantic_entities(entity_id),
                policy_type           VARCHAR NOT NULL,
                condition_expression  TEXT NOT NULL,
                target_roles          JSONB DEFAULT '[]',
                is_active             BOOLEAN DEFAULT TRUE,
                description           TEXT,
                tenant_id             VARCHAR NOT NULL,
                case_id               VARCHAR NOT NULL DEFAULT '',
                version               INTEGER NOT NULL DEFAULT 1,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_access_policies_entity
                ON access_policies(tenant_id, entity_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_access_policies_active
                ON access_policies(tenant_id, is_active)
        """)

        # L3: 온톨로지 규칙 — 개념에 바인딩되는 업무 규칙
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ontology_rules (
                rule_id               VARCHAR PRIMARY KEY,
                tenant_id             VARCHAR NOT NULL,
                concept_id            VARCHAR NOT NULL,
                rule_type             VARCHAR NOT NULL,
                rule_expression       TEXT NOT NULL,
                expression_lang       VARCHAR NOT NULL DEFAULT 'sql',
                severity              VARCHAR DEFAULT 'warning',
                description           TEXT,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ontology_rules_concept
                ON ontology_rules(tenant_id, concept_id)
        """)

        # L3: 온톨로지 정책 — 접근/PII/보존/거주지/집계 거버넌스 정책
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ontology_policies (
                policy_id             VARCHAR PRIMARY KEY,
                tenant_id             VARCHAR NOT NULL,
                concept_id            VARCHAR NOT NULL,
                policy_type           VARCHAR NOT NULL,
                policy_expression     TEXT NOT NULL,
                description           TEXT,
                is_active             BOOLEAN DEFAULT TRUE,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ontology_policies_concept
                ON ontology_policies(tenant_id, concept_id)
        """)

        # §5.1: 온톨로지 관계 (Neo4j 보완 PG 구조화 메타데이터)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ontology_relations (
                relation_id           VARCHAR PRIMARY KEY,
                tenant_id             VARCHAR NOT NULL,
                subject_concept_id    VARCHAR NOT NULL,
                predicate_type        VARCHAR NOT NULL,
                object_concept_id     VARCHAR NOT NULL,
                cardinality           VARCHAR DEFAULT '1:N',
                directionality        VARCHAR DEFAULT 'unidirectional',
                weight                NUMERIC(5,2) DEFAULT 1.0,
                confidence            NUMERIC(5,2) DEFAULT 1.0,
                effective_from        TIMESTAMPTZ,
                effective_to          TIMESTAMPTZ,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ontrel_tenant
                ON ontology_relations(tenant_id, subject_concept_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ontrel_object
                ON ontology_relations(tenant_id, object_concept_id)
        """)

        # Sprint 4: 용어 별칭 그룹 — 여러 alias를 하나의 정규 용어 클러스터로 묶는다
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ontology_term_alias_groups (
                id                    VARCHAR PRIMARY KEY,
                tenant_id             VARCHAR NOT NULL,
                domain_id             VARCHAR NOT NULL DEFAULT 'global',
                canonical_term_id     VARCHAR NOT NULL,
                group_name            VARCHAR(200) NOT NULL,
                language_code         VARCHAR(16) NOT NULL DEFAULT 'ko',
                status                VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_alias_groups_tenant
                ON ontology_term_alias_groups(tenant_id, domain_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_alias_groups_canonical
                ON ontology_term_alias_groups(tenant_id, canonical_term_id)
        """)

        # Sprint 4: 용어 확장 규칙 — exact/normalized/regex/time_alias 등 매칭 규칙
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ontology_term_expansion_rules (
                id                    VARCHAR PRIMARY KEY,
                tenant_id             VARCHAR NOT NULL,
                domain_id             VARCHAR NOT NULL DEFAULT 'global',
                alias_group_id        VARCHAR NOT NULL,
                rule_type             VARCHAR(32) NOT NULL,
                match_pattern         TEXT NOT NULL,
                normalized_pattern    TEXT,
                boost                 NUMERIC(5,2) NOT NULL DEFAULT 1.0,
                priority              INT NOT NULL DEFAULT 100,
                status                VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
                effective_from        TIMESTAMPTZ,
                effective_to          TIMESTAMPTZ,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_expansion_rules_group
                ON ontology_term_expansion_rules(alias_group_id)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_expansion_rules_tenant
                ON ontology_term_expansion_rules(tenant_id, status)
        """)

        # Sprint 4: 의도 분류 모델 관리
        cur.execute("""
            CREATE TABLE IF NOT EXISTS intent_models (
                id                    VARCHAR PRIMARY KEY,
                tenant_id             VARCHAR NOT NULL,
                model_key             VARCHAR(100) NOT NULL,
                model_version         VARCHAR(64) NOT NULL,
                model_type            VARCHAR(32) NOT NULL DEFAULT 'keyword',
                status                VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
                config_json           JSONB NOT NULL DEFAULT '{}',
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_intent_models_tenant
                ON intent_models(tenant_id, status)
        """)

        # Sprint 4: 의도 추론 로그 (Oracle에서 기록)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS intent_inference_logs (
                id                    VARCHAR PRIMARY KEY,
                tenant_id             VARCHAR NOT NULL,
                request_id            VARCHAR(100) NOT NULL,
                snapshot_version      VARCHAR(100),
                user_question         TEXT NOT NULL,
                normalized_question   TEXT NOT NULL DEFAULT '',
                top_intent            VARCHAR(64),
                confidence            NUMERIC(5,2),
                ambiguity_score       NUMERIC(5,2),
                fallback_mode         VARCHAR(32),
                feature_json          JSONB NOT NULL DEFAULT '{}',
                candidate_json        JSONB NOT NULL DEFAULT '{}',
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_inference_logs_tenant
                ON intent_inference_logs(tenant_id, created_at DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_inference_logs_request
                ON intent_inference_logs(request_id)
        """)

        # Sprint 4: 질문 이해 피드백 (운영자 교정)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS semantic_question_feedback (
                id                    VARCHAR PRIMARY KEY,
                tenant_id             VARCHAR NOT NULL,
                request_id            VARCHAR(100) NOT NULL,
                issue_type            VARCHAR(32) NOT NULL,
                expected_intent       VARCHAR(64),
                expected_concept_id   VARCHAR,
                expected_measure_id   VARCHAR,
                feedback_note         TEXT,
                resolved              BOOLEAN NOT NULL DEFAULT FALSE,
                created_by            VARCHAR,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_question_feedback_tenant
                ON semantic_question_feedback(tenant_id, resolved)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_question_feedback_request
                ON semantic_question_feedback(request_id)
        """)

        conn.commit()

        # ── §5.1: 도메인 네임스페이스 마이그레이션 (기존 테이블에 domain_id 추가) ──
        # ALTER TABLE ADD COLUMN IF NOT EXISTS 패턴으로 안전하게 추가
        _migration_sqls = [
            # 시멘틱 엔티티에 domain_id 추가 (기본값 'global')
            "ALTER TABLE semantic_entities ADD COLUMN IF NOT EXISTS domain_id VARCHAR DEFAULT 'global'",
            # 시멘틱 지표에 domain_id 추가
            "ALTER TABLE semantic_measures ADD COLUMN IF NOT EXISTS domain_id VARCHAR DEFAULT 'global'",
            # 시멘틱 차원에 domain_id 추가
            "ALTER TABLE semantic_dimensions ADD COLUMN IF NOT EXISTS domain_id VARCHAR DEFAULT 'global'",
            # 조인 계약에 domain_id 추가
            "ALTER TABLE join_contracts ADD COLUMN IF NOT EXISTS domain_id VARCHAR DEFAULT 'global'",
            # §5.2: 온톨로지 개념에 승인 스코프 + 승인자 추가
            "ALTER TABLE ontology_concepts ADD COLUMN IF NOT EXISTS approval_scope VARCHAR DEFAULT 'global'",
            "ALTER TABLE ontology_concepts ADD COLUMN IF NOT EXISTS approved_by VARCHAR",
        ]
        for sql in _migration_sqls:
            cur.execute(sql)

        # §5.1: 도메인별 조회 인덱스 추가
        cur.execute("CREATE INDEX IF NOT EXISTS idx_semantic_entities_domain ON semantic_entities(tenant_id, domain_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_semantic_measures_domain ON semantic_measures(tenant_id, domain_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_semantic_dimensions_domain ON semantic_dimensions(tenant_id, domain_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_join_contracts_domain ON join_contracts(tenant_id, domain_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ontology_concepts_approval ON ontology_concepts(tenant_id, approval_scope)")

        conn.commit()
        cur.close()
        conn.close()
        self._schema_ready = True
        logger.info("semantic_store_schema_ready")

    # ========================================
    # 온톨로지 개념 CRUD
    # ========================================

    def create_concept(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """온톨로지 개념을 등록한다."""
        self.ensure_schema()
        # 유효성 검증
        status = data.get("status", "draft")
        if status not in VALID_CONCEPT_STATUSES:
            raise ValueError(f"status는 {VALID_CONCEPT_STATUSES} 중 하나여야 합니다: {status}")
        sens = data.get("sensitivity_level", "internal")
        if sens not in VALID_SENSITIVITY_LEVELS:
            raise ValueError(f"sensitivity_level은 {VALID_SENSITIVITY_LEVELS} 중 하나여야 합니다: {sens}")
        # §5.2: 승인 스코프 검증
        approval_scope = data.get("approval_scope", "global")
        if approval_scope not in VALID_APPROVAL_SCOPES:
            raise ValueError(f"approval_scope는 {VALID_APPROVAL_SCOPES} 중 하나여야 합니다: {approval_scope}")

        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO ontology_concepts (
                    concept_id, case_id, domain_id, name_ko, name_en,
                    description, business_definition, status, owner_team, steward_user,
                    sensitivity_level, default_time_semantics, default_unit,
                    approval_scope,
                    version, tenant_id, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s
                )
            """, (
                data["concept_id"], data["case_id"], data.get("domain_id", "default"),
                data["name_ko"], data.get("name_en"),
                data.get("description"), data.get("business_definition"),
                status, data.get("owner_team"), data.get("steward_user"),
                sens, data.get("default_time_semantics"), data.get("default_unit"),
                approval_scope,
                tenant_id, now, now,
            ))
            # §4.2: ONTOLOGY_CONCEPT_CREATED 이벤트 발행 (같은 트랜잭션)
            from app.events.outbox import EventPublisher
            EventPublisher.publish(
                event_type="ONTOLOGY_CONCEPT_CREATED",
                aggregate_type="ontology_concept",
                aggregate_id=data["concept_id"],
                payload={
                    "concept_id": data["concept_id"],
                    "case_id": data["case_id"],
                    "name_ko": data["name_ko"],
                    "status": status,
                    "tenant_id": tenant_id,
                },
                tenant_id=tenant_id,
                conn=conn,
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            # 중복 PK 등
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"concept_id '{data['concept_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()

        return {
            "concept_id": data["concept_id"],
            "case_id": data["case_id"],
            "domain_id": data.get("domain_id", "default"),
            "name_ko": data["name_ko"],
            "status": status,
            "approval_scope": approval_scope,
            "version": 1,
            "created_at": now.isoformat(),
        }

    def get_concept(self, tenant_id: str, concept_id: str) -> dict[str, Any] | None:
        """개념 단건 조회"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(
            "SELECT * FROM ontology_concepts WHERE tenant_id = %s AND concept_id = %s",
            (tenant_id, concept_id),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_concepts(
        self, tenant_id: str, case_id: str | None = None,
        status: str | None = None, limit: int = 100, offset: int = 0,
        approval_scope: str | None = None, domain_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """개념 목록 조회 (상태/케이스/승인스코프/도메인 필터)"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        # 동적 WHERE 절
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if case_id:
            conditions.append("case_id = %s")
            params.append(case_id)
        if status:
            conditions.append("status = %s")
            params.append(status)
        # §5.2: 승인 스코프 필터
        if approval_scope:
            conditions.append("approval_scope = %s")
            params.append(approval_scope)
        # §5.1: 도메인 필터
        if domain_id:
            conditions.append("domain_id = %s")
            params.append(domain_id)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        cur.execute(
            f"SELECT * FROM ontology_concepts WHERE {where} ORDER BY updated_at DESC LIMIT %s OFFSET %s",
            params,
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_concept(self, tenant_id: str, concept_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """개념 수정 — None이 아닌 필드만 업데이트, 버전 증가"""
        self.ensure_schema()
        existing = self.get_concept(tenant_id, concept_id)
        if not existing:
            raise KeyError(f"concept_id '{concept_id}'를 찾을 수 없습니다")

        # 화이트리스트 필터 + None 제외
        update_fields = {k: v for k, v in data.items() if v is not None and k in _CONCEPT_UPDATABLE}
        if not update_fields:
            return existing

        if "sensitivity_level" in update_fields:
            if update_fields["sensitivity_level"] not in VALID_SENSITIVITY_LEVELS:
                raise ValueError(f"sensitivity_level 유효하지 않음: {update_fields['sensitivity_level']}")
        # §5.2: approval_scope 검증
        if "approval_scope" in update_fields:
            if update_fields["approval_scope"] not in VALID_APPROVAL_SCOPES:
                raise ValueError(f"approval_scope 유효하지 않음: {update_fields['approval_scope']}")

        update_fields["version"] = existing["version"] + 1
        update_fields["updated_at"] = _now_dt()

        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, concept_id]

        with self._cursor() as (conn, cur):
            cur.execute(
                f"UPDATE ontology_concepts SET {set_clause} WHERE tenant_id = %s AND concept_id = %s",
                values,
            )
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    def change_concept_status(
        self, tenant_id: str, concept_id: str, new_status: str,
        approved_by: str | None = None,
    ) -> dict[str, Any]:
        """개념 상태 전이 — 허용된 전이만 가능

        §5.2: approval_scope='domain'인 개념은 review→approved 직접 전이를 허용한다.
        approval_scope='global'인 개념은 기존 행동(관리자 리뷰 필요)을 유지한다.
        approved 전이 시 approved_by를 기록한다.
        """
        if new_status not in VALID_CONCEPT_STATUSES:
            raise ValueError(f"status는 {VALID_CONCEPT_STATUSES} 중 하나여야 합니다")
        existing = self.get_concept(tenant_id, concept_id)
        if not existing:
            raise KeyError(f"concept_id '{concept_id}'를 찾을 수 없습니다")
        current = existing["status"]
        allowed = _ALLOWED_TRANSITIONS.get(current, set())
        if new_status not in allowed:
            raise ValueError(f"'{current}' → '{new_status}' 전이가 허용되지 않습니다. 가능: {allowed}")

        now = _now_dt()
        with self._cursor() as (conn, cur):
            # §5.2: approved 전이 시 approved_by 기록
            if new_status == "approved" and approved_by:
                cur.execute(
                    "UPDATE ontology_concepts SET status = %s, approved_by = %s, updated_at = %s WHERE tenant_id = %s AND concept_id = %s",
                    (new_status, approved_by, now, tenant_id, concept_id),
                )
            else:
                cur.execute(
                    "UPDATE ontology_concepts SET status = %s, updated_at = %s WHERE tenant_id = %s AND concept_id = %s",
                    (new_status, now, tenant_id, concept_id),
                )
            # §4.2: ONTOLOGY_CONCEPT_UPDATED 이벤트 발행 (상태 전이)
            from app.events.outbox import EventPublisher
            EventPublisher.publish(
                event_type="ONTOLOGY_CONCEPT_UPDATED",
                aggregate_type="ontology_concept",
                aggregate_id=concept_id,
                payload={
                    "concept_id": concept_id,
                    "previous_status": current,
                    "new_status": new_status,
                    "tenant_id": tenant_id,
                },
                tenant_id=tenant_id,
                conn=conn,
            )
            # §4.8: deprecated 전이 시 SEMANTIC_MEASURE_DEPRECATED 추가 발행
            if new_status == "deprecated":
                EventPublisher.publish(
                    event_type="SEMANTIC_MEASURE_DEPRECATED",
                    aggregate_type="ontology_concept",
                    aggregate_id=concept_id,
                    payload={
                        "concept_id": concept_id,
                        "previous_status": current,
                        "tenant_id": tenant_id,
                    },
                    tenant_id=tenant_id,
                    conn=conn,
                )
            conn.commit()
        result = {**existing, "status": new_status, "updated_at": now.isoformat()}
        if new_status == "approved" and approved_by:
            result["approved_by"] = approved_by
        return result

    # ========================================
    # 온톨로지 용어 CRUD
    # ========================================

    def create_term(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """온톨로지 용어를 등록한다."""
        self.ensure_schema()
        term_type = data.get("term_type", "primary")
        if term_type not in VALID_TERM_TYPES:
            raise ValueError(f"term_type은 {VALID_TERM_TYPES} 중 하나여야 합니다")
        # 바인딩 대상 개념 존재 확인
        concept = self.get_concept(tenant_id, data["concept_id"])
        if not concept:
            raise KeyError(f"concept_id '{data['concept_id']}'를 찾을 수 없습니다")

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ontology_terms (concept_id, surface_form, language, term_type, confidence, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING term_id, created_at
        """, (
            data["concept_id"], data["surface_form"],
            data.get("language", "ko"), term_type,
            data.get("confidence", 1.0), tenant_id,
        ))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return {
            "term_id": row[0],
            "concept_id": data["concept_id"],
            "surface_form": data["surface_form"],
            "language": data.get("language", "ko"),
            "term_type": term_type,
            "confidence": data.get("confidence", 1.0),
            "created_at": row[1].isoformat() if row[1] else _now(),
        }

    def create_terms_bulk(self, tenant_id: str, terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """용어 일괄 등록"""
        results = []
        for t in terms:
            results.append(self.create_term(tenant_id, t))
        return results

    def search_terms(self, tenant_id: str, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """용어 검색 — surface_form ILIKE"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute("""
            SELECT t.*, c.name_ko AS concept_name, c.status AS concept_status
            FROM ontology_terms t
            JOIN ontology_concepts c ON t.concept_id = c.concept_id AND c.tenant_id = t.tenant_id
            WHERE t.tenant_id = %s AND t.surface_form ILIKE %s
            ORDER BY t.confidence DESC
            LIMIT %s
        """, (tenant_id, f"%{query}%", limit))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def list_terms_by_concept(self, tenant_id: str, concept_id: str) -> list[dict[str, Any]]:
        """특정 개념에 바인딩된 모든 용어 조회"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(
            "SELECT * FROM ontology_terms WHERE tenant_id = %s AND concept_id = %s ORDER BY term_type, surface_form",
            (tenant_id, concept_id),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def list_terms_by_concepts_bulk(self, tenant_id: str, concept_ids: list[str]) -> list[dict[str, Any]]:
        """여러 개념에 바인딩된 용어를 한 번의 쿼리로 조회 (N+1 방지)"""
        if not concept_ids:
            return []
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        # ANY(%s)에 리스트를 전달
        cur.execute(
            "SELECT * FROM ontology_terms WHERE tenant_id = %s AND concept_id = ANY(%s) ORDER BY concept_id, term_type",
            (tenant_id, concept_ids),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    # ========================================
    # 시멘틱 엔티티 CRUD
    # ========================================

    def create_entity(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """시멘틱 엔티티 등록"""
        self.ensure_schema()
        etype = data.get("entity_type", "fact")
        if etype not in VALID_ENTITY_TYPES:
            raise ValueError(f"entity_type은 {VALID_ENTITY_TYPES} 중 하나여야 합니다")
        # P3 §5.3: feature_config는 feature_source 타입에서만 허용
        feature_config = data.get("feature_config")
        if feature_config and etype != "feature_source":
            raise ValueError("feature_config는 entity_type='feature_source'일 때만 설정할 수 있습니다")
        now = _now_dt()
        filters_json = json.dumps(data.get("default_filters")) if data.get("default_filters") else None
        feature_config_json = json.dumps(feature_config) if feature_config else None
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO semantic_entities (
                    entity_id, bound_concept_id, physical_source_ref, entity_type,
                    grain_definition, primary_key_spec, default_filters, freshness_sla_minutes,
                    feature_config, domain_id,
                    tenant_id, case_id, status, version, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', 1, %s, %s)
            """, (
                data["entity_id"], data.get("bound_concept_id"),
                data["physical_source_ref"], etype,
                data.get("grain_definition"), data.get("primary_key_spec"),
                filters_json, data.get("freshness_sla_minutes"),
                feature_config_json, data.get("domain_id", "global"),
                tenant_id, data.get("case_id", ""), now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"entity_id '{data['entity_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"entity_id": data["entity_id"], "entity_type": etype, "domain_id": data.get("domain_id", "global"), "status": "draft", "version": 1, "created_at": now.isoformat()}

    def get_entity(self, tenant_id: str, entity_id: str) -> dict[str, Any] | None:
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(
            "SELECT * FROM semantic_entities WHERE tenant_id = %s AND entity_id = %s",
            (tenant_id, entity_id),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_entities(self, tenant_id: str, case_id: str | None = None, domain_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """시멘틱 엔티티 목록 조회 — §5.1: domain_id 필터 지원"""
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if case_id:
            conditions.append("case_id = %s")
            params.append(case_id)
        if domain_id:
            conditions.append("domain_id = %s")
            params.append(domain_id)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(f"SELECT * FROM semantic_entities WHERE {where} ORDER BY updated_at DESC LIMIT %s OFFSET %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_entity(self, tenant_id: str, entity_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """시멘틱 엔티티 수정 (PATCH)"""
        self.ensure_schema()
        existing = self.get_entity(tenant_id, entity_id)
        if not existing:
            raise KeyError(f"entity_id '{entity_id}'를 찾을 수 없습니다")
        update_fields = {k: v for k, v in data.items() if v is not None and k in _ENTITY_UPDATABLE}
        if not update_fields:
            return existing
        if "entity_type" in update_fields and update_fields["entity_type"] not in VALID_ENTITY_TYPES:
            raise ValueError(f"entity_type 유효하지 않음: {update_fields['entity_type']}")
        if "default_filters" in update_fields:
            update_fields["default_filters"] = json.dumps(update_fields["default_filters"])
        # P3 §5.3: feature_config도 JSON으로 직렬화
        if "feature_config" in update_fields:
            # feature_source 타입이 아닌 엔티티에 feature_config 설정 차단
            effective_type = update_fields.get("entity_type", existing.get("entity_type"))
            if effective_type != "feature_source":
                raise ValueError("feature_config는 entity_type='feature_source'일 때만 설정할 수 있습니다")
            update_fields["feature_config"] = json.dumps(update_fields["feature_config"])
        update_fields["version"] = existing["version"] + 1
        update_fields["updated_at"] = _now_dt()
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, entity_id]
        with self._cursor() as (conn, cur):
            cur.execute(f"UPDATE semantic_entities SET {set_clause} WHERE tenant_id = %s AND entity_id = %s", values)
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    # ========================================
    # 시멘틱 지표 CRUD
    # ========================================

    def create_measure(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """시멘틱 지표 등록"""
        self.ensure_schema()
        mtype = data.get("measure_type", "sum")
        if mtype not in VALID_MEASURE_TYPES:
            raise ValueError(f"measure_type은 {VALID_MEASURE_TYPES} 중 하나여야 합니다")
        atype = data.get("additive_type", "additive")
        if atype not in VALID_ADDITIVE_TYPES:
            raise ValueError(f"additive_type은 {VALID_ADDITIVE_TYPES} 중 하나여야 합니다")
        # SQL 프래그먼트 안전성 검증
        _validate_sql_fragment(data.get("sql_expression", ""), "sql_expression")
        _validate_sql_fragment(data.get("filter_expression", "") or "", "filter_expression")
        # 엔티티 존재 확인
        entity = self.get_entity(tenant_id, data["entity_id"])
        if not entity:
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO semantic_measures (
                    measure_id, bound_concept_id, entity_id, name, description,
                    measure_type, sql_expression, filter_expression,
                    numerator_measure_id, denominator_measure_id,
                    additive_type, default_agg_window, owner_team,
                    domain_id,
                    tenant_id, case_id, status, version, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft',1,%s,%s)
            """, (
                data["measure_id"], data.get("bound_concept_id"), data["entity_id"],
                data["name"], data.get("description"),
                mtype, data["sql_expression"], data.get("filter_expression"),
                data.get("numerator_measure_id"), data.get("denominator_measure_id"),
                atype, data.get("default_agg_window"), data.get("owner_team"),
                data.get("domain_id", "global"),
                tenant_id, data.get("case_id", ""), now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"measure_id '{data['measure_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"measure_id": data["measure_id"], "name": data["name"], "status": "draft", "version": 1, "created_at": now.isoformat()}

    def get_measure(self, tenant_id: str, measure_id: str) -> dict[str, Any] | None:
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute("SELECT * FROM semantic_measures WHERE tenant_id = %s AND measure_id = %s", (tenant_id, measure_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_measures(self, tenant_id: str, case_id: str | None = None, entity_id: str | None = None, domain_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """시멘틱 지표 목록 조회 — §5.1: domain_id 필터 지원"""
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if case_id:
            conditions.append("case_id = %s")
            params.append(case_id)
        if entity_id:
            conditions.append("entity_id = %s")
            params.append(entity_id)
        if domain_id:
            conditions.append("domain_id = %s")
            params.append(domain_id)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(f"SELECT * FROM semantic_measures WHERE {where} ORDER BY updated_at DESC LIMIT %s OFFSET %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_measure(self, tenant_id: str, measure_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.ensure_schema()
        existing = self.get_measure(tenant_id, measure_id)
        if not existing:
            raise KeyError(f"measure_id '{measure_id}'를 찾을 수 없습니다")
        update_fields = {k: v for k, v in data.items() if v is not None and k in _MEASURE_UPDATABLE}
        if not update_fields:
            return existing
        if "measure_type" in update_fields and update_fields["measure_type"] not in VALID_MEASURE_TYPES:
            raise ValueError(f"measure_type 유효하지 않음: {update_fields['measure_type']}")
        update_fields["version"] = existing["version"] + 1
        update_fields["updated_at"] = _now_dt()
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, measure_id]
        with self._cursor() as (conn, cur):
            cur.execute(f"UPDATE semantic_measures SET {set_clause} WHERE tenant_id = %s AND measure_id = %s", values)
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    # ========================================
    # 시멘틱 차원 CRUD
    # ========================================

    def create_dimension(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """시멘틱 차원 등록"""
        self.ensure_schema()
        vtype = data.get("value_type", "categorical")
        if vtype not in VALID_VALUE_TYPES:
            raise ValueError(f"value_type은 {VALID_VALUE_TYPES} 중 하나여야 합니다")
        _validate_sql_fragment(data.get("sql_expression", ""), "sql_expression")
        entity = self.get_entity(tenant_id, data["entity_id"])
        if not entity:
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO semantic_dimensions (
                    dimension_id, bound_concept_id, entity_id, name, sql_expression,
                    value_type, hierarchy_path, conformed_group,
                    domain_id,
                    tenant_id, case_id, status, version, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft',1,%s,%s)
            """, (
                data["dimension_id"], data.get("bound_concept_id"), data["entity_id"],
                data["name"], data["sql_expression"],
                vtype, data.get("hierarchy_path"), data.get("conformed_group"),
                data.get("domain_id", "global"),
                tenant_id, data.get("case_id", ""), now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"dimension_id '{data['dimension_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"dimension_id": data["dimension_id"], "name": data["name"], "status": "draft", "version": 1, "created_at": now.isoformat()}

    def get_dimension(self, tenant_id: str, dimension_id: str) -> dict[str, Any] | None:
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute("SELECT * FROM semantic_dimensions WHERE tenant_id = %s AND dimension_id = %s", (tenant_id, dimension_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_dimensions(self, tenant_id: str, case_id: str | None = None, entity_id: str | None = None, domain_id: str | None = None, conformed_group: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """시멘틱 차원 목록 조회 — §5.1: domain_id, conformed_group 필터 지원"""
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if case_id:
            conditions.append("case_id = %s")
            params.append(case_id)
        if entity_id:
            conditions.append("entity_id = %s")
            params.append(entity_id)
        # §5.1: 도메인 필터
        if domain_id:
            conditions.append("domain_id = %s")
            params.append(domain_id)
        # §5.1: conformed_group 필터 — 교차 도메인 공유 차원 조회
        if conformed_group:
            conditions.append("conformed_group = %s")
            params.append(conformed_group)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(f"SELECT * FROM semantic_dimensions WHERE {where} ORDER BY updated_at DESC LIMIT %s OFFSET %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_dimension(self, tenant_id: str, dimension_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.ensure_schema()
        existing = self.get_dimension(tenant_id, dimension_id)
        if not existing:
            raise KeyError(f"dimension_id '{dimension_id}'를 찾을 수 없습니다")
        update_fields = {k: v for k, v in data.items() if v is not None and k in _DIMENSION_UPDATABLE}
        if not update_fields:
            return existing
        if "value_type" in update_fields and update_fields["value_type"] not in VALID_VALUE_TYPES:
            raise ValueError(f"value_type 유효하지 않음: {update_fields['value_type']}")
        update_fields["version"] = existing["version"] + 1
        update_fields["updated_at"] = _now_dt()
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, dimension_id]
        with self._cursor() as (conn, cur):
            cur.execute(f"UPDATE semantic_dimensions SET {set_clause} WHERE tenant_id = %s AND dimension_id = %s", values)
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    # ========================================
    # 조인 계약 CRUD
    # ========================================

    def create_join_contract(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """조인 계약 등록"""
        self.ensure_schema()
        jtype = data.get("join_type", "LEFT")
        if jtype not in VALID_JOIN_TYPES:
            raise ValueError(f"join_type은 {VALID_JOIN_TYPES} 중 하나여야 합니다")
        rtype = data.get("relationship_type", "1:N")
        if rtype not in VALID_RELATIONSHIP_TYPES:
            raise ValueError(f"relationship_type은 {VALID_RELATIONSHIP_TYPES} 중 하나여야 합니다")
        _validate_sql_fragment(data.get("join_condition", ""), "join_condition")
        # 양쪽 엔티티 존재 확인
        left_entity = self.get_entity(tenant_id, data["left_entity_id"])
        right_entity = self.get_entity(tenant_id, data["right_entity_id"])
        if not left_entity:
            raise KeyError(f"entity_id '{data['left_entity_id']}'를 찾을 수 없습니다")
        if not right_entity:
            raise KeyError(f"entity_id '{data['right_entity_id']}'를 찾을 수 없습니다")
        # §5.1: 교차 도메인 조인은 허용하되 경고 로그를 남긴다
        left_domain = left_entity.get("domain_id", "global")
        right_domain = right_entity.get("domain_id", "global")
        if left_domain != right_domain:
            logger.warning(
                "cross_domain_join_contract",
                join_id=data["join_id"],
                left_entity_id=data["left_entity_id"],
                left_domain=left_domain,
                right_entity_id=data["right_entity_id"],
                right_domain=right_domain,
            )
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO join_contracts (
                    join_id, left_entity_id, right_entity_id, join_type,
                    join_condition, relationship_type, allowed_for_ai, fanout_risk_score,
                    domain_id,
                    tenant_id, case_id, status, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft',%s,%s)
            """, (
                data["join_id"], data["left_entity_id"], data["right_entity_id"],
                jtype, data["join_condition"], rtype,
                data.get("allowed_for_ai", True), data.get("fanout_risk_score", 0.0),
                data.get("domain_id", "global"),
                tenant_id, data.get("case_id", ""), now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"join_id '{data['join_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"join_id": data["join_id"], "status": "draft", "created_at": now.isoformat()}

    def get_join_contract(self, tenant_id: str, join_id: str) -> dict[str, Any] | None:
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute("SELECT * FROM join_contracts WHERE tenant_id = %s AND join_id = %s", (tenant_id, join_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_join_contracts(self, tenant_id: str, case_id: str | None = None, allowed_for_ai: bool | None = None, domain_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """조인 계약 목록 조회 — §5.1: domain_id 필터 지원"""
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if case_id:
            conditions.append("case_id = %s")
            params.append(case_id)
        if allowed_for_ai is not None:
            conditions.append("allowed_for_ai = %s")
            params.append(allowed_for_ai)
        # §5.1: 도메인 필터
        if domain_id:
            conditions.append("domain_id = %s")
            params.append(domain_id)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(f"SELECT * FROM join_contracts WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_join_contract(self, tenant_id: str, join_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.ensure_schema()
        existing = self.get_join_contract(tenant_id, join_id)
        if not existing:
            raise KeyError(f"join_id '{join_id}'를 찾을 수 없습니다")
        update_fields = {k: v for k, v in data.items() if v is not None and k in _JOIN_UPDATABLE}
        if not update_fields:
            return existing
        if "join_type" in update_fields and update_fields["join_type"] not in VALID_JOIN_TYPES:
            raise ValueError(f"join_type 유효하지 않음: {update_fields['join_type']}")
        if "relationship_type" in update_fields and update_fields["relationship_type"] not in VALID_RELATIONSHIP_TYPES:
            raise ValueError(f"relationship_type 유효하지 않음: {update_fields['relationship_type']}")
        update_fields["updated_at"] = _now_dt()
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, join_id]
        with self._cursor() as (conn, cur):
            cur.execute(f"UPDATE join_contracts SET {set_clause} WHERE tenant_id = %s AND join_id = %s", values)
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    # ========================================
    # 품질 계약 CRUD
    # ========================================

    def create_quality_contract(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """품질 계약 등록"""
        self.ensure_schema()
        target_type = data.get("target_type", "")
        if target_type not in VALID_SEMANTIC_OBJECT_TYPES:
            raise ValueError(f"target_type은 {VALID_SEMANTIC_OBJECT_TYPES} 중 하나여야 합니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO quality_contracts (
                    quality_contract_id, target_type, target_id,
                    freshness_sla_minutes, completeness_threshold, uniqueness_threshold,
                    owner_presence_required, lineage_required,
                    tenant_id, case_id, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["quality_contract_id"], target_type, data["target_id"],
                data.get("freshness_sla_minutes"), data.get("completeness_threshold", 95.0),
                data.get("uniqueness_threshold", 99.0),
                data.get("owner_presence_required", True), data.get("lineage_required", True),
                tenant_id, data.get("case_id", ""), now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"quality_contract_id '{data['quality_contract_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"quality_contract_id": data["quality_contract_id"], "target_type": target_type, "target_id": data["target_id"], "created_at": now.isoformat()}

    def list_quality_contracts(self, tenant_id: str, case_id: str | None = None, target_type: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if case_id:
            conditions.append("case_id = %s")
            params.append(case_id)
        if target_type:
            conditions.append("target_type = %s")
            params.append(target_type)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(f"SELECT * FROM quality_contracts WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    # ========================================
    # 배포 (Publish) + 릴리스
    # ========================================

    def publish(self, tenant_id: str, object_type: str, object_id: str, reviewer: str | None = None) -> dict[str, Any]:
        """시멘틱 객체 배포 — binding 검증 후 릴리스 기록 생성"""
        self.ensure_schema()
        if object_type not in VALID_SEMANTIC_OBJECT_TYPES:
            raise ValueError(f"object_type은 {VALID_SEMANTIC_OBJECT_TYPES} 중 하나여야 합니다")

        # binding 검증: measure/dimension은 bound_concept_id가 있어야 publish 가능
        version = 1
        if object_type == "entity":
            obj = self.get_entity(tenant_id, object_id)
            if not obj:
                raise KeyError(f"entity '{object_id}'를 찾을 수 없습니다")
            version = obj["version"]
        elif object_type == "measure":
            obj = self.get_measure(tenant_id, object_id)
            if not obj:
                raise KeyError(f"measure '{object_id}'를 찾을 수 없습니다")
            if not obj.get("bound_concept_id"):
                raise ValueError(f"measure '{object_id}'는 온톨로지 개념에 바인딩되어야 publish 가능합니다")
            version = obj["version"]
        elif object_type == "dimension":
            obj = self.get_dimension(tenant_id, object_id)
            if not obj:
                raise KeyError(f"dimension '{object_id}'를 찾을 수 없습니다")
            if not obj.get("bound_concept_id"):
                raise ValueError(f"dimension '{object_id}'는 온톨로지 개념에 바인딩되어야 publish 가능합니다")
            version = obj["version"]
        elif object_type == "join":
            obj = self.get_join_contract(tenant_id, object_id)
            if not obj:
                raise KeyError(f"join '{object_id}'를 찾을 수 없습니다")

        now = _now_dt()
        # 이벤트 타입 매핑 (모든 object_type 포함, §4.2 확장)
        _event_type_map = {
            "entity": "SEMANTIC_ENTITY_PUBLISHED",
            "measure": "SEMANTIC_MEASURE_PUBLISHED",
            "dimension": "SEMANTIC_DIMENSION_PUBLISHED",  # §4.2: 차원 전용 이벤트
            "join": "JOIN_CONTRACT_CREATED",
            "grain": "GRAIN_CONTRACT_CREATED",  # §4.2: 그레인 계약 이벤트
        }

        table_map = {"entity": "semantic_entities", "measure": "semantic_measures", "dimension": "semantic_dimensions", "join": "join_contracts"}
        pk_map = {"entity": "entity_id", "measure": "measure_id", "dimension": "dimension_id", "join": "join_id"}
        if object_type not in table_map:
            raise ValueError(f"publish 대상이 아닌 object_type: {object_type}")

        # 커넥션 누수 방지 — context manager 사용
        with self._cursor() as (conn, cur):
            cur.execute("""
                INSERT INTO semantic_releases (
                    semantic_object_type, semantic_object_id, version,
                    review_status, reviewer, deployed_at, tenant_id, created_at
                ) VALUES (%s, %s, %s, 'approved', %s, %s, %s, %s)
                RETURNING release_id
            """, (object_type, object_id, version, reviewer, now, tenant_id, now))
            release_id = cur.fetchone()[0]

            # 해당 객체 status를 approved로 변경
            table = table_map[object_type]
            pk = pk_map[object_type]
            cur.execute(f"UPDATE {table} SET status = 'approved', updated_at = %s WHERE tenant_id = %s AND {pk} = %s", (now, tenant_id, object_id))

            # Outbox 이벤트 발행 — 같은 트랜잭션(conn)으로 원자성 보장
            # try/except 없이 실패 시 전체 롤백 (Transactional Outbox 패턴 준수)
            event_type = _event_type_map.get(object_type)
            if event_type:
                from app.events.outbox import EventPublisher
                EventPublisher.publish(
                    event_type=event_type,
                    aggregate_type=f"semantic_{object_type}",
                    aggregate_id=object_id,
                    payload={
                        "object_type": object_type,
                        "object_id": object_id,
                        "version": version,
                        "bound_concept_id": obj.get("bound_concept_id") if object_type != "join" else None,
                        "tenant_id": tenant_id,
                        "deployed_at": now.isoformat(),
                    },
                    tenant_id=tenant_id,
                    conn=conn,
                )

            # §4.9: SEMANTIC_RELEASE_DEPLOYED — 릴리스 생성 시 배포 이벤트 발행
            from app.events.outbox import EventPublisher as _EP
            _EP.publish(
                event_type="SEMANTIC_RELEASE_DEPLOYED",
                aggregate_type="semantic_release",
                aggregate_id=release_id,
                payload={
                    "release_id": release_id,
                    "object_type": object_type,
                    "object_id": object_id,
                    "version": version,
                    "tenant_id": tenant_id,
                    "deployed_at": now.isoformat(),
                },
                tenant_id=tenant_id,
                conn=conn,
            )

            conn.commit()

        return {
            "release_id": release_id,
            "semantic_object_type": object_type,
            "semantic_object_id": object_id,
            "version": version,
            "review_status": "approved",
            "deployed_at": now.isoformat(),
        }

    def list_releases(self, tenant_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(
            "SELECT * FROM semantic_releases WHERE tenant_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (tenant_id, limit, offset),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    # ========================================
    # 통합 카탈로그
    # ========================================

    def get_catalog(self, tenant_id: str, case_id: str | None = None) -> dict[str, Any]:
        """통합 카탈로그 — 개념 + 엔티티 + 지표 + 차원 + 조인 + 그레인 요약"""
        concepts = self.list_concepts(tenant_id, case_id=case_id, limit=500)
        entities = self.list_entities(tenant_id, case_id=case_id, limit=500)
        measures = self.list_measures(tenant_id, case_id=case_id, limit=500)
        dimensions = self.list_dimensions(tenant_id, case_id=case_id, limit=500)
        joins = self.list_join_contracts(tenant_id, case_id=case_id, limit=500)
        grains = self.list_grain_contracts(tenant_id, case_id=case_id, limit=500)
        return {
            "summary": {
                "concepts": len(concepts),
                "entities": len(entities),
                "measures": len(measures),
                "dimensions": len(dimensions),
                "joins": len(joins),
                "grains": len(grains),
            },
            "concepts": concepts,
            "entities": entities,
            "measures": measures,
            "dimensions": dimensions,
            "joins": joins,
            "grains": grains,
        }

    # ========================================
    # 그레인 계약 CRUD
    # ========================================

    def create_grain_contract(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """그레인 계약 등록 — 엔티티의 행 단위 유일성 규칙"""
        self.ensure_schema()
        tg = data.get("time_grain", "none")
        if tg not in VALID_TIME_GRAINS:
            raise ValueError(f"time_grain은 {VALID_TIME_GRAINS} 중 하나여야 합니다")
        dr = data.get("duplicate_resolution_rule", "fail")
        if dr not in VALID_DUPLICATE_RESOLUTION:
            raise ValueError(f"duplicate_resolution_rule은 {VALID_DUPLICATE_RESOLUTION} 중 하나여야 합니다")
        _validate_sql_fragment(data.get("uniqueness_test", "") or "", "uniqueness_test")
        entity = self.get_entity(tenant_id, data["entity_id"])
        if not entity:
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO grain_contracts (
                    grain_id, entity_id, grain_key_set, time_grain,
                    uniqueness_test, duplicate_resolution_rule,
                    tenant_id, case_id, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["grain_id"], data["entity_id"],
                json.dumps(data["grain_key_set"]), tg,
                data.get("uniqueness_test"), dr,
                tenant_id, data.get("case_id", ""), now, now,
            ))
            # §4.2: GRAIN_CONTRACT_CREATED 이벤트 발행
            from app.events.outbox import EventPublisher
            EventPublisher.publish(
                event_type="GRAIN_CONTRACT_CREATED",
                aggregate_type="grain_contract",
                aggregate_id=data["grain_id"],
                payload={
                    "grain_id": data["grain_id"],
                    "entity_id": data["entity_id"],
                    "time_grain": tg,
                    "tenant_id": tenant_id,
                },
                tenant_id=tenant_id,
                conn=conn,
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"grain_id '{data['grain_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"grain_id": data["grain_id"], "entity_id": data["entity_id"], "created_at": now.isoformat()}

    def get_grain_contract(self, tenant_id: str, grain_id: str) -> dict[str, Any] | None:
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute("SELECT * FROM grain_contracts WHERE tenant_id = %s AND grain_id = %s", (tenant_id, grain_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_grain_contracts(self, tenant_id: str, case_id: str | None = None, entity_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if case_id:
            conditions.append("case_id = %s")
            params.append(case_id)
        if entity_id:
            conditions.append("entity_id = %s")
            params.append(entity_id)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(f"SELECT * FROM grain_contracts WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_grain_contract(self, tenant_id: str, grain_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.ensure_schema()
        existing = self.get_grain_contract(tenant_id, grain_id)
        if not existing:
            raise KeyError(f"grain_id '{grain_id}'를 찾을 수 없습니다")
        update_fields = {k: v for k, v in data.items() if v is not None and k in _GRAIN_UPDATABLE}
        if not update_fields:
            return existing
        if "time_grain" in update_fields and update_fields["time_grain"] not in VALID_TIME_GRAINS:
            raise ValueError(f"time_grain 유효하지 않음: {update_fields['time_grain']}")
        if "duplicate_resolution_rule" in update_fields and update_fields["duplicate_resolution_rule"] not in VALID_DUPLICATE_RESOLUTION:
            raise ValueError(f"duplicate_resolution_rule 유효하지 않음: {update_fields['duplicate_resolution_rule']}")
        if "grain_key_set" in update_fields:
            update_fields["grain_key_set"] = json.dumps(update_fields["grain_key_set"])
        update_fields["version"] = (existing.get("version") or 1) + 1
        update_fields["updated_at"] = _now_dt()
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, grain_id]
        with self._cursor() as (conn, cur):
            cur.execute(f"UPDATE grain_contracts SET {set_clause} WHERE tenant_id = %s AND grain_id = %s", values)
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    # ========================================
    # §5.2 시멘틱 세그먼트 CRUD
    # ========================================

    def create_segment(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """시멘틱 세그먼트 등록 — 엔티티의 필터 기반 데이터 분할"""
        self.ensure_schema()
        seg_type = data.get("segment_type", "static")
        if seg_type not in VALID_SEGMENT_TYPES:
            raise ValueError(f"segment_type은 {VALID_SEGMENT_TYPES} 중 하나여야 합니다")
        _validate_sql_fragment(data.get("filter_expression", "") or "", "filter_expression")
        # 엔티티 존재 확인
        entity = self.get_entity(tenant_id, data["entity_id"])
        if not entity:
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO semantic_segments (
                    segment_id, entity_id, name, filter_expression, segment_type,
                    description, tenant_id, case_id, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["segment_id"], data["entity_id"], data["name"],
                data["filter_expression"], seg_type,
                data.get("description"), tenant_id, data.get("case_id", ""),
                now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"segment_id '{data['segment_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"segment_id": data["segment_id"], "entity_id": data["entity_id"], "created_at": now.isoformat()}

    def get_segment(self, tenant_id: str, segment_id: str) -> dict[str, Any] | None:
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute("SELECT * FROM semantic_segments WHERE tenant_id = %s AND segment_id = %s", (tenant_id, segment_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_segments(self, tenant_id: str, entity_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if entity_id:
            conditions.append("entity_id = %s")
            params.append(entity_id)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(f"SELECT * FROM semantic_segments WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_segment(self, tenant_id: str, segment_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.ensure_schema()
        existing = self.get_segment(tenant_id, segment_id)
        if not existing:
            raise KeyError(f"segment_id '{segment_id}'를 찾을 수 없습니다")
        update_fields = {k: v for k, v in data.items() if v is not None and k in _SEGMENT_UPDATABLE}
        if not update_fields:
            return existing
        if "segment_type" in update_fields and update_fields["segment_type"] not in VALID_SEGMENT_TYPES:
            raise ValueError(f"segment_type 유효하지 않음: {update_fields['segment_type']}")
        if "filter_expression" in update_fields:
            _validate_sql_fragment(update_fields["filter_expression"], "filter_expression")
        update_fields["version"] = (existing.get("version") or 1) + 1
        update_fields["updated_at"] = _now_dt()
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, segment_id]
        with self._cursor() as (conn, cur):
            cur.execute(f"UPDATE semantic_segments SET {set_clause} WHERE tenant_id = %s AND segment_id = %s", values)
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    def delete_segment(self, tenant_id: str, segment_id: str) -> bool:
        """시멘틱 세그먼트 삭제"""
        self.ensure_schema()
        with self._cursor() as (conn, cur):
            cur.execute("DELETE FROM semantic_segments WHERE tenant_id = %s AND segment_id = %s", (tenant_id, segment_id))
            deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    # ========================================
    # §5.2 시간 계약 CRUD
    # ========================================

    def create_time_contract(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """시간 계약 등록 — 엔티티의 시간 축 의미론 정의"""
        self.ensure_schema()
        tg = data.get("time_grain", "")
        if tg not in VALID_TIME_CONTRACT_GRAINS:
            raise ValueError(f"time_grain은 {VALID_TIME_CONTRACT_GRAINS} 중 하나여야 합니다")
        entity = self.get_entity(tenant_id, data["entity_id"])
        if not entity:
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO time_contracts (
                    time_contract_id, entity_id, time_column, time_grain,
                    timezone, fiscal_calendar_offset, default_lookback_days,
                    description, tenant_id, case_id, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["time_contract_id"], data["entity_id"], data["time_column"], tg,
                data.get("timezone", "UTC"), data.get("fiscal_calendar_offset", 0),
                data.get("default_lookback_days", 365), data.get("description"),
                tenant_id, data.get("case_id", ""), now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"time_contract_id '{data['time_contract_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"time_contract_id": data["time_contract_id"], "entity_id": data["entity_id"], "created_at": now.isoformat()}

    def get_time_contract(self, tenant_id: str, time_contract_id: str) -> dict[str, Any] | None:
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute("SELECT * FROM time_contracts WHERE tenant_id = %s AND time_contract_id = %s", (tenant_id, time_contract_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_time_contracts(self, tenant_id: str, entity_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if entity_id:
            conditions.append("entity_id = %s")
            params.append(entity_id)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(f"SELECT * FROM time_contracts WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_time_contract(self, tenant_id: str, time_contract_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.ensure_schema()
        existing = self.get_time_contract(tenant_id, time_contract_id)
        if not existing:
            raise KeyError(f"time_contract_id '{time_contract_id}'를 찾을 수 없습니다")
        update_fields = {k: v for k, v in data.items() if v is not None and k in _TIME_CONTRACT_UPDATABLE}
        if not update_fields:
            return existing
        if "time_grain" in update_fields and update_fields["time_grain"] not in VALID_TIME_CONTRACT_GRAINS:
            raise ValueError(f"time_grain 유효하지 않음: {update_fields['time_grain']}")
        update_fields["version"] = (existing.get("version") or 1) + 1
        update_fields["updated_at"] = _now_dt()
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, time_contract_id]
        with self._cursor() as (conn, cur):
            cur.execute(f"UPDATE time_contracts SET {set_clause} WHERE tenant_id = %s AND time_contract_id = %s", values)
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    def delete_time_contract(self, tenant_id: str, time_contract_id: str) -> bool:
        """시간 계약 삭제"""
        self.ensure_schema()
        with self._cursor() as (conn, cur):
            cur.execute("DELETE FROM time_contracts WHERE tenant_id = %s AND time_contract_id = %s", (tenant_id, time_contract_id))
            deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    # ========================================
    # §5.2 접근 정책 CRUD
    # ========================================

    def create_access_policy(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """접근 정책 등록 — 행/열 수준 데이터 접근 제어"""
        self.ensure_schema()
        pt = data.get("policy_type", "")
        if pt not in VALID_ACCESS_POLICY_TYPES:
            raise ValueError(f"policy_type은 {VALID_ACCESS_POLICY_TYPES} 중 하나여야 합니다")
        _validate_sql_fragment(data.get("condition_expression", "") or "", "condition_expression")
        entity = self.get_entity(tenant_id, data["entity_id"])
        if not entity:
            raise KeyError(f"entity_id '{data['entity_id']}'를 찾을 수 없습니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO access_policies (
                    access_policy_id, entity_id, policy_type, condition_expression,
                    target_roles, is_active, description,
                    tenant_id, case_id, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["access_policy_id"], data["entity_id"], pt,
                data["condition_expression"],
                json.dumps(data.get("target_roles", [])),
                data.get("is_active", True), data.get("description"),
                tenant_id, data.get("case_id", ""), now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"access_policy_id '{data['access_policy_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"access_policy_id": data["access_policy_id"], "entity_id": data["entity_id"], "created_at": now.isoformat()}

    def get_access_policy(self, tenant_id: str, access_policy_id: str) -> dict[str, Any] | None:
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute("SELECT * FROM access_policies WHERE tenant_id = %s AND access_policy_id = %s", (tenant_id, access_policy_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_access_policies(self, tenant_id: str, entity_id: str | None = None, is_active: bool | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if entity_id:
            conditions.append("entity_id = %s")
            params.append(entity_id)
        if is_active is not None:
            conditions.append("is_active = %s")
            params.append(is_active)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(f"SELECT * FROM access_policies WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_access_policy(self, tenant_id: str, access_policy_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.ensure_schema()
        existing = self.get_access_policy(tenant_id, access_policy_id)
        if not existing:
            raise KeyError(f"access_policy_id '{access_policy_id}'를 찾을 수 없습니다")
        update_fields = {k: v for k, v in data.items() if v is not None and k in _ACCESS_POLICY_UPDATABLE}
        if not update_fields:
            return existing
        if "policy_type" in update_fields and update_fields["policy_type"] not in VALID_ACCESS_POLICY_TYPES:
            raise ValueError(f"policy_type 유효하지 않음: {update_fields['policy_type']}")
        if "condition_expression" in update_fields:
            _validate_sql_fragment(update_fields["condition_expression"], "condition_expression")
        if "target_roles" in update_fields:
            update_fields["target_roles"] = json.dumps(update_fields["target_roles"])
        update_fields["version"] = (existing.get("version") or 1) + 1
        update_fields["updated_at"] = _now_dt()
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, access_policy_id]
        with self._cursor() as (conn, cur):
            cur.execute(f"UPDATE access_policies SET {set_clause} WHERE tenant_id = %s AND access_policy_id = %s", values)
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    def delete_access_policy(self, tenant_id: str, access_policy_id: str) -> bool:
        """접근 정책 삭제"""
        self.ensure_schema()
        with self._cursor() as (conn, cur):
            cur.execute("DELETE FROM access_policies WHERE tenant_id = %s AND access_policy_id = %s", (tenant_id, access_policy_id))
            deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    # ========================================
    # AI 컨텍스트 팩 (Oracle/LLM 소비용)
    # ========================================

    def get_ai_context(self, tenant_id: str, case_id: str | None = None) -> dict[str, Any]:
        """AI 소비용 시멘틱 컨텍스트 팩 — approved 객체만 포함

        Oracle NL2SQL이 raw schema 대신 이 컨텍스트를 소비한다.
        """
        self.ensure_schema()

        # approved 개념 + 용어
        concepts = self.list_concepts(tenant_id, case_id=case_id, status="approved", limit=500)
        concept_ids = {c["concept_id"] for c in concepts}

        # approved 엔티티/지표/차원을 SQL 레벨에서 필터 (단일 쿼리)
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        try:
            # 엔티티
            e_cond = "tenant_id = %s AND status = 'approved'"
            e_params: list[Any] = [tenant_id]
            if case_id:
                e_cond += " AND case_id = %s"
                e_params.append(case_id)
            cur.execute(f"SELECT * FROM semantic_entities WHERE {e_cond} LIMIT 500", e_params)
            entities = [dict(r) for r in cur.fetchall()]
            entity_ids = {e["entity_id"] for e in entities}

            # 지표
            cur.execute(f"SELECT * FROM semantic_measures WHERE {e_cond} LIMIT 500", e_params)
            all_measures = [dict(r) for r in cur.fetchall()]
            measures = [m for m in all_measures if m.get("entity_id") in entity_ids]

            # 차원
            cur.execute(f"SELECT * FROM semantic_dimensions WHERE {e_cond} LIMIT 500", e_params)
            all_dims = [dict(r) for r in cur.fetchall()]
            dimensions = [d for d in all_dims if d.get("entity_id") in entity_ids]
        finally:
            cur.close()
            conn.close()

        # AI 허용 조인만
        joins = self.list_join_contracts(tenant_id, case_id=case_id, allowed_for_ai=True, limit=500)

        # 용어 사전 — bulk 조회 (N+1 방지)
        all_terms = self.list_terms_by_concepts_bulk(tenant_id, list(concept_ids)) if concept_ids else []

        # 품질 계약
        quality = self.list_quality_contracts(tenant_id, case_id=case_id, limit=500)

        # 금지 조인
        banned_joins = self.list_join_contracts(tenant_id, case_id=case_id, allowed_for_ai=False, limit=500)

        return {
            "context_type": "semantic_contract",
            "approved_only": True,
            "summary": {
                "concepts": len(concepts),
                "entities": len(entities),
                "measures": len(measures),
                "dimensions": len(dimensions),
                "allowed_joins": len(joins),
                "banned_joins": len(banned_joins),
                "terms": len(all_terms),
            },
            "concepts": [
                {"concept_id": c["concept_id"], "name_ko": c["name_ko"], "name_en": c.get("name_en"),
                 "business_definition": c.get("business_definition"),
                 "default_time_semantics": c.get("default_time_semantics"),
                 "default_unit": c.get("default_unit")}
                for c in concepts
            ],
            "synonym_map": {t["surface_form"]: t["concept_id"] for t in all_terms},
            "entities": [
                {"entity_id": e["entity_id"], "physical_source_ref": e["physical_source_ref"],
                 "entity_type": e["entity_type"], "grain_definition": e.get("grain_definition"),
                 "bound_concept_id": e.get("bound_concept_id")}
                for e in entities
            ],
            "measures": [
                {"measure_id": m["measure_id"], "name": m["name"], "description": m.get("description"),
                 "measure_type": m["measure_type"], "sql_expression": m["sql_expression"],
                 "filter_expression": m.get("filter_expression"), "additive_type": m.get("additive_type"),
                 "entity_id": m["entity_id"], "bound_concept_id": m.get("bound_concept_id")}
                for m in measures
            ],
            "dimensions": [
                {"dimension_id": d["dimension_id"], "name": d["name"],
                 "sql_expression": d["sql_expression"], "value_type": d.get("value_type"),
                 "hierarchy_path": d.get("hierarchy_path"), "entity_id": d["entity_id"]}
                for d in dimensions
            ],
            "allowed_joins": [
                {"join_id": j["join_id"], "left_entity_id": j["left_entity_id"],
                 "right_entity_id": j["right_entity_id"], "join_type": j["join_type"],
                 "join_condition": j["join_condition"], "relationship_type": j["relationship_type"],
                 "fanout_risk_score": j.get("fanout_risk_score", 0)}
                for j in joins
            ],
            "banned_joins": [
                {"left_entity_id": j["left_entity_id"], "right_entity_id": j["right_entity_id"]}
                for j in banned_joins
            ],
            "quality_contracts": [
                {"target_type": q["target_type"], "target_id": q["target_id"],
                 "freshness_sla_minutes": q.get("freshness_sla_minutes"),
                 "completeness_threshold": float(q.get("completeness_threshold") or 95)}
                for q in quality
            ],
        }

    # ========================================
    # L5: AI 컨텍스트 팩 CRUD
    # ========================================

    def create_context_pack(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """AI 컨텍스트 팩 등록 — 의도별 시멘틱 컨텍스트 프리셋"""
        self.ensure_schema()
        intent = data.get("intent_type", "general")
        if intent not in VALID_INTENT_TYPES:
            raise ValueError(f"intent_type은 {VALID_INTENT_TYPES} 중 하나여야 합니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO context_packs (
                    context_pack_id, domain_id, intent_type, description,
                    included_concept_ids, included_measure_ids, included_dimension_ids,
                    allowed_join_ids, banned_join_ids, temporal_rules,
                    answer_guardrails, quality_gate_min_score,
                    tenant_id, case_id, version, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s)
            """, (
                data["context_pack_id"], data.get("domain_id", "default"), intent,
                data.get("description"),
                json.dumps(data.get("included_concept_ids", [])),
                json.dumps(data.get("included_measure_ids", [])),
                json.dumps(data.get("included_dimension_ids", [])),
                json.dumps(data.get("allowed_join_ids", [])),
                json.dumps(data.get("banned_join_ids", [])),
                json.dumps(data.get("temporal_rules")) if data.get("temporal_rules") else None,
                json.dumps(data.get("answer_guardrails", [])),
                data.get("quality_gate_min_score", 0.0),
                tenant_id, data.get("case_id", ""), now, now,
            ))
            # §4.9: CONTEXT_PACK_GENERATED 이벤트 발행
            from app.events.outbox import EventPublisher
            EventPublisher.publish(
                event_type="CONTEXT_PACK_GENERATED",
                aggregate_type="context_pack",
                aggregate_id=data["context_pack_id"],
                payload={
                    "context_pack_id": data["context_pack_id"],
                    "intent_type": intent,
                    "action": "created",
                    "tenant_id": tenant_id,
                },
                tenant_id=tenant_id,
                conn=conn,
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"context_pack_id '{data['context_pack_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"context_pack_id": data["context_pack_id"], "intent_type": intent, "version": 1, "created_at": now.isoformat()}

    def get_context_pack(self, tenant_id: str, context_pack_id: str) -> dict[str, Any] | None:
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute("SELECT * FROM context_packs WHERE tenant_id = %s AND context_pack_id = %s", (tenant_id, context_pack_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_context_packs(self, tenant_id: str, case_id: str | None = None, intent_type: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if case_id:
            conditions.append("case_id = %s")
            params.append(case_id)
        if intent_type:
            conditions.append("intent_type = %s")
            params.append(intent_type)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(f"SELECT * FROM context_packs WHERE {where} ORDER BY updated_at DESC LIMIT %s OFFSET %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_context_pack(self, tenant_id: str, context_pack_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.ensure_schema()
        existing = self.get_context_pack(tenant_id, context_pack_id)
        if not existing:
            raise KeyError(f"context_pack_id '{context_pack_id}'를 찾을 수 없습니다")
        update_fields = {k: v for k, v in data.items() if v is not None and k in _CONTEXT_PACK_UPDATABLE}
        if not update_fields:
            return existing
        if "intent_type" in update_fields and update_fields["intent_type"] not in VALID_INTENT_TYPES:
            raise ValueError(f"intent_type 유효하지 않음: {update_fields['intent_type']}")
        # JSONB 필드 직렬화
        for jf in ("included_concept_ids", "included_measure_ids", "included_dimension_ids",
                    "allowed_join_ids", "banned_join_ids", "answer_guardrails"):
            if jf in update_fields:
                update_fields[jf] = json.dumps(update_fields[jf])
        if "temporal_rules" in update_fields:
            update_fields["temporal_rules"] = json.dumps(update_fields["temporal_rules"])
        update_fields["version"] = (existing.get("version") or 1) + 1
        update_fields["updated_at"] = _now_dt()
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, context_pack_id]
        with self._cursor() as (conn, cur):
            cur.execute(f"UPDATE context_packs SET {set_clause} WHERE tenant_id = %s AND context_pack_id = %s", values)
            # §4.9: CONTEXT_PACK_GENERATED 이벤트 발행 (update)
            from app.events.outbox import EventPublisher
            EventPublisher.publish(
                event_type="CONTEXT_PACK_GENERATED",
                aggregate_type="context_pack",
                aggregate_id=context_pack_id,
                payload={
                    "context_pack_id": context_pack_id,
                    "intent_type": update_fields.get("intent_type", existing.get("intent_type", "general")),
                    "action": "updated",
                    "version": update_fields["version"],
                    "tenant_id": tenant_id,
                },
                tenant_id=tenant_id,
                conn=conn,
            )
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    def delete_context_pack(self, tenant_id: str, context_pack_id: str) -> bool:
        """컨텍스트 팩 삭제 (CASCADE로 prompt_policies도 삭제)"""
        self.ensure_schema()
        with self._cursor() as (conn, cur):
            cur.execute("DELETE FROM context_packs WHERE tenant_id = %s AND context_pack_id = %s", (tenant_id, context_pack_id))
            deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    # ========================================
    # L5: 프롬프트 정책 CRUD
    # ========================================

    def create_prompt_policy(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """프롬프트 정책 등록"""
        self.ensure_schema()
        rule_type = data.get("rule_type", "")
        if rule_type not in VALID_PROMPT_RULE_TYPES:
            raise ValueError(f"rule_type은 {VALID_PROMPT_RULE_TYPES} 중 하나여야 합니다")
        # 컨텍스트 팩 존재 확인
        pack = self.get_context_pack(tenant_id, data["context_pack_id"])
        if not pack:
            raise KeyError(f"context_pack_id '{data['context_pack_id']}'를 찾을 수 없습니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO prompt_policies (
                    prompt_policy_id, context_pack_id, rule_type, rule_text, priority,
                    tenant_id, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["prompt_policy_id"], data["context_pack_id"],
                rule_type, data["rule_text"], data.get("priority", 0),
                tenant_id, now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"prompt_policy_id '{data['prompt_policy_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"prompt_policy_id": data["prompt_policy_id"], "rule_type": rule_type, "created_at": now.isoformat()}

    def list_prompt_policies(self, tenant_id: str, context_pack_id: str) -> list[dict[str, Any]]:
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(
            "SELECT * FROM prompt_policies WHERE tenant_id = %s AND context_pack_id = %s ORDER BY priority DESC, created_at",
            (tenant_id, context_pack_id),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def delete_prompt_policy(self, tenant_id: str, prompt_policy_id: str) -> bool:
        self.ensure_schema()
        with self._cursor() as (conn, cur):
            cur.execute("DELETE FROM prompt_policies WHERE tenant_id = %s AND prompt_policy_id = %s", (tenant_id, prompt_policy_id))
            deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    # ========================================
    # L3: 온톨로지 규칙 CRUD
    # ========================================

    def create_rule(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """온톨로지 규칙 등록 — 개념에 바인딩되는 업무 규칙"""
        self.ensure_schema()
        rt = data.get("rule_type", "")
        if rt not in VALID_RULE_TYPES:
            raise ValueError(f"rule_type은 {VALID_RULE_TYPES} 중 하나여야 합니다")
        el = data.get("expression_lang", "sql")
        if el not in VALID_EXPRESSION_LANGS:
            raise ValueError(f"expression_lang은 {VALID_EXPRESSION_LANGS} 중 하나여야 합니다")
        # 개념 존재 확인
        concept = self.get_concept(tenant_id, data["concept_id"])
        if not concept:
            raise KeyError(f"concept_id '{data['concept_id']}'를 찾을 수 없습니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO ontology_rules (
                    rule_id, tenant_id, concept_id, rule_type,
                    rule_expression, expression_lang, severity, description,
                    created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["rule_id"], tenant_id, data["concept_id"], rt,
                data["rule_expression"], el,
                data.get("severity", "warning"), data.get("description"),
                now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"rule_id '{data['rule_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"rule_id": data["rule_id"], "concept_id": data["concept_id"],
                "rule_type": rt, "expression_lang": el, "created_at": now.isoformat()}

    def get_rule(self, tenant_id: str, rule_id: str) -> dict[str, Any] | None:
        """단건 규칙 조회"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute("SELECT * FROM ontology_rules WHERE tenant_id = %s AND rule_id = %s", (tenant_id, rule_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_rules(self, tenant_id: str, concept_id: str | None = None,
                   rule_type: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """규칙 목록 조회 — concept_id, rule_type 필터"""
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if concept_id:
            conditions.append("concept_id = %s")
            params.append(concept_id)
        if rule_type:
            conditions.append("rule_type = %s")
            params.append(rule_type)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(f"SELECT * FROM ontology_rules WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_rule(self, tenant_id: str, rule_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """규칙 수정 (PATCH 방식)"""
        self.ensure_schema()
        existing = self.get_rule(tenant_id, rule_id)
        if not existing:
            raise KeyError(f"rule_id '{rule_id}'를 찾을 수 없습니다")
        update_fields = {k: v for k, v in data.items() if v is not None and k in _ONTOLOGY_RULE_UPDATABLE}
        if not update_fields:
            return existing
        if "rule_type" in update_fields and update_fields["rule_type"] not in VALID_RULE_TYPES:
            raise ValueError(f"rule_type 유효하지 않음: {update_fields['rule_type']}")
        if "expression_lang" in update_fields and update_fields["expression_lang"] not in VALID_EXPRESSION_LANGS:
            raise ValueError(f"expression_lang 유효하지 않음: {update_fields['expression_lang']}")
        update_fields["updated_at"] = _now_dt()
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, rule_id]
        with self._cursor() as (conn, cur):
            cur.execute(f"UPDATE ontology_rules SET {set_clause} WHERE tenant_id = %s AND rule_id = %s", values)
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    def delete_rule(self, tenant_id: str, rule_id: str) -> bool:
        """규칙 삭제"""
        self.ensure_schema()
        with self._cursor() as (conn, cur):
            cur.execute("DELETE FROM ontology_rules WHERE tenant_id = %s AND rule_id = %s", (tenant_id, rule_id))
            deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    # ========================================
    # L3: 온톨로지 정책 CRUD
    # ========================================

    def create_policy(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """온톨로지 정책 등록 — 접근/PII/보존/거주지/집계 거버넌스 정책"""
        self.ensure_schema()
        pt = data.get("policy_type", "")
        if pt not in VALID_POLICY_TYPES:
            raise ValueError(f"policy_type은 {VALID_POLICY_TYPES} 중 하나여야 합니다")
        concept = self.get_concept(tenant_id, data["concept_id"])
        if not concept:
            raise KeyError(f"concept_id '{data['concept_id']}'를 찾을 수 없습니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO ontology_policies (
                    policy_id, tenant_id, concept_id, policy_type,
                    policy_expression, description, is_active,
                    created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["policy_id"], tenant_id, data["concept_id"], pt,
                data["policy_expression"], data.get("description"),
                data.get("is_active", True), now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"policy_id '{data['policy_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {"policy_id": data["policy_id"], "concept_id": data["concept_id"],
                "policy_type": pt, "is_active": data.get("is_active", True), "created_at": now.isoformat()}

    def get_policy(self, tenant_id: str, policy_id: str) -> dict[str, Any] | None:
        """단건 정책 조회"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute("SELECT * FROM ontology_policies WHERE tenant_id = %s AND policy_id = %s", (tenant_id, policy_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_policies(self, tenant_id: str, concept_id: str | None = None,
                      policy_type: str | None = None, is_active: bool | None = None,
                      limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """정책 목록 조회 — concept_id, policy_type, is_active 필터"""
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if concept_id:
            conditions.append("concept_id = %s")
            params.append(concept_id)
        if policy_type:
            conditions.append("policy_type = %s")
            params.append(policy_type)
        if is_active is not None:
            conditions.append("is_active = %s")
            params.append(is_active)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(f"SELECT * FROM ontology_policies WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s", params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_policy(self, tenant_id: str, policy_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """정책 수정 (PATCH 방식)"""
        self.ensure_schema()
        existing = self.get_policy(tenant_id, policy_id)
        if not existing:
            raise KeyError(f"policy_id '{policy_id}'를 찾을 수 없습니다")
        update_fields = {k: v for k, v in data.items() if v is not None and k in _ONTOLOGY_POLICY_UPDATABLE}
        if not update_fields:
            return existing
        if "policy_type" in update_fields and update_fields["policy_type"] not in VALID_POLICY_TYPES:
            raise ValueError(f"policy_type 유효하지 않음: {update_fields['policy_type']}")
        update_fields["updated_at"] = _now_dt()
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, policy_id]
        with self._cursor() as (conn, cur):
            cur.execute(f"UPDATE ontology_policies SET {set_clause} WHERE tenant_id = %s AND policy_id = %s", values)
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    def delete_policy(self, tenant_id: str, policy_id: str) -> bool:
        """정책 삭제"""
        self.ensure_schema()
        with self._cursor() as (conn, cur):
            cur.execute("DELETE FROM ontology_policies WHERE tenant_id = %s AND policy_id = %s", (tenant_id, policy_id))
            deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    # ========================================
    # L4: Reasoning & Governance — 충돌 탐지 + 영향 분석
    # ========================================

    def detect_conflicts(self, tenant_id: str) -> dict[str, Any]:
        """동일 이름/용어를 가진 서로 다른 개념/지표를 탐지한다 (L4 거버넌스).

        세 가지 종류의 충돌을 감지한다:
        1. concept_conflicts: 동일 name_ko 또는 name_en을 공유하는 서로 다른 개념
        2. measure_conflicts: 동일 name을 공유하는 서로 다른 지표
        3. term_collisions: 동일 surface_form이 서로 다른 concept_id에 매핑된 용어
        """
        self.ensure_schema()
        concept_conflicts: list[dict] = []
        measure_conflicts: list[dict] = []
        term_collisions: list[dict] = []

        with self._cursor(dict_cursor=True) as (conn, cur):
            # 1) 개념 이름 충돌 — name_ko 기준
            cur.execute("""
                SELECT name_ko, array_agg(concept_id) AS concept_ids,
                       array_agg(COALESCE(description, '')) AS descriptions
                FROM ontology_concepts
                WHERE tenant_id = %s AND status != 'deprecated'
                  AND name_ko IS NOT NULL AND name_ko != ''
                GROUP BY name_ko
                HAVING COUNT(*) > 1
            """, (tenant_id,))
            for row in cur.fetchall():
                concept_conflicts.append({
                    "name": row["name_ko"],
                    "field": "name_ko",
                    "concept_ids": row["concept_ids"],
                    "descriptions": row["descriptions"],
                })

            # 2) 개념 이름 충돌 — name_en 기준
            cur.execute("""
                SELECT name_en, array_agg(concept_id) AS concept_ids,
                       array_agg(COALESCE(description, '')) AS descriptions
                FROM ontology_concepts
                WHERE tenant_id = %s AND status != 'deprecated'
                  AND name_en IS NOT NULL AND name_en != ''
                GROUP BY name_en
                HAVING COUNT(*) > 1
            """, (tenant_id,))
            for row in cur.fetchall():
                concept_conflicts.append({
                    "name": row["name_en"],
                    "field": "name_en",
                    "concept_ids": row["concept_ids"],
                    "descriptions": row["descriptions"],
                })

            # 3) 지표 이름 충돌 — 동일 name이 서로 다른 지표에 존재
            cur.execute("""
                SELECT name, array_agg(measure_id) AS measure_ids,
                       array_agg(COALESCE(bound_concept_id, '')) AS concept_ids
                FROM semantic_measures
                WHERE tenant_id = %s AND status != 'deprecated'
                GROUP BY name
                HAVING COUNT(*) > 1
            """, (tenant_id,))
            for row in cur.fetchall():
                measure_conflicts.append({
                    "name": row["name"],
                    "measure_ids": row["measure_ids"],
                    "concept_ids": row["concept_ids"],
                })

            # 4) 용어 충돌 — 동일 surface_form이 서로 다른 concept_id에 매핑
            cur.execute("""
                SELECT surface_form, array_agg(DISTINCT concept_id) AS concept_ids
                FROM ontology_terms
                WHERE tenant_id = %s
                GROUP BY surface_form
                HAVING COUNT(DISTINCT concept_id) > 1
            """, (tenant_id,))
            for row in cur.fetchall():
                term_collisions.append({
                    "surface_form": row["surface_form"],
                    "concept_ids": row["concept_ids"],
                })

        return {
            "concept_conflicts": concept_conflicts,
            "measure_conflicts": measure_conflicts,
            "term_collisions": term_collisions,
        }

    def analyze_impact(self, tenant_id: str, object_type: str, object_id: str) -> dict[str, Any]:
        """특정 객체 변경 시 영향받는 downstream 객체 목록을 반환한다 (L4 거버넌스).

        지원하는 object_type: concept, measure, entity, join, dimension
        각 타입에 따라 연관된 하위 객체를 SQL로 조회한다.
        """
        self.ensure_schema()

        affected: dict[str, list[str]] = {
            "context_packs": [],
            "entities": [],
            "measures": [],
            "dimensions": [],
            "joins": [],
            "grains": [],
        }

        with self._cursor(dict_cursor=True) as (conn, cur):
            if object_type == "concept":
                # 개념에 바인딩된 엔티티
                cur.execute(
                    "SELECT entity_id FROM semantic_entities WHERE tenant_id = %s AND bound_concept_id = %s",
                    (tenant_id, object_id),
                )
                affected["entities"] = [r["entity_id"] for r in cur.fetchall()]

                # 개념에 바인딩된 지표
                cur.execute(
                    "SELECT measure_id FROM semantic_measures WHERE tenant_id = %s AND bound_concept_id = %s",
                    (tenant_id, object_id),
                )
                affected["measures"] = [r["measure_id"] for r in cur.fetchall()]

                # 개념에 바인딩된 차원
                cur.execute(
                    "SELECT dimension_id FROM semantic_dimensions WHERE tenant_id = %s AND bound_concept_id = %s",
                    (tenant_id, object_id),
                )
                affected["dimensions"] = [r["dimension_id"] for r in cur.fetchall()]

                # 개념을 포함하는 컨텍스트 팩 (JSONB 배열 검색)
                cur.execute(
                    "SELECT context_pack_id FROM context_packs WHERE tenant_id = %s AND included_concept_ids @> %s::jsonb",
                    (tenant_id, json.dumps([object_id])),
                )
                affected["context_packs"] = [r["context_pack_id"] for r in cur.fetchall()]

            elif object_type == "entity":
                # 엔티티에 바인딩된 지표
                cur.execute(
                    "SELECT measure_id FROM semantic_measures WHERE tenant_id = %s AND entity_id = %s",
                    (tenant_id, object_id),
                )
                affected["measures"] = [r["measure_id"] for r in cur.fetchall()]

                # 엔티티에 바인딩된 차원
                cur.execute(
                    "SELECT dimension_id FROM semantic_dimensions WHERE tenant_id = %s AND entity_id = %s",
                    (tenant_id, object_id),
                )
                affected["dimensions"] = [r["dimension_id"] for r in cur.fetchall()]

                # 엔티티를 참조하는 조인 계약
                cur.execute(
                    "SELECT join_id FROM join_contracts WHERE tenant_id = %s AND (left_entity_id = %s OR right_entity_id = %s)",
                    (tenant_id, object_id, object_id),
                )
                affected["joins"] = [r["join_id"] for r in cur.fetchall()]

                # 엔티티를 참조하는 그레인 계약
                cur.execute(
                    "SELECT grain_id FROM grain_contracts WHERE tenant_id = %s AND entity_id = %s",
                    (tenant_id, object_id),
                )
                affected["grains"] = [r["grain_id"] for r in cur.fetchall()]

            elif object_type == "measure":
                # 지표의 entity_id 조회
                cur.execute(
                    "SELECT entity_id FROM semantic_measures WHERE tenant_id = %s AND measure_id = %s",
                    (tenant_id, object_id),
                )
                row = cur.fetchone()
                if row:
                    affected["entities"] = [row["entity_id"]]

                    # 해당 엔티티를 참조하는 조인 계약
                    cur.execute(
                        "SELECT join_id FROM join_contracts WHERE tenant_id = %s AND (left_entity_id = %s OR right_entity_id = %s)",
                        (tenant_id, row["entity_id"], row["entity_id"]),
                    )
                    affected["joins"] = [r["join_id"] for r in cur.fetchall()]

                # 지표를 포함하는 컨텍스트 팩
                cur.execute(
                    "SELECT context_pack_id FROM context_packs WHERE tenant_id = %s AND included_measure_ids @> %s::jsonb",
                    (tenant_id, json.dumps([object_id])),
                )
                affected["context_packs"] = [r["context_pack_id"] for r in cur.fetchall()]

            elif object_type == "dimension":
                # 차원의 entity_id 조회
                cur.execute(
                    "SELECT entity_id FROM semantic_dimensions WHERE tenant_id = %s AND dimension_id = %s",
                    (tenant_id, object_id),
                )
                row = cur.fetchone()
                if row:
                    affected["entities"] = [row["entity_id"]]

                # 차원을 포함하는 컨텍스트 팩
                cur.execute(
                    "SELECT context_pack_id FROM context_packs WHERE tenant_id = %s AND included_dimension_ids @> %s::jsonb",
                    (tenant_id, json.dumps([object_id])),
                )
                affected["context_packs"] = [r["context_pack_id"] for r in cur.fetchall()]

            elif object_type == "join":
                # 조인을 포함/금지하는 컨텍스트 팩
                cur.execute(
                    """SELECT context_pack_id FROM context_packs
                       WHERE tenant_id = %s AND (
                           allowed_join_ids @> %s::jsonb OR banned_join_ids @> %s::jsonb
                       )""",
                    (tenant_id, json.dumps([object_id]), json.dumps([object_id])),
                )
                affected["context_packs"] = [r["context_pack_id"] for r in cur.fetchall()]

                # 조인의 양쪽 엔티티
                cur.execute(
                    "SELECT left_entity_id, right_entity_id FROM join_contracts WHERE tenant_id = %s AND join_id = %s",
                    (tenant_id, object_id),
                )
                row = cur.fetchone()
                if row:
                    affected["entities"] = [row["left_entity_id"], row["right_entity_id"]]

        # 총 영향 수 계산
        total = sum(len(v) for v in affected.values())

        return {
            "object_type": object_type,
            "object_id": object_id,
            "affected": affected,
            "total_affected": total,
        }

    # ========================================
    # L5: 컨텍스트 팩 해석 (resolve)
    # ========================================

    def resolve_context_pack(self, tenant_id: str, context_pack_id: str) -> dict[str, Any]:
        """컨텍스트 팩을 해석하여 실제 시멘틱 객체 + 프롬프트 정책을 조합한다.

        Oracle이 의도별 LLM 컨텍스트를 구성할 때 이 메서드를 호출한다.
        """
        pack = self.get_context_pack(tenant_id, context_pack_id)
        if not pack:
            raise KeyError(f"context_pack_id '{context_pack_id}'를 찾을 수 없습니다")

        # JSONB 필드 파싱 (이미 dict/list이면 그대로)
        def _parse(v):
            if isinstance(v, str):
                return json.loads(v)
            return v or []

        concept_ids = _parse(pack.get("included_concept_ids"))
        measure_ids = _parse(pack.get("included_measure_ids"))
        dimension_ids = _parse(pack.get("included_dimension_ids"))
        allowed_join_ids = _parse(pack.get("allowed_join_ids"))
        banned_join_ids = _parse(pack.get("banned_join_ids"))
        guardrails = _parse(pack.get("answer_guardrails"))

        # 실제 객체 조회
        concepts = [self.get_concept(tenant_id, cid) for cid in concept_ids]
        concepts = [c for c in concepts if c]

        measures = [self.get_measure(tenant_id, mid) for mid in measure_ids]
        measures = [m for m in measures if m]

        dimensions = [self.get_dimension(tenant_id, did) for did in dimension_ids]
        dimensions = [d for d in dimensions if d]

        allowed_joins = [self.get_join_contract(tenant_id, jid) for jid in allowed_join_ids]
        allowed_joins = [j for j in allowed_joins if j]

        banned_joins = [self.get_join_contract(tenant_id, jid) for jid in banned_join_ids]
        banned_joins = [j for j in banned_joins if j]

        # 용어 — 포함된 개념의 용어만
        terms = self.list_terms_by_concepts_bulk(tenant_id, concept_ids) if concept_ids else []

        # 프롬프트 정책
        policies = self.list_prompt_policies(tenant_id, context_pack_id)

        return {
            "context_pack_id": context_pack_id,
            "intent_type": pack.get("intent_type"),
            "quality_gate_min_score": float(pack.get("quality_gate_min_score") or 0),
            "concepts": concepts,
            "measures": measures,
            "dimensions": dimensions,
            "allowed_joins": allowed_joins,
            "banned_joins": banned_joins,
            "synonym_map": {t["surface_form"]: t["concept_id"] for t in terms},
            "answer_guardrails": guardrails,
            "temporal_rules": _parse(pack.get("temporal_rules")) if pack.get("temporal_rules") else {},
            "prompt_policies": [
                {"rule_type": p["rule_type"], "rule_text": p["rule_text"], "priority": p.get("priority", 0)}
                for p in policies
            ],
        }

    # ========================================
    # P3 §5.3: ML/Feature Source 바인딩
    # ========================================

    def list_feature_sources(self, tenant_id: str, case_id: str | None = None,
                              limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """feature_source 타입 엔티티만 조회한다."""
        self.ensure_schema()
        conditions = ["tenant_id = %s", "entity_type = 'feature_source'"]
        params: list[Any] = [tenant_id]
        if case_id:
            conditions.append("case_id = %s")
            params.append(case_id)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(
            f"SELECT * FROM semantic_entities WHERE {where} ORDER BY updated_at DESC LIMIT %s OFFSET %s",
            params,
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def generate_training_query(self, tenant_id: str, entity_id: str,
                                 columns: list[str] | None = None,
                                 date_range: dict[str, str] | None = None) -> dict[str, Any]:
        """피처 엔티티 기반 학습 데이터셋 SQL을 생성한다.

        feature_config.feature_columns 또는 사용자 지정 컬럼으로
        training_query_template을 렌더링한다.
        """
        self.ensure_schema()
        entity = self.get_entity(tenant_id, entity_id)
        if not entity:
            raise KeyError(f"entity_id '{entity_id}'를 찾을 수 없습니다")
        if entity.get("entity_type") != "feature_source":
            raise ValueError(f"entity_id '{entity_id}'의 타입이 feature_source가 아닙니다: {entity.get('entity_type')}")

        # feature_config 파싱 (JSONB → dict)
        fc = entity.get("feature_config")
        if isinstance(fc, str):
            fc = json.loads(fc)
        if not fc:
            raise ValueError(f"entity_id '{entity_id}'에 feature_config가 설정되지 않았습니다")

        # 컬럼 결정: 사용자 지정 → feature_columns → *
        use_columns = columns or fc.get("feature_columns") or ["*"]
        col_str = ", ".join(use_columns)

        # 소스 테이블
        source = entity.get("physical_source_ref", "UNKNOWN_SOURCE")

        # 날짜 필터 생성
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

        # 템플릿 기반 SQL 생성 (기본 템플릿 제공)
        template = fc.get(
            "training_query_template",
            "SELECT {columns} FROM {entity_source} WHERE {date_filter}",
        )
        sql = template.format(
            columns=col_str,
            entity_source=source,
            date_filter=date_filter,
        )

        return {
            "sql": sql,
            "entity_id": entity_id,
            "columns": use_columns,
            "source": source,
            "date_range": date_range,
        }

    def check_feature_consistency(self, tenant_id: str, entity_id: str) -> dict[str, Any]:
        """BI 지표와 ML 피처 정의의 일관성을 검증한다.

        feature_source 엔티티에 바인딩된 시멘틱 지표(measure)의 sql_expression을
        동일 tenant의 fact 엔티티 지표와 비교하여 불일치를 보고한다.
        """
        self.ensure_schema()
        entity = self.get_entity(tenant_id, entity_id)
        if not entity:
            raise KeyError(f"entity_id '{entity_id}'를 찾을 수 없습니다")
        if entity.get("entity_type") != "feature_source":
            raise ValueError(f"entity_id '{entity_id}'의 타입이 feature_source가 아닙니다")

        # 해당 feature_source 엔티티의 지표 목록
        feature_measures = self.list_measures(tenant_id, entity_id=entity_id)

        # 동일 tenant의 fact 엔티티 지표 전체 (이름 기반 매칭)
        all_measures = self.list_measures(tenant_id, limit=500)
        # fact 엔티티에 속한 지표만 필터 (자기 자신 제외)
        bi_measures_by_name: dict[str, dict] = {}
        for m in all_measures:
            if m.get("entity_id") == entity_id:
                continue  # 자기 자신 제외
            # 이름으로 매핑 (첫 번째 발견된 것을 사용)
            mname = m.get("name", "")
            if mname and mname not in bi_measures_by_name:
                bi_measures_by_name[mname] = m

        mismatches: list[dict[str, Any]] = []
        matched = 0
        for fm in feature_measures:
            fname = fm.get("name", "")
            if fname in bi_measures_by_name:
                bi_m = bi_measures_by_name[fname]
                # sql_expression 비교 (공백 정규화)
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
            # BI에 대응하는 지표가 없으면 불일치로 취급하지 않음 (ML 전용 피처)

        return {
            "entity_id": entity_id,
            "consistent": len(mismatches) == 0,
            "total_feature_measures": len(feature_measures),
            "matched": matched,
            "mismatches": mismatches,
        }

    # ========================================
    # 온톨로지 관계 CRUD (§5.1 Neo4j 보완)
    # ========================================

    def create_relation(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """온톨로지 관계를 등록한다 — 양쪽 개념 존재 확인 + 자기참조 방지."""
        self.ensure_schema()

        # 술어 타입 유효성 검증
        pred = data.get("predicate_type", "")
        if pred not in VALID_PREDICATE_TYPES:
            raise ValueError(f"predicate_type은 {VALID_PREDICATE_TYPES} 중 하나여야 합니다: {pred}")

        # 기수성 검증
        card = data.get("cardinality", "1:N")
        if card not in VALID_CARDINALITIES:
            raise ValueError(f"cardinality는 {VALID_CARDINALITIES} 중 하나여야 합니다: {card}")

        # 방향성 검증
        dirn = data.get("directionality", "unidirectional")
        if dirn not in VALID_DIRECTIONALITIES:
            raise ValueError(f"directionality는 {VALID_DIRECTIONALITIES} 중 하나여야 합니다: {dirn}")

        # 자기참조 방지
        subj = data["subject_concept_id"]
        obj = data["object_concept_id"]
        if subj == obj:
            raise ValueError("subject_concept_id와 object_concept_id가 동일합니다 (자기참조 금지)")

        # 양쪽 개념 존재 확인
        if not self.get_concept(tenant_id, subj):
            raise KeyError(f"subject concept_id '{subj}'를 찾을 수 없습니다")
        if not self.get_concept(tenant_id, obj):
            raise KeyError(f"object concept_id '{obj}'를 찾을 수 없습니다")

        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO ontology_relations (
                    relation_id, tenant_id, subject_concept_id, predicate_type,
                    object_concept_id, cardinality, directionality,
                    weight, confidence, effective_from, effective_to,
                    created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["relation_id"], tenant_id, subj, pred, obj,
                card, dirn,
                data.get("weight", 1.0), data.get("confidence", 1.0),
                data.get("effective_from"), data.get("effective_to"),
                now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"relation_id '{data['relation_id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()

        return {
            "relation_id": data["relation_id"],
            "subject_concept_id": subj,
            "predicate_type": pred,
            "object_concept_id": obj,
            "cardinality": card,
            "directionality": dirn,
            "weight": data.get("weight", 1.0),
            "confidence": data.get("confidence", 1.0),
            "created_at": now.isoformat(),
        }

    def get_relation(self, tenant_id: str, relation_id: str) -> dict[str, Any] | None:
        """관계 단건 조회"""
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(
            "SELECT * FROM ontology_relations WHERE tenant_id = %s AND relation_id = %s",
            (tenant_id, relation_id),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    def list_relations(
        self, tenant_id: str,
        subject_id: str | None = None,
        object_id: str | None = None,
        predicate_type: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[dict[str, Any]]:
        """관계 목록 조회 — 주체/객체/술어 필터 지원"""
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if subject_id:
            conditions.append("subject_concept_id = %s")
            params.append(subject_id)
        if object_id:
            conditions.append("object_concept_id = %s")
            params.append(object_id)
        if predicate_type:
            conditions.append("predicate_type = %s")
            params.append(predicate_type)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        cur.execute(
            f"SELECT * FROM ontology_relations WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            params,
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

    def update_relation(self, tenant_id: str, relation_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """관계 수정 — None 필드 무시 (PATCH 방식)"""
        self.ensure_schema()
        existing = self.get_relation(tenant_id, relation_id)
        if not existing:
            raise KeyError(f"relation_id '{relation_id}'를 찾을 수 없습니다")

        update_fields = {k: v for k, v in data.items() if v is not None and k in _RELATION_UPDATABLE}
        if not update_fields:
            return existing

        # 유효성 검증
        if "predicate_type" in update_fields and update_fields["predicate_type"] not in VALID_PREDICATE_TYPES:
            raise ValueError(f"predicate_type 유효하지 않음: {update_fields['predicate_type']}")
        if "cardinality" in update_fields and update_fields["cardinality"] not in VALID_CARDINALITIES:
            raise ValueError(f"cardinality 유효하지 않음: {update_fields['cardinality']}")
        if "directionality" in update_fields and update_fields["directionality"] not in VALID_DIRECTIONALITIES:
            raise ValueError(f"directionality 유효하지 않음: {update_fields['directionality']}")

        update_fields["updated_at"] = _now_dt()
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, relation_id]
        with self._cursor() as (conn, cur):
            cur.execute(
                f"UPDATE ontology_relations SET {set_clause} WHERE tenant_id = %s AND relation_id = %s",
                values,
            )
            conn.commit()
        return {**existing, **update_fields, "updated_at": update_fields["updated_at"].isoformat()}

    def delete_relation(self, tenant_id: str, relation_id: str) -> bool:
        """관계 삭제 — 존재하면 삭제 후 True, 없으면 False 반환"""
        self.ensure_schema()
        with self._cursor() as (conn, cur):
            cur.execute(
                "DELETE FROM ontology_relations WHERE tenant_id = %s AND relation_id = %s",
                (tenant_id, relation_id),
            )
            deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    # ========================================
    # Sprint 4: 별칭 그룹 CRUD
    # ========================================

    def create_alias_group(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """별칭 그룹을 등록한다 — 여러 표면 형태를 정규 용어 클러스터로 묶기"""
        self.ensure_schema()
        status = data.get("status", "ACTIVE")
        if status not in VALID_ALIAS_GROUP_STATUSES:
            raise ValueError(f"status는 {VALID_ALIAS_GROUP_STATUSES} 중 하나여야 합니다: {status}")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO ontology_term_alias_groups (
                    id, tenant_id, domain_id, canonical_term_id,
                    group_name, language_code, status, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data["id"], tenant_id, data.get("domain_id", "global"),
                data["canonical_term_id"], data["group_name"],
                data.get("language_code", "ko"), status, now, now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"alias_group id '{data['id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {
            "id": data["id"], "tenant_id": tenant_id,
            "domain_id": data.get("domain_id", "global"),
            "canonical_term_id": data["canonical_term_id"],
            "group_name": data["group_name"],
            "language_code": data.get("language_code", "ko"),
            "status": status,
            "created_at": now.isoformat(), "updated_at": now.isoformat(),
        }

    def list_alias_groups(
        self, tenant_id: str, domain_id: str | None = None,
        status: str | None = None, limit: int = 100, offset: int = 0,
    ) -> list[dict[str, Any]]:
        """별칭 그룹 목록을 조회한다 — 도메인/상태 필터 지원"""
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if domain_id:
            conditions.append("domain_id = %s")
            params.append(domain_id)
        if status:
            conditions.append("status = %s")
            params.append(status)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        with self._cursor(dict_cursor=True) as (conn, cur):
            cur.execute(
                f"SELECT * FROM ontology_term_alias_groups WHERE {where} ORDER BY updated_at DESC LIMIT %s OFFSET %s",
                params,
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_alias_group(self, tenant_id: str, group_id: str) -> dict[str, Any] | None:
        """별칭 그룹 단건 조회"""
        self.ensure_schema()
        with self._cursor(dict_cursor=True) as (conn, cur):
            cur.execute(
                "SELECT * FROM ontology_term_alias_groups WHERE tenant_id = %s AND id = %s",
                (tenant_id, group_id),
            )
            row = cur.fetchone()
        return dict(row) if row else None

    # ========================================
    # Sprint 4: 확장 규칙 CRUD
    # ========================================

    def create_expansion_rule(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """확장 규칙을 등록한다 — 매칭 패턴 정의"""
        self.ensure_schema()
        rule_type = data.get("rule_type", "")
        if rule_type not in VALID_EXPANSION_RULE_TYPES:
            raise ValueError(f"rule_type은 {VALID_EXPANSION_RULE_TYPES} 중 하나여야 합니다: {rule_type}")
        status = data.get("status", "ACTIVE")
        if status not in VALID_EXPANSION_RULE_STATUSES:
            raise ValueError(f"status는 {VALID_EXPANSION_RULE_STATUSES} 중 하나여야 합니다: {status}")
        # 별칭 그룹 존재 확인
        group = self.get_alias_group(tenant_id, data["alias_group_id"])
        if not group:
            raise KeyError(f"alias_group_id '{data['alias_group_id']}'를 찾을 수 없습니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO ontology_term_expansion_rules (
                    id, tenant_id, domain_id, alias_group_id, rule_type,
                    match_pattern, normalized_pattern, boost, priority,
                    status, effective_from, effective_to, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data["id"], tenant_id, data.get("domain_id", "global"),
                data["alias_group_id"], rule_type,
                data["match_pattern"], data.get("normalized_pattern"),
                data.get("boost", 1.0), data.get("priority", 100),
                status, data.get("effective_from"), data.get("effective_to"), now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"expansion_rule id '{data['id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {
            "id": data["id"], "tenant_id": tenant_id,
            "domain_id": data.get("domain_id", "global"),
            "alias_group_id": data["alias_group_id"],
            "rule_type": rule_type,
            "match_pattern": data["match_pattern"],
            "normalized_pattern": data.get("normalized_pattern"),
            "boost": data.get("boost", 1.0),
            "priority": data.get("priority", 100),
            "status": status, "created_at": now.isoformat(),
        }

    def list_expansion_rules(
        self, tenant_id: str, alias_group_id: str | None = None,
        rule_type: str | None = None, status: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[dict[str, Any]]:
        """확장 규칙 목록 조회 — 그룹/타입/상태 필터 지원"""
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if alias_group_id:
            conditions.append("alias_group_id = %s")
            params.append(alias_group_id)
        if rule_type:
            conditions.append("rule_type = %s")
            params.append(rule_type)
        if status:
            conditions.append("status = %s")
            params.append(status)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        with self._cursor(dict_cursor=True) as (conn, cur):
            cur.execute(
                f"SELECT * FROM ontology_term_expansion_rules WHERE {where} ORDER BY priority DESC, created_at DESC LIMIT %s OFFSET %s",
                params,
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def update_expansion_rule(self, tenant_id: str, rule_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """확장 규칙 수정 — 허용된 필드만 업데이트"""
        self.ensure_schema()
        _RULE_UPDATABLE = {"rule_type", "match_pattern", "normalized_pattern", "boost", "priority", "effective_from", "effective_to"}
        # 기존 규칙 확인
        with self._cursor(dict_cursor=True) as (conn, cur):
            cur.execute(
                "SELECT * FROM ontology_term_expansion_rules WHERE tenant_id = %s AND id = %s",
                (tenant_id, rule_id),
            )
            existing = cur.fetchone()
        if not existing:
            raise KeyError(f"expansion_rule id '{rule_id}'를 찾을 수 없습니다")
        existing = dict(existing)
        update_fields = {k: v for k, v in data.items() if v is not None and k in _RULE_UPDATABLE}
        if not update_fields:
            return existing
        if "rule_type" in update_fields and update_fields["rule_type"] not in VALID_EXPANSION_RULE_TYPES:
            raise ValueError(f"rule_type 유효하지 않음: {update_fields['rule_type']}")
        set_clause = ", ".join(f"{k} = %s" for k in update_fields)
        values = list(update_fields.values()) + [tenant_id, rule_id]
        with self._cursor() as (conn, cur):
            cur.execute(
                f"UPDATE ontology_term_expansion_rules SET {set_clause} WHERE tenant_id = %s AND id = %s",
                values,
            )
            conn.commit()
        return {**existing, **update_fields}

    def activate_rule(self, tenant_id: str, rule_id: str) -> dict[str, Any]:
        """확장 규칙을 ACTIVE 상태로 전환한다"""
        self.ensure_schema()
        with self._cursor(dict_cursor=True) as (conn, cur):
            cur.execute(
                "SELECT * FROM ontology_term_expansion_rules WHERE tenant_id = %s AND id = %s",
                (tenant_id, rule_id),
            )
            row = cur.fetchone()
        if not row:
            raise KeyError(f"expansion_rule id '{rule_id}'를 찾을 수 없습니다")
        row = dict(row)
        if row["status"] == "ACTIVE":
            return row
        with self._cursor() as (conn, cur):
            cur.execute(
                "UPDATE ontology_term_expansion_rules SET status = 'ACTIVE' WHERE tenant_id = %s AND id = %s",
                (tenant_id, rule_id),
            )
            conn.commit()
        row["status"] = "ACTIVE"
        return row

    def deprecate_rule(self, tenant_id: str, rule_id: str) -> dict[str, Any]:
        """확장 규칙을 DEPRECATED 상태로 전환한다"""
        self.ensure_schema()
        with self._cursor(dict_cursor=True) as (conn, cur):
            cur.execute(
                "SELECT * FROM ontology_term_expansion_rules WHERE tenant_id = %s AND id = %s",
                (tenant_id, rule_id),
            )
            row = cur.fetchone()
        if not row:
            raise KeyError(f"expansion_rule id '{rule_id}'를 찾을 수 없습니다")
        row = dict(row)
        if row["status"] == "DEPRECATED":
            return row
        with self._cursor() as (conn, cur):
            cur.execute(
                "UPDATE ontology_term_expansion_rules SET status = 'DEPRECATED' WHERE tenant_id = %s AND id = %s",
                (tenant_id, rule_id),
            )
            conn.commit()
        row["status"] = "DEPRECATED"
        return row

    # ========================================
    # Sprint 4: 의도 모델 CRUD
    # ========================================

    def create_intent_model(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """의도 분류 모델을 등록한다"""
        self.ensure_schema()
        model_type = data.get("model_type", "keyword")
        if model_type not in VALID_INTENT_MODEL_TYPES:
            raise ValueError(f"model_type은 {VALID_INTENT_MODEL_TYPES} 중 하나여야 합니다: {model_type}")
        now = _now_dt()
        config = data.get("config_json", {})
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO intent_models (
                    id, tenant_id, model_key, model_version,
                    model_type, status, config_json, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data["id"], tenant_id, data["model_key"], data["model_version"],
                model_type, data.get("status", "ACTIVE"),
                json.dumps(config), now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"intent_model id '{data['id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {
            "id": data["id"], "tenant_id": tenant_id,
            "model_key": data["model_key"], "model_version": data["model_version"],
            "model_type": model_type, "status": data.get("status", "ACTIVE"),
            "config_json": config, "created_at": now.isoformat(),
        }

    def list_intent_models(
        self, tenant_id: str, status: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[dict[str, Any]]:
        """의도 분류 모델 목록 조회"""
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if status:
            conditions.append("status = %s")
            params.append(status)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        with self._cursor(dict_cursor=True) as (conn, cur):
            cur.execute(
                f"SELECT * FROM intent_models WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params,
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ========================================
    # Sprint 4: 추론 로그 CRUD
    # ========================================

    def create_inference_log(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """의도 추론 로그를 기록한다 — Oracle에서 호출"""
        self.ensure_schema()
        now = _now_dt()
        feature_json = data.get("feature_json", {})
        candidate_json = data.get("candidate_json", {})
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO intent_inference_logs (
                    id, tenant_id, request_id, snapshot_version,
                    user_question, normalized_question, top_intent,
                    confidence, ambiguity_score, fallback_mode,
                    feature_json, candidate_json, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data["id"], tenant_id, data["request_id"],
                data.get("snapshot_version"), data["user_question"],
                data.get("normalized_question", ""), data.get("top_intent"),
                data.get("confidence"), data.get("ambiguity_score"),
                data.get("fallback_mode"),
                json.dumps(feature_json), json.dumps(candidate_json), now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"inference_log id '{data['id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {
            "id": data["id"], "tenant_id": tenant_id,
            "request_id": data["request_id"],
            "user_question": data["user_question"],
            "top_intent": data.get("top_intent"),
            "confidence": data.get("confidence"),
            "created_at": now.isoformat(),
        }

    def list_inference_logs(
        self, tenant_id: str, limit: int = 50, offset: int = 0,
    ) -> list[dict[str, Any]]:
        """추론 로그 목록 조회 — 최근순"""
        self.ensure_schema()
        with self._cursor(dict_cursor=True) as (conn, cur):
            cur.execute(
                "SELECT * FROM intent_inference_logs WHERE tenant_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (tenant_id, limit, offset),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ========================================
    # Sprint 4: 질문 피드백 CRUD
    # ========================================

    def create_question_feedback(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """질문 이해 피드백을 등록한다 — 운영자 교정 기록"""
        self.ensure_schema()
        issue_type = data.get("issue_type", "")
        if issue_type not in VALID_FEEDBACK_ISSUE_TYPES:
            raise ValueError(f"issue_type은 {VALID_FEEDBACK_ISSUE_TYPES} 중 하나여야 합니다: {issue_type}")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO semantic_question_feedback (
                    id, tenant_id, request_id, issue_type,
                    expected_intent, expected_concept_id, expected_measure_id,
                    feedback_note, resolved, created_by, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data["id"], tenant_id, data["request_id"], issue_type,
                data.get("expected_intent"), data.get("expected_concept_id"),
                data.get("expected_measure_id"), data.get("feedback_note"),
                False, data.get("created_by"), now,
            ))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"feedback id '{data['id']}'가 이미 존재합니다") from exc
            raise
        finally:
            cur.close()
            conn.close()
        return {
            "id": data["id"], "tenant_id": tenant_id,
            "request_id": data["request_id"], "issue_type": issue_type,
            "expected_intent": data.get("expected_intent"),
            "resolved": False, "created_at": now.isoformat(),
        }

    def list_question_feedback(
        self, tenant_id: str, resolved: bool | None = None,
        limit: int = 50, offset: int = 0,
    ) -> list[dict[str, Any]]:
        """질문 피드백 목록 조회 — 해결 여부 필터 지원"""
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if resolved is not None:
            conditions.append("resolved = %s")
            params.append(resolved)
        where = " AND ".join(conditions)
        params.extend([limit, offset])
        with self._cursor(dict_cursor=True) as (conn, cur):
            cur.execute(
                f"SELECT * FROM semantic_question_feedback WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params,
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def resolve_feedback(self, tenant_id: str, feedback_id: str) -> dict[str, Any]:
        """피드백을 해결 완료 상태로 전환한다"""
        self.ensure_schema()
        with self._cursor(dict_cursor=True) as (conn, cur):
            cur.execute(
                "SELECT * FROM semantic_question_feedback WHERE tenant_id = %s AND id = %s",
                (tenant_id, feedback_id),
            )
            row = cur.fetchone()
        if not row:
            raise KeyError(f"feedback id '{feedback_id}'를 찾을 수 없습니다")
        row = dict(row)
        if row["resolved"]:
            return row
        with self._cursor() as (conn, cur):
            cur.execute(
                "UPDATE semantic_question_feedback SET resolved = TRUE WHERE tenant_id = %s AND id = %s",
                (tenant_id, feedback_id),
            )
            conn.commit()
        row["resolved"] = True
        return row
