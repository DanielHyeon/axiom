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
  releases: (params?: Record<string, unknown>) => ['semantic', 'releases', params] as const,
  aliasGroups: (params?: Record<string, unknown>) => ['semantic', 'alias-groups', params] as const,
  expansionRules: (groupId?: string) => ['semantic', 'expansion-rules', groupId] as const,
  snapshots: (params?: Record<string, unknown>) => ['semantic', 'snapshots', params] as const,
  activeSnapshot: () => ['semantic', 'snapshots', 'active'] as const,
  relations: (params?: Record<string, unknown>) => ['semantic', 'relations', params] as const,
  rules: (params?: Record<string, unknown>) => ['semantic', 'rules', params] as const,
  policies: (params?: Record<string, unknown>) => ['semantic', 'policies', params] as const,
  segments: (params?: Record<string, unknown>) => ['semantic', 'segments', params] as const,
  timeContracts: (params?: Record<string, unknown>) => ['semantic', 'time-contracts', params] as const,
  accessPolicies: (params?: Record<string, unknown>) => ['semantic', 'access-policies', params] as const,
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

// ── 릴리스 (배포 이력) ──

export function useReleases(params?: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: KEYS.releases(params),
    queryFn: () => api.listReleases(params),
    staleTime: 30 * 1000,
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

// ── 별칭 그룹 ──

export function useAliasGroups(params?: { domain_id?: string; status?: string }) {
  return useQuery({
    queryKey: KEYS.aliasGroups(params),
    queryFn: () => api.listAliasGroups(params),
    staleTime: 60 * 1000,
  });
}

export function useCreateAliasGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createAliasGroup,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'alias-groups'] });
      toast.success('별칭 그룹이 등록되었습니다');
    },
    onError: () => toast.error('별칭 그룹 등록 실패'),
  });
}

// ── 확장 규칙 ──

export function useExpansionRules(aliasGroupId?: string) {
  return useQuery({
    queryKey: KEYS.expansionRules(aliasGroupId),
    queryFn: () => api.listExpansionRules({ alias_group_id: aliasGroupId }),
    enabled: !!aliasGroupId,
    staleTime: 30 * 1000,
  });
}

export function useCreateExpansionRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createExpansionRule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'expansion-rules'] });
      toast.success('확장 규칙이 등록되었습니다');
    },
    onError: () => toast.error('확장 규칙 등록 실패'),
  });
}

export function useActivateRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.activateExpansionRule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'expansion-rules'] });
      toast.success('규칙이 활성화되었습니다');
    },
    onError: (err) => toast.error(`규칙 활성화 실패: ${(err as Error).message}`),
  });
}

export function useDeprecateRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deprecateExpansionRule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'expansion-rules'] });
      toast.success('규칙이 비활성화되었습니다');
    },
    onError: (err) => toast.error(`규칙 비활성화 실패: ${(err as Error).message}`),
  });
}

// ── 스냅샷 ──

export function useSnapshots(params?: { status?: string; limit?: number }) {
  return useQuery({
    queryKey: KEYS.snapshots(params),
    queryFn: () => api.listSnapshots(params),
    staleTime: 30 * 1000,
  });
}

export function useActiveSnapshot() {
  return useQuery({
    queryKey: KEYS.activeSnapshot(),
    queryFn: () => api.getActiveSnapshot(),
    staleTime: 30 * 1000,
  });
}

export function useBuildSnapshot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.buildSnapshot,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'snapshots'] });
      toast.success('스냅샷 빌드가 시작되었습니다');
    },
    onError: (err) => toast.error(`스냅샷 빌드 실패: ${(err as Error).message}`),
  });
}

export function useActivateSnapshot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.activateSnapshot,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'snapshots'] });
      toast.success('스냅샷이 활성화되었습니다');
    },
    onError: (err) => toast.error(`스냅샷 활성화 실패: ${(err as Error).message}`),
  });
}

export function useInvalidateSnapshot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ version, reason }: { version: string; reason: string }) =>
      api.invalidateSnapshot(version, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'snapshots'] });
      toast.success('스냅샷이 무효화되었습니다');
    },
    onError: (err) => toast.error(`스냅샷 무효화 실패: ${(err as Error).message}`),
  });
}

// ── 온톨로지 관계 ──

export function useRelations(params?: { concept_id?: string; predicate_type?: string }) {
  return useQuery({
    queryKey: KEYS.relations(params),
    queryFn: () => api.listRelations(params),
    staleTime: 60 * 1000,
  });
}

export function useCreateRelation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createRelation,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'relations'] });
      toast.success('관계가 등록되었습니다');
    },
    onError: () => toast.error('관계 등록 실패'),
  });
}

export function useDeleteRelation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteRelation,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'relations'] });
      toast.success('관계가 삭제되었습니다');
    },
    onError: () => toast.error('관계 삭제 실패'),
  });
}

// ── 온톨로지 규칙 ──

export function useRules(params?: { concept_id?: string; rule_type?: string }) {
  return useQuery({
    queryKey: KEYS.rules(params),
    queryFn: () => api.listRules(params),
    staleTime: 60 * 1000,
  });
}

export function useCreateRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createRule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'rules'] });
      toast.success('규칙이 등록되었습니다');
    },
    onError: () => toast.error('규칙 등록 실패'),
  });
}

export function useDeleteRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteRule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'rules'] });
      toast.success('규칙이 삭제되었습니다');
    },
    onError: () => toast.error('규칙 삭제 실패'),
  });
}

// ── 온톨로지 정책 ──

export function usePolicies(params?: { concept_id?: string; policy_type?: string }) {
  return useQuery({
    queryKey: KEYS.policies(params),
    queryFn: () => api.listPolicies(params),
    staleTime: 60 * 1000,
  });
}

export function useCreatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createPolicy,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'policies'] });
      toast.success('정책이 등록되었습니다');
    },
    onError: () => toast.error('정책 등록 실패'),
  });
}

export function useDeletePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deletePolicy,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'policies'] });
      toast.success('정책이 삭제되었습니다');
    },
    onError: () => toast.error('정책 삭제 실패'),
  });
}

export function useTogglePolicyActive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      api.togglePolicyActive(id, isActive),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['semantic', 'policies'] });
      toast.success('정책 상태가 변경되었습니다');
    },
    onError: () => toast.error('정책 상태 변경 실패'),
  });
}

// ── L2 세그먼트 / 시간 계약 / 접근 정책 ──

export function useSegments(params?: { entity_id?: string; segment_type?: string }) {
  return useQuery({
    queryKey: KEYS.segments(params),
    queryFn: () => api.listSegments(params),
    staleTime: 60 * 1000,
  });
}

export function useTimeContracts(params?: { entity_id?: string }) {
  return useQuery({
    queryKey: KEYS.timeContracts(params),
    queryFn: () => api.listTimeContracts(params),
    staleTime: 60 * 1000,
  });
}

export function useAccessPolicies(params?: { entity_id?: string; is_active?: boolean }) {
  return useQuery({
    queryKey: KEYS.accessPolicies(params),
    queryFn: () => api.listAccessPolicies(params),
    staleTime: 60 * 1000,
  });
}
