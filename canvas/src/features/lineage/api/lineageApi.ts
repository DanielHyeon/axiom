/**
 * 리니지 API 클라이언트
 * Synapse 서비스를 경유하여 Neo4j 리니지 데이터를 조회한다.
 */

import { synapseApi } from '@/lib/api/clients';
import type {
  LineageGraph,
  LineageSearchResult,
  LineageDirection,
  LineageNode,
} from '../types/lineage';

// ---------------------------------------------------------------------------
// 백엔드 응답 타입
// ---------------------------------------------------------------------------

interface LineageGraphResponse {
  success: boolean;
  data: {
    nodes: LineageNode[];
    edges: Array<{
      id: string;
      source: string;
      target: string;
      type: string;
      sql?: string;
    }>;
    root_node_id: string;
    depth: number;
  };
}

interface LineageSearchResponse {
  success: boolean;
  data: LineageSearchResult[];
}

interface LineageOverviewResponse {
  success: boolean;
  data: {
    nodes: LineageNode[];
    edges: Array<{
      id: string;
      source: string;
      target: string;
      type: string;
      sql?: string;
    }>;
    stats: {
      source_count: number;
      table_count: number;
      transform_count: number;
      view_count: number;
      report_count: number;
      edge_count: number;
    };
  };
}

// ---------------------------------------------------------------------------
// API 함수
// ---------------------------------------------------------------------------

/**
 * 특정 노드 기준 리니지 그래프 조회
 * @param nodeId - 시작 노드 ID
 * @param direction - 탐색 방향 (upstream/downstream/both)
 * @param depth - 탐색 깊이 (1~5 hop)
 */
export async function getLineageGraph(
  nodeId: string,
  direction: LineageDirection = 'both',
  depth = 3,
): Promise<LineageGraph> {
  const res = (await synapseApi.get(
    `/api/v3/synapse/lineage/${encodeURIComponent(nodeId)}`,
    { params: { direction, depth } },
  )) as unknown as LineageGraphResponse;

  return {
    nodes: res.data.nodes,
    edges: res.data.edges.map((e) => ({
      ...e,
      type: e.type as LineageGraph['edges'][number]['type'],
    })),
    rootNodeId: res.data.root_node_id,
    depth: res.data.depth,
  };
}

/**
 * 리니지 전체 개요 (overview) 조회 — 초기 로딩용
 * 전체 리니지 그래프 + 통계를 반환한다.
 */
export async function getLineageOverview(): Promise<{
  nodes: LineageGraph['nodes'];
  edges: LineageGraph['edges'];
  stats: {
    sourceCount: number;
    tableCount: number;
    transformCount: number;
    viewCount: number;
    reportCount: number;
    edgeCount: number;
  };
}> {
  const res = (await synapseApi.get(
    '/api/v3/synapse/lineage/overview',
  )) as unknown as LineageOverviewResponse;

  return {
    nodes: res.data.nodes,
    edges: res.data.edges.map((e) => ({
      ...e,
      type: e.type as LineageGraph['edges'][number]['type'],
    })),
    stats: {
      sourceCount: res.data.stats.source_count,
      tableCount: res.data.stats.table_count,
      transformCount: res.data.stats.transform_count,
      viewCount: res.data.stats.view_count,
      reportCount: res.data.stats.report_count,
      edgeCount: res.data.stats.edge_count,
    },
  };
}

/**
 * 리니지 노드 검색 — 테이블/컬럼 이름으로 검색
 */
export async function searchLineageNodes(
  query: string,
): Promise<LineageSearchResult[]> {
  const res = (await synapseApi.get('/api/v3/synapse/lineage/search', {
    params: { q: query },
  })) as unknown as LineageSearchResponse;

  return res.data;
}

/**
 * 특정 노드 상세 정보 조회
 */
export async function getLineageNodeDetail(
  nodeId: string,
): Promise<LineageNode> {
  const res = (await synapseApi.get(
    `/api/v3/synapse/lineage/nodes/${encodeURIComponent(nodeId)}`,
  )) as unknown as { success: boolean; data: LineageNode };

  return res.data;
}
