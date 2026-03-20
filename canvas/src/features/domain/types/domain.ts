/**
 * 도메인 레이어 — ObjectType 타입 정의
 *
 * 핵심 타입(ObjectType, ObjectTypeField, Behavior 등)은 shared/types/domain.ts에서 관리하며,
 * 이 파일은 하위 호환성을 위해 re-export한 뒤 domain feature 전용 DTO만 추가로 정의한다.
 */

// ── 공통 도메인 타입 re-export (하위 호환성 유지) ──
export type {
  ObjectTypeStatus,
  RelationType,
  BehaviorType,
  BehaviorTrigger,
  ChartType,
  ObjectTypeField,
  Behavior,
  ObjectTypeRelation,
  ChartConfig,
  ObjectType,
  DomainGraphNode,
  DomainGraphEdge,
  DomainGraphData,
} from '@/shared/types/domain';

// ── 아래부터는 domain feature 전용 API DTO (다른 feature에서 참조 안 함) ──

import type { ObjectTypeField, Behavior, ObjectTypeRelation, ChartConfig, ObjectTypeStatus } from '@/shared/types/domain';

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
  objectTypes: import('@/shared/types/domain').ObjectType[];
  total: number;
}
