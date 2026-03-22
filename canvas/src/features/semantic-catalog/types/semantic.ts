/**
 * 시멘틱 계약 계층 타입 정의
 * Synapse /api/v3/synapse/semantic/* 엔드포인트의 요청/응답 모델
 */

// ── 공통 ──

export type ConceptStatus = 'draft' | 'review' | 'approved' | 'deprecated';
export type EntityType = 'fact' | 'dimension' | 'bridge' | 'aggregate' | 'feature_source';
export type MeasureType = 'sum' | 'count' | 'distinct_count' | 'ratio' | 'rate' | 'avg' | 'percentile' | 'derived';
export type AdditiveType = 'additive' | 'semi_additive' | 'non_additive';
export type ValueType = 'categorical' | 'temporal' | 'numeric';
export type IntentType = 'kpi_query' | 'root_cause' | 'trend' | 'comparison' | 'forecast_support' | 'narrative' | 'segment' | 'anomaly' | 'general';

// ── L3: 온톨로지 개념 ──

export interface OntologyConcept {
  concept_id: string;
  case_id: string;
  domain_id: string;
  name_ko: string;
  name_en?: string;
  description?: string;
  business_definition?: string;
  status: ConceptStatus;
  owner_team?: string;
  steward_user?: string;
  sensitivity_level: string;
  default_time_semantics?: string;
  default_unit?: string;
  version: number;
  tenant_id: string;
  created_at: string;
  updated_at: string;
  terms?: OntologyTerm[];
}

export interface OntologyTerm {
  term_id: number;
  concept_id: string;
  surface_form: string;
  language: string;
  term_type: string;
  confidence: number;
  created_at: string;
}

// ── L2: 시멘틱 엔티티 ──

export interface SemanticEntity {
  entity_id: string;
  bound_concept_id?: string;
  physical_source_ref: string;
  entity_type: EntityType;
  grain_definition?: string;
  primary_key_spec?: string;
  freshness_sla_minutes?: number;
  tenant_id: string;
  case_id: string;
  status: ConceptStatus;
  version: number;
  created_at: string;
  updated_at: string;
}

// ── L2: 시멘틱 지표 ──

export interface SemanticMeasure {
  measure_id: string;
  bound_concept_id?: string;
  entity_id: string;
  name: string;
  description?: string;
  measure_type: MeasureType;
  sql_expression: string;
  filter_expression?: string;
  additive_type?: AdditiveType;
  default_agg_window?: string;
  owner_team?: string;
  tenant_id: string;
  case_id: string;
  status: ConceptStatus;
  version: number;
  created_at: string;
  updated_at: string;
}

// ── L2: 시멘틱 차원 ──

export interface SemanticDimension {
  dimension_id: string;
  bound_concept_id?: string;
  entity_id: string;
  name: string;
  sql_expression: string;
  value_type?: ValueType;
  hierarchy_path?: string;
  conformed_group?: string;
  tenant_id: string;
  case_id: string;
  status: ConceptStatus;
  version: number;
  created_at: string;
  updated_at: string;
}

// ── L2: 조인 계약 ──

export interface JoinContract {
  join_id: string;
  left_entity_id: string;
  right_entity_id: string;
  join_type: string;
  join_condition: string;
  relationship_type: string;
  allowed_for_ai: boolean;
  fanout_risk_score: number;
  status: ConceptStatus;
  created_at: string;
}

// ── L2: 그레인 계약 ──

export interface GrainContract {
  grain_id: string;
  entity_id: string;
  grain_key_set: string[];
  time_grain: string;
  uniqueness_test?: string;
  duplicate_resolution_rule: string;
  tenant_id: string;
  case_id: string;
  version: number;
  created_at: string;
  updated_at: string;
}

// ── L2: 품질 계약 ──

export interface QualityContract {
  quality_contract_id: string;
  target_type: string;
  target_id: string;
  freshness_sla_minutes?: number;
  completeness_threshold: number;
  uniqueness_threshold: number;
  owner_presence_required: boolean;
  lineage_required: boolean;
}

// ── L5: 컨텍스트 팩 ──

export interface ContextPack {
  context_pack_id: string;
  domain_id: string;
  intent_type: IntentType;
  description?: string;
  included_concept_ids: string[];
  included_measure_ids: string[];
  included_dimension_ids: string[];
  allowed_join_ids: string[];
  banned_join_ids: string[];
  answer_guardrails: string[];
  quality_gate_min_score: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface PromptPolicy {
  prompt_policy_id: string;
  context_pack_id: string;
  rule_type: string;
  rule_text: string;
  priority: number;
  created_at: string;
}

// ── 통합 카탈로그 ──

export interface CatalogSummary {
  concepts: number;
  entities: number;
  measures: number;
  dimensions: number;
  joins: number;
  grains: number;
}

export interface CatalogData {
  summary: CatalogSummary;
  concepts: OntologyConcept[];
  entities: SemanticEntity[];
  measures: SemanticMeasure[];
  dimensions: SemanticDimension[];
  joins: JoinContract[];
}

// ── 컴파일 결과 ──

export interface CompileIssue {
  severity: 'error' | 'warning' | 'info';
  code: string;
  message: string;
  target_id?: string;
}

export interface CompileResult {
  valid: boolean;
  sql_template?: string;
  issues: CompileIssue[];
  metadata: Record<string, unknown>;
}

// ── API 응답 래퍼 ──

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  count?: number;
}
