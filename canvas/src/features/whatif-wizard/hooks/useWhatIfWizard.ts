/**
 * What-if 위자드 오케스트레이션 훅
 *
 * 5단계 위자드 전체 흐름을 관리한다.
 * - DAG 모드: 인과 발견 → 모델 학습 → DAG 시뮬레이션
 * - Event Fork 모드: 브랜치 생성 → 이벤트 포크 시뮬레이션
 *
 * 기존 whatif 피처의 visionWizardApi + 새 eventForkApi를 통합 사용한다.
 */
import { useState, useMemo } from 'react';
import { toast } from 'sonner';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import { useEventFork } from './useEventFork';
import * as wizardApi from '@/features/whatif/api/visionWizardApi';
import type {
  CausalRelation,
  InterventionSpec,
  ForkResult,
  KpiDeltaSummary,
} from '../types/whatifWizard.types';

interface UseWhatIfWizardReturn {
  // ── 로딩 상태 ──
  isDiscovering: boolean;
  isSimulating: boolean;
  isComparing: boolean;

  // ── 에러 ──
  error: string | null;
  clearError: () => void;

  // ── Step 3: 인과 관계 발견 ──
  runCausalDiscovery: (caseId: string) => Promise<void>;

  // ── Step 4→5: 시뮬레이션 실행 ──
  runDagSimulation: (caseId: string) => Promise<void>;
  runEventForkSimulation: (caseId: string) => Promise<ForkResult | null>;

  // ── Step 5: 비교 ──
  runComparison: (caseId: string) => Promise<void>;

  // ── 유틸리티 ──
  /** DAG 시뮬레이션 결과를 KPI 델타 요약으로 변환 */
  kpiDeltaSummaries: KpiDeltaSummary[];
  /** 현재 스텝의 유효성 */
  isStepValid: boolean;

  // Event Fork 훅 전달
  eventFork: ReturnType<typeof useEventFork>;
}

