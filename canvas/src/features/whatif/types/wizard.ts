/**
 * What-if 5단계 위자드 전용 타입 정의
 *
 * 5단계: 시나리오 정의 → 데이터 선택 → 인과 관계 발견 → 모델 학습 → 시뮬레이션
 */

// ── 위자드 단계 ──
export type WizardStep = 'scenario' | 'data' | 'edges' | 'train' | 'simulate';

/** 위자드 단계 순서 배열 (네비게이션 계산용) */
export const WIZARD_STEPS: WizardStep[] = [
  'scenario',
  'data',
  'edges',
  'train',
  'simulate',
];

/** 단계별 메타데이터 (라벨, 설명 등) */
export const WIZARD_STEP_META: Record<
  WizardStep,
  { label: string; description: string; index: number }
> = {
  scenario: { label: '시나리오 정의', description: '시나리오 이름과 대상 KPI를 설정합니다.', index: 0 },
  data: { label: '데이터 선택', description: '분석할 데이터 소스와 기간을 선택합니다.', index: 1 },
  edges: { label: '인과 관계 발견', description: '변수 간 인과 관계를 자동으로 분석합니다.', index: 2 },
  train: { label: '모델 학습', description: '예측 모델을 학습하고 등록합니다.', index: 3 },
  simulate: { label: '시뮬레이션', description: '파라미터를 변경하여 시뮬레이션을 실행합니다.', index: 4 },
};

// ── 인과 관계 엣지 ──
export interface CausalEdge {
  /** 소스 노드 ID */
  source: string;
  /** 소스 노드 이름 */
  sourceName: string;
  /** 소스 필드명 */
  sourceField: string;
  /** 타겟 노드 ID */
  target: string;
  /** 타겟 노드 이름 */
  targetName: string;
  /** 타겟 필드명 */
  targetField: string;
  /** 인과 분석 방법 */
  method: 'granger' | 'correlation' | 'decomposition';
  /** 관계 강도 (0~1) */
  strength: number;
  /** 시차 (lag, 일 단위) */
  lag: number;
  /** Granger p-value */
  pValue: number;
  /** Pearson 상관계수 */
  pearson: number;
  /** 방향 */
  direction: 'positive' | 'negative';
  /** 사용자 선택 여부 — 위자드 내에서 토글 가능 */
  selected: boolean;
}

// ── 학습된 모델 ──
export interface TrainedModel {
  /** 모델 고유 ID */
  modelId: string;
  /** 모델 이름 */
  name: string;
  /** 입력 노드 필드 목록 */
  inputNodes: string[];
  /** 출력 노드 필드 */
  outputNode: string;
  /** 모델 타입 (예: linear_regression, lightgbm 등) */
  modelType: string;
  /** R2 결정 계수 */
  r2Score: number;
  /** RMSE */
  rmse: number;
  /** 학습 상태 */
  status: 'pending' | 'training' | 'trained' | 'failed';
  /** 실행 순서 */
  executionOrder: number;
  /** Neo4j 등록 여부 */
  neo4jSaved: boolean;
}

// ── 모델 스펙 (학습 요청용) ──
export interface ModelSpec {
  modelId: string;
  name: string;
  targetNodeId: string;
  targetField: string;
  features: Array<{
    nodeId: string;
    field: string;
    lag: number;
    score: number;
  }>;
  executionOrder: number;
}

// ── 시뮬레이션 결과 ──
export interface SimulationTrace {
  modelId: string;
  modelName: string;
  inputs: Record<string, number>;
  outputField: string;
  baselineValue: number;
  predictedValue: number;
  delta: number;
  pctChange: number;
  wave: number;
  effectiveDay: number;
  triggeredBy: string[];
}

export interface SimulationResult {
  /** 시나리오 이름 */
  scenarioName: string;
  /** 개입 목록 */
  interventions: Array<{
    nodeId: string;
    field: string;
    value: number;
    description: string;
  }>;
  /** 실행 트레이스 */
  traces: SimulationTrace[];
  /** 타임라인 (day → traces) */
  timeline: Record<string, SimulationTrace[]>;
  /** 시뮬레이션 후 최종 상태 */
  finalState: Record<string, number>;
  /** 시뮬레이션 전 베이스라인 */
  baselineState: Record<string, number>;
  /** 변화량 (delta) */
  deltas: Record<string, number>;
  /** 전파 단계 수 */
  propagationWaves: number;
  /** 실행 시각 */
  executedAt: string;
}

// ── 스냅샷 데이터 (시뮬레이션 베이스라인) ──
export interface SnapshotData {
  date: string;
  snapshot: Record<string, number>;
  snapshotByNode: Record<
    string,
    {
      nodeName: string;
      fields: Record<string, number>;
    }
  >;
  availableDates: string[];
  timeseries?: Record<string, number[] | string[]>;
  fieldDescriptions?: Record<string, string>;
}

// ── 위자드 전체 상태 ──
export interface WizardState {
  /** 현재 위자드 단계 */
  currentStep: WizardStep;
  /** 시나리오 이름 */
  scenarioName: string;
  /** 시나리오 설명 */
  description: string;
  /** 케이스 ID (온톨로지 스키마) */
  caseId: string;
  /** 대상 KPI ID */
  targetKpiId: string;
  /** 분석 기간 */
  dateRange: { from: string; to: string };
  /** 선택된 분석 노드 목록 */
  selectedNodes: string[];
  /** 발견된 인과 관계 엣지 */
  discoveredEdges: CausalEdge[];
  /** 모델 스펙 (학습 전 구성) */
  modelSpecs: ModelSpec[];
  /** 학습된 모델 목록 */
  trainedModels: TrainedModel[];
  /** 시뮬레이션 결과 목록 */
  simulationResults: SimulationResult[];
  /** 스냅샷 데이터 (시뮬레이션용) */
  snapshotData: SnapshotData | null;
  /** 인과 분석 파라미터 */
  discoveryParams: {
    maxLag: number;
    minCorrelation: number;
  };
}
