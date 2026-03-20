/**
 * DomainGraphViewer — 도메인 모델 그래프 (Cytoscape)
 *
 * ObjectType 간 관계를 시각화한다.
 * 노드 = ObjectType, 엣지 = 관계 (FK / 관계 이름 라벨).
 * KAIR MultiLayerOntologyViewer.vue의 그래프 부분을 경량 Cytoscape 컴포넌트로 재구현.
 */

import React, { useRef, useEffect, useCallback } from 'react';
import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import { Maximize2, Minimize2, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { DomainGraphData } from '../types/domain';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface DomainGraphViewerProps {
  /** 그래프 데이터 */
  data: DomainGraphData;
  /** 노드 클릭 콜백 */
  onNodeClick?: (nodeId: string) => void;
  /** 선택된 노드 ID (하이라이트용) */
  selectedNodeId?: string | null;
  /** 접힘 상태 */
  collapsed?: boolean;
  /** 접힘 토글 */
  onToggleCollapse?: () => void;
  className?: string;
}

// ──────────────────────────────────────
// 스타일 상수
// ──────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  active: '#10b981',
  draft: '#f59e0b',
  deprecated: '#6b7280',
};

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const DomainGraphViewer: React.FC<DomainGraphViewerProps> = ({
  data,
  onNodeClick,
  selectedNodeId,
  collapsed = false,
  onToggleCollapse,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  // Cytoscape 초기화
  useEffect(() => {
    if (!containerRef.current || collapsed) return;

    // 요소 생성
    const elements: ElementDefinition[] = [
      // 노드
      ...data.nodes.map((n) => ({
        data: {
          id: n.id,
          label: n.label,
          status: n.status,
          fieldCount: n.fieldCount,
          behaviorCount: n.behaviorCount,
        },
      })),
      // 엣지
      ...data.edges.map((e, idx) => ({
        data: {
          id: `edge_${idx}`,
          source: e.source,
          target: e.target,
          label: e.label,
          relType: e.type,
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        // 노드 스타일
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '11px',
            'font-weight': 600,
            color: '#e2e8f0',
            'text-outline-width': 2,
            'text-outline-color': '#1e293b',
            'background-color': '#3b82f6',
            width: 60,
            height: 60,
            'border-width': 2,
            'border-color': '#1e40af',
            shape: 'roundrectangle',
          },
        },
        // 상태별 색상
        {
          selector: 'node[status="active"]',
          style: { 'background-color': '#10b981', 'border-color': '#059669' },
        },
        {
          selector: 'node[status="draft"]',
          style: { 'background-color': '#f59e0b', 'border-color': '#d97706' },
        },
        {
          selector: 'node[status="deprecated"]',
          style: { 'background-color': '#6b7280', 'border-color': '#4b5563' },
        },
        // 선택 노드 강조
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#818cf8',
            'background-color': '#6366f1',
          },
        },
        // 엣지 스타일
        {
          selector: 'edge',
          style: {
            label: 'data(label)',
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#475569',
            'line-color': '#475569',
            width: 1.5,
            'font-size': '9px',
            color: '#94a3b8',
            'text-background-color': '#0f172a',
            'text-background-opacity': 0.8,
            'text-background-padding': '2px',
            'text-rotation': 'autorotate',
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: true,
        animationDuration: 500,
        randomize: false,
        componentSpacing: 80,
        nodeOverlap: 20,
        idealEdgeLength: () => 120,
        edgeElasticity: () => 100,
        nestingFactor: 1.2,
        gravity: 50,
        numIter: 300,
      },
      // 인터랙션 설정
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      minZoom: 0.3,
      maxZoom: 3,
    });

    // 노드 클릭 이벤트
    cy.on('tap', 'node', (evt) => {
      const nodeId = evt.target.id();
      onNodeClick?.(nodeId);
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [data, collapsed]); // onNodeClick는 의도적으로 의존성에서 제외 (ref 패턴 사용)

  // 선택 노드 하이라이트
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.nodes().unselect();
    if (selectedNodeId) {
      const node = cy.getElementById(selectedNodeId);
      if (node.length) {
        node.select();
        cy.animate({ center: { eles: node }, duration: 300 });
      }
    }
  }, [selectedNodeId]);

  // 줌 컨트롤
  const zoomIn = useCallback(() => cyRef.current?.zoom(cyRef.current.zoom() * 1.3), []);
  const zoomOut = useCallback(() => cyRef.current?.zoom(cyRef.current.zoom() / 1.3), []);
  const fitAll = useCallback(() => cyRef.current?.fit(undefined, 40), []);

  if (collapsed) {
    return (
      <div className="flex items-center justify-center h-full w-10 border-l border-border bg-card">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onToggleCollapse}
          title="그래프 패널 열기"
        >
          <Maximize2 className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col h-full border-l border-border bg-card', className)}>
      {/* 툴바 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <span className="text-xs font-semibold text-foreground">도메인 그래프</span>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={zoomIn} title="확대">
            <ZoomIn className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={zoomOut} title="축소">
            <ZoomOut className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={fitAll} title="전체 보기">
            <RotateCcw className="h-3.5 w-3.5" />
          </Button>
          {onToggleCollapse && (
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onToggleCollapse} title="접기">
              <Minimize2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {/* Cytoscape 컨테이너 */}
      <div ref={containerRef} className="flex-1" />

      {/* 범례 */}
      <div className="flex items-center gap-3 px-3 py-1.5 border-t border-border text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500" /> Active
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-sm bg-amber-500" /> Draft
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-sm bg-zinc-500" /> Deprecated
        </span>
      </div>
    </div>
  );
};
