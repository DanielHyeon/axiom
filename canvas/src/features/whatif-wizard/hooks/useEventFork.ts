/**
 * Event Fork API 호출 훅
 *
 * 브랜치 생성, 시뮬레이션 실행, 비교 등의
 * API 호출을 로딩/에러 상태와 함께 제공한다.
 */
import { useCallback, useState } from 'react';
import { toast } from 'sonner';
import * as eventForkApi from '../api/eventForkApi';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import type {
  InterventionSpec,
  ForkResult,
  SimulationBranch,
  ScenarioComparisonResult,
  ForkEvent,
} from '../types/whatifWizard.types';

interface UseEventForkReturn {
  // 로딩 상태
  isCreating: boolean;
  isRunning: boolean;
  isComparing: boolean;
  isDeleting: boolean;
  isFetchingEvents: boolean;

  // 에러
  error: string | null;

  // 브랜치 관리
  createBranch: (
    caseId: string,
    name: string,
    description: string,
    interventions: InterventionSpec[],
  ) => Promise<string | null>;

  // 시뮬레이션 실행
  runSimulation: (caseId: string, branchId: string) => Promise<ForkResult | null>;

  // 브랜치 조회
  fetchBranch: (caseId: string, branchId: string) => Promise<SimulationBranch | null>;

  // 이벤트 목록 조회
  fetchEvents: (
    caseId: string,
    branchId: string,
    limit?: number,
    offset?: number,
  ) => Promise<{ events: ForkEvent[]; total: number } | null>;

  // 시나리오 비교
  compareScenarios: (
    caseId: string,
    branchIds: string[],
  ) => Promise<ScenarioComparisonResult | null>;

  // 브랜치 삭제
  deleteBranch: (caseId: string, branchId: string) => Promise<boolean>;
}

export function useEventFork(): UseEventForkReturn {
  const store = useWhatIfWizardStore;

  const [isCreating, setIsCreating] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isFetchingEvents, setIsFetchingEvents] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── 브랜치 생성 ──
  const createBranch = useCallback(
    async (
      caseId: string,
      name: string,
      description: string,
      interventions: InterventionSpec[],
    ): Promise<string | null> => {
      setIsCreating(true);
      setError(null);

      try {
        const branchId = await eventForkApi.createBranch(caseId, {
          name,
          description,
          interventions,
        });

        // 스토어에 브랜치 추가
        const newBranch: SimulationBranch = {
          branchId,
          name,
          description,
          interventions,
          status: 'created',
          createdAt: new Date().toISOString(),
        };
        store.getState().addBranch(newBranch);

        toast.success('브랜치가 생성되었습니다.');
        return branchId;
      } catch (e) {
        const msg = e instanceof Error ? e.message : '브랜치 생성 중 오류가 발생했습니다.';
        setError(msg);
        toast.error(msg);
        return null;
      } finally {
        setIsCreating(false);
      }
    },
    [],
  );

  // ── 시뮬레이션 실행 ──
  const runSimulation = useCallback(
    async (caseId: string, branchId: string): Promise<ForkResult | null> => {
      setIsRunning(true);
      setError(null);

      // 브랜치 상태를 running으로 업데이트
      store.getState().updateBranch(branchId, { status: 'running' });

      try {
        const result = await eventForkApi.runSimulation(caseId, branchId);

        // 스토어에 결과 저장
        store.getState().addForkResult(result);
        store.getState().updateBranch(branchId, {
          status: 'completed',
          completedAt: new Date().toISOString(),
        });

        toast.success('시뮬레이션이 완료되었습니다.');
        return result;
      } catch (e) {
        const msg = e instanceof Error ? e.message : '시뮬레이션 실행 중 오류가 발생했습니다.';
        setError(msg);
        store.getState().updateBranch(branchId, { status: 'failed' });
        toast.error(msg);
        return null;
      } finally {
        setIsRunning(false);
      }
    },
    [],
  );

  // ── 브랜치 조회 ──
  const fetchBranch = useCallback(
    async (caseId: string, branchId: string): Promise<SimulationBranch | null> => {
      try {
        return await eventForkApi.getBranch(caseId, branchId);
      } catch (e) {
        const msg = e instanceof Error ? e.message : '브랜치 조회 중 오류가 발생했습니다.';
        setError(msg);
        return null;
      }
    },
    [],
  );

  // ── 이벤트 목록 조회 ──
  const fetchEvents = useCallback(
    async (
      caseId: string,
      branchId: string,
      limit = 50,
      offset = 0,
    ): Promise<{ events: ForkEvent[]; total: number } | null> => {
      setIsFetchingEvents(true);
      try {
        return await eventForkApi.getBranchEvents(caseId, branchId, limit, offset);
      } catch (e) {
        const msg = e instanceof Error ? e.message : '이벤트 조회 중 오류가 발생했습니다.';
        setError(msg);
        return null;
      } finally {
        setIsFetchingEvents(false);
      }
    },
    [],
  );

  // ── 시나리오 비교 ──
  const compareScenarios = useCallback(
    async (
      caseId: string,
      branchIds: string[],
    ): Promise<ScenarioComparisonResult | null> => {
      setIsComparing(true);
      setError(null);

      try {
        const result = await eventForkApi.compareScenarios(caseId, branchIds);
        store.getState().setComparisonResult(result);
        return result;
      } catch (e) {
        const msg = e instanceof Error ? e.message : '시나리오 비교 중 오류가 발생했습니다.';
        setError(msg);
        toast.error(msg);
        return null;
      } finally {
        setIsComparing(false);
      }
    },
    [],
  );

  // ── 브랜치 삭제 ──
  const deleteBranch = useCallback(
    async (caseId: string, branchId: string): Promise<boolean> => {
      setIsDeleting(true);
      setError(null);

      try {
        await eventForkApi.deleteBranch(caseId, branchId);
        store.getState().removeBranch(branchId);
        toast.success('브랜치가 삭제되었습니다.');
        return true;
      } catch (e) {
        const msg = e instanceof Error ? e.message : '브랜치 삭제 중 오류가 발생했습니다.';
        setError(msg);
        toast.error(msg);
        return false;
      } finally {
        setIsDeleting(false);
      }
    },
    [],
  );

  return {
    isCreating,
    isRunning,
    isComparing,
    isDeleting,
    isFetchingEvents,
    error,
    createBranch,
    runSimulation,
    fetchBranch,
    fetchEvents,
    compareScenarios,
    deleteBranch,
  };
}
