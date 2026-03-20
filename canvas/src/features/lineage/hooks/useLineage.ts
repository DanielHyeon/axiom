/**
 * 리니지 데이터 로딩 훅 (TanStack Query)
 * API → 스토어 연동, 검색, 개요 로딩 등
 */

import { useQuery } from '@tanstack/react-query';
import { useCallback } from 'react';
import {
  getLineageOverview,
  getLineageGraph,
  searchLineageNodes,
} from '../api/lineageApi';
import { useLineageStore } from '../store/useLineageStore';
import type { LineageDirection } from '../types/lineage';

// ---------------------------------------------------------------------------
// 리니지 개요 (전체 그래프) — 초기 로딩
// ---------------------------------------------------------------------------

/** 전체 리니지 개요 로딩 훅 */
export function useLineageOverview() {
  const { setGraphData, setStats } = useLineageStore();

  return useQuery({
    queryKey: ['lineage', 'overview'],
    queryFn: async () => {
      const result = await getLineageOverview();
      // 스토어에 동기화
      setGraphData(result.nodes, result.edges);
      setStats(result.stats);
      return result;
    },
    staleTime: 5 * 60 * 1000, // 5분 캐시
    refetchOnWindowFocus: false,
  });
}

// ---------------------------------------------------------------------------
// 특정 노드 기준 리니지 그래프
// ---------------------------------------------------------------------------

/** 특정 노드 기준 리니지 그래프 훅 */
export function useLineageGraph(
  nodeId: string | null,
  direction: LineageDirection = 'both',
  depth = 3,
) {
  const { setGraphData } = useLineageStore();

  return useQuery({
    queryKey: ['lineage', 'graph', nodeId, direction, depth],
    queryFn: async () => {
      if (!nodeId) return null;
      const result = await getLineageGraph(nodeId, direction, depth);
      setGraphData(result.nodes, result.edges);
      return result;
    },
    enabled: !!nodeId,
    staleTime: 2 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

// ---------------------------------------------------------------------------
// 검색
// ---------------------------------------------------------------------------

/** 리니지 노드 검색 훅 (디바운스 적용 권장) */
export function useLineageSearch(query: string) {
  return useQuery({
    queryKey: ['lineage', 'search', query],
    queryFn: () => searchLineageNodes(query),
    enabled: query.length >= 2,
    staleTime: 30 * 1000,
  });
}

// ---------------------------------------------------------------------------
// 리프레시 핸들러
// ---------------------------------------------------------------------------

/** 리니지 데이터 강제 새로고침 콜백 */
export function useLineageRefresh() {
  const { setGraphData, setStats } = useLineageStore();

  return useCallback(async () => {
    const result = await getLineageOverview();
    setGraphData(result.nodes, result.edges);
    setStats(result.stats);
    return result;
  }, [setGraphData, setStats]);
}
