/**
 * 글로서리 TanStack Query 훅
 * 서버 상태(용어집/용어/카테고리)를 캐시 관리
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '../api/glossaryApi';
import type {
  GlossaryCreateRequest,
  TermCreateRequest,
  TermSearchParams,
  TermStatus,
} from '../types/glossary';

// ---------------------------------------------------------------------------
// 쿼리 키 팩토리 — 캐시 무효화를 체계적으로 관리
// ---------------------------------------------------------------------------
export const glossaryKeys = {
  all: ['glossary'] as const,
  lists: () => [...glossaryKeys.all, 'list'] as const,
  glossaries: () => [...glossaryKeys.lists(), 'glossaries'] as const,
  terms: (glossaryId: string) =>
    [...glossaryKeys.lists(), 'terms', glossaryId] as const,
  termsFiltered: (params: TermSearchParams) =>
    [...glossaryKeys.terms(params.glossaryId), params] as const,
  categories: () => [...glossaryKeys.all, 'categories'] as const,
};

// ---------------------------------------------------------------------------
// 용어집 목록
// ---------------------------------------------------------------------------
export function useGlossaries() {
  return useQuery({
    queryKey: glossaryKeys.glossaries(),
    queryFn: api.fetchGlossaries,
    staleTime: 30_000, // 30초간 캐시 유지
  });
}

// ---------------------------------------------------------------------------
// 용어 목록 (검색/필터 지원)
// ---------------------------------------------------------------------------
export function useTerms(
  glossaryId: string | null,
  options?: { query?: string; category?: string; status?: TermStatus },
) {
  const params: TermSearchParams = {
    glossaryId: glossaryId ?? '',
    query: options?.query,
    category: options?.category,
    status: options?.status,
  };

  return useQuery({
    queryKey: glossaryKeys.termsFiltered(params),
    queryFn: () => api.fetchTerms(params),
    enabled: !!glossaryId, // 용어집 미선택 시 비활성화
    staleTime: 15_000,
  });
}

// ---------------------------------------------------------------------------
// 카테고리 목록
// ---------------------------------------------------------------------------
export function useCategories() {
  return useQuery({
    queryKey: glossaryKeys.categories(),
    queryFn: api.fetchCategories,
    staleTime: 60_000,
  });
}

// ---------------------------------------------------------------------------
// 용어집 Mutations
// ---------------------------------------------------------------------------

export function useCreateGlossary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: GlossaryCreateRequest) => api.createGlossary(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: glossaryKeys.glossaries() });
    },
  });
}

export function useUpdateGlossary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<GlossaryCreateRequest> }) =>
      api.updateGlossary(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: glossaryKeys.glossaries() });
    },
  });
}

export function useDeleteGlossary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteGlossary(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: glossaryKeys.glossaries() });
    },
  });
}

// ---------------------------------------------------------------------------
// 용어 Mutations
// ---------------------------------------------------------------------------

export function useCreateTerm(glossaryId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: TermCreateRequest) =>
      api.createTerm(glossaryId, data),
    onSuccess: () => {
      // 용어 목록 + 용어집(termCount 갱신) 캐시 무효화
      qc.invalidateQueries({ queryKey: glossaryKeys.terms(glossaryId) });
      qc.invalidateQueries({ queryKey: glossaryKeys.glossaries() });
    },
  });
}

export function useUpdateTerm(glossaryId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ termId, data }: { termId: string; data: Partial<TermCreateRequest> }) =>
      api.updateTerm(glossaryId, termId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: glossaryKeys.terms(glossaryId) });
    },
  });
}

export function useDeleteTerm(glossaryId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (termId: string) => api.deleteTerm(glossaryId, termId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: glossaryKeys.terms(glossaryId) });
      qc.invalidateQueries({ queryKey: glossaryKeys.glossaries() });
    },
  });
}

// ---------------------------------------------------------------------------
// 카테고리 Mutations
// ---------------------------------------------------------------------------

export function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, color }: { name: string; color: string }) =>
      api.createCategory(name, color),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: glossaryKeys.categories() });
    },
  });
}

export function useDeleteCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteCategory(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: glossaryKeys.categories() });
    },
  });
}
