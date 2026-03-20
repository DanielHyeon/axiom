/**
 * 도메인 레이어 공통 타입 정의
 *
 * object-explorer 등 여러 feature에서 참조하는 ObjectType 핵심 인터페이스를
 * shared 레이어로 추출한 파일이다.
 * domain feature 고유의 API DTO(Create/Update Payload 등)는 여기에 포함하지 않는다.
 */

// ──────────────────────────────────────
// ObjectType 상태/열거형
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
// 그래프 뷰어용 타입
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
