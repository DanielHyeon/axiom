/**
 * 시멘틱 카탈로그 TanStack Query 훅
 * 카탈로그 데이터 조회, 캐싱, 뮤테이션을 관리한다.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import * as api from '../api/semanticApi';
import type { ConceptStatus } from '../types/semantic';

// ── 쿼리 키 ──
const KEYS = {
  catalog: (caseId?: string) => ['semantic', 'catalog', caseId] as const,
  concepts: (params?: Record<string, unknown>) => ['semantic', 'concepts', params] as const,
  concept: (id: string) => ['semantic', 'concept', id] as const,
  entities: (params?: Record<string, unknown>) => ['semantic', 'entities', params] as const,
  measures: (params?: Record<string, unknown>) => ['semantic', 'measures', params] as const,
  dimensions: (params?: Record<string, unknown>) => ['semantic', 'dimensions', params] as const,
  joins: (params?: Record<string, unknown>) => ['semantic', 'joins', params] as const,
  grains: (params?: Record<string, unknown>) => ['semantic', 'grains', params] as const,
  qualityContracts: (params?: Record<string, unknown>) => ['semantic', 'quality', params] as const,
  contextPacks: (params?: Record<string, unknown>) => ['semantic', 'context-packs', params] as const,
  compile: (type: string, id: string) => ['semantic', 'compile', type, id] as const,
};

// ── 카탈로그 ──

export function useSemanticCatalog(caseId?: string) {
  return useQuery({
    queryKey: KEYS.catalog(caseId),
    queryFn: () => api.getCatalog(caseId),
    staleTime: 2 * 60 * 1000, // 2분 캐시
  });
}

// ── 개념 ──

export function useConcepts(params?: { case_id?: string; status?: string }) {
  return useQuery({
    queryKey: KEYS.concepts(params),
    queryFn: () => api.listConcepts(params),
    staleTime: 60 * 1000,
  });
}

export function useConcept(conceptId: string) {
  return useQuery({
    queryKey: KEYS.concept(conceptId),
    queryFn: () => api.getConcept(conceptId),
    enabled: !!conceptId,
  });
}

export function useCreateConcept() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createConcept,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'concepts'] });
      qc.invalidateQueries({ queryKey: ['semantic', 'catalog'] });
      toast.success('개념이 등록되었습니다');
    },
    onError: () => toast.error('개념 등록 실패'),
  });
}

export function useChangeConceptStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ conceptId, status }: { conceptId: string; status: ConceptStatus }) =>
      api.changeConceptStatus(conceptId, status),
    onSuccess: (_, { status }) => {
      qc.invalidateQueries({ queryKey: ['semantic', 'concepts'] });
      qc.invalidateQueries({ queryKey: ['semantic', 'catalog'] });
      toast.success(`상태가 '${status}'로 변경되었습니다`);
    },
    onError: (err) => toast.error(`상태 변경 실패: ${(err as Error).message}`),
  });
}

// ── 엔티티 ──

export function useEntities(params?: { case_id?: string }) {
  return useQuery({
    queryKey: KEYS.entities(params),
    queryFn: () => api.listEntities(params),
    staleTime: 60 * 1000,
  });
}

// ── 지표 ──

export function useMeasures(params?: { case_id?: string; entity_id?: string }) {
  return useQuery({
    queryKey: KEYS.measures(params),
    queryFn: () => api.listMeasures(params),
    staleTime: 60 * 1000,
  });
}

// ── 차원 ──

export function useDimensions(params?: { case_id?: string; entity_id?: string }) {
  return useQuery({
    queryKey: KEYS.dimensions(params),
    queryFn: () => api.listDimensions(params),
    staleTime: 60 * 1000,
  });
}

// ── 조인 ──

export function useJoins(params?: { case_id?: string; allowed_for_ai?: boolean }) {
  return useQuery({
    queryKey: KEYS.joins(params),
    queryFn: () => api.listJoins(params),
    staleTime: 60 * 1000,
  });
}

// ── 그레인 계약 ──

export function useGrains(params?: { case_id?: string; entity_id?: string }) {
  return useQuery({
    queryKey: KEYS.grains(params),
    queryFn: () => api.listGrains(params),
    staleTime: 60 * 1000,
  });
}

// ── 품질 계약 ──

export function useQualityContracts(params?: { target_type?: string }) {
  return useQuery({
    queryKey: KEYS.qualityContracts(params),
    queryFn: () => api.listQualityContracts(params),
    staleTime: 60 * 1000,
  });
}

// ── 컴파일 ──

export function useCompileEntity() {
  return useMutation({
    mutationFn: api.compileEntity,
    onError: () => toast.error('엔티티 컴파일 실패'),
  });
}

export function useCompileMeasure() {
  return useMutation({
    mutationFn: api.compileMeasure,
    onError: () => toast.error('지표 컴파일 실패'),
  });
}

// ── 배포 ──

export function usePublish() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ objectType, objectId }: { objectType: string; objectId: string }) =>
      api.publishObject(objectType, objectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic'] });
      toast.success('배포 완료');
    },
    onError: (err) => toast.error(`배포 실패: ${(err as Error).message}`),
  });
}

// ── 컨텍스트 팩 ──

export function useContextPacks(params?: { intent_type?: string }) {
  return useQuery({
    queryKey: KEYS.contextPacks(params),
    queryFn: () => api.listContextPacks(params),
    staleTime: 60 * 1000,
  });
}

export function useCreateContextPack() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createContextPack,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'context-packs'] });
      toast.success('컨텍스트 팩이 등록되었습니다');
    },
    onError: () => toast.error('컨텍스트 팩 등록 실패'),
  });
}

export function useDeleteContextPack() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteContextPack,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'context-packs'] });
      toast.success('컨텍스트 팩이 삭제되었습니다');
    },
  });
}
