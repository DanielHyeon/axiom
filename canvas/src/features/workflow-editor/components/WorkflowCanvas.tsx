/**
 * WorkflowCanvas — Cytoscape.js 기반 워크플로 시각화 캔버스
 *
 * 노드를 타입별로 색상·모양을 구분하고, 엣지를 라벨과 함께 렌더링한다.
 * 클릭으로 노드를 선택하면 속성 패널에 상세 정보가 표시된다.
 * DomainGraphViewer 패턴을 참고하여 구현.
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import cytoscape, { type Core } from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useWorkflowEditorStore } from '../store/useWorkflowEditorStore';
import type { WorkflowNodeType } from '../types/workflowEditor.types';

// dagre 레이아웃 확장 등록 (한 번만)
try {
  cytoscape.use(dagre);
} catch {
  // 이미 등록된 경우 무시
}

// ──────────────────────────────────────
// 노드 타입별 색상 매핑
// ──────────────────────────────────────

const NODE_COLORS: Record<WorkflowNodeType, { bg: string; border: string }> = {
  trigger:   { bg: '#f59e0b', border: '#d97706' },  // 앰버 (시작점)
  condition: { bg: '#0ea5e9', border: '#0284c7' },  // 스카이 (조건)
  action:    { bg: '#10b981', border: '#059669' },  // 에메랄드 (실행)
  policy:    { bg: '#8b5cf6', border: '#7c3aed' },  // 바이올렛 (정책)
  gateway:   { bg: '#f43f5e', border: '#e11d48' },  // 로즈 (게이트웨이)
};

const NODE_SHAPES: Record<WorkflowNodeType, string> = {
  trigger: 'diamond',
  condition: 'roundrectangle',
  action: 'roundrectangle',
  policy: 'hexagon',
  gateway: 'diamond',
};

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export function WorkflowCanvas() {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  const nodes = useWorkflowEditorStore((s) => s.nodes);
  const edges = useWorkflowEditorStore((s) => s.edges);
  const selectedNodeId = useWorkflowEditorStore((s) => s.selectedNodeId);
  const setSelectedNode = useWorkflowEditorStore((s) => s.setSelectedNode);

  // setSelectedNode 를 ref 에 저장하여 초기화 effect 의 deps 문제 방지
  const setSelectedNodeRef = useRef(setSelectedNode);
  setSelectedNodeRef.current = setSelectedNode;

  // Cytoscape 를 한 번만 초기화하는 effect (cy 인스턴스를 ref 에 보관)
  const [cyReady, setCyReady] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [], // 요소는 아래 동기화 effect 에서 추가
      style: [
        // 기본 노드 스타일
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 6,
            'font-size': '11px',
            'font-weight': 600,
            color: '#e2e8f0',
            'text-outline-width': 2,
            'text-outline-color': '#0f172a',
            'background-color': '#6b7280',
            width: 50,
            height: 50,
            'border-width': 2,
            'border-color': '#4b5563',
            shape: 'roundrectangle',
          },
        },
        // 타입별 스타일 — 각 타입에 대해 동적 생성
        ...Object.entries(NODE_COLORS).map(([type, colors]) => ({
          selector: `node[nodeType="${type}"]`,
          style: {
            'background-color': colors.bg,
            'border-color': colors.border,
            shape: NODE_SHAPES[type as WorkflowNodeType],
          } as cytoscape.Css.Node,
        })),
        // 선택 노드 강조
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#fbbf24',
            'overlay-opacity': 0.08,
            'overlay-color': '#fbbf24',
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
            width: 2,
            'font-size': '9px',
            color: '#94a3b8',
            'text-background-color': '#0f172a',
            'text-background-opacity': 0.8,
            'text-background-padding': '2px',
            'text-rotation': 'autorotate',
          },
        },
      ],
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      minZoom: 0.2,
      maxZoom: 4,
    });

    // 노드 클릭 → 선택 (ref 를 통해 항상 최신 콜백 사용)
    cy.on('tap', 'node', (evt) => {
      setSelectedNodeRef.current(evt.target.id());
    });

    // 캔버스 빈 곳 클릭 → 선택 해제
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelectedNodeRef.current(null);
      }
    });

    cyRef.current = cy;
    setCyReady(true);

    return () => {
      cy.destroy();
      cyRef.current = null;
      setCyReady(false);
    };
    // 초기화는 한 번만 수행 — 컨테이너가 마운트될 때
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // nodes/edges 변경 시 diff 기반으로 요소를 추가/제거/갱신
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !cyReady) return;

    // ── 노드 동기화 ──
    const currentNodeIds = new Set(cy.nodes().map((n) => n.id()));
    const nextNodeIds = new Set(nodes.map((n) => n.id));

    // 삭제된 노드 제거
    for (const id of currentNodeIds) {
      if (!nextNodeIds.has(id)) {
        cy.getElementById(id).remove();
      }
    }

    // 추가/갱신
    for (const n of nodes) {
      const existing = cy.getElementById(n.id);
      if (existing.length === 0) {
        // 새 노드 추가
        cy.add({
          data: { id: n.id, label: n.label, nodeType: n.type },
          position: { x: n.position.x, y: n.position.y },
        });
      } else {
        // 기존 노드 데이터 갱신
        existing.data('label', n.label);
        existing.data('nodeType', n.type);
      }
    }

    // ── 엣지 동기화 ──
    const currentEdgeIds = new Set(cy.edges().map((e) => e.id()));
    const nextEdgeIds = new Set(edges.map((e) => e.id));

    // 삭제된 엣지 제거
    for (const id of currentEdgeIds) {
      if (!nextEdgeIds.has(id)) {
        cy.getElementById(id).remove();
      }
    }

    // 추가/갱신
    for (const e of edges) {
      const existing = cy.getElementById(e.id);
      if (existing.length === 0) {
        cy.add({
          data: {
            id: e.id,
            source: e.source,
            target: e.target,
            label: e.label ?? '',
          },
        });
      } else {
        existing.data('label', e.label ?? '');
      }
    }

    // 새 요소가 추가된 경우에만 레이아웃 재실행
    if (nodes.length > 0) {
      cy.layout({
        name: 'dagre',
        rankDir: 'LR',
        nodeSep: 60,
        rankSep: 100,
        animate: true,
        animationDuration: 400,
      } as cytoscape.LayoutOptions).run();
    }
  }, [nodes, edges, cyReady]);

  // 선택 노드 하이라이트 동기화
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
  const zoomIn = useCallback(() => {
    const cy = cyRef.current;
    if (cy) cy.zoom({ level: cy.zoom() * 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);

  const zoomOut = useCallback(() => {
    const cy = cyRef.current;
    if (cy) cy.zoom({ level: cy.zoom() / 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);

  const fitAll = useCallback(() => {
    cyRef.current?.fit(undefined, 40);
  }, []);

  return (
    <div className="relative flex-1 h-full bg-background">
      {/* Cytoscape 컨테이너 */}
      <div
        ref={containerRef}
        className="w-full h-full"
        role="img"
        aria-label="워크플로 캔버스"
      />

      {/* 줌 컨트롤 오버레이 */}
      <div className="absolute bottom-3 right-3 flex flex-col gap-1 bg-card/80 backdrop-blur-sm border border-border rounded-lg p-1">
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={zoomIn} title="확대">
          <ZoomIn className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={zoomOut} title="축소">
          <ZoomOut className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={fitAll} title="전체 보기">
          <RotateCcw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* 범례 */}
      <div className="absolute bottom-3 left-3 flex items-center gap-3 bg-card/80 backdrop-blur-sm border border-border rounded-lg px-3 py-1.5 text-[10px] text-muted-foreground">
        {Object.entries(NODE_COLORS).map(([type, colors]) => (
          <span key={type} className="flex items-center gap-1">
            <span
              className="w-2.5 h-2.5 rounded-sm"
              style={{ backgroundColor: colors.bg }}
            />
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </span>
        ))}
      </div>

      {/* 빈 상태 안내 */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center text-muted-foreground">
            <p className="text-sm font-medium">{t('workflowEditor.canvas.empty')}</p>
            <p className="text-xs mt-1">
              {t('workflowEditor.canvas.emptyHint')}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
