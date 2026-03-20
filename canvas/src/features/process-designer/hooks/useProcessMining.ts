// features/process-designer/hooks/useProcessMining.ts
// 프로세스 마이닝 결과 조회 hook (설계 §5.2)
// Required: "프로세스 마이닝 API를 컴포넌트에서 직접 호출 금지"

import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  getConformance,
  getBottlenecks,
  type ConformanceResult,
  type BottleneckResult,
} from '../api/processDesignerApi';
import type { EventLogBindingData } from '../types/processDesigner';

interface UseProcessMiningOptions {
  boardId: string | undefined;
  bindings: EventLogBindingData[];
  enabled?: boolean;
}

interface UseProcessMiningReturn {
  conformance: ConformanceResult | null;
  bottlenecks: BottleneckResult | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  toggleOverlay: () => void;
  overlayVisible: boolean;
}

export function useProcessMining({
  boardId,
  bindings,
  enabled: externalEnabled = true,
}: UseProcessMiningOptions): UseProcessMiningReturn {
  const [overlayVisible, setOverlayVisible] = useState(false);

  const hasBindings = bindings.length > 0;
  const queryEnabled = externalEnabled && hasBindings && !!boardId;

  const conformanceQuery = useQuery({
    queryKey: ['process-mining', 'conformance', boardId, bindings],
    queryFn: () => getConformance(boardId!, bindings),
    enabled: queryEnabled,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const bottleneckQuery = useQuery({
    queryKey: ['process-mining', 'bottleneck', boardId, bindings],
    queryFn: () => getBottlenecks(boardId!, bindings),
    enabled: queryEnabled,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const loading = conformanceQuery.isLoading || bottleneckQuery.isLoading;
  const error = conformanceQuery.error?.message ?? bottleneckQuery.error?.message ?? null;

  const refresh = useCallback(() => {
    conformanceQuery.refetch();
    bottleneckQuery.refetch();
  }, [conformanceQuery, bottleneckQuery]);

  const toggleOverlay = useCallback(() => {
    setOverlayVisible((v) => !v);
  }, []);

  return {
    conformance: conformanceQuery.data ?? null,
    bottlenecks: bottleneckQuery.data ?? null,
    loading,
    error,
    refresh,
    toggleOverlay,
    overlayVisible,
  };
}
