/**
 * useInstanceDetail — 인스턴스 상세 로딩 훅
 *
 * TanStack Query로 인스턴스 상세 + 관련 인스턴스 정보를 로딩한다.
 * queryKey: ['object-explorer', 'instanceDetail', instanceId]
 */

import { useQuery } from '@tanstack/react-query';
import { getInstanceDetail } from '../api/objectExplorerApi';

/** 인스턴스 상세 조회 (관련 인스턴스 포함) */
export function useInstanceDetail(instanceId: string | null) {
  return useQuery({
    queryKey: ['object-explorer', 'instanceDetail', instanceId ?? ''],
    queryFn: () => getInstanceDetail(instanceId!),
    enabled: !!instanceId,
    staleTime: 60_000, // 1분 캐시
  });
}
