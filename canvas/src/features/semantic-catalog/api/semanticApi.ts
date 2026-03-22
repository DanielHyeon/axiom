/**
 * 시멘틱 계약 API 클라이언트
 * Synapse /api/v3/synapse/semantic/* 엔드포인트 호출
 */
import { synapseApi } from '@/lib/api/clients';
import type {
  ApiResponse,
  CatalogData,
  OntologyConcept,
  SemanticEntity,
  SemanticMeasure,
  SemanticDimension,
  JoinContract,
  GrainContract,
  QualityContract,
  ContextPack,
  PromptPolicy,
  CompileResult,
  SemanticRelease,
  AliasGroup,
  ExpansionRule,
  SemanticSnapshot,
  OntologyRelation,
  OntologyRule,
  OntologyPolicy,
  SemanticSegment,
  TimeContract,
  AccessPolicyL2,
} from '../types/semantic';

const BASE = '/api/v3/synapse/semantic';

// ── 카탈로그 ──

export async function getCatalog(caseId?: string): Promise<CatalogData> {
  const params = caseId ? { case_id: caseId } : {};
  const res = await synapseApi.get(`${BASE}/catalog`, { params });
  return (res as unknown as ApiResponse<CatalogData>).data;
}

// ── 개념 CRUD ──

export async function listConcepts(params?: {
  case_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<OntologyConcept[]> {
  const res = await synapseApi.get(`${BASE}/concepts`, { params });
  return (res as unknown as ApiResponse<OntologyConcept[]>).data;
}

export async function getConcept(conceptId: string): Promise<OntologyConcept> {
  const res = await synapseApi.get(`${BASE}/concepts/${conceptId}`);
  return (res as unknown as ApiResponse<OntologyConcept>).data;
}

export async function createConcept(data: Partial<OntologyConcept>): Promise<OntologyConcept> {
  const res = await synapseApi.post(`${BASE}/concepts`, data);
  return (res as unknown as ApiResponse<OntologyConcept>).data;
}

export async function updateConcept(conceptId: string, data: Partial<OntologyConcept>): Promise<OntologyConcept> {
  const res = await synapseApi.put(`${BASE}/concepts/${conceptId}`, data);
  return (res as unknown as ApiResponse<OntologyConcept>).data;
}

export async function changeConceptStatus(conceptId: string, status: string): Promise<OntologyConcept> {
  const res = await synapseApi.patch(`${BASE}/concepts/${conceptId}/status`, { status });
  return (res as unknown as ApiResponse<OntologyConcept>).data;
}

// ── 용어 ──

export async function searchTerms(q: string, limit = 50): Promise<{ surface_form: string; concept_id: string }[]> {
  const res = await synapseApi.get(`${BASE}/terms/search`, { params: { q, limit } });
  return (res as unknown as ApiResponse<{ surface_form: string; concept_id: string }[]>).data;
}

// ── 엔티티 ──

export async function listEntities(params?: { case_id?: string; limit?: number }): Promise<SemanticEntity[]> {
  const res = await synapseApi.get(`${BASE}/entities`, { params });
  return (res as unknown as ApiResponse<SemanticEntity[]>).data;
}

// ── 지표 ──

export async function listMeasures(params?: { case_id?: string; entity_id?: string; limit?: number }): Promise<SemanticMeasure[]> {
  const res = await synapseApi.get(`${BASE}/measures`, { params });
  return (res as unknown as ApiResponse<SemanticMeasure[]>).data;
}

// ── 차원 ──

export async function listDimensions(params?: { case_id?: string; entity_id?: string; limit?: number }): Promise<SemanticDimension[]> {
  const res = await synapseApi.get(`${BASE}/dimensions`, { params });
  return (res as unknown as ApiResponse<SemanticDimension[]>).data;
}

// ── 조인 ──

export async function listJoins(params?: { case_id?: string; allowed_for_ai?: boolean }): Promise<JoinContract[]> {
  const res = await synapseApi.get(`${BASE}/joins`, { params });
  return (res as unknown as ApiResponse<JoinContract[]>).data;
}

// ── 그레인 계약 ──

export async function listGrains(params?: { case_id?: string; entity_id?: string }): Promise<GrainContract[]> {
  const res = await synapseApi.get(`${BASE}/grains`, { params });
  return (res as unknown as ApiResponse<GrainContract[]>).data;
}

// ── 품질 계약 ──

export async function listQualityContracts(params?: { case_id?: string; target_type?: string }): Promise<QualityContract[]> {
  const res = await synapseApi.get(`${BASE}/quality-contracts`, { params });
  return (res as unknown as ApiResponse<QualityContract[]>).data;
}

// ── 컴파일 ──

export async function compileEntity(entityId: string): Promise<CompileResult> {
  const res = await synapseApi.post(`${BASE}/compile/entity/${entityId}`);
  return (res as unknown as ApiResponse<CompileResult>).data;
}

export async function compileMeasure(measureId: string): Promise<CompileResult> {
  const res = await synapseApi.post(`${BASE}/compile/measure/${measureId}`);
  return (res as unknown as ApiResponse<CompileResult>).data;
}

// ── 배포 ──

export async function publishObject(objectType: string, objectId: string): Promise<unknown> {
  const res = await synapseApi.post(`${BASE}/publish`, {
    semantic_object_type: objectType,
    semantic_object_id: objectId,
  });
  return (res as unknown as ApiResponse<unknown>).data;
}

// ── 릴리스 (배포 이력) ──

export async function listReleases(params?: { limit?: number; offset?: number }): Promise<SemanticRelease[]> {
  const res = await synapseApi.get(`${BASE}/releases`, { params });
  return (res as unknown as ApiResponse<SemanticRelease[]>).data;
}

// ── 품질 런타임 ──

export interface TrustTierResult {
  trust_tier: string;
  final_score: number;
  allow_execution: boolean;
  response_mode: string;
  user_banner: string;
  hard_fail_codes: string[];
  soft_fail_codes: string[];
  dimension_breakdown: Record<string, number>;
}

export async function getQualityRuntime(entityId: string): Promise<{ entity_id: string; quality: TrustTierResult }> {
  const res = await synapseApi.get(`${BASE}/quality/runtime/${entityId}`);
  return (res as unknown as ApiResponse<{ entity_id: string; quality: TrustTierResult }>).data;
}

// ── 컨텍스트 팩 ──

export async function listContextPacks(params?: { case_id?: string; intent_type?: string }): Promise<ContextPack[]> {
  const res = await synapseApi.get(`${BASE}/context-packs`, { params });
  return (res as unknown as ApiResponse<ContextPack[]>).data;
}

export async function getContextPack(packId: string): Promise<ContextPack> {
  const res = await synapseApi.get(`${BASE}/context-packs/${packId}`);
  return (res as unknown as ApiResponse<ContextPack>).data;
}

export async function createContextPack(data: Partial<ContextPack>): Promise<ContextPack> {
  const res = await synapseApi.post(`${BASE}/context-packs`, data);
  return (res as unknown as ApiResponse<ContextPack>).data;
}

export async function deleteContextPack(packId: string): Promise<void> {
  await synapseApi.delete(`${BASE}/context-packs/${packId}`);
}

// ── 프롬프트 정책 ──

export async function listPromptPolicies(contextPackId: string): Promise<PromptPolicy[]> {
  const res = await synapseApi.get(`${BASE}/prompt-policies`, { params: { context_pack_id: contextPackId } });
  return (res as unknown as ApiResponse<PromptPolicy[]>).data;
}

export async function createPromptPolicy(data: Partial<PromptPolicy>): Promise<PromptPolicy> {
  const res = await synapseApi.post(`${BASE}/prompt-policies`, data);
  return (res as unknown as ApiResponse<PromptPolicy>).data;
}

// ── 별칭 그룹 ──

export async function listAliasGroups(params?: {
  domain_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<AliasGroup[]> {
  const res = await synapseApi.get(`${BASE}/ontology/alias-groups`, { params });
  return (res as unknown as ApiResponse<AliasGroup[]>).data;
}

export async function createAliasGroup(data: Partial<AliasGroup>): Promise<AliasGroup> {
  const res = await synapseApi.post(`${BASE}/ontology/alias-groups`, data);
  return (res as unknown as ApiResponse<AliasGroup>).data;
}

// ── 확장 규칙 ──

export async function listExpansionRules(params?: {
  alias_group_id?: string;
  status?: string;
  limit?: number;
}): Promise<ExpansionRule[]> {
  const res = await synapseApi.get(`${BASE}/ontology/expansion-rules`, { params });
  return (res as unknown as ApiResponse<ExpansionRule[]>).data;
}

export async function createExpansionRule(data: Partial<ExpansionRule>): Promise<ExpansionRule> {
  const res = await synapseApi.post(`${BASE}/ontology/expansion-rules`, data);
  return (res as unknown as ApiResponse<ExpansionRule>).data;
}

export async function activateExpansionRule(id: string): Promise<ExpansionRule> {
  const res = await synapseApi.post(`${BASE}/ontology/expansion-rules/${id}/activate`);
  return (res as unknown as ApiResponse<ExpansionRule>).data;
}

export async function deprecateExpansionRule(id: string): Promise<ExpansionRule> {
  const res = await synapseApi.post(`${BASE}/ontology/expansion-rules/${id}/deprecate`);
  return (res as unknown as ApiResponse<ExpansionRule>).data;
}

// ── 스냅샷 ──

export async function listSnapshots(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<SemanticSnapshot[]> {
  const res = await synapseApi.get(`${BASE}/snapshots`, { params });
  return (res as unknown as ApiResponse<SemanticSnapshot[]>).data;
}

export async function getActiveSnapshot(): Promise<SemanticSnapshot> {
  const res = await synapseApi.get(`${BASE}/snapshots/active`);
  return (res as unknown as ApiResponse<SemanticSnapshot>).data;
}

export async function buildSnapshot(data?: { release_id?: string }): Promise<SemanticSnapshot> {
  const res = await synapseApi.post(`${BASE}/snapshots/build`, data ?? {});
  return (res as unknown as ApiResponse<SemanticSnapshot>).data;
}

export async function activateSnapshot(version: string): Promise<SemanticSnapshot> {
  const res = await synapseApi.post(`${BASE}/snapshots/${version}/activate`);
  return (res as unknown as ApiResponse<SemanticSnapshot>).data;
}

export async function invalidateSnapshot(version: string, reason: string): Promise<SemanticSnapshot> {
  const res = await synapseApi.post(`${BASE}/snapshots/${version}/invalidate`, { reason });
  return (res as unknown as ApiResponse<SemanticSnapshot>).data;
}

// ── 온톨로지 관계 ──

export async function listRelations(params?: {
  concept_id?: string;
  predicate_type?: string;
  limit?: number;
  offset?: number;
}): Promise<OntologyRelation[]> {
  const res = await synapseApi.get(`${BASE}/ontology/relations`, { params });
  return (res as unknown as ApiResponse<OntologyRelation[]>).data;
}

export async function createRelation(data: Partial<OntologyRelation>): Promise<OntologyRelation> {
  const res = await synapseApi.post(`${BASE}/ontology/relations`, data);
  return (res as unknown as ApiResponse<OntologyRelation>).data;
}

export async function deleteRelation(id: string): Promise<void> {
  await synapseApi.delete(`${BASE}/ontology/relations/${id}`);
}

// ── 온톨로지 규칙 ──

export async function listRules(params?: {
  concept_id?: string;
  rule_type?: string;
  limit?: number;
}): Promise<OntologyRule[]> {
  const res = await synapseApi.get(`${BASE}/ontology/rules`, { params });
  return (res as unknown as ApiResponse<OntologyRule[]>).data;
}

export async function createRule(data: Partial<OntologyRule>): Promise<OntologyRule> {
  const res = await synapseApi.post(`${BASE}/ontology/rules`, data);
  return (res as unknown as ApiResponse<OntologyRule>).data;
}

export async function deleteRule(id: string): Promise<void> {
  await synapseApi.delete(`${BASE}/ontology/rules/${id}`);
}

// ── 온톨로지 정책 ──

export async function listPolicies(params?: {
  concept_id?: string;
  policy_type?: string;
  limit?: number;
}): Promise<OntologyPolicy[]> {
  const res = await synapseApi.get(`${BASE}/ontology/policies`, { params });
  return (res as unknown as ApiResponse<OntologyPolicy[]>).data;
}

export async function createPolicy(data: Partial<OntologyPolicy>): Promise<OntologyPolicy> {
  const res = await synapseApi.post(`${BASE}/ontology/policies`, data);
  return (res as unknown as ApiResponse<OntologyPolicy>).data;
}

export async function deletePolicy(id: string): Promise<void> {
  await synapseApi.delete(`${BASE}/ontology/policies/${id}`);
}

export async function togglePolicyActive(id: string, isActive: boolean): Promise<OntologyPolicy> {
  const res = await synapseApi.patch(`${BASE}/ontology/policies/${id}`, { is_active: isActive });
  return (res as unknown as ApiResponse<OntologyPolicy>).data;
}

// ── L2 세그먼트 ──

export async function listSegments(params?: {
  entity_id?: string;
  segment_type?: string;
  limit?: number;
}): Promise<SemanticSegment[]> {
  const res = await synapseApi.get(`${BASE}/segments`, { params });
  return (res as unknown as ApiResponse<SemanticSegment[]>).data;
}

// ── L2 시간 계약 ──

export async function listTimeContracts(params?: {
  entity_id?: string;
  limit?: number;
}): Promise<TimeContract[]> {
  const res = await synapseApi.get(`${BASE}/time-contracts`, { params });
  return (res as unknown as ApiResponse<TimeContract[]>).data;
}

// ── L2 접근 정책 ──

export async function listAccessPolicies(params?: {
  entity_id?: string;
  is_active?: boolean;
  limit?: number;
}): Promise<AccessPolicyL2[]> {
  const res = await synapseApi.get(`${BASE}/access-policies`, { params });
  return (res as unknown as ApiResponse<AccessPolicyL2[]>).data;
}
