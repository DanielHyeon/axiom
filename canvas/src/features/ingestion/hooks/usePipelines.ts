/**
 * 파이프라인 CRUD 및 실행 상태 관리 훅
 * TanStack Query 패턴 — 목록 조회/실행/중지/폴링
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import {
  listPipelines,
  runPipeline as apiRunPipeline,
  stopPipeline as apiStopPipeline,
  getPipelineStatus,
  createPipeline as apiCreatePipeline,
  deletePipeline as apiDeletePipeline,
  listIngestionHistory,
} from '../api/ingestionApi';
import { useIngestionStore } from '../store/useIngestionStore';
import type {
  Pipeline,
  PipelineStatusResponse,
  IngestionRecord,
} from '../types/ingestion';

/** 상태 폴링 간격 (ms) */
const POLL_INTERVAL = 2000;

export function usePipelines() {
  // 파이프라인 목록
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // 실행 상태 폴링
  const [runningStatus, setRunningStatus] = useState<PipelineStatusResponse | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 수집 이력
  const [history, setHistory] = useState<IngestionRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const { selectedPipelineId, setSelectedPipelineId } = useIngestionStore();

  // ------------------------------------------------------------------
  // 목록 조회
  // ------------------------------------------------------------------

  const fetchPipelines = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await listPipelines();
      setPipelines(res.pipelines);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
      setPipelines([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPipelines();
  }, [fetchPipelines]);

  // ------------------------------------------------------------------
  // 파이프라인 CRUD
  // ------------------------------------------------------------------

  const createPipelineHandler = useCallback(
    async (payload: { name: string; datasourceId: string; schedule?: string }) => {
      try {
        const created = await apiCreatePipeline(payload);
        setPipelines((prev) => [...prev, created]);
        toast.success(`파이프라인 "${payload.name}" 생성 완료`);
        return created;
      } catch (err) {
        toast.error('파이프라인 생성에 실패했습니다.');
        throw err;
      }
    },
    [],
  );

  const deletePipelineHandler = useCallback(
    async (id: string) => {
      try {
        await apiDeletePipeline(id);
        setPipelines((prev) => prev.filter((p) => p.id !== id));
        if (selectedPipelineId === id) setSelectedPipelineId(null);
        toast.success('파이프라인이 삭제되었습니다.');
      } catch (err) {
        toast.error('파이프라인 삭제에 실패했습니다.');
        throw err;
      }
    },
    [selectedPipelineId, setSelectedPipelineId],
  );

  // ------------------------------------------------------------------
  // 파이프라인 실행 / 중지
  // ------------------------------------------------------------------

  /** 실행 상태 폴링 시작 */
  const startPolling = useCallback((pipelineId: string) => {
    // 기존 폴링 정리
    if (pollingRef.current) clearInterval(pollingRef.current);

    pollingRef.current = setInterval(async () => {
      try {
        const status = await getPipelineStatus(pipelineId);
        setRunningStatus(status);

        // 파이프라인 목록에서도 상태 반영
        setPipelines((prev) =>
          prev.map((p) =>
            p.id === pipelineId
              ? { ...p, status: status.status, steps: status.steps }
              : p,
          ),
        );

        // 완료/실패 시 폴링 중지
        if (status.status === 'completed' || status.status === 'failed') {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          if (status.status === 'completed') {
            toast.success('파이프라인 실행이 완료되었습니다.');
          } else {
            toast.error('파이프라인 실행이 실패했습니다.');
          }
        }
      } catch {
        // 폴링 실패 시 무시 (일시적 네트워크 오류)
      }
    }, POLL_INTERVAL);
  }, []);

  /** 실행 */
  const runPipelineHandler = useCallback(
    async (id: string) => {
      try {
        await apiRunPipeline(id);
        // 목록에서 상태 즉시 반영
        setPipelines((prev) =>
          prev.map((p) => (p.id === id ? { ...p, status: 'running' as const } : p)),
        );
        toast.success('파이프라인 실행을 시작했습니다.');
        startPolling(id);
      } catch (err) {
        toast.error('파이프라인 실행에 실패했습니다.');
        throw err;
      }
    },
    [startPolling],
  );

  /** 중지 */
  const stopPipelineHandler = useCallback(async (id: string) => {
    try {
      await apiStopPipeline(id);
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      setPipelines((prev) =>
        prev.map((p) => (p.id === id ? { ...p, status: 'idle' as const } : p)),
      );
      setRunningStatus(null);
      toast.success('파이프라인이 중지되었습니다.');
    } catch (err) {
      toast.error('파이프라인 중지에 실패했습니다.');
      throw err;
    }
  }, []);

  // ------------------------------------------------------------------
  // 수집 이력
  // ------------------------------------------------------------------

  const fetchHistory = useCallback(async (pipelineId?: string) => {
    setHistoryLoading(true);
    try {
      const res = await listIngestionHistory({ pipelineId, limit: 50 });
      setHistory(res.records);
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  // ------------------------------------------------------------------
  // 정리
  // ------------------------------------------------------------------

  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  return {
    // 파이프라인 목록
    pipelines,
    loading,
    error,
    refetch: fetchPipelines,

    // CRUD
    createPipeline: createPipelineHandler,
    deletePipeline: deletePipelineHandler,

    // 실행
    runPipeline: runPipelineHandler,
    stopPipeline: stopPipelineHandler,
    runningStatus,

    // 이력
    history,
    historyLoading,
    fetchHistory,
  };
}
