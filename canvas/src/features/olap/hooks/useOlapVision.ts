import { useQuery, useMutation } from '@tanstack/react-query';
import { useState, useCallback } from 'react';
import { listCubes, pivotQuery, type PivotQueryResponse } from '../api/visionOlapApi';
import type { PivotConfig, CubeDefinition } from '../types/olap';
import type { OlapQueryResult } from './useOlapMock';

function pivotResponseToResult(res: PivotQueryResponse): OlapQueryResult {
  const headers = res.columns?.map((c) => c.name) ?? [];
  const data = (res.rows ?? []).map((row) => headers.map((h) => row[h] ?? null));
  return {
    headers,
    data,
    executionTimeMs: res.execution_time_ms ?? 0,
  };
}

export function useOlapVision() {
  const [error, setError] = useState<string | null>(null);

  const { data: cubes = [], isLoading: cubesLoading } = useQuery({
    queryKey: ['olap', 'cubes'],
    queryFn: listCubes,
    staleTime: 60 * 1000,
  });

  const mutation = useMutation({
    mutationFn: async (config: PivotConfig) => {
      if (!config.cubeId) throw new Error('분석할 큐브를 선택하세요.');
      if (config.measures.length === 0) throw new Error('최소 1개 이상의 측정값을 배치해야 합니다.');
      if (config.rows.length === 0 && config.columns.length === 0) {
        throw new Error('분석할 행 또는 열 차원을 1개 이상 배치해 주세요.');
      }
      return pivotQuery({
        cube_name: config.cubeId,
        rows: config.rows.map((r) => r.name),
        columns: config.columns.map((c) => c.name),
        measures: config.measures.map((m) => m.name),
      });
    },
    onSuccess: () => setError(null),
    onError: (err: Error) => setError(err.message || '쿼리 실행 중 오류가 발생했습니다.'),
  });

  const executeQuery = useCallback(
    async (config: PivotConfig) => {
      setError(null);
      try {
        const res = await mutation.mutateAsync(config);
        return pivotResponseToResult(res);
      } catch {
        return null;
      }
    },
    [mutation]
  );

  return {
    cubes: cubes as CubeDefinition[],
    cubesLoading,
    executeQuery,
    isQuerying: mutation.isPending,
    queryResult: mutation.data ? pivotResponseToResult(mutation.data) : null,
    error,
  };
}
