/**
 * 스키마 캔버스 관련 타입 정의.
 * DatabaseTree, SchemaCanvas, TableDetailPanel 등에서 사용하는 공용 인터페이스.
 */

import type { TableMeta, ColumnMeta } from './nl2sql';
import type { ColumnPair } from '@/shared/types/schemaNavigation';

// ─── 트리 노드 타입 ───────────────────────────────────────

/** DB 트리에서 사용하는 스키마 노드 */
export interface SchemaNode {
  name: string;
  /** 해당 스키마에 속하는 테이블 목록 (지연 로딩) */
  tables?: TableMeta[];
  isLoading?: boolean;
}

/** 트리 노드 선택 타입 */
export type TreeSelection =
  | { type: 'schema'; schema: string }
  | { type: 'table'; schema: string; table: string }
  | { type: 'column'; schema: string; table: string; column: string };

// ─── 테이블 상세 타입 ─────────────────────────────────────

/** 테이블 상세 정보 (컬럼 + 통계 + 샘플) */
export interface TableDetail {
  meta: TableMeta;
  columns: ColumnMeta[];
  sampleRows?: unknown[][];
  stats?: TableStats;
}

/** 테이블 통계 */
export interface TableStats {
  rowCount: number;
  columnCount: number;
  lastUpdated?: string;
}

// ─── FK 관계 타입 ─────────────────────────────────────────

/** FK 관계 소스 타입 */
export type FkSource = 'ddl' | 'user' | 'fabric';

/** FK 관계 (사용자가 수동 추가한 관계 포함) */
export interface SchemaRelationship {
  id?: string;
  fromTable: string;
  fromColumn: string;
  toTable: string;
  toColumn: string;
  cardinality: 'one-to-one' | 'one-to-many' | 'many-to-one' | 'many-to-many';
  description?: string;
  isInferred?: boolean; // _id 접미사 기반 추론 여부
  source?: FkSource;        // G1: 관계 소스 식별
  columnPairs?: ColumnPair[]; // G4: 복수 컬럼 매핑
}

// ─── 캔버스 관련 타입 ─────────────────────────────────────

/** 캔버스에 배치된 테이블 노드 */
export interface CanvasTableNode {
  tableName: string;
  schema: string;
  /** 캔버스 좌표 */
  position: { x: number; y: number };
  /** NL2SQL LLM 컨텍스트에 포함할지 여부 */
  includedInContext: boolean;
  /** 컬럼 목록 (캐싱) */
  columns: ColumnMeta[];
}

// ─── ReAct 요약 타입 ──────────────────────────────────────

/** ReAct 에이전트 실행 요약 */
export interface ReactSummary {
  status: 'idle' | 'running' | 'needs_user_input' | 'completed' | 'error';
  /** 부분 SQL (실행 중) */
  partialSql: string | null;
  /** 최종 SQL */
  finalSql: string | null;
  /** 검증된 SQL */
  validatedSql: string | null;
  /** 경고 목록 */
  warnings: string[];
  /** 남은 도구 호출 횟수 */
  remainingToolCalls: number;
  /** 현재 스텝 번호 */
  currentStep: number;
  /** 최근 사용된 도구 이름 */
  latestToolName: string | null;
}

// ─── 검색 타입 ────────────────────────────────────────────

/** 스키마 검색 결과 */
export interface SchemaSearchResult {
  type: 'table' | 'column';
  tableName: string;
  columnName?: string;
  schema: string;
  /** 검색 매치된 텍스트 */
  matchedText: string;
}
