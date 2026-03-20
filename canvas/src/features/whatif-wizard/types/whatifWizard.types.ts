/**
 * What-if 위자드 타입 정의 (Event Fork + DAG 통합)
 *
 * 기존 whatif/types/wizard.ts의 DAG 모드에
 * Event Fork 모드를 추가하여 통합 5단계 위자드를 지원한다.
 */

// ── 시뮬레이션 모드 ──
export type SimulationMode = 'dag' | 'event-fork';

// ── 위자드 단계 (1~5) ──
export type WizardStepNumber = 1 | 2 | 3 | 4 | 5;

/** 단계별 메타데이터 */
export const WIZARD_STEP_META: Record<
  WizardStepNumber,
  { label: string; description: string }
> = {
  1: { label: '시나리오 정의', description: '시나리오 이름과 시뮬레이션 모드를 설정합니다.' },
  2: { label: '데이터 선택', description: '분석할 온톨로지 노드를 선택합니다.' },
  3: { label: '인과 관계 발견', description: '선택한 노드 간 인과 관계를 분석합니다.' },
  4: { label: '개입 설정', description: '시뮬레이션할 파라미터 변경 값을 설정합니다.' },
  5: { label: '결과 비교', description: '시나리오 실행 결과를 비교 분석합니다.' },
};

// ── 온톨로지 노드 타입 ──
export type OntologyNodeType = 'KPI' | 'Measure' | 'Process' | 'Resource';

/** 온톨로지 노드 (검색 결과용) */
export interface OntologyNode {
  id: string;
  name: string;
  type: OntologyNodeType;
  description?: string;
}

// ── 인과 관계 ──
export interface CausalRelation {
  /** 소스 노드 ID */
  sourceId: string;
  /** 소스 노드 이름 */
  sourceName: string;
  /** 타겟 노드 ID */
  targetId: string;
  /** 타겟 노드 이름 */
  targetName: string;
  /** 관계 가중치 (0~1) */
  weight: number;
  /** 시차 (일 단위) */
  lag: number;
  /** 신뢰도 (0~1) */
  confidence: number;
  /** 분석 방법 */
  method: 'granger' | 'correlation' | 'decomposition';
  /** 방향 */
  direction: 'positive' | 'negative';
}

// ── 개입(Intervention) 설정 ──
export interface InterventionSpec {
  /** 대상 노드 ID */
  nodeId: string;
  /** 대상 노드 이름 */
  nodeName: string;
  /** 대상 필드 */
  field: string;
  /** 변경할 값 */
  value: number;
  /** 기존(베이스라인) 값 */
  baselineValue: number;
  /** 설명 */
  description: string;
}

// ── Event Fork 브랜치 ──
export interface SimulationBranch {
  /** 브랜치 ID */
  branchId: string;
  /** 브랜치 이름 */
  name: string;
  /** 브랜치 설명 */
  description?: string;
  /** 적용된 개입 목록 */
  interventions: InterventionSpec[];
  /** 상태 */
  status: 'created' | 'running' | 'completed' | 'failed';
  /** 생성 시각 */
  createdAt: string;
  /** 완료 시각 */
  completedAt?: string;
}

// ── Event Fork 실행 결과 ──
export interface ForkResult {
  /** 브랜치 ID */
  branchId: string;
  /** 시나리오 이름 */
  scenarioName: string;
  /** 결과 상태 */
  status: 'completed' | 'failed';
  /** KPI 델타 맵 (key: KPI 이름, value: 변화량) */
  kpiDeltas: Record<string, number>;
  /** KPI 기존값 맵 */
  kpiBaselines: Record<string, number>;
  /** KPI 새 값 맵 */
  kpiResults: Record<string, number>;
  /** 이벤트 타임라인 */
  events: ForkEvent[];
  /** 실행 시각 */
  executedAt: string;
}

/** Event Fork 이벤트 (타임라인) */
export interface ForkEvent {
  /** 이벤트 ID */
  id: string;
  /** 이벤트 타입 */
  type: string;
  /** 이벤트 발생 시각 */
  timestamp: string;
  /** 관련 노드 */
  nodeId: string;
  /** 이벤트 설명 */
  description: string;
  /** 이벤트 데이터 */
  data?: Record<string, unknown>;
}

// ── 시나리오 비교 결과 ──
export interface ScenarioComparisonResult {
  /** 비교 항목(KPI) 이름 목록 */
  metrics: string[];
  /** 시나리오별 결과 */
  scenarios: ScenarioComparisonItem[];
}

export interface ScenarioComparisonItem {
  /** 시나리오/브랜치 ID */
  id: string;
  /** 시나리오 이름 */
  name: string;
  /** 메트릭별 값 */
  values: Record<string, number>;
  /** 메트릭별 델타(베이스라인 대비) */
  deltas: Record<string, number>;
}

// ── KPI 델타 요약 카드 ──
export interface KpiDeltaSummary {
  /** KPI 이름 */
  name: string;
  /** 기존 값 */
  baseline: number;
  /** 새 값 */
  result: number;
  /** 델타 */
  delta: number;
  /** 변화율(%) */
  pctChange: number;
  /** 변화 방향 (positive=좋은 방향, negative=나쁜 방향) */
  impact: 'positive' | 'negative' | 'neutral';
}
