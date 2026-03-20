/**
 * What-if 위자드 Zustand 스토어
 *
 * DAG Propagation + Event Fork 두 가지 모드를 지원하는
 * 5단계 위자드의 전체 상태를 관리한다.
 *
 * 단계 구조:
 *  1. 시나리오 정의 (이름, 설명, 모드 선택)
 *  2. 데이터 선택 (온톨로지 노드 검색 + 선택)
 *  3. 인과 관계 발견 (자동 분석 + 신뢰도 필터링)
 *  4. 개입 설정 (파라미터 값 변경)
 *  5. 결과 비교 (KPI 델타, 차트, 테이블)
 */
import { create } from 'zustand';
import type {
  SimulationMode,
  WizardStepNumber,
  OntologyNode,
  CausalRelation,
  InterventionSpec,
  SimulationBranch,
  ForkResult,
  ScenarioComparisonResult,
} from '../types/whatifWizard.types';

// ── 스토어 상태 인터페이스 ──
interface WhatIfWizardState {
  // 위자드 네비게이션
  currentStep: WizardStepNumber;

  /** 대상 케이스 ID (URL 파라미터에서 주입) */
  caseId: string;

  // Step 1: 시나리오 정의
  scenarioName: string;
  scenarioDescription: string;
  simulationMode: SimulationMode;

  // Step 2: 데이터 선택
  selectedNodeIds: string[];
  /** 선택된 노드의 상세 정보 (UI 표시용) */
  selectedNodes: OntologyNode[];
  /** 노드 검색 쿼리 */
  nodeSearchQuery: string;
  /** 노드 타입 필터 */
  nodeTypeFilter: string | null;

  // Step 3: 인과 관계 발견
  causalRelations: CausalRelation[];
  /** 신뢰도 임계값 (0~1) */
  confidenceThreshold: number;

  // Step 4: 개입 설정
  interventions: InterventionSpec[];

  // Step 5: 결과 비교
  branches: SimulationBranch[];
  forkResults: ForkResult[];
  comparisonResult: ScenarioComparisonResult | null;

  // 로딩/에러 상태
  loading: boolean;
  error: string | null;
}

// ── 스토어 액션 인터페이스 ──
interface WhatIfWizardActions {
  // 네비게이션
  nextStep: () => void;
  prevStep: () => void;
  goToStep: (step: WizardStepNumber) => void;
  canProceed: () => boolean;

  // caseId
  setCaseId: (caseId: string) => void;

  // Step 1
  setScenarioName: (name: string) => void;
  setScenarioDescription: (desc: string) => void;
  setSimulationMode: (mode: SimulationMode) => void;

  // Step 2
  addNode: (node: OntologyNode) => void;
  removeNode: (nodeId: string) => void;
  setSelectedNodes: (nodes: OntologyNode[]) => void;
  setNodeSearchQuery: (query: string) => void;
  setNodeTypeFilter: (filter: string | null) => void;

  // Step 3
  setCausalRelations: (relations: CausalRelation[]) => void;
  setConfidenceThreshold: (threshold: number) => void;

  // Step 4
  addIntervention: (intervention: InterventionSpec) => void;
  removeIntervention: (index: number) => void;
  updateIntervention: (index: number, updates: Partial<InterventionSpec>) => void;
  setInterventions: (interventions: InterventionSpec[]) => void;

  // Step 5 — 브랜치 CRUD
  addBranch: (branch: SimulationBranch) => void;
  updateBranch: (branchId: string, updates: Partial<SimulationBranch>) => void;
  removeBranch: (branchId: string) => void;
  setBranches: (branches: SimulationBranch[]) => void;
  addForkResult: (result: ForkResult) => void;
  setComparisonResult: (result: ScenarioComparisonResult | null) => void;

  // 공통
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  resetWizard: () => void;
}

type WhatIfWizardStore = WhatIfWizardState & WhatIfWizardActions;

// ── 초기 상태 ──
const initialState: WhatIfWizardState = {
  currentStep: 1,
  caseId: 'demo_manufacturing',
  scenarioName: '',
  scenarioDescription: '',
  simulationMode: 'dag',
  selectedNodeIds: [],
  selectedNodes: [],
  nodeSearchQuery: '',
  nodeTypeFilter: null,
  causalRelations: [],
  confidenceThreshold: 0.5,
  interventions: [],
  branches: [],
  forkResults: [],
  comparisonResult: null,
  loading: false,
  error: null,
};

