/**
 * Deep Agents 온톨로지 생성 위자드 타입 정의
 * 4단계 위자드 흐름: 입력 → 생성 중 → 검토 → 완료
 */

/** 위자드 단계 열거형 */
export type WizardStep = 'INPUT' | 'GENERATING' | 'REVIEW' | 'COMPLETE';

/** 온톨로지 5계층 레이어 타입 */
export type TargetLayer = 'kpi' | 'measure' | 'driver' | 'process' | 'resource';

/** 레이어별 진행 상태 */
export interface LayerProgress {
  /** 레이어 이름 (대문자: KPI, Measure 등) */
  layer: string;
  /** 진행률 (0~100) */
  progress: number;
  /** 진행 메시지 */
  message: string;
  /** 생성된 노드 수 */
  nodeCount: number;
  /** 생성된 관계 수 */
  relationCount: number;
  /** 레이어 상태 */
  status: 'pending' | 'in_progress' | 'complete' | 'error';
}

/** 레이어별 스키마 결과 */
export interface LayerSchema {
  layer: string;
  nodes: Array<{
    id: string;
    label: string;
    layer: string;
    properties: Record<string, unknown>;
  }>;
  relations: Array<{
    source: string;
    target: string;
    type: string;
    properties?: Record<string, unknown>;
  }>;
}

/** 최종 생성 결과 */
export interface GenerationResult {
  /** 레이어별 스키마 데이터 */
  layerSchemas: LayerSchema[];
  /** 전체 노드 수 */
  totalNodes: number;
  /** 전체 관계 수 */
  totalRelations: number;
}

/** 레이어별 한글 이름 매핑 */
export const LAYER_LABELS: Record<string, string> = {
  KPI: 'KPI',
  kpi: 'KPI',
  Measure: '측정지표',
  measure: '측정지표',
  Driver: '동인',
  driver: '동인',
  Process: '프로세스',
  process: '프로세스',
  Resource: '자원',
  resource: '자원',
};

/** 레이어별 색상 테마 */
export const LAYER_COLORS: Record<string, { bg: string; border: string; text: string; progress: string }> = {
  KPI:      { bg: 'bg-blue-50',   border: 'border-blue-200',   text: 'text-blue-700',   progress: 'bg-blue-500' },
  kpi:      { bg: 'bg-blue-50',   border: 'border-blue-200',   text: 'text-blue-700',   progress: 'bg-blue-500' },
  Measure:  { bg: 'bg-green-50',  border: 'border-green-200',  text: 'text-green-700',  progress: 'bg-green-500' },
  measure:  { bg: 'bg-green-50',  border: 'border-green-200',  text: 'text-green-700',  progress: 'bg-green-500' },
  Driver:   { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-700', progress: 'bg-orange-500' },
  driver:   { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-700', progress: 'bg-orange-500' },
  Process:  { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700', progress: 'bg-purple-500' },
  process:  { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700', progress: 'bg-purple-500' },
  Resource: { bg: 'bg-gray-50',   border: 'border-gray-200',   text: 'text-gray-700',   progress: 'bg-gray-500' },
  resource: { bg: 'bg-gray-50',   border: 'border-gray-200',   text: 'text-gray-700',   progress: 'bg-gray-500' },
};
