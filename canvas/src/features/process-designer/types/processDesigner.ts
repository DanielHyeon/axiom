// features/process-designer/types/processDesigner.ts
// Process Designer type definitions based on design spec v1.2 §2-§3

// ---------------------------------------------------------------------------
// Canvas Item Types (8 basic + 3 extended = 11)
// ---------------------------------------------------------------------------

/** 8종 기본 비즈니스 노드 + 3종 확장 노드 */
export type CanvasItemType =
  // 8종 비즈니스 노드 (EventStorming 확장)
  | 'contextBox'          // Business Domain (부서/사업부 영역)
  | 'businessAction'      // Business Action (업무 행위)
  | 'businessEvent'       // Business Event (업무 사건)
  | 'businessEntity'      // Business Entity (업무 객체)
  | 'businessRule'        // Business Rule (업무 규칙)
  | 'stakeholder'         // Stakeholder / Role (이해관계자)
  | 'businessReport'      // Business Report (업무 보고서)
  | 'measure'             // Measure (KPI/측정값)
  // 3종 확장 노드
  | 'eventLogBinding'     // EventLogBinding (데이터 소스 바인딩)
  | 'temporalAnnotation'; // TemporalAnnotation (시간 주석)

// ---------------------------------------------------------------------------
// Connection Types (4종)
// ---------------------------------------------------------------------------

/** 설계 §3.1 연결선 4종 */
export type ConnectionType = 'triggers' | 'reacts_to' | 'produces' | 'binds_to';

// ---------------------------------------------------------------------------
// Canvas Item Sub-types
// ---------------------------------------------------------------------------

/** 시간축 속성 — businessEvent, businessAction에 적용 */
export interface TemporalData {
  expectedDuration?: number;   // 예상 소요 시간 (분)
  sla?: number;                // SLA 제한 (분)
  actualAvg?: number;          // 실제 평균 (프로세스 마이닝 결과, 읽기전용)
  status?: 'ok' | 'warning' | 'violation';
}

/** 측정값 바인딩 — measure 노드에 적용 */
export interface MeasureBindingData {
  kpiId?: string;
  formula?: string;
  unit?: string;
}

/** 이벤트 로그 바인딩 — eventLogBinding 노드에 적용 */
export interface EventLogBindingData {
  sourceTable: string;
  timestampColumn: string;
  caseIdColumn: string;
  activityColumn?: string;
  filter?: string;
}

// ---------------------------------------------------------------------------
// Canvas Item
// ---------------------------------------------------------------------------

/** 캔버스 아이템 (설계 §2.3) */
export interface CanvasItem {
  id: string;
  type: CanvasItemType;
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  description?: string;
  color: string;
  parentContextBoxId?: string | null;

  // 시간축 속성 (businessEvent, businessAction에 적용)
  temporal?: TemporalData;
  // 측정값 바인딩 (measure 노드에 적용)
  measureBinding?: MeasureBindingData;
  // 이벤트 로그 바인딩 (eventLogBinding 노드에 적용)
  eventLogBinding?: EventLogBindingData;
}

// ---------------------------------------------------------------------------
// Connection
// ---------------------------------------------------------------------------

export interface ConnectionStyle {
  stroke: string;
  strokeWidth: number;
  dashArray?: string;
  arrowSize: number;
}

/** 연결선 (설계 §3.2) */
export interface Connection {
  id: string;
  type: ConnectionType;
  sourceId: string;
  targetId: string;
  label?: string;
  style: ConnectionStyle;
}

// ---------------------------------------------------------------------------
// UI State Types
// ---------------------------------------------------------------------------

/** 도구 모드: 선택, 연결선, 또는 노드 추가 모드 */
export type ToolMode = 'select' | 'connect' | CanvasItemType;

/** 캔버스 뷰 상태 (패닝/줌) */
export interface StageViewState {
  x: number;
  y: number;
  scale: number;
}

/** 연결선 그리기 임시 상태 */
export interface PendingConnection {
  sourceId: string;
  mousePos: { x: number; y: number };
}
