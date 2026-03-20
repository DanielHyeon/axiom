/**
 * 워크플로 에디터 — 타입 정의
 *
 * GWT(Given-When-Then) 기반 정책 워크플로를 시각적으로 편집하기 위한
 * 노드·엣지·정의 타입. BPM ProcessDefinition과 연동 가능하도록 설계.
 */

// ──────────────────────────────────────
// 노드 타입
// ──────────────────────────────────────

/** 워크플로 노드 유형: 트리거 → 조건 → 액션 → 정책 → 게이트웨이 */
export type WorkflowNodeType =
  | 'trigger'   // 이벤트 시작점
  | 'condition' // GWT Given (조건)
  | 'action'    // GWT Then (SET / EMIT 동작)
  | 'policy'    // 크로스-서비스 명령
  | 'gateway';  // AND / OR / XOR 분기

/** 트리거 이벤트 유형 */
export type TriggerEventType =
  | 'case_created'
  | 'case_updated'
  | 'kpi_threshold'
  | 'schedule_cron'
  | 'manual'
  | 'webhook';

/** 조건 연산자 */
export type ConditionOperator =
  | 'equals'
  | 'not_equals'
  | 'greater_than'
  | 'less_than'
  | 'contains'
  | 'in'
  | 'is_null'
  | 'is_not_null';

/** 액션 동작 유형 */
export type ActionOperation = 'SET' | 'EMIT' | 'NOTIFY' | 'INVOKE';

/** 게이트웨이 모드 */
export type GatewayMode = 'AND' | 'OR' | 'XOR';

// ──────────────────────────────────────
// 노드 데이터 페이로드 (타입별 데이터)
// ──────────────────────────────────────

/** 트리거 노드 데이터 */
export interface TriggerData {
  eventType: TriggerEventType;
  /** cron 표현식 (schedule_cron 전용) */
  cronExpression?: string;
  /** webhook URL (webhook 전용) */
  webhookUrl?: string;
  /** KPI 필드 이름 (kpi_threshold 전용) */
  kpiField?: string;
  /** KPI 임계값 (kpi_threshold 전용) */
  kpiThreshold?: number;
}

/** 조건(Given) 노드 데이터 */
export interface ConditionData {
  conditions: ConditionRow[];
  /** 조건 간 논리 연산 */
  logicalOp: 'AND' | 'OR';
}

/** 개별 조건 행 */
export interface ConditionRow {
  id: string;
  field: string;
  operator: ConditionOperator;
  value: string;
}

/** 액션(Then) 노드 데이터 */
export interface ActionData {
  actions: ActionRow[];
}

/** 개별 액션 행 */
export interface ActionRow {
  id: string;
  operation: ActionOperation;
  /** SET 대상 필드 / EMIT 이벤트명 / INVOKE 서비스 */
  target: string;
  /** SET 값 / EMIT 페이로드 JSON / INVOKE 파라미터 */
  payload: string;
}

/** 정책 노드 데이터 */
export interface PolicyData {
  /** 대상 서비스 */
  targetService: string;
  /** 명령 이름 */
  command: string;
  /** 파라미터 (JSON) */
  parameters: string;
  /** 재시도 횟수 */
  retryCount: number;
  /** 타임아웃 (ms) */
  timeoutMs: number;
}

/** 게이트웨이 노드 데이터 */
export interface GatewayData {
  mode: GatewayMode;
}

/** 노드 데이터 유니온 */
export type WorkflowNodeData =
  | TriggerData
  | ConditionData
  | ActionData
  | PolicyData
  | GatewayData;

// ──────────────────────────────────────
// 워크플로 노드
// ──────────────────────────────────────

/** 워크플로 노드 (캔버스에 배치되는 단위) */
export interface WorkflowNode {
  id: string;
  type: WorkflowNodeType;
  label: string;
  /** 캔버스 위치 */
  position: { x: number; y: number };
  /** 타입별 데이터 */
  data: WorkflowNodeData;
}

// ──────────────────────────────────────
// 워크플로 엣지
// ──────────────────────────────────────

/** 노드 간 연결선 */
export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

// ──────────────────────────────────────
// 워크플로 정의 (저장 단위)
// ──────────────────────────────────────

/** 워크플로 메타데이터 */
export interface WorkflowMetadata {
  id: string;
  name: string;
  description: string;
  version: number;
  createdAt: string;
  updatedAt: string;
  createdBy: string;
  /** 활성화 여부 */
  enabled: boolean;
}

/** 워크플로 정의 전체 구조 */
export interface WorkflowDefinition {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  metadata: WorkflowMetadata;
}

// ──────────────────────────────────────
// UI 헬퍼 타입
// ──────────────────────────────────────

/** 노드 타입별 표시 정보 */
export interface NodeTypeInfo {
  type: WorkflowNodeType;
  label: string;
  color: string;
  borderColor: string;
  description: string;
}

/** 노드 타입별 기본 데이터 팩토리 */
export const DEFAULT_NODE_DATA: Record<WorkflowNodeType, () => WorkflowNodeData> = {
  trigger: () => ({ eventType: 'manual' }) satisfies TriggerData,
  condition: () => ({
    conditions: [{ id: crypto.randomUUID(), field: '', operator: 'equals', value: '' }],
    logicalOp: 'AND',
  }) satisfies ConditionData,
  action: () => ({
    actions: [{ id: crypto.randomUUID(), operation: 'SET', target: '', payload: '' }],
  }) satisfies ActionData,
  policy: () => ({
    targetService: '',
    command: '',
    parameters: '{}',
    retryCount: 3,
    timeoutMs: 5000,
  }) satisfies PolicyData,
  gateway: () => ({ mode: 'AND' }) satisfies GatewayData,
};
