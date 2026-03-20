/**
 * 도메인 모델러 — Kinetic 행동 모델 타입 정의
 *
 * GWT(Given-When-Then) 규칙, ActionType, Policy,
 * 엔티티 추출, 시뮬레이션 브랜치 등 행동 레이어의 핵심 타입.
 * 디자인 문서 Section 9.2 기반.
 */

// ──────────────────────────────────────
// 온톨로지 계층 필터
// ──────────────────────────────────────

/** 온톨로지 5계층 식별자 */
export type OntologyLayer = 'kpi' | 'driver' | 'measure' | 'process' | 'resource';

/** 계층 필터링 옵션 */
export interface LayerFilter {
  /** 표시할 계층 목록 */
  layers: OntologyLayer[];
  /** 검색어 (노드 이름 필터) */
  searchQuery?: string;
  /** 상태 필터 */
  statusFilter?: 'all' | 'active' | 'draft' | 'deprecated';
}

// ──────────────────────────────────────
// GWT(Given-When-Then) 조건·액션
// ──────────────────────────────────────

/** 비교 연산자 */
export type ComparisonOperator = '==' | '!=' | '>' | '<' | '>=' | '<=';

/** 조건 타입 */
export type ConditionType = 'state' | 'relation' | 'expression';

/** GWT 규칙의 Given 조건 한 행 */
export interface GWTCondition {
  /** 고유 ID (프론트 전용, UUID) */
  id: string;
  /** 조건 타입: state(노드 상태), relation(관계 존재), expression(수식) */
  type: ConditionType;
  /** 대상 온톨로지 계층 */
  layer: OntologyLayer;
  /** 대상 필드명 (예: "availability", "defect_rate") */
  field: string;
  /** 비교 연산자 */
  operator: ComparisonOperator;
  /** 비교할 값 (문자열로 직렬화, 실행 시 타입 변환) */
  value: string;
}

/** GWT 규칙의 Then 액션 오퍼레이션 유형 */
export type ActionOp = 'SET' | 'EMIT' | 'EXECUTE';

/** GWT 규칙의 Then 액션 한 행 */
export interface GWTAction {
  /** 고유 ID (프론트 전용, UUID) */
  id: string;
  /** 오퍼레이션 유형 */
  op: ActionOp;
  /** SET 전용: 대상 노드 ID */
  targetNodeId?: string;
  /** SET 전용: 변경할 필드명 */
  field?: string;
  /** SET 전용: 설정할 값 */
  value?: string;
  /** EMIT 전용: 발행할 이벤트 타입 */
  eventType?: string;
  /** EMIT 전용: 이벤트 페이로드 (JSON 문자열) */
  payload?: string;
  /** EXECUTE 전용: 실행할 ActionType ID */
  actionId?: string;
}

// ──────────────────────────────────────
// ActionType — 행동 규칙 단위
// ──────────────────────────────────────

/** ActionType: GWT 규칙을 묶어놓은 실행 단위 */
export interface ActionType {
  /** 서버 발급 고유 ID */
  id: string;
  /** 사람이 읽기 쉬운 이름 */
  name: string;
  /** 설명 */
  description: string;
  /** 활성 여부 */
  enabled: boolean;
  /** 실행 우선순위 (낮을수록 먼저 실행) */
  priority: number;
  /** When 이벤트 타입 (예: "kpi.threshold_breached") */
  when_event: string;
  /** Given 조건 목록 */
  conditions: GWTCondition[];
  /** Then 액션 목록 */
  actions: GWTAction[];
  /** 생성 일시 */
  created_at: string;
  /** 수정 일시 */
  updated_at: string;
}

/** ActionType 생성 요청 페이로드 */
export interface CreateActionTypePayload {
  name: string;
  description?: string;
  enabled?: boolean;
  priority?: number;
  when_event: string;
  conditions: Omit<GWTCondition, 'id'>[];
  actions: Omit<GWTAction, 'id'>[];
}

/** ActionType 수정 요청 페이로드 */
export interface UpdateActionTypePayload {
  name?: string;
  description?: string;
  enabled?: boolean;
  priority?: number;
  when_event?: string;
  conditions?: Omit<GWTCondition, 'id'>[];
  actions?: Omit<GWTAction, 'id'>[];
}

/** ActionType 목록 응답 */
export interface ActionTypeListResponse {
  actionTypes: ActionType[];
  total: number;
}

/** Dry-Run 테스트 결과 */
export interface DryRunResult {
  /** 조건 매칭 여부 */
  matched: boolean;
  /** 매칭된 조건 수 / 전체 조건 수 */
  matchedConditions: number;
  totalConditions: number;
  /** 실행될 액션 목록 (미리보기) */
  pendingActions: GWTAction[];
  /** 오류 메시지 (있으면) */
  error?: string;
}

