/**
 * What-if 위자드 Zustand 스토어
 *
 * 5단계 위자드의 전체 상태를 관리한다.
 * 각 단계의 결과 데이터가 다음 단계의 입력으로 사용되므로
 * 이전 단계 결과를 변경하면 후속 단계 데이터를 초기화한다.
 */
import { create } from 'zustand';
import type {
  WizardStep,
  WizardState,
  CausalEdge,
  ModelSpec,
  TrainedModel,
  SimulationResult,
  SnapshotData,
} from '../types/wizard';
import { WIZARD_STEPS } from '../types/wizard';

interface WhatIfWizardActions {
  // ── 네비게이션 ──
  /** 특정 단계로 이동 (유효성 검사 포함) */
  goToStep: (step: WizardStep) => void;
  /** 다음 단계로 이동 */
  nextStep: () => void;
  /** 이전 단계로 이동 */
  prevStep: () => void;
  /** 현재 단계가 완료 조건을 충족하는지 */
  canProceed: () => boolean;

  // ── Step 1: 시나리오 정의 ──
  setScenarioName: (name: string) => void;
  setDescription: (desc: string) => void;
  setCaseId: (id: string) => void;
  setTargetKpiId: (id: string) => void;

  // ── Step 2: 데이터 선택 ──
  setDateRange: (range: { from: string; to: string }) => void;
  setSelectedNodes: (nodes: string[]) => void;
  toggleNode: (nodeId: string) => void;

  // ── Step 3: 인과 관계 발견 ──
  setDiscoveredEdges: (edges: CausalEdge[]) => void;
  toggleEdgeSelection: (index: number) => void;
  setDiscoveryParams: (params: { maxLag: number; minCorrelation: number }) => void;
  setModelSpecs: (specs: ModelSpec[]) => void;

  // ── Step 4: 모델 학습 ──
  setTrainedModels: (models: TrainedModel[]) => void;
  updateModelStatus: (
    modelId: string,
    status: TrainedModel['status'],
    r2?: number,
    rmse?: number
  ) => void;

  // ── Step 5: 시뮬레이션 ──
  setSnapshotData: (data: SnapshotData) => void;
  addSimulationResult: (result: SimulationResult) => void;
  clearSimulationResults: () => void;

  // ── 전체 초기화 ──
  resetWizard: () => void;
}

type WhatIfWizardStore = WizardState & WhatIfWizardActions;

/** 초기 상태 */
const initialState: WizardState = {
  currentStep: 'scenario',
  scenarioName: '',
  description: '',
  caseId: '',
  targetKpiId: '',
  dateRange: { from: '', to: '' },
  selectedNodes: [],
  discoveredEdges: [],
  modelSpecs: [],
  trainedModels: [],
  simulationResults: [],
  snapshotData: null,
  discoveryParams: {
    maxLag: 3,
    minCorrelation: 0.3,
  },
};

export const useWhatIfWizardStore = create<WhatIfWizardStore>((set, get) => ({
  ...initialState,

  // ── 네비게이션 ──
  goToStep: (step) => {
    const state = get();
    const targetIdx = WIZARD_STEPS.indexOf(step);
    const currentIdx = WIZARD_STEPS.indexOf(state.currentStep);

    // 뒤로 가는 것은 항상 허용
    if (targetIdx <= currentIdx) {
      set({ currentStep: step });
      return;
    }

    // 앞으로 가려면 모든 이전 단계가 완료되어야 함
    // 간소화: 한 단계씩만 전진 허용
    if (targetIdx === currentIdx + 1 && get().canProceed()) {
      set({ currentStep: step });
    }
  },

  nextStep: () => {
    const state = get();
    const idx = WIZARD_STEPS.indexOf(state.currentStep);
    if (idx < WIZARD_STEPS.length - 1 && state.canProceed()) {
      set({ currentStep: WIZARD_STEPS[idx + 1] });
    }
  },

  prevStep: () => {
    const state = get();
    const idx = WIZARD_STEPS.indexOf(state.currentStep);
    if (idx > 0) {
      set({ currentStep: WIZARD_STEPS[idx - 1] });
    }
  },

  canProceed: () => {
    const state = get();
    switch (state.currentStep) {
      case 'scenario':
        return state.scenarioName.trim().length > 0 && state.caseId.trim().length > 0;
      case 'data':
        return state.selectedNodes.length > 0;
      case 'edges':
        return state.discoveredEdges.some((e) => e.selected);
      case 'train':
        return state.trainedModels.some((m) => m.status === 'trained');
      case 'simulate':
        return true; // 시뮬레이션은 마지막 단계, 항상 진행 가능
      default:
        return false;
    }
  },

  // ── Step 1 ──
  setScenarioName: (name) => set({ scenarioName: name }),
  setDescription: (desc) => set({ description: desc }),
  setCaseId: (id) => set({ caseId: id }),
  setTargetKpiId: (id) => set({ targetKpiId: id }),

  // ── Step 2 ──
  setDateRange: (range) => set({ dateRange: range }),
  setSelectedNodes: (nodes) => set({ selectedNodes: nodes }),
  toggleNode: (nodeId) =>
    set((state) => {
      const exists = state.selectedNodes.includes(nodeId);
      return {
        selectedNodes: exists
          ? state.selectedNodes.filter((n) => n !== nodeId)
          : [...state.selectedNodes, nodeId],
      };
    }),

  // ── Step 3 ──
  setDiscoveredEdges: (edges) =>
    set({
      discoveredEdges: edges,
      // 인과 관계가 변경되면 후속 단계 데이터 초기화
      modelSpecs: [],
      trainedModels: [],
      simulationResults: [],
      snapshotData: null,
    }),

  toggleEdgeSelection: (index) =>
    set((state) => {
      const edges = [...state.discoveredEdges];
      if (edges[index]) {
        edges[index] = { ...edges[index], selected: !edges[index].selected };
      }
      return { discoveredEdges: edges };
    }),

  setDiscoveryParams: (params) => set({ discoveryParams: params }),

  setModelSpecs: (specs) =>
    set({
      modelSpecs: specs,
      // 모델 구성이 변경되면 후속 단계 초기화
      trainedModels: [],
      simulationResults: [],
      snapshotData: null,
    }),

  // ── Step 4 ──
  setTrainedModels: (models) =>
    set({
      trainedModels: models,
      // 모델이 변경되면 시뮬레이션 초기화
      simulationResults: [],
    }),

  updateModelStatus: (modelId, status, r2, rmse) =>
    set((state) => ({
      trainedModels: state.trainedModels.map((m) =>
        m.modelId === modelId
          ? {
              ...m,
              status,
              ...(r2 !== undefined ? { r2Score: r2 } : {}),
              ...(rmse !== undefined ? { rmse } : {}),
            }
          : m
      ),
    })),

  // ── Step 5 ──
  setSnapshotData: (data) => set({ snapshotData: data }),
  addSimulationResult: (result) =>
    set((state) => ({
      simulationResults: [...state.simulationResults, result],
    })),
  clearSimulationResults: () => set({ simulationResults: [] }),

  // ── 초기화 ──
  resetWizard: () => set(initialState),
}));
