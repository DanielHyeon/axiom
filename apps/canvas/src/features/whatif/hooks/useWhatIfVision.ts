import { useState, useEffect, useCallback } from 'react';
import {
  listScenarios,
  createScenario,
  getScenario,
  computeScenario,
  getScenarioStatus,
  getScenarioResult,
  compareScenarios,
  type VisionScenario,
  type VisionScenarioCreate,
  type CompareItem,
} from '../api/visionWhatIfApi';

const POLL_INTERVAL_MS = 1500;
const POLL_MAX_ATTEMPTS = 60;

export function useWhatIfVision(caseId: string | undefined) {
  const [scenarios, setScenarios] = useState<VisionScenario[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [compareResult, setCompareResult] = useState<{ items: CompareItem[] } | null>(null);

  const refetch = useCallback(async () => {
    if (!caseId) return;
    setError(null);
    setLoading(true);
    try {
      const res = await listScenarios(caseId);
      setScenarios(res.data);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
      setScenarios([]);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  const addScenario = useCallback(
    async (payload: VisionScenarioCreate) => {
      if (!caseId) return;
      await createScenario(caseId, payload);
      await refetch();
    },
    [caseId, refetch]
  );

  const runCompute = useCallback(
    async (scenarioId: string): Promise<VisionScenario['result'] | null> => {
      if (!caseId) return null;
      await computeScenario(caseId, scenarioId);
      for (let i = 0; i < POLL_MAX_ATTEMPTS; i++) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
        const status = await getScenarioStatus(caseId, scenarioId);
        if (status.status === 'COMPLETED') {
          const result = await getScenarioResult(caseId, scenarioId);
          await refetch();
          return result ?? null;
        }
        if (status.status === 'FAILED') {
          await refetch();
          return null;
        }
      }
      await refetch();
      return null;
    },
    [caseId, refetch]
  );

  const fetchCompare = useCallback(
    async (scenarioIds: string[]) => {
      if (!caseId || scenarioIds.length < 2) return;
      setCompareResult(null);
      try {
        const res = await compareScenarios(caseId, scenarioIds);
        setCompareResult({ items: res.items });
      } catch (e) {
        console.error('Compare failed', e);
      }
    },
    [caseId]
  );

  return {
    scenarios,
    loading,
    error,
    compareResult,
    refetch,
    addScenario,
    runCompute,
    fetchCompare,
    getScenario: caseId ? (id: string) => getScenario(caseId, id) : () => Promise.reject(new Error('no caseId')),
  };
}
