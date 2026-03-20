/**
 * 도메인 레이어 — ObjectType 타입 정의
 *
 * KAIR의 OntologyType/OntologyBehavior 모델을 Axiom 패턴으로 재설계.
 * Synapse 서비스가 Neo4j에 :ObjectType 노드를 저장한다.
 */

// ──────────────────────────────────────
// ObjectType 핵심 모델
// ──────────────────────────────────────

/** ObjectType 상태: draft → active → deprecated */
export type ObjectTypeStatus = 'draft' | 'active' | 'deprecated';

/** 관계 카디날리티 */
export type RelationType =
  | 'one-to-many'
  | 'many-to-one'
  | 'one-to-one'
  | 'many-to-many';

/** Behavior 실행 유형 (KAIR 4유형 호환) */
export type BehaviorType = 'rest' | 'javascript' | 'python' | 'dmn';

/** Behavior 트리거 */
export type BehaviorTrigger = 'manual' | 'on_create' | 'on_update' | 'scheduled';

/** 차트 유형 */
export type ChartType = 'bar' | 'line' | 'pie' | 'map' | 'none';

// ──────────────────────────────────────
// 필드(컬럼) 정의
// ──────────────────────────────────────

export interface ObjectTypeField {
  id: string;
  name: string;
  displayName: string;
  sourceColumn: string;
  dataType: string;
  isPrimaryKey: boolean;
  isForeignKey: boolean;
  isVisible: boolean;
  description?: string;
}

// ──────────────────────────────────────
// Behavior 정의
// ──────────────────────────────────────

export interface Behavior {
  id: string;
  name: string;
  type: BehaviorType;
  trigger: BehaviorTrigger;
  code: string;
  description?: string;
  enabled: boolean;
  /** REST API 전용 — 엔드포인트 URL */
  endpoint?: string;
  /** REST API 전용 — HTTP 메서드 */
  httpMethod?: string;
  /** 입력으로 사용할 필드 이름 목록 */
  inputFields?: string[];
  /** 출력 필드 이름 */
  outputField?: string;
}

// ──────────────────────────────────────
// 관계 정의
// ──────────────────────────────────────

export interface ObjectTypeRelation {
  id: string;
  name: string;
  targetObjectTypeId: string;
  targetObjectTypeName: string;
  type: RelationType;
  foreignKey: string;
  /** 매칭 전략 (선택) */
  matchStrategy?: 'EXACT_MATCH' | 'CONTAINS' | 'STARTS_WITH' | 'ENDS_WITH';
}

// ──────────────────────────────────────
// 차트 설정
// ──────────────────────────────────────

export interface ChartConfig {
  chartType: ChartType;
  xAxis?: string;
  yAxis?: string;
  valueField?: string;
  labelField?: string;
}

// ──────────────────────────────────────
// ObjectType 메인 인터페이스
// ──────────────────────────────────────

export interface ObjectType {
  id: string;
  name: string;
  displayName: string;
  description: string;
  sourceTable: string;
  sourceSchema: string;
  fields: ObjectTypeField[];
  behaviors: Behavior[];
  relations: ObjectTypeRelation[];
  chartConfig?: ChartConfig;
  /** 온톨로지 노드와 연결 시 ID */
  ontologyNodeId?: string;
  /** Materialized View SQL (있으면) */
  materializedViewSql?: string;
  status: ObjectTypeStatus;
  created_at: string;
  updated_at: string;
}

// ──────────────────────────────────────
// API 요청/응답 DTO
// ──────────────────────────────────────

/** ObjectType 생성 요청 */
export interface CreateObjectTypePayload {
  name: string;
  displayName?: string;
  description?: string;
  sourceTable?: string;
  sourceSchema?: string;
  fields?: Omit<ObjectTypeField, 'id'>[];
  behaviors?: Omit<Behavior, 'id'>[];
  relations?: Omit<ObjectTypeRelation, 'id'>[];
  chartConfig?: ChartConfig;
  materializedViewSql?: string;
}

/** ObjectType 수정 요청 */
export interface UpdateObjectTypePayload {
  displayName?: string;
  description?: string;
  fields?: ObjectTypeField[];
  behaviors?: Behavior[];
  relations?: ObjectTypeRelation[];
  chartConfig?: ChartConfig;
  materializedViewSql?: string;
  status?: ObjectTypeStatus;
}

/** 테이블로부터 ObjectType 자동 생성 요청 */
export interface GenerateFromTablePayload {
  datasource: string;
  schema: string;
  table: string;
}

/** Behavior 실행 요청 */
export interface ExecuteBehaviorPayload {
  instanceData?: Record<string, unknown>;
}

/** Behavior 실행 결과 */
export interface BehaviorExecutionResult {
  success: boolean;
  result?: unknown;
  error?: string;
  execution_time_ms?: number;
}

/** ObjectType 목록 응답 */
export interface ObjectTypeListResponse {
  objectTypes: ObjectType[];
  total: number;
}

// ──────────────────────────────────────
// 도메인 그래프 뷰어용 타입
// ──────────────────────────────────────

export interface DomainGraphNode {
  id: string;
  label: string;
  status: ObjectTypeStatus;
  fieldCount: number;
  behaviorCount: number;
}

export interface DomainGraphEdge {
  source: string;
  target: string;
  label: string;
  type: RelationType;
}

export interface DomainGraphData {
  nodes: DomainGraphNode[];
  edges: DomainGraphEdge[];
}
