/**
 * InstanceGraph — 인스턴스 관계 그래프 (Cytoscape)
 *
 * 선택된 인스턴스를 중심으로 1-hop 관련 인스턴스를 시각화한다.
 * DomainGraphViewer.tsx의 Cytoscape 패턴을 재사용.
 *
 * 주요 기능:
 *  - 중심 노드: 선택된 인스턴스 (강조 표시)
 *  - 주변 노드: 관련 인스턴스 (ObjectType별 색상)
 *  - 엣지: 관계명 라벨
 *  - 줌/팬/드래그 인터랙션
 */

import React, { useRef, useEffect, useCallback } from 'react';
import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import { ZoomIn, ZoomOut, RotateCcw, Minimize2, Maximize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { ObjectInstance } from '../types/object-explorer';

// ──────────────────────────────────────
// 색상 팔레트 (ObjectType별 동적 할당)
// ──────────────────────────────────────

const COLOR_PALETTE = [
  '#22c55e', // green
  '#3b82f6', // blue
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#06b6d4', // cyan
  '#ec4899', // pink
  '#ef4444', // red
  '#10b981', // emerald
  '#f97316', // orange
  '#6366f1', // indigo
];

const DEFAULT_COLOR = '#6b7280';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface InstanceGraphProps {
  /** 중심 인스턴스 */
  instance: ObjectInstance | null;
  /** 노드 클릭 콜백 (관련 인스턴스 ID) */
  onNodeClick?: (instanceId: string) => void;
  /** 접힘 상태 */
  collapsed?: boolean;
  /** 접힘 토글 */
  onToggleCollapse?: () => void;
  className?: string;
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const InstanceGraph: React.FC<InstanceGraphProps> = ({
  instance,
  onNodeClick,
  collapsed = false,
  onToggleCollapse,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  // ObjectType → 색상 매핑 생성
  const getColor = useCallback(
    (typeName: string, typeColorMap: Map<string, string>): string => {
      if (typeColorMap.has(typeName)) return typeColorMap.get(typeName)!;
      const color = COLOR_PALETTE[typeColorMap.size % COLOR_PALETTE.length];
      typeColorMap.set(typeName, color);
      return color;
    },
    [],
  );

  // Cytoscape 초기화
  useEffect(() => {
    if (!containerRef.current || collapsed || !instance) return;

    const typeColorMap = new Map<string, string>();

    // 요소 생성
    const elements: ElementDefinition[] = [];

    // 중심 노드 (선택된 인스턴스)
    const centerColor = getColor(instance.objectTypeName, typeColorMap);
    elements.push({
      data: {
        id: instance.id,
        label: instance.displayName,
        typeName: instance.objectTypeName,
        isCenter: true,
      },
    });

    // 관련 인스턴스 노드 + 엣지
    for (const rel of instance.relatedInstances) {
      // 노드 (중복 방지)
      if (!elements.some((el) => el.data.id === rel.instanceId)) {
        getColor(rel.objectTypeName, typeColorMap);
        elements.push({
          data: {
            id: rel.instanceId,
            label: rel.displayName,
            typeName: rel.objectTypeName,
            isCenter: false,
          },
        });
      }

      // 엣지
      elements.push({
        data: {
          id: `edge_${instance.id}_${rel.instanceId}_${rel.relationName}`,
          source: instance.id,
          target: rel.instanceId,
          label: rel.relationName,
        },
      });
    }

    // typeColorMap을 stylesheet에서 사용할 수 있도록 배열로 변환
    const typeStyles = Array.from(typeColorMap.entries()).map(
      ([typeName, color]) => ({
        selector: `node[typeName="${typeName}"]`,
        style: {
          'background-color': color,
          'border-color': color,
        } as Record<string, string>,
      }),
    );

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        // 기본 노드 스타일
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'font-size': '10px',
            'font-weight': 500,
            color: '#64748b',
            'text-margin-y': 6,
            'background-color': DEFAULT_COLOR,
            width: 40,
            height: 40,
            'border-width': 2,
            'border-color': DEFAULT_COLOR,
            shape: 'ellipse',
          } as Record<string, unknown>,
        },
        // 중심 노드 강조
        {
          selector: 'node[isCenter]',
          style: {
            width: 55,
            height: 55,
            'border-width': 3,
            'font-size': '11px',
            'font-weight': 700,
            color: '#1e293b',
          } as Record<string, unknown>,
        },
        // ObjectType별 색상
        ...typeStyles,
        // 엣지 스타일
        {
          selector: 'edge',
          style: {
            label: 'data(label)',
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#94a3b8',
            'line-color': '#cbd5e1',
            width: 1.5,
            'font-size': '9px',
            color: '#94a3b8',
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.9,
            'text-background-padding': '2px',
            'text-rotation': 'autorotate',
          } as Record<string, unknown>,
        },
      ],
      layout: {
        name: 'cose',
        animate: true,
        animationDuration: 500,
        randomize: false,
        componentSpacing: 60,
        nodeOverlap: 20,
        idealEdgeLength: () => 100,
        edgeElasticity: () => 80,
        nestingFactor: 1.2,
        gravity: 60,
        numIter: 200,
      },
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      minZoom: 0.3,
      maxZoom: 3,
    });

    // 노드 클릭 이벤트
    cy.on('tap', 'node', (evt) => {
      const nodeId = evt.target.id();
      // 중심 노드가 아닌 경우에만 콜백
      if (nodeId !== instance.id) {
        onNodeClick?.(nodeId);
      }
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [instance, collapsed, getColor]); // onNodeClick 의도적 제외

  // 줌 컨트롤
  const zoomIn = useCallback(() => cyRef.current?.zoom(cyRef.current.zoom() * 1.3), []);
  const zoomOut = useCallback(() => cyRef.current?.zoom(cyRef.current.zoom() / 1.3), []);
  const fitAll = useCallback(() => cyRef.current?.fit(undefined, 30), []);

  // 접힌 상태
  if (collapsed) {
    return (
      <div className="flex items-center justify-center h-10 border-t border-border bg-card">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onToggleCollapse}
          title="그래프 패널 열기"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    );
  }

  // 인스턴스 미선택
  if (!instance) {
    return (
      <div
        className={cn(
          'flex items-center justify-center border-t border-border bg-card text-muted-foreground text-xs',
          className,
        )}
        style={{ minHeight: 200 }}
      >
        인스턴스를 선택하면 관계 그래프가 표시됩니다
      </div>
    );
  }

  // 관련 인스턴스가 없는 경우
  if (instance.relatedInstances.length === 0) {
    return (
      <div
        className={cn(
          'flex items-center justify-center border-t border-border bg-card text-muted-foreground text-xs',
          className,
        )}
        style={{ minHeight: 200 }}
      >
        관련 인스턴스가 없습니다
      </div>
    );
  }

  // 범례 데이터 생성
  const legendTypes = new Map<string, string>();
  legendTypes.set(
    instance.objectTypeName,
    COLOR_PALETTE[0] || DEFAULT_COLOR,
  );
  instance.relatedInstances.forEach((rel) => {
    if (!legendTypes.has(rel.objectTypeName)) {
      legendTypes.set(
        rel.objectTypeName,
        COLOR_PALETTE[legendTypes.size % COLOR_PALETTE.length],
      );
    }
  });

  return (
    <div className={cn('flex flex-col border-t border-border bg-card', className)}>
      {/* 툴바 */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border">
        <span className="text-[11px] font-semibold text-foreground">
          관계 그래프
        </span>
        <div className="flex items-center gap-0.5">
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={zoomIn} title="확대">
            <ZoomIn className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={zoomOut} title="축소">
            <ZoomOut className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={fitAll} title="전체 보기">
            <RotateCcw className="h-3 w-3" />
          </Button>
          {onToggleCollapse && (
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onToggleCollapse} title="접기">
              <Minimize2 className="h-3 w-3" />
            </Button>
          )}
        </div>
      </div>

      {/* Cytoscape 컨테이너 */}
      <div ref={containerRef} className="flex-1" style={{ minHeight: 250 }} />

      {/* 범례 */}
      <div className="flex items-center gap-3 px-3 py-1.5 border-t border-border text-[10px] text-muted-foreground">
        {Array.from(legendTypes.entries()).map(([typeName, color]) => (
          <span key={typeName} className="flex items-center gap-1">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: color }}
            />
            {typeName}
          </span>
        ))}
      </div>
    </div>
  );
};
