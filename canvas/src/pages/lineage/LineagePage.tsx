/**
 * LineagePage — 데이터 리니지 캔버스 페이지 (디자인 리뉴얼)
 *
 * .pen 디자인 매칭:
 * - 자유 캔버스 레이아웃 (layout: none), 배경 #FAFAFA
 * - 범례: 좌측 상단, 흰색 카드, 8px radius, 12/16px 패딩, 색상 도트 (Source=파랑/Transform=주황/DW=초록)
 * - 노드: 절대 위치, 흰색 배경, 8px radius, 컬러 2px border
 *   - Source(#3B82F6), ETL(#FF8400), Fact(#22C55E), Cube(#666666)
 *   - 이름: JetBrains Mono 11px medium, 타입 라벨: Geist 9px
 *
 * 백엔드 연동: 기존 lineageApi.ts + useLineage.ts 훅 재사용
 * Cytoscape 대신 간결한 positioned divs + SVG 연결선 사용 (디자인 명세 준수)
 */

import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';
import { useLineageOverview } from '@/features/lineage/hooks/useLineage';
import { useLineageStore } from '@/features/lineage/store/useLineageStore';
import type { LineageNode, LineageEdge, LineageNodeType } from '@/features/lineage/types/lineage';

// ── 노드 타입별 스타일 매핑 (디자인 명세 기반) ──
const NODE_STYLE: Record<string, { border: string; typeColor: string; typeLabel: string }> = {
  source: { border: '#3B82F6', typeColor: '#3B82F6', typeLabel: 'PostgreSQL \u00B7 Source' },
  table: { border: '#6B7280', typeColor: '#6B7280', typeLabel: 'Table' },
  transform: { border: '#FF8400', typeColor: '#FF8400', typeLabel: 'ETL \u00B7 Transform' },
  view: { border: '#8B5CF6', typeColor: '#8B5CF6', typeLabel: 'View' },
  report: { border: '#22C55E', typeColor: '#22C55E', typeLabel: 'DW \u00B7 Fact Table' },
  // "column" 노드는 캔버스에서 잘 안 쓰지만 fallback
  column: { border: '#06B6D4', typeColor: '#06B6D4', typeLabel: 'Column' },
};

// ── 범례 항목 (디자인 기준 3종) ──
const LEGEND_ITEMS = [
  { color: '#3B82F6', label: 'Source' },
  { color: '#FF8400', label: 'Transform' },
  { color: '#22C55E', label: 'DW' },
];

// ── 자동 레이아웃: 노드를 깊이별로 좌→우 배치 ──
interface PositionedNode extends LineageNode {
  x: number;
  y: number;
}

/** 노드 위치를 DAG 깊이 기반으로 자동 계산 */
function layoutNodes(
  nodes: LineageNode[],
  edges: LineageEdge[],
): PositionedNode[] {
  if (nodes.length === 0) return [];

  // 인접 리스트 생성 (source → target)
  const adj = new Map<string, string[]>();
  const inDeg = new Map<string, number>();
  for (const n of nodes) {
    adj.set(n.id, []);
    inDeg.set(n.id, 0);
  }
  for (const e of edges) {
    adj.get(e.source)?.push(e.target);
    inDeg.set(e.target, (inDeg.get(e.target) ?? 0) + 1);
  }

  // BFS 위상 정렬로 깊이(column) 계산
  const depth = new Map<string, number>();
  const queue: string[] = [];
  for (const n of nodes) {
    if ((inDeg.get(n.id) ?? 0) === 0) {
      queue.push(n.id);
      depth.set(n.id, 0);
    }
  }
  while (queue.length > 0) {
    const curr = queue.shift()!;
    const currDepth = depth.get(curr) ?? 0;
    for (const next of adj.get(curr) ?? []) {
      const newDepth = currDepth + 1;
      if (!depth.has(next) || depth.get(next)! < newDepth) {
        depth.set(next, newDepth);
      }
      const newIn = (inDeg.get(next) ?? 1) - 1;
      inDeg.set(next, newIn);
      if (newIn <= 0) {
        queue.push(next);
      }
    }
  }

  // 아직 depth가 없는 노드(고립) 처리
  for (const n of nodes) {
    if (!depth.has(n.id)) depth.set(n.id, 0);
  }

  // 깊이별 그룹
  const columns = new Map<number, LineageNode[]>();
  for (const n of nodes) {
    const d = depth.get(n.id) ?? 0;
    if (!columns.has(d)) columns.set(d, []);
    columns.get(d)!.push(n);
  }

  // 위치 배정: x = depth * 260 + 60, y = 인덱스 * 120 + 120
  const positioned: PositionedNode[] = [];
  const sortedDepths = Array.from(columns.keys()).sort((a, b) => a - b);
  for (const d of sortedDepths) {
    const col = columns.get(d)!;
    col.forEach((n, i) => {
      positioned.push({
        ...n,
        x: d * 260 + 60,
        y: i * 120 + 120,
      });
    });
  }

  return positioned;
}

