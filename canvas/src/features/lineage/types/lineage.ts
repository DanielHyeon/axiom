/**
 * 데이터 리니지 타입 정의
 * Synapse 서비스의 Neo4j 리니지 데이터 모델
 */

/** 리니지 노드 유형 — 소스/테이블/컬럼/뷰/변환/리포트 */
export type LineageNodeType = 'source' | 'table' | 'column' | 'view' | 'transform' | 'report';

/** 탐색 방향 */
export type LineageDirection = 'upstream' | 'downstream' | 'both';

/** 엣지 관계 유형 */
export type LineageEdgeType = 'derives_from' | 'transforms' | 'aggregates' | 'joins' | 'filters';

/** 리니지 그래프 노드 */
export interface LineageNode {
  id: string;
  name: string;
  type: LineageNodeType;
  /** 스키마 이름 (테이블/뷰 노드에 해당) */
  schema?: string;
  /** 데이터소스 이름 */
  datasource?: string;
  /** 사용자 정의 설명 */
  description?: string;
  /** 노드 메타 속성 (컬럼 수, 오퍼레이션 등) */
  properties: Record<string, unknown>;
}

/** 리니지 그래프 엣지 */
export interface LineageEdge {
  id: string;
  source: string;
  target: string;
  type: LineageEdgeType;
  /** 변환 SQL (transform 엣지인 경우) */
  sql?: string;
}

/** 리니지 통계 요약 */
export interface LineageStats {
  sourceCount: number;
  tableCount: number;
  transformCount: number;
  viewCount: number;
  reportCount: number;
  edgeCount: number;
}

/** 리니지 그래프 응답 전체 */
export interface LineageGraph {
  nodes: LineageNode[];
  edges: LineageEdge[];
  rootNodeId: string;
  depth: number;
}

/** 리니지 검색 결과 항목 */
export interface LineageSearchResult {
  id: string;
  name: string;
  type: LineageNodeType;
  schema?: string;
  datasource?: string;
}

/** 리니지 필터 상태 */
export interface LineageFilters {
  direction: LineageDirection;
  depth: number;
  nodeTypes: Set<LineageNodeType>;
  searchQuery: string;
}

/** 노드 타입별 시각화 설정 */
export interface LineageNodeStyle {
  color: string;
  borderColor: string;
  label: string;
  shape: string;
}

/** 노드 타입 → 시각화 설정 매핑 */
export const LINEAGE_NODE_STYLES: Record<LineageNodeType, LineageNodeStyle> = {
  source: {
    color: '#3B82F6',
    borderColor: '#1D4ED8',
    label: '소스',
    shape: 'round-rectangle',
  },
  table: {
    color: '#6B7280',
    borderColor: '#374151',
    label: '테이블',
    shape: 'round-rectangle',
  },
  column: {
    color: '#06B6D4',
    borderColor: '#0E7490',
    label: '컬럼',
    shape: 'ellipse',
  },
  view: {
    color: '#8B5CF6',
    borderColor: '#6D28D9',
    label: '뷰',
    shape: 'diamond',
  },
  transform: {
    color: '#F59E0B',
    borderColor: '#D97706',
    label: '변환',
    shape: 'hexagon',
  },
  report: {
    color: '#10B981',
    borderColor: '#047857',
    label: '리포트',
    shape: 'round-rectangle',
  },
};
