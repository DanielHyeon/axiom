/**
 * 스키마 네비게이션 타입 — related-tables API 계약
 */
import type { SchemaMode } from '@/shared/utils/nodeKey';

/** 가용성 응답 */
export interface SchemaAvailability {
  robo: { table_count: number };
  text2sql: { table_count: number };
}

/** FK 컬럼 매핑 한 쌍 */
export interface ColumnPair {
  sourceColumn: string;
  targetColumn: string;
}

/** 관련 테이블 항목 */
export interface RelatedTableItem {
  tableId: string;      // nodeKey 형식
  tableName: string;
  schemaName: string;
  datasourceName: string;
  relationType: 'FK_OUT' | 'FK_IN';
  score: number;
  fkCount: number;
  sourceColumns: string[];
  targetColumns: string[];
  columnPairs: ColumnPair[];
  hopDistance: number;   // 1=직접 연결, 2+=multi-hop
  autoAddRecommended: boolean;
}

/** related-tables API 응답 */
export interface RelatedTableResponse {
  sourceTable: {
    tableId: string;
    tableName: string;
    schemaName: string;
    datasourceName: string;
  };
  relatedTables: RelatedTableItem[];
  meta: {
    mode: string;
    limitApplied: number;
    excludedAlreadyLoaded: number;
    depthUsed: number;
  };
}

/** related-tables API 요청 파라미터 */
export interface RelatedTableRequest {
  mode: 'ROBO' | 'TEXT2SQL';
  tableName: string;
  schemaName?: string;
  datasourceName?: string;
  nodeKey?: string;
  alreadyLoadedTableIds?: string[];
  limit?: number;
  depth?: number;
}

/** 초기 모드 판정 상태 머신 */
export type InitialModeStatus = 'idle' | 'loading' | 'resolved' | 'failed';