export const useWhatIfWizardStore = create<WhatIfWizardStore>((set, get) => ({
  ...initialState,

  // ── 네비게이션 ──

  nextStep: () => {
    const { currentStep, canProceed } = get();
    if (currentStep < 5 && canProceed()) {
      set({ currentStep: (currentStep + 1) as WizardStepNumber });
    }
  },

  prevStep: () => {
    const { currentStep } = get();
    if (currentStep > 1) {
      set({ currentStep: (currentStep - 1) as WizardStepNumber });
    }
  },

  goToStep: (step) => {
    const { currentStep } = get();
    // 뒤로 가는 것은 항상 허용, 앞으로는 한 단계씩만
    if (step <= currentStep || (step === currentStep + 1 && get().canProceed())) {
      set({ currentStep: step });
    }
  },

  canProceed: () => {
    const state = get();
    switch (state.currentStep) {
      case 1:
        // 시나리오 이름 필수
        return state.scenarioName.trim().length > 0;
      case 2:
        // 최소 1개 노드 선택
        return state.selectedNodeIds.length > 0;
      case 3:
        // Event Fork 모드에서는 자동 건너뛰기 허용
        if (state.simulationMode === 'event-fork') return true;
        // DAG 모드: 최소 1개 인과관계 필요
        return state.causalRelations.length > 0;
      case 4:
        // 최소 1개 개입 설정
        return state.interventions.length > 0;
      case 5:
        // 마지막 단계, 항상 진행 가능
        return true;
      default:
        return false;
    }
  },

  // ── caseId ──
  setCaseId: (caseId) => set({ caseId }),

  // ── Step 1 ──

  setScenarioName: (name) => set({ scenarioName: name }),
  setScenarioDescription: (desc) => set({ scenarioDescription: desc }),
  setSimulationMode: (mode) =>
    set({
      simulationMode: mode,
      // 모드 변경 시 Step 3 이후 데이터 초기화
      causalRelations: [],
      interventions: [],
      branches: [],
      forkResults: [],
      comparisonResult: null,
    }),

  // ── Step 2 ──

  addNode: (node) =>
    set((state) => {
      if (state.selectedNodeIds.includes(node.id)) return state;
      return {
        selectedNodeIds: [...state.selectedNodeIds, node.id],
        selectedNodes: [...state.selectedNodes, node],
      };
    }),

  removeNode: (nodeId) =>
    set((state) => ({
      selectedNodeIds: state.selectedNodeIds.filter((id) => id !== nodeId),
      selectedNodes: state.selectedNodes.filter((n) => n.id !== nodeId),
      // 관련 개입도 제거
      interventions: state.interventions.filter((iv) => iv.nodeId !== nodeId),
    })),

  setSelectedNodes: (nodes) =>
    set({
      selectedNodes: nodes,
      selectedNodeIds: nodes.map((n) => n.id),
    }),

  setNodeSearchQuery: (query) => set({ nodeSearchQuery: query }),
  setNodeTypeFilter: (filter) => set({ nodeTypeFilter: filter }),

  // ── Step 3 ──

  setCausalRelations: (relations) => set({ causalRelations: relations }),
  setConfidenceThreshold: (threshold) => set({ confidenceThreshold: threshold }),

  // ── Step 4 ──

  addIntervention: (intervention) =>
    set((state) => ({
      interventions: [...state.interventions, intervention],
    })),

  removeIntervention: (index) =>
    set((state) => ({
      interventions: state.interventions.filter((_, i) => i !== index),
    })),

  updateIntervention: (index, updates) =>
    set((state) => ({
      interventions: state.interventions.map((iv, i) =>
        i === index ? { ...iv, ...updates } : iv,
      ),
    })),

  setInterventions: (interventions) => set({ interventions }),

  // ── Step 5 ──

  addBranch: (branch) =>
    set((state) => ({
      branches: [...state.branches, branch],
    })),

  updateBranch: (branchId, updates) =>
    set((state) => ({
      branches: state.branches.map((b) =>
        b.branchId === branchId ? { ...b, ...updates } : b,
      ),
    })),

  removeBranch: (branchId) =>
    set((state) => ({
      branches: state.branches.filter((b) => b.branchId !== branchId),
      forkResults: state.forkResults.filter((r) => r.branchId !== branchId),
    })),

  setBranches: (branches) => set({ branches }),

  addForkResult: (result) =>
    set((state) => ({
      forkResults: [...state.forkResults, result],
    })),

  setComparisonResult: (result) => set({ comparisonResult: result }),

  // ── 공통 ──

  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  resetWizard: () => set(initialState),
}));