export function useWhatIfWizard(): UseWhatIfWizardReturn {
  // 리렌더링이 필요한 상태만 구독 (stale closure 방지)
  const forkResults = useWhatIfWizardStore((s) => s.forkResults);
  const canProceed = useWhatIfWizardStore((s) => s.canProceed);
  const eventFork = useEventFork();

  const [isDiscovering, setIsDiscovering] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clearError = () => setError(null);

  // ── Step 3: 인과 관계 발견 (DAG 모드) ──
  // useCallback 제거 — 이벤트 핸들러이므로 메모이제이션 불필요
  // store 참조는 getState()로 읽어 stale closure 방지
  const runCausalDiscovery = async (caseId: string) => {
    setIsDiscovering(true);
    setError(null);

    try {
      const { confidenceThreshold, selectedNodeIds, setCausalRelations } =
        useWhatIfWizardStore.getState();

      const result = await wizardApi.discoverEdges(caseId, {
        maxLag: 3,
        minCorrelation: confidenceThreshold,
        selectedNodes:
          selectedNodeIds.length > 0 ? selectedNodeIds : undefined,
      });

      // 기존 CausalEdge → 새 CausalRelation으로 변환
      const relations: CausalRelation[] = result.edges.map((e) => ({
        sourceId: e.source,
        sourceName: e.sourceName,
        targetId: e.target,
        targetName: e.targetName,
        weight: e.strength,
        lag: e.lag,
        confidence: 1 - e.pValue, // p-value를 신뢰도로 변환
        method: e.method as CausalRelation['method'],
        direction: e.direction,
      }));

      setCausalRelations(relations);
      toast.success(`${relations.length}개의 인과 관계가 발견되었습니다.`);
    } catch (e) {
      const msg =
        e instanceof Error ? e.message : '인과 관계 분석 중 오류가 발생했습니다.';
      setError(msg);
      toast.error(msg);
    } finally {
      setIsDiscovering(false);
    }
  };

  // ── Step 4→5: DAG 시뮬레이션 실행 ──
  const runDagSimulation = async (caseId: string) => {
    setIsSimulating(true);
    setError(null);

    try {
      const { interventions, scenarioName, addForkResult } =
        useWhatIfWizardStore.getState();

      // 개입 목록을 Vision DAG API 형식으로 변환
      const mappedInterventions = interventions.map((iv: InterventionSpec) => ({
        nodeId: iv.nodeId,
        field: iv.field,
        value: iv.value,
        description: iv.description,
      }));

      const result = await wizardApi.runSimulation(
        caseId,
        scenarioName || '시뮬레이션',
        mappedInterventions,
      );

      // 결과를 브랜치 형태로 변환하여 스토어에 저장
      const forkResult: ForkResult = {
        branchId: `dag_${Date.now()}`,
        scenarioName: result.scenarioName,
        status: 'completed',
        kpiDeltas: result.deltas,
        kpiBaselines: result.baselineState,
        kpiResults: result.finalState,
        events: result.traces.map((t, idx) => ({
          id: `trace_${idx}`,
          type: 'dag_propagation',
          timestamp: result.executedAt,
          nodeId: t.outputField.split('::')[0] ?? t.modelId,
          description: `${t.modelName}: ${t.baselineValue.toFixed(2)} → ${t.predictedValue.toFixed(2)} (${t.pctChange > 0 ? '+' : ''}${t.pctChange.toFixed(1)}%)`,
        })),
        executedAt: result.executedAt,
      };

      addForkResult(forkResult);
      toast.success('DAG 시뮬레이션이 완료되었습니다.');
    } catch (e) {
      const msg =
        e instanceof Error ? e.message : '시뮬레이션 실행 중 오류가 발생했습니다.';
      setError(msg);
      toast.error(msg);
    } finally {
      setIsSimulating(false);
    }
  };

  // ── Step 4→5: Event Fork 시뮬레이션 ──
  const runEventForkSimulation = async (caseId: string): Promise<ForkResult | null> => {
    setIsSimulating(true);
    setError(null);

    try {
      const { scenarioName, scenarioDescription, interventions } =
        useWhatIfWizardStore.getState();

      // 브랜치 생성
      const branchId = await eventFork.createBranch(
        caseId,
        scenarioName || 'Event Fork 시뮬레이션',
        scenarioDescription,
        interventions,
      );

      if (!branchId) {
        throw new Error('브랜치 생성에 실패했습니다.');
      }

      // 시뮬레이션 실행
      return await eventFork.runSimulation(caseId, branchId);
    } catch (e) {
      const msg =
        e instanceof Error ? e.message : 'Event Fork 시뮬레이션 중 오류가 발생했습니다.';
      setError(msg);
      toast.error(msg);
      return null;
    } finally {
      setIsSimulating(false);
    }
  };

  // ── Step 5: 시나리오 비교 ──
  const runComparison = async (caseId: string) => {
    setIsComparing(true);
    setError(null);

    const { branches } = useWhatIfWizardStore.getState();
    const branchIds = branches
      .filter((b) => b.status === 'completed')
      .map((b) => b.branchId);

    if (branchIds.length < 2) {
      setError('비교하려면 최소 2개의 완료된 시나리오가 필요합니다.');
      setIsComparing(false);
      return;
    }

    try {
      await eventFork.compareScenarios(caseId, branchIds);
      toast.success('시나리오 비교가 완료되었습니다.');
    } catch (e) {
      const msg =
        e instanceof Error ? e.message : '시나리오 비교 중 오류가 발생했습니다.';
      setError(msg);
    } finally {
      setIsComparing(false);
    }
  };

  // ── KPI 델타 요약 계산 ──
  const kpiDeltaSummaries = useMemo((): KpiDeltaSummary[] => {
    const { forkResults } = useWhatIfWizardStore.getState();
    if (forkResults.length === 0) return [];

    // 가장 최근 결과 사용
    const latest = forkResults[forkResults.length - 1];
    const summaries: KpiDeltaSummary[] = [];

    for (const [key, delta] of Object.entries(latest.kpiDeltas)) {
      const baseline = latest.kpiBaselines[key] ?? 0;
      const result = latest.kpiResults[key] ?? baseline + delta;
      const pctChange = baseline !== 0 ? (delta / Math.abs(baseline)) * 100 : 0;

      // 필드명을 사람이 읽을 수 있는 이름으로 변환
      const name = key.includes('::') ? key.split('::').pop()! : key;

      summaries.push({
        name,
        baseline,
        result,
        delta,
        pctChange,
        impact:
          Math.abs(pctChange) < 0.1 ? 'neutral' : pctChange > 0 ? 'positive' : 'negative',
      });
    }

    return summaries;
  }, [forkResults]);

  // ── 스텝 유효성 ──
  const isStepValid = canProceed();

  return {
    isDiscovering,
    isSimulating,
    isComparing,
    error,
    clearError,
    runCausalDiscovery,
    runDagSimulation,
    runEventForkSimulation,
    runComparison,
    kpiDeltaSummaries,
    isStepValid,
    eventFork,
  };
}
