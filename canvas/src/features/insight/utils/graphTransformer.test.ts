// graphTransformer 단위 테스트
import { describe, it, expect } from 'vitest';
import { toCytoscapeElements, getLayoutConfig } from './graphTransformer';
import type { GraphData, GraphNode, GraphEdge, GraphMeta } from '../types/insight';

// ---------------------------------------------------------------------------
// 헬퍼: 테스트용 GraphData 빌더
// ---------------------------------------------------------------------------

const baseMeta: GraphMeta = {
  schema_version: '1.0',
  analysis_version: '1.0',
  generated_at: '2026-03-20T00:00:00Z',
  time_range: { from: '2026-03-01', to: '2026-03-20' },
  datasource: 'test',
  cache_hit: false,
  limits: { max_nodes: 100, max_edges: 200, depth: 3 },
  truncated: false,
};

function makeGraphData(
  nodes: GraphNode[],
  edges: GraphEdge[],
): GraphData {
  return { meta: baseMeta, nodes, edges };
}

// ---------------------------------------------------------------------------
// toCytoscapeElements
// ---------------------------------------------------------------------------

describe('toCytoscapeElements', () => {
  it('빈 입력 → 빈 배열 반환', () => {
    const result = toCytoscapeElements(makeGraphData([], []));
    expect(result).toEqual([]);
  });

  it('노드 변환: id, label, nodeType, 스타일 속성이 정확히 매핑됨', () => {
    const nodes: GraphNode[] = [
      { id: 'kpi-1', label: 'OEE', type: 'KPI' },
    ];
    const result = toCytoscapeElements(makeGraphData(nodes, []));

    expect(result).toHaveLength(1);
    const el = result[0];
    expect(el.group).toBe('nodes');
    expect(el.data.id).toBe('kpi-1');
    expect(el.data.label).toBe('OEE');
    expect(el.data.nodeType).toBe('KPI');
    // KPI 노드는 star 형태
    expect(el.data.shape).toBe('star');
    expect(el.data.color).toBe('#60a5fa');
    // KPI 노드 크기
    expect(el.data.width).toBe(70);
    expect(el.data.height).toBe(60);
  });

  it('DRIVER 노드의 너비가 score에 비례 (score=0 → 38, score=1 → 90)', () => {
    const nodes: GraphNode[] = [
      { id: 'd0', label: 'Driver Zero', type: 'DRIVER', score: 0 },
      { id: 'd1', label: 'Driver Full', type: 'DRIVER', score: 1 },
    ];
    const result = toCytoscapeElements(makeGraphData(nodes, []));

    const d0 = result.find((e) => e.data.id === 'd0')!;
    const d1 = result.find((e) => e.data.id === 'd1')!;
    expect(d0.data.width).toBe(38);
    expect(d1.data.width).toBe(90);
  });

  it('score가 없는 DRIVER 노드 → 기본 너비 40', () => {
    const nodes: GraphNode[] = [
      { id: 'd-no-score', label: 'No Score', type: 'DRIVER' },
    ];
    const result = toCytoscapeElements(makeGraphData(nodes, []));
    expect(result[0].data.width).toBe(40);
  });

  it('엣지 변환: source, target, edgeType, 스타일 속성이 정확히 매핑됨', () => {
    const edges: GraphEdge[] = [
      { source: 'a', target: 'b', type: 'IMPACT', label: 'affects' },
    ];
    const result = toCytoscapeElements(makeGraphData([], edges));

    expect(result).toHaveLength(1);
    const el = result[0];
    expect(el.group).toBe('edges');
    expect(el.data.source).toBe('a');
    expect(el.data.target).toBe('b');
    expect(el.data.edgeType).toBe('IMPACT');
    expect(el.data.label).toBe('affects');
    // IMPACT 스타일
    expect(el.data.lineStyle).toBe('solid');
    expect(el.data.lineColor).toBe('#f43f5e');
    expect(el.data.lineWidth).toBe(3);
  });

  it('엣지 id가 없으면 인덱스 기반 fallback id 생성', () => {
    const edges: GraphEdge[] = [
      { source: 'x', target: 'y', type: 'FK' },
    ];
    const result = toCytoscapeElements(makeGraphData([], edges));
    expect(result[0].data.id).toBe('e0_x_y');
  });

  it('엣지 id가 있으면 그대로 사용', () => {
    const edges: GraphEdge[] = [
      { id: 'custom-id', source: 'x', target: 'y', type: 'FK' },
    ];
    const result = toCytoscapeElements(makeGraphData([], edges));
    expect(result[0].data.id).toBe('custom-id');
  });

  it('알 수 없는 노드 타입 → TABLE 기본 스타일 적용', () => {
    const nodes: GraphNode[] = [
      { id: 'unknown', label: 'Unknown', type: 'UNKNOWN_TYPE' as any },
    ];
    const result = toCytoscapeElements(makeGraphData(nodes, []));
    // TABLE 스타일 fallback
    expect(result[0].data.shape).toBe('rectangle');
    expect(result[0].data.color).toBe('#94a3b8');
  });

  it('알 수 없는 엣지 타입 → JOIN 기본 스타일 적용', () => {
    const edges: GraphEdge[] = [
      { source: 'a', target: 'b', type: 'UNKNOWN_EDGE' as any },
    ];
    const result = toCytoscapeElements(makeGraphData([], edges));
    expect(result[0].data.lineColor).toBe('#94a3b8');
  });

  it('노드에 position이 있으면 position 속성 포함', () => {
    const nodes: GraphNode[] = [
      { id: 'p1', label: 'Pos', type: 'TABLE', position: { x: 100, y: 200 } },
    ];
    const result = toCytoscapeElements(makeGraphData(nodes, []));
    expect(result[0].position).toEqual({ x: 100, y: 200 });
  });

  it('노드에 position이 없으면 position 속성 미포함', () => {
    const nodes: GraphNode[] = [
      { id: 'np', label: 'No Pos', type: 'TABLE' },
    ];
    const result = toCytoscapeElements(makeGraphData(nodes, []));
    expect(result[0].position).toBeUndefined();
  });

  it('노드와 엣지가 혼합된 경우 노드가 먼저, 엣지가 나중', () => {
    const nodes: GraphNode[] = [
      { id: 'n1', label: 'Node', type: 'KPI' },
    ];
    const edges: GraphEdge[] = [
      { source: 'n1', target: 'n2', type: 'IMPACT' },
    ];
    const result = toCytoscapeElements(makeGraphData(nodes, edges));

    expect(result[0].group).toBe('nodes');
    expect(result[1].group).toBe('edges');
  });
});

// ---------------------------------------------------------------------------
// getLayoutConfig
// ---------------------------------------------------------------------------

describe('getLayoutConfig', () => {
  it('impact → cose-bilkent 레이아웃', () => {
    const config = getLayoutConfig('impact');
    expect(config.name).toBe('cose-bilkent');
  });

  it('instance → dagre TB 레이아웃', () => {
    const config = getLayoutConfig('instance');
    expect(config.name).toBe('dagre');
    expect(config.rankDir).toBe('TB');
  });

  it('query → dagre LR 레이아웃', () => {
    const config = getLayoutConfig('query');
    expect(config.name).toBe('dagre');
    expect(config.rankDir).toBe('LR');
  });

  it('알 수 없는 타입 → cose-bilkent 기본값', () => {
    const config = getLayoutConfig('unknown' as any);
    expect(config.name).toBe('cose-bilkent');
  });
});
