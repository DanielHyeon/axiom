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
}
_ENTITY_UPDATABLE = {
    "bound_concept_id", "physical_source_ref", "entity_type", "grain_definition",
    "primary_key_spec", "default_filters", "freshness_sla_minutes", "version", "updated_at",
}
_MEASURE_UPDATABLE = {
    "bound_concept_id", "entity_id", "name", "description", "measure_type",
    "sql_expression", "filter_expression", "numerator_measure_id", "denominator_measure_id",
    "additive_type", "default_agg_window", "owner_team", "version", "updated_at",
}
_DIMENSION_UPDATABLE = {
    "bound_concept_id", "entity_id", "name", "sql_expression", "value_type",
    "hierarchy_path", "conformed_group", "version", "updated_at",
}
_JOIN_UPDATABLE = {
    "join_type", "join_condition", "relationship_type", "allowed_for_ai",
    "fanout_risk_score", "updated_at",
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
                tenant_id             VARCHAR NOT NULL,
                case_id               VARCHAR NOT NULL,
                status                VARCHAR NOT NULL DEFAULT 'draft',
                version               INTEGER NOT NULL DEFAULT 1,
                created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
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

        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO ontology_concepts (
                    concept_id, case_id, domain_id, name_ko, name_en,
                    description, business_definition, status, owner_team, steward_user,
                    sensitivity_level, default_time_semantics, default_unit,
                    version, tenant_id, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s
                )
            """, (
                data["concept_id"], data["case_id"], data.get("domain_id", "default"),
                data["name_ko"], data.get("name_en"),
                data.get("description"), data.get("business_definition"),
                status, data.get("owner_team"), data.get("steward_user"),
                sens, data.get("default_time_semantics"), data.get("default_unit"),
                tenant_id, now, now,
            ))
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
    ) -> list[dict[str, Any]]:
        """개념 목록 조회 (상태/케이스 필터)"""
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

    def change_concept_status(self, tenant_id: str, concept_id: str, new_status: str) -> dict[str, Any]:
        """개념 상태 전이 — 허용된 전이만 가능"""
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
            cur.execute(
                "UPDATE ontology_concepts SET status = %s, updated_at = %s WHERE tenant_id = %s AND concept_id = %s",
                (new_status, now, tenant_id, concept_id),
            )
            conn.commit()
        return {**existing, "status": new_status, "updated_at": now.isoformat()}

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
        now = _now_dt()
        filters_json = json.dumps(data.get("default_filters")) if data.get("default_filters") else None
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO semantic_entities (
                    entity_id, bound_concept_id, physical_source_ref, entity_type,
                    grain_definition, primary_key_spec, default_filters, freshness_sla_minutes,
                    tenant_id, case_id, status, version, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', 1, %s, %s)
            """, (
                data["entity_id"], data.get("bound_concept_id"),
                data["physical_source_ref"], etype,
                data.get("grain_definition"), data.get("primary_key_spec"),
                filters_json, data.get("freshness_sla_minutes"),
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
        return {"entity_id": data["entity_id"], "status": "draft", "version": 1, "created_at": now.isoformat()}

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

    def list_entities(self, tenant_id: str, case_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        self.ensure_schema()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=self._dict_cursor())
        if case_id:
            cur.execute(
                "SELECT * FROM semantic_entities WHERE tenant_id = %s AND case_id = %s ORDER BY updated_at DESC LIMIT %s OFFSET %s",
                (tenant_id, case_id, limit, offset),
            )
        else:
            cur.execute(
                "SELECT * FROM semantic_entities WHERE tenant_id = %s ORDER BY updated_at DESC LIMIT %s OFFSET %s",
                (tenant_id, limit, offset),
            )
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
                    tenant_id, case_id, status, version, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft',1,%s,%s)
            """, (
                data["measure_id"], data.get("bound_concept_id"), data["entity_id"],
                data["name"], data.get("description"),
                mtype, data["sql_expression"], data.get("filter_expression"),
                data.get("numerator_measure_id"), data.get("denominator_measure_id"),
                atype, data.get("default_agg_window"), data.get("owner_team"),
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

    def list_measures(self, tenant_id: str, case_id: str | None = None, entity_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
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
                    tenant_id, case_id, status, version, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft',1,%s,%s)
            """, (
                data["dimension_id"], data.get("bound_concept_id"), data["entity_id"],
                data["name"], data["sql_expression"],
                vtype, data.get("hierarchy_path"), data.get("conformed_group"),
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

    def list_dimensions(self, tenant_id: str, case_id: str | None = None, entity_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
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
        for eid in (data["left_entity_id"], data["right_entity_id"]):
            if not self.get_entity(tenant_id, eid):
                raise KeyError(f"entity_id '{eid}'를 찾을 수 없습니다")
        now = _now_dt()
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO join_contracts (
                    join_id, left_entity_id, right_entity_id, join_type,
                    join_condition, relationship_type, allowed_for_ai, fanout_risk_score,
                    tenant_id, case_id, status, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft',%s,%s)
            """, (
                data["join_id"], data["left_entity_id"], data["right_entity_id"],
                jtype, data["join_condition"], rtype,
                data.get("allowed_for_ai", True), data.get("fanout_risk_score", 0.0),
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

    def list_join_contracts(self, tenant_id: str, case_id: str | None = None, allowed_for_ai: bool | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        self.ensure_schema()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [tenant_id]
        if case_id:
            conditions.append("case_id = %s")
            params.append(case_id)
        if allowed_for_ai is not None:
            conditions.append("allowed_for_ai = %s")
            params.append(allowed_for_ai)
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
        # 이벤트 타입 매핑 (모든 object_type 포함)
        _event_type_map = {
            "entity": "SEMANTIC_ENTITY_PUBLISHED",
            "measure": "SEMANTIC_MEASURE_PUBLISHED",
            "dimension": "SEMANTIC_ENTITY_PUBLISHED",  # 차원도 엔티티 레벨 이벤트
            "join": "JOIN_CONTRACT_CREATED",
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
