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
VALID_TIME_GRAINS = {"daily", "hourly", "monthly", "weekly", "yearly", "none"}


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
    case_id: str = ""


class SemanticEntityUpdate(BaseModel):
    """시멘틱 엔티티 수정 (PATCH)"""
    bound_concept_id: str | None = None
    physical_source_ref: str | None = None
    entity_type: str | None = None
    grain_definition: str | None = None
    primary_key_spec: str | None = None
    default_filters: dict[str, Any] | None = None
    freshness_sla_minutes: int | None = None


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


class SemanticDimensionUpdate(BaseModel):
    """시멘틱 차원 수정 (PATCH)"""
    bound_concept_id: str | None = None
    entity_id: str | None = None
    name: str | None = None
    sql_expression: str | None = None
    value_type: str | None = None
    hierarchy_path: str | None = None
    conformed_group: str | None = None


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


class JoinContractUpdate(BaseModel):
    """조인 계약 수정 (PATCH)"""
    join_type: str | None = None
    join_condition: str | None = None
    relationship_type: str | None = None
    allowed_for_ai: bool | None = None
    fanout_risk_score: float | None = Field(None, ge=0.0, le=1.0)


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
