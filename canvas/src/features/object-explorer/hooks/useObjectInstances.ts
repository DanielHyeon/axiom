/**
 * useObjectInstances — 인스턴스 목록 로딩 훅
 *
 * TanStack Query로 페이지네이션된 인스턴스 목록을 관리한다.
 * queryKey: ['object-explorer', 'instances', objectTypeId, filter]
 */

import { useQuery } from '@tanstack/react-query';
import { listInstances, searchInstances } from '../api/objectExplorerApi';
import type { InstanceFilter } from '../types/object-explorer';

// ── Query Keys ──
const KEYS = {
  /** ObjectType 하위 인스턴스 목록 */
  instances: (objectTypeId: string, filter: InstanceFilter) =>
    ['object-explorer', 'instances', objectTypeId, filter] as const,

  /** 전체 검색 */
  search: (query: string, page: number) =>
    ['object-explorer', 'search', query, page] as const,
};

// ──────────────────────────────────────
// 인스턴스 목록 훅
// ──────────────────────────────────────

/** 선택된 ObjectType의 인스턴스 목록을 가져온다 */
export function useObjectInstances(
  objectTypeId: string | null,
  filter: InstanceFilter,
) {
  return useQuery({
    queryKey: KEYS.instances(objectTypeId ?? '', filter),
    queryFn: () => listInstances(objectTypeId!, filter),
    enabled: !!objectTypeId,
    staleTime: 30_000, // 30초 캐시
    placeholderData: (prev) => prev, // 페이지 전환 시 이전 데이터 유지
  });
}

// ──────────────────────────────────────
// 전체 검색 훅
// ──────────────────────────────────────

/** 모든 ObjectType에서 인스턴스를 검색한다 */
export function useInstanceSearch(query: string, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: KEYS.search(query, page),
    queryFn: () => searchInstances(query, page, pageSize),
    enabled: query.trim().length >= 2, // 최소 2글자 이상
    staleTime: 30_000,
  });
}
