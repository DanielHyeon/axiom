// features/insight/hooks/useImpactGraph.ts
// Polling hook for Impact Graph analysis (202 async pattern)

import { useEffect, useRef, useCallback } from 'react';
import { useInsightStore } from '../store/useInsightStore';
import {
  requestImpact,
  isJobResponse,
  getJobStatus,
} from '../api/insightApi';
import type {
  TimeRange,
  ImpactResponse,
  GraphData,
  ImpactPath,
  BackendPath,
} from '../types/insight';

/** Maximum number of poll attempts */
const MAX_POLL = 30;
/** Maximum total polling time (ms) */
const MAX_POLL_TOTAL_MS = 300_000;

interface UseImpactGraphOptions {
  kpiFingerprint: string | null;
  timeRange: TimeRange;
  datasource?: string | null;
}

interface UseImpactGraphReturn {
  loading: boolean;
  error: string | null;
  graph: GraphData | null;
  paths: ImpactPath[];   // derived from store.impactPaths
  cancel: () => void;
  retry: () => void;
}

/** Transform backend path format → ImpactPath (add path_id, strength alias) */
function transformPaths(
  rawPaths: BackendPath[],
  kpiFingerprint: string,
): ImpactPath[] {
  return rawPaths.map((p, idx) => ({
    path_id: `path_${idx}`,
    kpi_id: kpiFingerprint,
    driver_id: p.nodes[1] ?? '',
    nodes: p.nodes,
    strength: p.score,
    queries_count: 0,
  }));
}

export function useImpactGraph({
  kpiFingerprint,
  timeRange,
  datasource,
}: UseImpactGraphOptions): UseImpactGraphReturn {
  const store = useInsightStore();
  const abortRef = useRef<AbortController | null>(null);
  const pollCountRef = useRef(0);
  const pollStartRef = useRef(0);
  // pathsRef kept for backward-compat return value; store is the source of truth
  const pathsRef = useRef<ImpactPath[]>([]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const runAnalysis = useCallback(async () => {
    if (!kpiFingerprint) return;

    // Cancel any previous in-flight request
    cancel();

    const controller = new AbortController();
    abortRef.current = controller;

    store.setImpactGraphLoading(true);
    store.setImpactGraphError(null);
    store.setImpactPaths([]);
    store.setImpactEvidence(null);
    pathsRef.current = [];

    try {
      // Step 1: Request impact analysis
      const response = await requestImpact({
        kpi_fingerprint: kpiFingerprint,
        time_range: timeRange,
        datasource_id: datasource ?? undefined,
      });

      if (controller.signal.aborted) return;

      // Step 2a: 200 — Cached result available immediately
      // Backend returns the same { graph, paths, evidence } structure as job result,
      // so we drill into .graph.graph the same way as the polling path.
      if (!isJobResponse(response)) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const result = response as any;
        const graphData = result.graph?.graph ?? (result.graph as ImpactResponse['graph'] | undefined);
        if (graphData?.nodes) {
          store.setImpactGraph(graphData);
          const paths = transformPaths(
            (result.graph?.paths as BackendPath[] | undefined) ?? [],
            kpiFingerprint,
          );
          pathsRef.current = paths;
          store.setImpactPaths(paths);
          if (result.graph?.evidence) {
            store.setImpactEvidence(result.graph.evidence);
          }
        } else {
          store.setImpactGraphError('서버 응답에 그래프 데이터가 없습니다.');
        }
        return;
      }

      // Step 2b: 202 — Start polling
      const jobId = response.job_id;
      let pollInterval = response.poll_after_ms || 1000;
      pollCountRef.current = 0;
      pollStartRef.current = Date.now();

      store.setJobStatus({
        job_id: jobId,
        status: response.status,
        poll_after_ms: pollInterval,
      });

      const poll = async (): Promise<void> => {
        if (controller.signal.aborted) return;

        // Guard: max poll count
        if (pollCountRef.current >= MAX_POLL) {
          store.setImpactGraphError(
            `분석 시간이 초과되었습니다. (최대 ${MAX_POLL}회 폴링)`,
          );
          return;
        }

        // Guard: max total time
        if (Date.now() - pollStartRef.current > MAX_POLL_TOTAL_MS) {
          store.setImpactGraphError(
            '분석 시간이 초과되었습니다. (5분 타임아웃)',
          );
          return;
        }

        pollCountRef.current += 1;

        try {
          const status = await getJobStatus(jobId);

          if (controller.signal.aborted) return;

          store.setJobStatus({
            job_id: status.job_id,
            status: status.status,
            progress_pct: status.progress,
            poll_after_ms: pollInterval,
            error: status.error,
          });

          if (status.status === 'done') {
            // Extract graph from job result
            if (status.graph?.graph) {
              store.setImpactGraph(status.graph.graph);
              const paths = transformPaths(
                status.graph.paths ?? [],
                kpiFingerprint,
              );
              pathsRef.current = paths;
              store.setImpactPaths(paths);
              if (status.graph.evidence) {
                store.setImpactEvidence(status.graph.evidence);
              }
            } else {
              store.setImpactGraphError(
                '분석이 완료되었지만 그래프 데이터가 비어 있습니다.',
              );
            }
            return;
          }

          if (status.status === 'failed') {
            store.setImpactGraphError(
              status.error ?? '분석에 실패했습니다.',
            );
            return;
          }

          // Still running: schedule next poll with increasing interval
          pollInterval = Math.min(pollInterval * 1.2, 5000);

          await new Promise<void>((resolve) => {
            const timer = setTimeout(resolve, pollInterval);
            controller.signal.addEventListener('abort', () => {
              clearTimeout(timer);
              resolve();
            });
          });

          await poll();
        } catch (err) {
          if (controller.signal.aborted) return;
          store.setImpactGraphError(
            err instanceof Error ? err.message : '폴링 중 오류가 발생했습니다.',
          );
        }
      };

      // Start first poll after initial delay
      await new Promise<void>((resolve) => {
        const timer = setTimeout(resolve, pollInterval);
        controller.signal.addEventListener('abort', () => {
          clearTimeout(timer);
          resolve();
        });
      });

      await poll();
    } catch (err) {
      if (controller.signal.aborted) return;
      store.setImpactGraphError(
        err instanceof Error ? err.message : 'Impact 분석 요청에 실패했습니다.',
      );
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kpiFingerprint, timeRange, datasource, cancel]);

  // Run analysis when inputs change
  useEffect(() => {
    runAnalysis();
    return () => {
      cancel();
    };
  }, [runAnalysis, cancel]);

  return {
    loading: store.impactGraphLoading,
    error: store.impactGraphError,
    graph: store.impactGraph,
    paths: store.impactPaths,
    cancel,
    retry: runAnalysis,
  };
}
