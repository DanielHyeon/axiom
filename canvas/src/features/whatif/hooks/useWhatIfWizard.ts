/**
 * What-if 위자드 상태 관리 훅
 *
 * 스토어 + API 호출 로직을 결합하여
 * 각 단계의 비즈니스 로직을 제공한다.
 */
import { useCallback, useState } from 'react';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import * as wizardApi from '../api/visionWizardApi';
import type { CausalEdge, ModelSpec, SimulationResult, SnapshotData } from '../types/wizard';

interface UseWhatIfWizardReturn {
  // ── 로딩 상태 ──
  isDiscovering: boolean;
  isBuildingGraph: boolean;
  isTraining: boolean;
  isSimulating: boolean;
  isLoadingSnapshot: boolean;

  // ── 에러 상태 ──
  error: string | null;

  // ── Step 3: 인과 관계 발견 ──
  runDiscovery: () => Promise<void>;
  buildModelGraph: () => Promise<void>;

  // ── Step 4: 모델 학습 ──
  runTraining: () => Promise<void>;

  // ── Step 5: 시뮬레이션 ──
  loadSnapshot: (date?: string) => Promise<void>;
  runSimulation: (
    interventions: Array<{ nodeId: string; field: string; value: number; description: string }>
  ) => Promise<SimulationResult | null>;

  // ── 추가 데이터 ──
  discoveryStats: { dataRows: number; variablesCount: number } | null;
}

export function useWhatIfWizard(): UseWhatIfWizardReturn {
  const store = useWhatIfWizardStore();

  // 로딩 상태
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [isBuildingGraph, setIsBuildingGraph] = useState(false);
  const [isTraining, setIsTraining] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isLoadingSnapshot, setIsLoadingSnapshot] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [discoveryStats, setDiscoveryStats] = useState<{
    dataRows: number;
    variablesCount: number;
  } | null>(null);

  // ── Step 3: 인과 관계 발견 ──
  const runDiscovery = useCallback(async () => {
    const { caseId, discoveryParams, selectedNodes } = useWhatIfWizardStore.getState();
    if (!caseId) {
      setError('케이스 ID가 설정되지 않았습니다.');
      return;
    }

    setIsDiscovering(true);
    setError(null);

    try {
      const result = await wizardApi.discoverEdges(caseId, {
        maxLag: discoveryParams.maxLag,
        minCorrelation: discoveryParams.minCorrelation,
        selectedNodes: selectedNodes.length > 0 ? selectedNodes : undefined,
      });

      store.setDiscoveredEdges(result.edges);
      setDiscoveryStats({
        dataRows: result.dataRows,
        variablesCount: result.variablesCount,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : '인과 관계 분석 중 오류가 발생했습니다.');
    } finally {
      setIsDiscovering(false);
    }
  }, [store]);

  // ── Step 3→4: 모델 그래프 구성 ──
  const buildModelGraph = useCallback(async () => {
    const { caseId, discoveredEdges } = useWhatIfWizardStore.getState();
    if (!caseId) return;

    const selectedEdges = discoveredEdges.filter((e: CausalEdge) => e.selected);
    if (selectedEdges.length === 0) {
      setError('선택된 인과 관계가 없습니다.');
      return;
    }

    setIsBuildingGraph(true);
    setError(null);

    try {
      const specs = await wizardApi.buildModelGraph(caseId, selectedEdges);
      store.setModelSpecs(specs);
    } catch (e) {
      setError(e instanceof Error ? e.message : '모델 그래프 구성 중 오류가 발생했습니다.');
    } finally {
      setIsBuildingGraph(false);
    }
  }, [store]);

  // ── Step 4: 모델 학습 ──
  const runTraining = useCallback(async () => {
    const { caseId, modelSpecs } = useWhatIfWizardStore.getState();
    if (!caseId || modelSpecs.length === 0) return;

    setIsTraining(true);
    setError(null);

    // 모든 모델을 pending 상태로 설정
    store.setTrainedModels(
      modelSpecs.map((s: ModelSpec) => ({
        modelId: s.modelId,
        name: s.name,
        inputNodes: s.features.map((f) => `${f.nodeId}::${f.field}`),
        outputNode: `${s.targetNodeId}::${s.targetField}`,
        modelType: '',
        r2Score: 0,
        rmse: 0,
        status: 'training' as const,
        executionOrder: s.executionOrder,
        neo4jSaved: false,
      }))
    );

    try {
      const trainedModels = await wizardApi.trainModels(caseId, modelSpecs);
      store.setTrainedModels(trainedModels);
    } catch (e) {
      setError(e instanceof Error ? e.message : '모델 학습 중 오류가 발생했습니다.');
      // 실패 시 모든 모델을 failed 상태로
      const { trainedModels } = useWhatIfWizardStore.getState();
      store.setTrainedModels(
        trainedModels.map((m) => ({
          ...m,
          status: 'failed' as const,
        }))
      );
    } finally {
      setIsTraining(false);
    }
  }, [store]);

  // ── Step 5: 스냅샷 로드 ──
  const loadSnapshot = useCallback(
    async (date?: string) => {
      const { caseId } = useWhatIfWizardStore.getState();
      if (!caseId) return;

      setIsLoadingSnapshot(true);
      setError(null);

      try {
        const data: SnapshotData = await wizardApi.getSnapshot(caseId, date);
        store.setSnapshotData(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : '스냅샷 로드 중 오류가 발생했습니다.');
      } finally {
        setIsLoadingSnapshot(false);
      }
    },
    [store]
  );

  // ── Step 5: 시뮬레이션 실행 ──
  const runSimulation = useCallback(
    async (
      interventions: Array<{ nodeId: string; field: string; value: number; description: string }>
    ): Promise<SimulationResult | null> => {
      const { caseId, scenarioName, snapshotData } = useWhatIfWizardStore.getState();
      if (!caseId) return null;

      setIsSimulating(true);
      setError(null);

      try {
        const result = await wizardApi.runSimulation(
          caseId,
          scenarioName || '시뮬레이션',
          interventions,
          snapshotData?.snapshot
        );
        store.addSimulationResult(result);
        return result;
      } catch (e) {
        setError(e instanceof Error ? e.message : '시뮬레이션 실행 중 오류가 발생했습니다.');
        return null;
      } finally {
        setIsSimulating(false);
      }
    },
    [store]
  );

  return {
    isDiscovering,
    isBuildingGraph,
    isTraining,
    isSimulating,
    isLoadingSnapshot,
    error,
    runDiscovery,
    buildModelGraph,
    runTraining,
    loadSnapshot,
    runSimulation,
    discoveryStats,
  };
}
