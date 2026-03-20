/**
 * LineageGraph — Cytoscape 기반 리니지 DAG 시각화
 *
 * 좌 → 우 dagre 레이아웃으로 노드 타입별 색상/모양을 적용한다.
 * GraphViewer(ontology) 패턴을 참고하되 리니지 전용 스타일을 사용.
 */

import { useEffect, useRef, useCallback } from 'react';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { useLineageStore } from '../store/useLineageStore';
import {
  LINEAGE_NODE_STYLES,
  type LineageNode,
  type LineageEdge,
  type LineageNodeType,
} from '../types/lineage';

// dagre 레이아웃 확장 등록 (한 번만)
try {
  cytoscape.use(dagre);
} catch {
  // 이미 등록된 경우 무시
}

// ---------------------------------------------------------------------------
// Cytoscape 스타일시트
// ---------------------------------------------------------------------------

function buildStylesheet(): cytoscape.Stylesheet[] {
  const base: cytoscape.Stylesheet[] = [
    // 공통 노드 스타일
    {
      selector: 'node',
      style: {
        label: 'data(label)',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-size': 11,
        color: '#ffffff',
        'text-outline-width': 0,
        'background-color': '#6B7280',
        width: 36,
        height: 36,
        'border-width': 2,
        'border-color': '#374151',
        'overlay-opacity': 0,
        'text-wrap': 'ellipsis',
        'text-max-width': '120px',
      },
    },
    // 노드 선택 상태
    {
      selector: 'node:selected',
      style: {
        'border-width': 3,
        'border-color': '#FBBF24',
        'overlay-opacity': 0.08,
        'overlay-color': '#FBBF24',
      },
    },
    // 공통 엣지 스타일
    {
      selector: 'edge',
      style: {
        width: 1.5,
        'line-color': '#94A3B8',
        'target-arrow-color': '#94A3B8',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        'arrow-scale': 0.8,
      },
    },
    // 엣지 hover 강조
    {
      selector: 'edge:selected',
      style: {
        width: 2.5,
        'line-color': '#FBBF24',
        'target-arrow-color': '#FBBF24',
      },
    },
  ];

  // 노드 타입별 스타일 추가
  for (const [type, config] of Object.entries(LINEAGE_NODE_STYLES)) {
    base.push({
      selector: `node.${type}`,
      style: {
        'background-color': config.color,
        'border-color': config.borderColor,
        shape: config.shape as any,
      },
    });
  }

  return base;
}

// ---------------------------------------------------------------------------
// 그래프 데이터 → Cytoscape 엘리먼트 변환
// ---------------------------------------------------------------------------

function toElements(
  nodes: LineageNode[],
  edges: LineageEdge[],
  activeTypes: Set<LineageNodeType>,
): cytoscape.ElementDefinition[] {
  // 노드 타입 필터 적용
  const visibleNodes = nodes.filter((n) => activeTypes.has(n.type));
  const visibleIds = new Set(visibleNodes.map((n) => n.id));

  const elements: cytoscape.ElementDefinition[] = [];

  // 노드
  for (const n of visibleNodes) {
    elements.push({
      data: {
        id: n.id,
        label: n.name,
        nodeType: n.type,
        schema: n.schema,
        datasource: n.datasource,
      },
      classes: n.type,
    });
  }

  // 엣지 — 양쪽 노드가 모두 보이는 경우만
  for (const e of edges) {
    if (visibleIds.has(e.source) && visibleIds.has(e.target)) {
      elements.push({
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          edgeType: e.type,
        },
      });
    }
  }

  return elements;
}

// ---------------------------------------------------------------------------
// 컴포넌트
// ---------------------------------------------------------------------------

interface LineageGraphProps {
  /** 로딩 상태 오버레이 표시 */
  isLoading?: boolean;
}

export function LineageGraph({ isLoading = false }: LineageGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  const { nodes, edges, filters, selectNode } = useLineageStore();

  // Cytoscape 인스턴스 초기화
  const initCy = useCallback(() => {
    if (!containerRef.current) return;

    // 기존 인스턴스 정리
    cyRef.current?.destroy();

    const cy = cytoscape({
      container: containerRef.current,
      elements: toElements(nodes, edges, filters.nodeTypes),
      style: buildStylesheet(),
      layout: {
        name: 'dagre',
        // 좌→우 방향 DAG
        rankDir: 'LR',
        nodeSep: 60,
        rankSep: 180,
        edgeSep: 30,
        padding: 40,
      } as any,
      minZoom: 0.15,
      maxZoom: 3,
      wheelSensitivity: 0.3,
    });

    // 노드 클릭 핸들러
    cy.on('tap', 'node', (evt) => {
      const nodeId = evt.target.id();
      const originalNode = nodes.find((n) => n.id === nodeId) ?? null;
      selectNode(originalNode);
    });

    // 배경 클릭 → 선택 해제
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        selectNode(null);
      }
    });

    // 초기 화면 맞춤
    cy.fit(undefined, 40);

    cyRef.current = cy;
  }, [nodes, edges, filters.nodeTypes, selectNode]);

  // 마운트 시 초기화
  useEffect(() => {
    initCy();

    return () => {
      cyRef.current?.destroy();
      cyRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 데이터 또는 필터 변경 시 그래프 갱신
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) {
      initCy();
      return;
    }

    const elements = toElements(nodes, edges, filters.nodeTypes);

    // 배치 업데이트 — 기존 엘리먼트 제거 후 새로 추가
    cy.elements().remove();
    cy.add(elements);

    // 레이아웃 재실행
    cy.layout({
      name: 'dagre',
      rankDir: 'LR',
      nodeSep: 60,
      rankSep: 180,
      edgeSep: 30,
      padding: 40,
      animate: true,
      animationDuration: 300,
    } as any).run();

    // 약간의 딜레이 후 fitView
    setTimeout(() => cy.fit(undefined, 40), 350);
  }, [nodes, edges, filters.nodeTypes, initCy]);

  return (
    <div className="relative h-full w-full">
      {/* Cytoscape 컨테이너 */}
      <div
        ref={containerRef}
        className="h-full w-full"
        role="img"
        aria-label="데이터 리니지 그래프"
      />

      {/* 로딩 오버레이 */}
      {isLoading && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-3 bg-background/80 backdrop-blur-sm">
          <div className="h-9 w-9 animate-spin rounded-full border-[3px] border-border border-t-primary" />
          <span className="text-sm font-medium text-muted-foreground">
            데이터 로딩 중...
          </span>
        </div>
      )}

      {/* 데이터 없음 */}
      {!isLoading && nodes.length === 0 && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4 text-center">
          <span className="text-5xl opacity-40">&#128279;</span>
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              데이터 리니지 없음
            </h3>
            <p className="mt-1 max-w-xs text-sm text-muted-foreground">
              데이터소스를 등록하거나 ETL을 구성하면 리니지가 자동으로 생성됩니다.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
