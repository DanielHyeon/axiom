"""
시멘틱 계약 계층 Pydantic 모델 — Control Plane 메타모델

L3 온톨로지 거버넌스 확장 + L2 시멘틱 계약 정의를 위한 요청/응답 모델.
기존 파편(OLAP Studio Model, Oracle FK-path, Weaver Glossary)을
정식 시멘틱 계약으로 승격시키는 구조.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 공통 상수 ──

VALID_CONCEPT_STATUSES = {"draft", "review", "approved", "deprecated"}
VALID_SENSITIVITY_LEVELS = {"public", "internal", "confidential", "restricted"}
VALID_TERM_TYPES = {"primary", "synonym", "alias", "abbreviation", "legacy"}
VALID_ENTITY_TYPES = {"fact", "dimension", "bridge", "aggregate", "feature_source"}
VALID_MEASURE_TYPES = {
    "sum", "count", "distinct_count", "ratio", "rate",
    "avg", "percentile", "derived",
}
VALID_ADDITIVE_TYPES = {"additive", "semi_additive", "non_additive"}
VALID_VALUE_TYPES = {"categorical", "temporal", "numeric"}
VALID_JOIN_TYPES = {"INNER", "LEFT", "RIGHT", "FULL"}
VALID_RELATIONSHIP_TYPES = {"1:1", "1:N", "N:1", "N:N"}
VALID_REVIEW_STATUSES = {"pending", "approved", "rejected"}
VALID_SEMANTIC_OBJECT_TYPES = {"entity", "measure", "dimension", "join"}
VALID_INTENT_TYPES = {
    "kpi_query", "root_cause", "trend", "comparison",
    "forecast_support", "narrative", "segment", "anomaly", "general",
}
VALID_PROMPT_RULE_TYPES = {
    "must_use_metric", "must_cite_quality", "must_avoid_raw_table",
    "must_confirm_timegrain", "prefer_dimension", "forbid_join",
    "max_row_limit", "custom",
}
VALID_DUPLICATE_RESOLUTION = {"fail", "latest_wins", "aggregate"}
VALID_PREDICATE_TYPES = {
    "is_a", "part_of", "relates_to", "derives_from",
    "equivalent_to", "owned_by", "constrained_by",
}
VALID_CARDINALITIES = {"1:1", "1:N", "N:1", "N:N"}
VALID_DIRECTIONALITIES = {"unidirectional", "bidirectional"}
VALID_TIME_GRAINS = {"daily", "hourly", "monthly", "weekly", "yearly", "none"}
VALID_APPROVAL_SCOPES = {"domain", "global"}

# Sprint 4: 질문 이해 인프라 상수
VALID_EXPANSION_RULE_TYPES = {
    "EXACT", "NORMALIZED_EXACT", "TOKEN_SET", "REGEX",
    "TIME_ALIAS", "ACRONYM", "TRANSLITERATION", "ABBREVIATION", "NEGATIVE_RULE",
}
VALID_FEEDBACK_ISSUE_TYPES = {
    "wrong_intent", "missing_synonym", "wrong_mapping", "ambiguity", "other",
}
VALID_INTENT_MODEL_TYPES = {"keyword", "logistic", "llm", "hybrid"}
VALID_ALIAS_GROUP_STATUSES = {"ACTIVE", "DEPRECATED"}
VALID_EXPANSION_RULE_STATUSES = {"ACTIVE", "DEPRECATED"}

VALID_SEGMENT_TYPES = {"static", "dynamic"}
VALID_TIME_CONTRACT_GRAINS = {
    "second", "minute", "hour", "day", "week", "month", "quarter", "year",
}
VALID_ACCESS_POLICY_TYPES = {"row_filter", "column_mask", "field_redact"}
VALID_RULE_TYPES = {"definition", "eligibility", "exclusion", "time_window", "policy"}
VALID_EXPRESSION_LANGS = {"sql", "jsonlogic", "python", "dsl"}
VALID_POLICY_TYPES = {"access", "pii", "retention", "residency", "aggregation"}


# ========================================
# L3: 온톨로지 개념 (거버넌스 확장)
# ========================================

class OntologyConceptCreate(BaseModel):
    """온톨로지 개념 등록 요청 — Neo4j 노드에 담기 어려운 거버넌스 메타데이터"""
    concept_id: str = Field(..., description="Neo4j node_id와 동일한 고유 식별자")
    case_id: str
    domain_id: str = "default"
    name_ko: str = Field(..., min_length=1, description="한글 개념명")
    name_en: str | None = None
    description: str | None = None
    business_definition: str | None = Field(None, description="업무 규칙 기반 상세 정의")
    status: str = "draft"
    owner_team: str | None = None
    steward_user: str | None = None
    sensitivity_level: str = "internal"
    default_time_semantics: str | None = Field(None, description="transaction_date, created_at 등")
    default_unit: str | None = None
    # §5.2: 도메인 스코프 승인 워크플로
    approval_scope: str = Field("global", description="domain: 도메인 스튜어드 직접 승인, global: 중앙 리뷰어 필요")


class OntologyConceptUpdate(BaseModel):
    """온톨로지 개념 수정 — None 필드는 무시 (PATCH 방식)"""
    domain_id: str | None = None
    name_ko: str | None = None
    name_en: str | None = None
    description: str | None = None
    business_definition: str | None = None
    owner_team: str | None = None
    steward_user: str | None = None
    sensitivity_level: str | None = None
    default_time_semantics: str | None = None
    default_unit: str | None = None
    # §5.2: 도메인 스코프 승인 워크플로
    approval_scope: str | None = None


class OntologyConceptStatusChange(BaseModel):
    """상태 전이 요청 — draft→review→approved / approved→deprecated"""
    status: str = Field(..., description="목표 상태: draft, review, approved, deprecated")


# ========================================
# L3: 온톨로지 용어 (Weaver Glossary 통합)
# ========================================

class OntologyTermCreate(BaseModel):
    """온톨로지 용어 등록 — 동의어, 약어, 레거시 용어 관리"""
    concept_id: str = Field(..., description="바인딩할 온톨로지 개념 ID")
    surface_form: str = Field(..., min_length=1, description="표면 형태: '활성고객', 'active customer'")
    language: str = "ko"
    term_type: str = "primary"
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class OntologyTermBulkCreate(BaseModel):
    """여러 용어 일괄 등록"""
    terms: list[OntologyTermCreate]


# ========================================
# L2: 시멘틱 엔티티
# ========================================

class SemanticEntityCreate(BaseModel):
    """시멘틱 엔티티 등록 — 물리 테이블을 의미 계층으로 승격"""
    entity_id: str
    bound_concept_id: str | None = Field(None, description="바인딩할 온톨로지 개념 (publish 시 필수)")
    physical_source_ref: str = Field(..., description="'schema.table_name' 또는 'datasource_id:table'")
    entity_type: str = "fact"
    grain_definition: str | None = Field(None, description="예: '1 row = 1 일별 고객 활동'")
    primary_key_spec: str | None = None
    default_filters: dict[str, Any] | None = None
    freshness_sla_minutes: int | None = None
    feature_config: dict[str, Any] | None = Field(None, description="ML 피처 설정 (entity_type=feature_source일 때)")
    case_id: str = ""
    # §5.1: 도메인 네임스페이스 정책
    domain_id: str = Field("global", description="소속 도메인 (global = 전체 공유)")


class SemanticEntityUpdate(BaseModel):
    """시멘틱 엔티티 수정 (PATCH)"""
    bound_concept_id: str | None = None
    physical_source_ref: str | None = None
    entity_type: str | None = None
    grain_definition: str | None = None
    primary_key_spec: str | None = None
    default_filters: dict[str, Any] | None = None
    freshness_sla_minutes: int | None = None
    feature_config: dict[str, Any] | None = Field(None, description="ML 피처 설정 (entity_type=feature_source일 때)")
    # §5.1: 도메인 네임스페이스
    domain_id: str | None = None


# ========================================
# P3 §5.3: ML/Feature Source 바인딩 요청 모델
# ========================================

class TrainingQueryRequest(BaseModel):
    """학습 데이터셋 SQL 생성 요청 — feature_source 엔티티 기반"""
    entity_id: str = Field(..., description="feature_source 타입 시멘틱 엔티티 ID")
    columns: list[str] | None = Field(None, description="선택할 컬럼 (None이면 feature_columns 전체)")
    date_range: dict[str, str] | None = Field(None, description="날짜 필터 예: {'start': '2025-01-01', 'end': '2025-12-31'}")


# ========================================
# L2: 시멘틱 지표
# ========================================

class SemanticMeasureCreate(BaseModel):
    """시멘틱 지표 등록 — 중앙화된 단일 지표 정의"""
    measure_id: str
    bound_concept_id: str | None = None
    entity_id: str = Field(..., description="이 지표가 속한 시멘틱 엔티티")
    name: str = Field(..., min_length=1)
    description: str | None = None
    measure_type: str = "sum"
    sql_expression: str = Field(..., description="예: 'COUNT(DISTINCT customer_id)'")
    filter_expression: str | None = None
    numerator_measure_id: str | None = None
    denominator_measure_id: str | None = None
    additive_type: str = "additive"
    default_agg_window: str | None = Field(None, description="monthly, daily 등")
    owner_team: str | None = None
    case_id: str = ""
    # §5.1: 도메인 네임스페이스 정책
    domain_id: str = Field("global", description="소속 도메인 (global = 전체 공유)")


class SemanticMeasureUpdate(BaseModel):
    """시멘틱 지표 수정 (PATCH)"""
    bound_concept_id: str | None = None
    entity_id: str | None = None
    name: str | None = None
    description: str | None = None
    measure_type: str | None = None
    sql_expression: str | None = None
    filter_expression: str | None = None
    numerator_measure_id: str | None = None
    denominator_measure_id: str | None = None
    additive_type: str | None = None
    default_agg_window: str | None = None
    owner_team: str | None = None
    # §5.1: 도메인 네임스페이스
    domain_id: str | None = None


# ========================================
# L2: 시멘틱 차원
# ========================================

class SemanticDimensionCreate(BaseModel):
    """시멘틱 차원 등록"""
    dimension_id: str
    bound_concept_id: str | None = None
    entity_id: str = Field(..., description="이 차원이 속한 시멘틱 엔티티")
    name: str = Field(..., min_length=1)
    sql_expression: str = Field(..., description="예: DATE_TRUNC('month', order_date)")
    value_type: str = "categorical"
    hierarchy_path: str | None = Field(None, description="year > quarter > month > day")
    conformed_group: str | None = Field(None, description="동일 차원 그룹명")
    case_id: str = ""
    # §5.1: 도메인 네임스페이스 정책
    domain_id: str = Field("global", description="소속 도메인 (global = 전체 공유)")


class SemanticDimensionUpdate(BaseModel):
    """시멘틱 차원 수정 (PATCH)"""
    bound_concept_id: str | None = None
    entity_id: str | None = None
    name: str | None = None
    sql_expression: str | None = None
    value_type: str | None = None
    hierarchy_path: str | None = None
    conformed_group: str | None = None
    # §5.1: 도메인 네임스페이스
    domain_id: str | None = None


# ========================================
# L2: 조인 계약
# ========================================

class JoinContractCreate(BaseModel):
    """조인 계약 등록 — 허용/금지 조인 명시화"""
    join_id: str
    left_entity_id: str
    right_entity_id: str
    join_type: str = "LEFT"
    join_condition: str = Field(..., description="예: 'left.customer_id = right.customer_id'")
    relationship_type: str = "1:N"
    allowed_for_ai: bool = True
    fanout_risk_score: float = Field(0.0, ge=0.0, le=1.0)
    case_id: str = ""
    # §5.1: 도메인 네임스페이스 정책 (교차 도메인 조인 허용)
    domain_id: str = Field("global", description="소속 도메인 (global = 전체 공유)")


class JoinContractUpdate(BaseModel):
    """조인 계약 수정 (PATCH)"""
    join_type: str | None = None
    join_condition: str | None = None
    relationship_type: str | None = None
    allowed_for_ai: bool | None = None
    fanout_risk_score: float | None = Field(None, ge=0.0, le=1.0)
    # §5.1: 도메인 네임스페이스
    domain_id: str | None = None


# ========================================
# L2: 그레인 계약
# ========================================

class GrainContractCreate(BaseModel):
    """그레인 계약 등록 — 엔티티의 행 단위(grain) 유일성 규칙 정의"""
    grain_id: str
    entity_id: str = Field(..., description="대상 시멘틱 엔티티")
    grain_key_set: list[str] = Field(..., min_length=1, description="유일성을 구성하는 컬럼 집합")
    time_grain: str = Field("none", description="daily, hourly, monthly, weekly, yearly, none")
    uniqueness_test: str | None = Field(None, description="SQL 검증식, 예: COUNT(*) = COUNT(DISTINCT pk)")
    duplicate_resolution_rule: str = Field("fail", description="fail, latest_wins, aggregate")
    case_id: str = ""


class GrainContractUpdate(BaseModel):
    """그레인 계약 수정 (PATCH)"""
    grain_key_set: list[str] | None = None
    time_grain: str | None = None
    uniqueness_test: str | None = None
    duplicate_resolution_rule: str | None = None


# ========================================
# L2: 품질 계약
# ========================================

class QualityContractCreate(BaseModel):
    """품질 계약 등록 — 엔티티/지표/차원에 대한 품질 SLA"""
    quality_contract_id: str
    target_type: str = Field(..., description="entity, measure, dimension")
    target_id: str
    freshness_sla_minutes: int | None = None
    completeness_threshold: float = Field(95.0, ge=0.0, le=100.0)
    uniqueness_threshold: float = Field(99.0, ge=0.0, le=100.0)
    owner_presence_required: bool = True
    lineage_required: bool = True
    case_id: str = ""


class QualityContractUpdate(BaseModel):
    """품질 계약 수정 (PATCH)"""
    freshness_sla_minutes: int | None = None
    completeness_threshold: float | None = Field(None, ge=0.0, le=100.0)
    uniqueness_threshold: float | None = Field(None, ge=0.0, le=100.0)
    owner_presence_required: bool | None = None
    lineage_required: bool | None = None


# ========================================
# 배포(Publish) + 릴리스
# ========================================

class SemanticPublishRequest(BaseModel):
    """시멘틱 객체 배포 요청 — ontology binding 검증 후 승인"""
    semantic_object_type: str = Field(..., description="entity, measure, dimension, join")
    semantic_object_id: str


class SemanticReleaseResponse(BaseModel):
    """배포 이력 응답"""
    release_id: int
    semantic_object_type: str
    semantic_object_id: str
    version: int
    review_status: str
    reviewer: str | None
    deployed_at: datetime | None
    created_at: datetime


# ========================================
# Semantic Compiler 요청/응답
# ========================================

class CompileRequest(BaseModel):
    """시멘틱 컴파일 요청 — 엔티티 또는 지표 단위"""
    entity_id: str | None = None
    measure_id: str | None = None


# ========================================
# L5: AI Context Pack + Prompt Policy
# ========================================

class ContextPackCreate(BaseModel):
    """AI 컨텍스트 팩 등록 — 의도별 사전 구성된 시멘틱 컨텍스트 프리셋"""
    context_pack_id: str
    domain_id: str = "default"
    intent_type: str = Field("general", description="kpi_query, root_cause, trend, comparison 등")
    description: str | None = None
    included_concept_ids: list[str] = Field(default_factory=list, description="포함할 온톨로지 개념 ID 목록")
    included_measure_ids: list[str] = Field(default_factory=list, description="포함할 시멘틱 지표 ID 목록")
    included_dimension_ids: list[str] = Field(default_factory=list, description="포함할 시멘틱 차원 ID 목록")
    allowed_join_ids: list[str] = Field(default_factory=list, description="허용할 조인 계약 ID 목록")
    banned_join_ids: list[str] = Field(default_factory=list, description="금지할 조인 계약 ID 목록")
    temporal_rules: dict[str, Any] | None = Field(None, description="시간 의미론 규칙 (예: default_timegrain)")
    answer_guardrails: list[str] = Field(default_factory=list, description="응답 가드레일 텍스트 목록")
    quality_gate_min_score: float = Field(0.0, ge=0.0, le=100.0, description="최소 품질 점수 (0이면 비활성)")
    case_id: str = ""


class ContextPackUpdate(BaseModel):
    """컨텍스트 팩 수정 (PATCH)"""
    domain_id: str | None = None
    intent_type: str | None = None
    description: str | None = None
    included_concept_ids: list[str] | None = None
    included_measure_ids: list[str] | None = None
    included_dimension_ids: list[str] | None = None
    allowed_join_ids: list[str] | None = None
    banned_join_ids: list[str] | None = None
    temporal_rules: dict[str, Any] | None = None
    answer_guardrails: list[str] | None = None
    quality_gate_min_score: float | None = Field(None, ge=0.0, le=100.0)


class PromptPolicyCreate(BaseModel):
    """프롬프트 정책 등록 — ContextPack에 바인딩되는 LLM 가드레일 규칙"""
    prompt_policy_id: str
    context_pack_id: str = Field(..., description="바인딩할 컨텍스트 팩 ID")
    rule_type: str = Field(..., description="must_use_metric, must_avoid_raw_table 등")
    rule_text: str = Field(..., min_length=1, description="LLM에 주입할 규칙 텍스트")
    priority: int = Field(0, ge=0, description="우선순위 (높을수록 먼저 적용)")


class PromptPolicyUpdate(BaseModel):
    """프롬프트 정책 수정 (PATCH)"""
    rule_type: str | None = None
    rule_text: str | None = None
    priority: int | None = Field(None, ge=0)


# ========================================
# L2: 시멘틱 세그먼트 (§5.2)
# ========================================

class SemanticSegmentCreate(BaseModel):
    """시멘틱 세그먼트 등록 — 엔티티에 대한 필터 기반 데이터 분할"""
    segment_id: str
    entity_id: str = Field(..., description="대상 시멘틱 엔티티")
    name: str = Field(..., min_length=1, description="세그먼트 이름")
    filter_expression: str = Field(..., min_length=1, description="SQL WHERE 조건식")
    segment_type: str = Field("static", description="static 또는 dynamic")
    description: str | None = None
    case_id: str = ""


class SemanticSegmentUpdate(BaseModel):
    """시멘틱 세그먼트 수정 (PATCH)"""
    name: str | None = None
    filter_expression: str | None = None
    segment_type: str | None = None
    description: str | None = None


# ========================================
# L2: 시간 계약 (§5.2)
# ========================================

class TimeContractCreate(BaseModel):
    """시간 계약 등록 — 엔티티의 시간 축 의미론 정의"""
    time_contract_id: str
    entity_id: str = Field(..., description="대상 시멘틱 엔티티")
    time_column: str = Field(..., min_length=1, description="시간 컬럼명")
    time_grain: str = Field(..., description="second|minute|hour|day|week|month|quarter|year")
    timezone: str = Field("UTC", description="타임존 (IANA)")
    fiscal_calendar_offset: int = Field(0, description="회계연도 오프셋 (월)")
    default_lookback_days: int = Field(365, ge=1, description="기본 조회 기간 (일)")
    description: str | None = None
    case_id: str = ""


class TimeContractUpdate(BaseModel):
    """시간 계약 수정 (PATCH)"""
    time_column: str | None = None
    time_grain: str | None = None
    timezone: str | None = None
    fiscal_calendar_offset: int | None = None
    default_lookback_days: int | None = Field(None, ge=1)
    description: str | None = None


# ========================================
# L2: 접근 정책 (§5.2 — 행/열 수준 데이터 접근 제어)
# ========================================

class AccessPolicyCreate(BaseModel):
    """접근 정책 등록 — 엔티티의 행/열 수준 데이터 접근 제어"""
    access_policy_id: str
    entity_id: str = Field(..., description="대상 시멘틱 엔티티")
    policy_type: str = Field(..., description="row_filter|column_mask|field_redact")
    condition_expression: str = Field(..., min_length=1, description="조건식 (SQL 또는 JSONLogic)")
    target_roles: list[str] = Field(default_factory=list, description="적용 대상 역할 목록")
    is_active: bool = Field(True, description="활성화 여부")
    description: str | None = None
    case_id: str = ""


class AccessPolicyUpdate(BaseModel):
    """접근 정책 수정 (PATCH)"""
    policy_type: str | None = None
    condition_expression: str | None = None
    target_roles: list[str] | None = None
    is_active: bool | None = None
    description: str | None = None


# ========================================
# L3: 온톨로지 규칙 (OntologyRule)
# ========================================

class OntologyRuleCreate(BaseModel):
    """온톨로지 규칙 등록 — 개념에 바인딩되는 업무 규칙/정의/자격/제외/시간창/정책"""
    rule_id: str = Field(..., description="고유 규칙 식별자")
    concept_id: str = Field(..., description="바인딩할 온톨로지 개념 ID (FK → ontology_concepts)")
    rule_type: str = Field(..., description="definition, eligibility, exclusion, time_window, policy")
    rule_expression: str = Field(..., min_length=1, description="규칙 표현식 (SQL, JSONLogic 등)")
    expression_lang: str = Field("sql", description="표현식 언어: sql, jsonlogic, python, dsl")
    severity: str = Field("warning", description="위반 시 심각도: info, warning, error, critical")
    description: str | None = None


class OntologyRuleUpdate(BaseModel):
    """온톨로지 규칙 수정 (PATCH) — None 필드는 무시"""
    rule_type: str | None = None
    rule_expression: str | None = None
    expression_lang: str | None = None
    severity: str | None = None
    description: str | None = None


# ========================================
# L3: 온톨로지 정책 (OntologyPolicy)
# ========================================

class OntologyPolicyCreate(BaseModel):
    """온톨로지 정책 등록 — 접근, PII, 보존, 거주지, 집계 등 데이터 거버넌스 정책"""
    policy_id: str = Field(..., description="고유 정책 식별자")
    concept_id: str = Field(..., description="바인딩할 온톨로지 개념 ID (FK → ontology_concepts)")
    policy_type: str = Field(..., description="access, pii, retention, residency, aggregation")
    policy_expression: str = Field(..., min_length=1, description="정책 표현식")
    description: str | None = None
    is_active: bool = Field(True, description="정책 활성 여부")


class OntologyPolicyUpdate(BaseModel):
    """온톨로지 정책 수정 (PATCH) — None 필드는 무시"""
    policy_type: str | None = None
    policy_expression: str | None = None
    description: str | None = None
    is_active: bool | None = None


# ========================================
# L3: 온톨로지 관계 (Neo4j 보완 PG 메타데이터)
# ========================================

class OntologyRelationCreate(BaseModel):
    """온톨로지 관계 등록 — Neo4j 그래프와 병행하는 PG 구조화 메타데이터"""
    relation_id: str = Field(..., description="고유 관계 식별자")
    subject_concept_id: str = Field(..., description="주체 온톨로지 개념 ID (FK → ontology_concepts)")
    predicate_type: str = Field(..., description="관계 술어: is_a, part_of, relates_to, derives_from, equivalent_to, owned_by, constrained_by")
    object_concept_id: str = Field(..., description="객체 온톨로지 개념 ID (FK → ontology_concepts)")
    cardinality: str = Field("1:N", description="기수성: 1:1, 1:N, N:1, N:N")
    directionality: str = Field("unidirectional", description="방향성: unidirectional, bidirectional")
    weight: float = Field(1.0, ge=0.0, le=99.99, description="관계 가중치 (0.0~99.99)")
    confidence: float = Field(1.0, ge=0.0, le=99.99, description="신뢰도 (0.0~99.99)")
    effective_from: str | None = Field(None, description="유효 시작일 (ISO 8601)")
    effective_to: str | None = Field(None, description="유효 종료일 (ISO 8601)")


class OntologyRelationUpdate(BaseModel):
    """온톨로지 관계 수정 (PATCH) — None 필드는 무시"""
    predicate_type: str | None = None
    cardinality: str | None = None
    directionality: str | None = None
    weight: float | None = Field(None, ge=0.0, le=99.99)
    confidence: float | None = Field(None, ge=0.0, le=99.99)
    effective_from: str | None = None
    effective_to: str | None = None


# ========================================
# Sprint 4: 질문 이해 인프라 모델
# ========================================

class AliasGroupCreate(BaseModel):
    """별칭 그룹 등록 — 여러 표면 형태를 하나의 정규 용어 클러스터로 묶는다"""
    id: str = Field(..., description="별칭 그룹 고유 ID")
    domain_id: str = Field("global", description="소속 도메인")
    canonical_term_id: str = Field(..., description="정규 용어 ID (ontology_terms 참조)")
    group_name: str = Field(..., min_length=1, max_length=200, description="그룹 표시명")
    language_code: str = Field("ko", max_length=16, description="언어 코드 (ko, en)")
    status: str = Field("ACTIVE", description="ACTIVE 또는 DEPRECATED")


class ExpansionRuleCreate(BaseModel):
    """용어 확장 규칙 등록 — exact/regex/time_alias 등 매칭 규칙 정의"""
    id: str = Field(..., description="확장 규칙 고유 ID")
    domain_id: str = Field("global", description="소속 도메인")
    alias_group_id: str = Field(..., description="소속 별칭 그룹 ID")
    rule_type: str = Field(..., description="EXACT, NORMALIZED_EXACT, TOKEN_SET, REGEX, TIME_ALIAS 등")
    match_pattern: str = Field(..., min_length=1, description="매칭할 패턴 (예: '활성고객', '\\d{4}년')")
    normalized_pattern: str | None = Field(None, description="정규화된 패턴 (소문자/공백제거 등)")
    boost: float = Field(1.0, ge=0.0, le=999.99, description="부스트 가중치")
    priority: int = Field(100, ge=0, description="우선순위 (높을수록 먼저 매칭)")
    status: str = Field("ACTIVE", description="ACTIVE 또는 DEPRECATED")
    effective_from: str | None = Field(None, description="유효 시작일 (ISO 8601)")
    effective_to: str | None = Field(None, description="유효 종료일 (ISO 8601)")


class ExpansionRuleUpdate(BaseModel):
    """확장 규칙 수정 (PATCH) — None 필드 무시"""
    rule_type: str | None = None
    match_pattern: str | None = None
    normalized_pattern: str | None = None
    boost: float | None = Field(None, ge=0.0, le=999.99)
    priority: int | None = Field(None, ge=0)
    effective_from: str | None = None
    effective_to: str | None = None


class IntentModelCreate(BaseModel):
    """의도 분류 모델 등록 — 모델 버전 관리"""
    id: str = Field(..., description="모델 고유 ID")
    model_key: str = Field(..., max_length=100, description="모델 식별 키 (예: 'intent_v2')")
    model_version: str = Field(..., max_length=64, description="모델 버전 (예: '2.1.0')")
    model_type: str = Field("keyword", description="keyword, logistic, llm, hybrid")
    status: str = Field("ACTIVE", description="모델 상태")
    config_json: dict = Field(default_factory=dict, description="모델 설정 JSON")


class InferenceLogCreate(BaseModel):
    """의도 추론 로그 기록 — Oracle에서 질의 시 기록"""
    id: str = Field(..., description="추론 로그 고유 ID")
    request_id: str = Field(..., max_length=100, description="원본 요청 ID")
    snapshot_version: str | None = Field(None, max_length=100, description="사용된 스냅샷 버전")
    user_question: str = Field(..., min_length=1, description="사용자 원문 질문")
    normalized_question: str = Field("", description="정규화된 질문")
    top_intent: str | None = Field(None, max_length=64, description="최종 분류된 의도")
    confidence: float | None = Field(None, ge=0.0, le=99.99, description="분류 신뢰도")
    ambiguity_score: float | None = Field(None, ge=0.0, le=99.99, description="모호성 점수")
    fallback_mode: str | None = Field(None, max_length=32, description="폴백 모드 (raw_schema 등)")
    feature_json: dict = Field(default_factory=dict, description="추출된 피처 JSON")
    candidate_json: dict = Field(default_factory=dict, description="후보 의도 목록 JSON")


class QuestionFeedbackCreate(BaseModel):
    """질문 이해 피드백 등록 — 운영자 교정 기록"""
    id: str = Field(..., description="피드백 고유 ID")
    request_id: str = Field(..., max_length=100, description="대상 추론 로그의 요청 ID")
    issue_type: str = Field(..., description="wrong_intent, missing_synonym, wrong_mapping, ambiguity, other")
    expected_intent: str | None = Field(None, max_length=64, description="기대 의도")
    expected_concept_id: str | None = Field(None, description="기대 온톨로지 개념 ID")
    expected_measure_id: str | None = Field(None, description="기대 시멘틱 지표 ID")
    feedback_note: str | None = Field(None, description="운영자 코멘트")
    created_by: str | None = Field(None, description="피드백 작성자")


# ========================================
# 시멘틱 스냅샷 (Sprint 3)
# ========================================

class SnapshotBuildRequest(BaseModel):
    """스냅샷 빌드 요청"""
    release_id: str | None = Field(None, description="릴리스 ID (없으면 현재 활성 데이터 기반)")
    release_version: str | None = Field(None, description="릴리스 버전")


class SnapshotActivateRequest(BaseModel):
    """스냅샷 활성화 요청"""
    pass  # 버전은 경로 파라미터로 받음


class SnapshotInvalidateRequest(BaseModel):
    """스냅샷 무효화 요청"""
    reason: str = Field("", max_length=100, description="무효화 사유")


class ConsumerBindingHeartbeat(BaseModel):
    """소비자 바인딩 하트비트 — 소비자가 주기적으로 호출"""
    consumer_name: str = Field(..., max_length=50, description="소비자 서비스명 (oracle, canvas 등)")
    consumer_instance_id: str = Field("default", max_length=100, description="소비자 인스턴스 ID")
    snapshot_version: str = Field(..., max_length=64, description="바인딩할 스냅샷 버전")
    binding_mode: str = Field("AUTO", description="바인딩 모드 (AUTO, PINNED)")