/** ActionType 링크 요청 — 온톨로지 노드에 연결 */
export interface LinkActionTypePayload {
  /** 대상 온톨로지 노드 ID */
  ontologyNodeId: string;
  /** 관계 유형 */
  relationshipType: 'READS_FIELD' | 'PREDICTS_FIELD' | 'TRIGGERS';
}

// ──────────────────────────────────────
// Policy — 이벤트 기반 서비스 명령 발행
// ──────────────────────────────────────

/** 트리거 조건 */
export interface TriggerCondition {
  /** 비교할 필드 경로 (이벤트 페이로드 내) */
  field: string;
  /** 비교 연산자 */
  operator: ComparisonOperator;
  /** 비교 값 */
  value: string;
}

/** Policy: 이벤트 수신 시 서비스 커맨드를 발행하는 정책 규칙 */
export interface Policy {
  /** 서버 발급 고유 ID */
  id: string;
  /** 정책 이름 */
  name: string;
  /** 설명 */
  description: string;
  /** 활성 여부 */
  enabled: boolean;
  /** 감시할 이벤트 타입 */
  trigger_event: string;
  /** 트리거 조건 목록 (AND 로직) */
  trigger_conditions: TriggerCondition[];
  /** 대상 서비스 (core / synapse / weaver / oracle / vision) */
  target_service: string;
  /** 대상 커맨드 (예: "create_case", "run_insight") */
  target_command: string;
  /** 커맨드 페이로드 템플릿 (JSON 문자열, Mustache 변수 지원) */
  command_payload_template: string;
  /** 쿨다운(초) — 동일 이벤트 재발행 방지 */
  cooldown_seconds: number;
  /** 생성 일시 */
  created_at: string;
  /** 수정 일시 */
  updated_at: string;
}

/** Policy 생성 요청 페이로드 */
export interface CreatePolicyPayload {
  name: string;
  description?: string;
  enabled?: boolean;
  trigger_event: string;
  trigger_conditions?: TriggerCondition[];
  target_service: string;
  target_command: string;
  command_payload_template?: string;
  cooldown_seconds?: number;
}

/** Policy 수정 요청 페이로드 */
export interface UpdatePolicyPayload {
  name?: string;
  description?: string;
  enabled?: boolean;
  trigger_event?: string;
  trigger_conditions?: TriggerCondition[];
  target_service?: string;
  target_command?: string;
  command_payload_template?: string;
  cooldown_seconds?: number;
}

/** Policy 목록 응답 */
export interface PolicyListResponse {
  policies: Policy[];
  total: number;
}

// ──────────────────────────────────────
// 엔티티 추출 (NLP → 온톨로지 매핑)
// ──────────────────────────────────────

/** 추출된 엔티티 하나 */
export interface ExtractedEntity {
  /** 원본 텍스트에서의 시작 위치 */
  start: number;
  /** 원본 텍스트에서의 끝 위치 */
  end: number;
  /** 추출된 텍스트 */
  text: string;
  /** 매핑된 온톨로지 계층 */
  layer: OntologyLayer;
  /** 매핑된 온톨로지 노드 ID (있으면) */
  ontologyNodeId?: string;
  /** 매핑 신뢰도 (0.0~1.0) */
  confidence: number;
}

/** 엔티티 추출 결과 */
export interface ExtractionResult {
  /** 원본 입력 텍스트 */
  sourceText: string;
  /** 추출된 엔티티 목록 */
  entities: ExtractedEntity[];
  /** 추출 소요 시간 (ms) */
  processingTimeMs: number;
}

// ──────────────────────────────────────
// 시뮬레이션 브랜치 & 시나리오 비교
// ──────────────────────────────────────

/** 개입(Intervention) 사양 */
export interface InterventionSpec {
  /** 개입 대상 노드 ID */
  nodeId: string;
  /** 개입 대상 필드 */
  field: string;
  /** 개입 값 */
  value: number;
}

/** 시뮬레이션 브랜치 */
export interface SimulationBranch {
  /** 브랜치 ID */
  id: string;
  /** 브랜치 이름 */
  name: string;
  /** 적용된 개입 목록 */
  interventions: InterventionSpec[];
  /** 시뮬레이션 결과 스냅샷 (노드ID → 필드 → 값) */
  resultSnapshot: Record<string, Record<string, number>>;
  /** 시뮬레이션 실행 시각 */
  simulated_at: string;
}

/** 시나리오 비교 결과 */
export interface ScenarioComparison {
  /** 기준(baseline) 브랜치 ID */
  baselineBranchId: string;
  /** 비교 대상 브랜치 ID */
  comparisonBranchId: string;
  /** 변화량 맵 (노드ID → 필드 → delta) */
  deltas: Record<string, Record<string, number>>;
}
