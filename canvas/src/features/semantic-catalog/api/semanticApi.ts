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