/** SVG 연결선 컴포넌트 — 노드 중심점 간 베지어 곡선 */
function EdgeLines({
  edges,
  nodePositions,
}: {
  edges: LineageEdge[];
  nodePositions: Map<string, { x: number; y: number }>;
}) {
  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden="true">
      <defs>
        <marker
          id="arrowhead"
          markerWidth="8"
          markerHeight="6"
          refX="8"
          refY="3"
          orient="auto"
        >
          <polygon points="0 0, 8 3, 0 6" fill="#94A3B8" />
        </marker>
      </defs>
      {edges.map((e) => {
        const from = nodePositions.get(e.source);
        const to = nodePositions.get(e.target);
        if (!from || !to) return null;

        // 노드 사이즈: 140~160 x 56
        const x1 = from.x + 140;
        const y1 = from.y + 28;
        const x2 = to.x;
        const y2 = to.y + 28;
        const cx = (x1 + x2) / 2;

        return (
          <path
            key={e.id}
            d={`M ${x1} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}`}
            fill="none"
            stroke="#94A3B8"
            strokeWidth={1.5}
            markerEnd="url(#arrowhead)"
          />
        );
      })}
    </svg>
  );
}

export function LineagePage() {
  const { t } = useTranslation();
  const { isLoading } = useLineageOverview();
  const nodes = useLineageStore((s) => s.nodes);
  const edges = useLineageStore((s) => s.edges);

  // 레이아웃 계산
  const positioned = useMemo(() => layoutNodes(nodes, edges), [nodes, edges]);

  // 노드 위치 맵 (엣지 렌더용)
  const nodePositions = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();
    for (const n of positioned) {
      map.set(n.id, { x: n.x, y: n.y });
    }
    return map;
  }, [positioned]);

  // 캔버스 최소 크기 계산
  const canvasWidth = useMemo(
    () => Math.max(1200, ...positioned.map((n) => n.x + 200)),
    [positioned],
  );
  const canvasHeight = useMemo(
    () => Math.max(700, ...positioned.map((n) => n.y + 100)),
    [positioned],
  );

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 자유 캔버스 영역 — 배경 #FAFAFA */}
      <div className="relative flex-1 min-h-0 overflow-auto bg-background">
        {/* 범례 — 좌측 상단, 흰색 카드, 8px radius */}
        <div
          className="absolute top-[60px] left-[60px] z-10 flex gap-4 rounded-lg bg-card border border-border px-4 py-3"
          role="region"
          aria-label={t('lineageExt.legendAriaLabel', '리니지 범례')}
        >
          {LEGEND_ITEMS.map(({ color, label }) => (
            <div key={label} className="flex items-center gap-1">
              {/* 색상 도트 — 8px 원형 */}
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="text-[10px] text-text-secondary">{label}</span>
            </div>
          ))}
        </div>

        {/* 로딩 오버레이 */}
        {isLoading && (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-background/80">
            <Loader2 className="h-6 w-6 animate-spin text-text-placeholder" />
            <span className="text-xs text-text-placeholder">
              {t('common.loading', '로딩 중...')}
            </span>
          </div>
        )}

        {/* 빈 상태 */}
        {!isLoading && nodes.length === 0 && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3">
            <span className="text-4xl opacity-30">&#128279;</span>
            <p className="text-sm text-text-placeholder">
              {t('lineage.noData', '리니지 데이터가 없습니다.')}
            </p>
          </div>
        )}

        {/* 캔버스 내 노드 + 엣지 */}
        {!isLoading && nodes.length > 0 && (
          <div
            className="relative"
            style={{ width: canvasWidth, height: canvasHeight, minHeight: '100%' }}
          >
            {/* SVG 연결선 */}
            <EdgeLines edges={edges} nodePositions={nodePositions} />

            {/* 노드들 — 절대 위치 */}
            {positioned.map((node) => {
              const style = NODE_STYLE[node.type] ?? NODE_STYLE.table;
              const nodeWidth = node.type === 'source' ? 140 : 160;

              return (
                <div
                  key={node.id}
                  className="absolute flex flex-col justify-center gap-0.5 rounded-lg bg-card"
                  style={{
                    left: node.x,
                    top: node.y,
                    width: nodeWidth,
                    height: 56,
                    border: `2px solid ${style.border}`,
                    padding: '8px 12px',
                  }}
                >
                  {/* 이름 — JetBrains Mono 11px medium */}
                  <span
                    className="font-mono text-[11px] font-medium text-foreground truncate"
                  >
                    {node.name}
                  </span>
                  {/* 타입 라벨 — Geist 9px */}
                  <span
                    className="text-[9px] font-medium truncate"
                    style={{ color: style.typeColor }}
                  >
                    {node.datasource ? `${node.datasource} \u00B7 ` : ''}
                    {style.typeLabel}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
