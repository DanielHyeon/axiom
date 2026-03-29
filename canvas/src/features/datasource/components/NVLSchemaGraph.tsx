/**
 * NVL(Neo4j Visualization Library) 기반 인터랙티브 스키마 그래프 뷰어.
 *
 * ERDTableInfo[] 데이터를 받아 테이블을 노드로, FK 관계를 엣지로 표현하는
 * 인터랙티브 그래프를 렌더링한다.
 *
 * 주요 기능:
 * - 테이블별 컬러 노드 (스키마 기준 색상 할당)
 * - FK 관계 엣지 (컬럼명 캡션)
 * - 드래그, 팬, 줌 인터랙션
 * - 노드 클릭 시 선택 및 상세 패널 표시
 * - 더블클릭 시 연결된 노드 강조
 */

import { useRef, useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import NVL from '@neo4j-nvl/base';
import type { Node as NvlNode, Relationship as NvlRelationship, ExternalCallbacks } from '@neo4j-nvl/base';
import {
  ClickInteraction,
  DragNodeInteraction,
  PanInteraction,
  ZoomInteraction,
} from '@neo4j-nvl/interaction-handlers';
import { X, Table2, Key, ArrowRight } from 'lucide-react';
import type { ERDTableInfo } from '@/shared/types/schema';

// ─── 테이블 노드 컬러 팔레트 ─────────────────────────────────
const TABLE_COLORS = [
  '#E35A5C', // Rose red
  '#3B82F6', // Blue
  '#22C55E', // Green
  '#F59E0B', // Amber
  '#8B5CF6', // Purple
  '#EC4899', // Pink
  '#06B6D4', // Cyan
  '#F97316', // Orange
  '#14B8A6', // Teal
  '#6366F1', // Indigo
];

/** 스키마 이름별 색상 매핑 캐시 */
const schemaColorMap = new Map<string, string>();
let nextColorIndex = 0;

/**
 * 테이블의 스키마를 기준으로 일관된 색상을 반환한다.
 * 동일 스키마의 테이블은 같은 색상을 사용한다.
 */
function getTableColor(table: ERDTableInfo): string {
  const schemaKey = (table.schema || 'default').toLowerCase();
  if (!schemaColorMap.has(schemaKey)) {
    schemaColorMap.set(schemaKey, TABLE_COLORS[nextColorIndex % TABLE_COLORS.length]);
    nextColorIndex++;
  }
  return schemaColorMap.get(schemaKey)!;
}

// ─── FK 관계 추출 유틸 ───────────────────────────────────────

interface GraphEdgeInfo {
  id: string;
  from: string;
  to: string;
  caption: string;
}

/**
 * 테이블 데이터에서 FK 관계를 추출하여 엣지 정보로 변환한다.
 * ERDTableInfo의 isForeignKey / referencedTable 플래그를 활용하며,
 * 대상 테이블이 존재하는 경우에만 엣지를 생성한다.
 */
function extractEdges(tables: ERDTableInfo[]): GraphEdgeInfo[] {
  // 전체 테이블명 집합 (엣지 검증용)
  const tableNameSet = new Set(tables.map((t) => t.name));
  const edges: GraphEdgeInfo[] = [];
  const seen = new Set<string>();

  for (const table of tables) {
    for (const col of table.columns) {
      if (col.isForeignKey && col.referencedTable && tableNameSet.has(col.referencedTable)) {
        const edgeId = `${table.name}.${col.name}->${col.referencedTable}`;
        if (seen.has(edgeId)) continue;
        seen.add(edgeId);

        edges.push({
          id: edgeId,
          from: table.name,
          to: col.referencedTable,
          caption: col.name,
        });
      }
    }
  }

  return edges;
}

// ─── Props 타입 ──────────────────────────────────────────────

interface NVLSchemaGraphProps {
  /** 렌더링할 테이블 목록 */
  tables: ERDTableInfo[];
  /** 노드 선택 시 호출되는 콜백 (null이면 선택 해제) */
  onNodeSelect?: (tableName: string | null) => void;
}

// ─── 선택 노드 상세 패널 ─────────────────────────────────────

interface NodeDetailPanelProps {
  table: ERDTableInfo;
  edges: GraphEdgeInfo[];
  onClose: () => void;
}

/**
 * 선택된 노드의 상세 정보를 보여주는 플로팅 패널.
 * 테이블명, 스키마, 컬럼 목록, FK 관계를 표시한다.
 */
function NodeDetailPanel({ table, edges, onClose }: NodeDetailPanelProps) {
  const { t } = useTranslation();
  // 이 테이블에서 나가는 FK 관계
  const outgoingEdges = edges.filter((e) => e.from === table.name);
  // 이 테이블로 들어오는 FK 관계
  const incomingEdges = edges.filter((e) => e.to === table.name);

  return (
    <div className="absolute top-4 right-4 z-20 w-72 max-h-[calc(100%-2rem)] overflow-y-auto bg-card border border-border rounded-lg shadow-lg">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-muted/50">
        <div className="flex items-center gap-2 min-w-0">
          <Table2 className="h-3.5 w-3.5 shrink-0 text-foreground/60" />
          <span className="text-[13px] font-semibold text-foreground truncate font-heading">
            {table.name}
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-0.5 text-foreground/40 hover:text-foreground transition-colors"
          aria-label={t('common.close', '닫기')}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* 메타 정보 */}
      <div className="px-3 py-2 space-y-1 border-b border-border">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-foreground/50 font-mono uppercase">Schema</span>
          <span className="text-foreground/80 font-mono">{table.schema || '—'}</span>
        </div>
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-foreground/50 font-mono uppercase">Columns</span>
          <span className="text-foreground/80 font-mono">{table.columns.length}</span>
        </div>
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-foreground/50 font-mono uppercase">FK Out / In</span>
          <span className="text-foreground/80 font-mono">
            {outgoingEdges.length} / {incomingEdges.length}
          </span>
        </div>
      </div>

      {/* FK 관계 목록 */}
      {(outgoingEdges.length > 0 || incomingEdges.length > 0) && (
        <div className="px-3 py-2 space-y-1.5 border-b border-border">
          <span className="text-[10px] font-semibold text-foreground/50 font-mono uppercase tracking-wider">
            Relationships
          </span>
          {outgoingEdges.map((edge) => (
            <div key={edge.id} className="flex items-center gap-1 text-[11px] text-foreground/70 font-mono">
              <ArrowRight className="h-2.5 w-2.5 text-blue-500 shrink-0" />
              <span className="truncate">
                {edge.caption} <span className="text-foreground/40">-&gt;</span> {edge.to}
              </span>
            </div>
          ))}
          {incomingEdges.map((edge) => (
            <div key={edge.id} className="flex items-center gap-1 text-[11px] text-foreground/70 font-mono">
              <ArrowRight className="h-2.5 w-2.5 text-green-500 shrink-0 rotate-180" />
              <span className="truncate">
                {edge.from} <span className="text-foreground/40">-&gt;</span> {edge.caption}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 컬럼 목록 (최대 15개) */}
      <div className="px-3 py-2 space-y-1">
        <span className="text-[10px] font-semibold text-foreground/50 font-mono uppercase tracking-wider">
          Columns
        </span>
        {table.columns.slice(0, 15).map((col) => (
          <div key={col.name} className="flex items-center gap-1.5 text-[11px] font-mono">
            {col.isPrimaryKey && <Key className="h-2.5 w-2.5 text-amber-500 shrink-0" />}
            {col.isForeignKey && !col.isPrimaryKey && (
              <Key className="h-2.5 w-2.5 text-blue-400 shrink-0" />
            )}
            {!col.isPrimaryKey && !col.isForeignKey && (
              <span className="w-2.5 shrink-0" />
            )}
            <span className="text-foreground/80 truncate">{col.name}</span>
            <span className="text-foreground/40 ml-auto shrink-0">{col.dataType}</span>
          </div>
        ))}
        {table.columns.length > 15 && (
          <p className="text-[10px] text-foreground/40 text-center pt-1">
            +{table.columns.length - 15} more
          </p>
        )}
      </div>
    </div>
  );
}

// ─── NVL 스키마 그래프 컴포넌트 ──────────────────────────────

export function NVLSchemaGraph({ tables, onNodeSelect }: NVLSchemaGraphProps) {
  const { t } = useTranslation();
  /** NVL 인스턴스가 렌더링될 컨테이너 DOM 참조 */
  const containerRef = useRef<HTMLDivElement>(null);
  /** NVL 인스턴스 참조 — 정리 및 업데이트에 사용 */
  const nvlRef = useRef<NVL | null>(null);
  /** 인터랙션 핸들러 참조 — 정리용 */
  const interactionsRef = useRef<Array<{ destroy: () => void }>>([]);
  /** 현재 선택된 노드 ID */
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  /** 줌 레벨 (% 표시용) */
  const [zoomLevel, setZoomLevel] = useState(100);
  /** 레이아웃 완료 여부 */
  const [layoutDone, setLayoutDone] = useState(false);

  // 엣지 데이터 계산 (테이블 변경 시)
  const edgesData = extractEdges(tables);

  // 선택된 테이블 정보 조회
  const selectedTable = selectedNodeId
    ? tables.find((t) => t.name === selectedNodeId) ?? null
    : null;

  // ─── NVL 인스턴스 초기화 & 정리 ─────────────────────────────

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // 컨테이너 크기가 0이면 NVL 초기화 지연
    if (container.clientWidth === 0 || container.clientHeight === 0) return;

    // NVL 콜백 — 레이아웃 완료 시 뷰포트 맞춤
    const callbacks: ExternalCallbacks = {
      onLayoutDone: () => {
        setLayoutDone(true);
        const nvl = nvlRef.current;
        if (nvl) {
          // 모든 노드를 뷰포트에 맞춤
          const allNodeIds = nvl.getNodes().map((n) => n.id);
          if (allNodeIds.length > 0) {
            nvl.fit(allNodeIds, { animated: false });
          }
          setZoomLevel(Math.round(nvl.getScale() * 100));
        }
      },
      onError: (error) => {
        console.error('[NVLSchemaGraph] NVL 오류:', error);
      },
    };

    // NVL 인스턴스 생성
    const nvl = new NVL(container, [], [], {
      disableTelemetry: true,
      initialZoom: 1.0,
      renderer: 'canvas',
      layout: 'forceDirected',
      minZoom: 0.05,
      maxZoom: 5,
      allowDynamicMinZoom: true,
      callbacks,
    });

    nvlRef.current = nvl;

    // ─── 인터랙션 핸들러 등록 ───────────────────────────────

    // 클릭 인터랙션: 노드 선택 + 하이라이트
    const clickInteraction = new ClickInteraction(nvl, {
      selectOnClick: true,
    });

    // 노드 클릭 콜백 등록
    clickInteraction.updateCallback('onNodeClick', (node) => {
      const nodeId = node.id;
      setSelectedNodeId((prev) => {
        const newVal = prev === nodeId ? null : nodeId;
        onNodeSelect?.(newVal);
        return newVal;
      });
    });

    // 캔버스 빈 공간 클릭 → 선택 해제
    clickInteraction.updateCallback('onCanvasClick', () => {
      setSelectedNodeId(null);
      onNodeSelect?.(null);
      // 모든 노드 선택 해제
      nvl.deselectAll();
    });

    // 노드 더블클릭 → 연결된 노드 하이라이트
    clickInteraction.updateCallback('onNodeDoubleClick', (node) => {
      const allNodes = nvl.getNodes();
      const allRels = nvl.getRelationships();
      // 이 노드와 연결된 관계 찾기
      const connectedRelIds = new Set<string>();
      const connectedNodeIds = new Set<string>([node.id]);

      for (const rel of allRels) {
        if (rel.from === node.id || rel.to === node.id) {
          connectedRelIds.add(rel.id);
          connectedNodeIds.add(rel.from);
          connectedNodeIds.add(rel.to);
        }
      }

      // 연결된 노드/엣지만 활성화, 나머지는 비활성화
      const updatedNodes: NvlNode[] = allNodes.map((n) => ({
        ...n,
        disabled: !connectedNodeIds.has(n.id),
        activated: connectedNodeIds.has(n.id),
      }));
      const updatedRels: NvlRelationship[] = allRels.map((r) => ({
        ...r,
        disabled: !connectedRelIds.has(r.id),
      }));

      nvl.updateElementsInGraph(updatedNodes, updatedRels);
    });

    // 캔버스 더블클릭 → 하이라이트 해제 (전체 활성화)
    clickInteraction.updateCallback('onCanvasDoubleClick', () => {
      const allNodes = nvl.getNodes();
      const allRels = nvl.getRelationships();
      nvl.updateElementsInGraph(
        allNodes.map((n) => ({ ...n, disabled: false, activated: false })),
        allRels.map((r) => ({ ...r, disabled: false })),
      );
    });

    // 드래그, 팬, 줌 인터랙션
    const dragInteraction = new DragNodeInteraction(nvl);
    const panInteraction = new PanInteraction(nvl);
    const zoomInteraction = new ZoomInteraction(nvl);

    // 줌 변경 시 레벨 업데이트
    zoomInteraction.updateCallback('onZoom', (zoomValue) => {
      setZoomLevel(Math.round(zoomValue * 100));
    });

    interactionsRef.current = [clickInteraction, dragInteraction, panInteraction, zoomInteraction];

    // 정리 함수
    return () => {
      // 인터랙션 핸들러 정리
      for (const interaction of interactionsRef.current) {
        interaction.destroy();
      }
      interactionsRef.current = [];

      // NVL 인스턴스 정리
      nvl.destroy();
      nvlRef.current = null;
      setLayoutDone(false);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── 테이블 데이터 변경 시 그래프 업데이트 ──────────────────

  useEffect(() => {
    const nvl = nvlRef.current;
    if (!nvl) return;

    if (tables.length === 0) {
      // 테이블 없으면 그래프 비우기
      const existingNodes = nvl.getNodes();
      const existingRels = nvl.getRelationships();
      if (existingNodes.length > 0) {
        nvl.removeNodesWithIds(existingNodes.map((n) => n.id));
      }
      if (existingRels.length > 0) {
        nvl.removeRelationshipsWithIds(existingRels.map((r) => r.id));
      }
      return;
    }

    // 이펙트 내에서 엣지 계산 (의존성 안정화)
    const edges = extractEdges(tables);

    // NVL 노드 생성 — 각 테이블이 하나의 노드
    const nodes: NvlNode[] = tables.map((table) => ({
      id: table.name,
      caption: table.name,
      color: getTableColor(table),
      size: 35,
    }));

    // NVL 엣지 생성 — FK 관계
    const relationships: NvlRelationship[] = edges.map((edge) => ({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      caption: edge.caption,
      color: '#9CA3AB',
      width: 2,
      captionSize: 10,
    }));

    // 기존 요소 제거 후 새로 추가 (addAndUpdateElementsInGraph 사용)
    const existingNodes = nvl.getNodes();
    const existingRels = nvl.getRelationships();
    if (existingRels.length > 0) {
      nvl.removeRelationshipsWithIds(existingRels.map((r) => r.id));
    }
    if (existingNodes.length > 0) {
      nvl.removeNodesWithIds(existingNodes.map((n) => n.id));
    }

    // 새 요소 추가
    nvl.addAndUpdateElementsInGraph(nodes, relationships);

    // 선택 상태 초기화
    setSelectedNodeId(null);
    setLayoutDone(false);
  }, [tables]);

  // ─── 리사이즈 옵저버 ───────────────────────────────────────

  useEffect(() => {
    const container = containerRef.current;
    const nvl = nvlRef.current;
    if (!container || !nvl) return;

    const ro = new ResizeObserver(() => {
      // NVL은 내부적으로 컨테이너 크기를 감지하지만, 수동 트리거로 보정
      nvl.restart(undefined, true);
    });
    ro.observe(container);
    return () => ro.disconnect();
  }, []);

  // ─── 줌 컨트롤 핸들러 ──────────────────────────────────────

  const handleZoomIn = useCallback(() => {
    const nvl = nvlRef.current;
    if (!nvl) return;
    const current = nvl.getScale();
    nvl.setZoom(current * 1.3);
    setZoomLevel(Math.round(nvl.getScale() * 100));
  }, []);

  const handleZoomOut = useCallback(() => {
    const nvl = nvlRef.current;
    if (!nvl) return;
    const current = nvl.getScale();
    nvl.setZoom(current / 1.3);
    setZoomLevel(Math.round(nvl.getScale() * 100));
  }, []);

  const handleResetView = useCallback(() => {
    const nvl = nvlRef.current;
    if (!nvl) return;
    const allNodeIds = nvl.getNodes().map((n) => n.id);
    if (allNodeIds.length > 0) {
      nvl.fit(allNodeIds, { animated: false });
    }
    setZoomLevel(Math.round(nvl.getScale() * 100));
    // 비활성화 상태 해제
    const allNodes = nvl.getNodes();
    const allRels = nvl.getRelationships();
    nvl.updateElementsInGraph(
      allNodes.map((n) => ({ ...n, disabled: false, activated: false })),
      allRels.map((r) => ({ ...r, disabled: false })),
    );
    nvl.deselectAll();
    setSelectedNodeId(null);
    onNodeSelect?.(null);
  }, [onNodeSelect]);

  // ─── 빈 상태 처리 ──────────────────────────────────────────

  if (tables.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-foreground/60 text-sm h-full">
        {t('datasourcePage.whenDatasourceSelected', '데이터소스를 선택하면 그래프가 표시됩니다.')}
      </div>
    );
  }

  // ─── 렌더링 ────────────────────────────────────────────────

  return (
    <div className="relative w-full h-full overflow-hidden bg-card">
      {/* NVL 렌더링 컨테이너 */}
      <div
        ref={containerRef}
        className="w-full h-full"
        role="application"
        aria-label={`스키마 그래프. 테이블 ${tables.length}개, 관계 ${edgesData.length}개 표시.`}
      />

      {/* 레이아웃 진행 중 표시 */}
      {!layoutDone && tables.length > 0 && (
        <div className="absolute inset-0 flex items-center justify-center bg-card/60 z-10 pointer-events-none">
          <div className="flex items-center gap-2 text-sm text-foreground/60">
            <div className="h-4 w-4 border-2 border-foreground/30 border-t-foreground/60 rounded-full animate-spin" />
            {t('datasource.graph.layoutRunning', '레이아웃 계산 중...')}
          </div>
        </div>
      )}

      {/* 줌 컨트롤 — 좌하단 고정 */}
      <div className="absolute bottom-4 left-4 flex items-center gap-1 bg-card border border-border rounded shadow-sm z-10">
        <button
          type="button"
          onClick={handleZoomIn}
          className="px-2 py-1 text-xs text-foreground/60 hover:text-foreground transition-colors"
          title={t('datasourceExt.zoomIn', '확대')}
          aria-label={t('datasourceExt.zoomIn', '확대')}
        >
          +
        </button>
        <span className="px-2 py-1 text-[10px] text-foreground/60 font-mono min-w-[40px] text-center">
          {zoomLevel}%
        </span>
        <button
          type="button"
          onClick={handleZoomOut}
          className="px-2 py-1 text-xs text-foreground/60 hover:text-foreground transition-colors"
          title={t('datasourceExt.zoomOut', '축소')}
          aria-label={t('datasourceExt.zoomOut', '축소')}
        >
          -
        </button>
        <button
          type="button"
          onClick={handleResetView}
          className="px-2 py-1 text-[10px] text-foreground/60 hover:text-foreground transition-colors border-l border-border"
          title={t('datasourceExt.resetZoom', '초기화')}
          aria-label={t('datasourceExt.resetZoom', '초기화')}
        >
          Reset
        </button>
      </div>

      {/* 통계 뱃지 — 좌상단 */}
      <div className="absolute top-4 left-4 flex items-center gap-3 z-10">
        <span className="px-2 py-1 bg-card/90 border border-border rounded text-[10px] font-mono text-foreground/60 shadow-sm">
          {t('datasource.graph.nodeCount', '노드')}: {tables.length}
        </span>
        <span className="px-2 py-1 bg-card/90 border border-border rounded text-[10px] font-mono text-foreground/60 shadow-sm">
          {t('datasource.graph.edgeCount', '관계')}: {edgesData.length}
        </span>
      </div>

      {/* 선택된 노드 상세 패널 */}
      {selectedTable && (
        <NodeDetailPanel
          table={selectedTable}
          edges={edgesData}
          onClose={() => {
            setSelectedNodeId(null);
            onNodeSelect?.(null);
            nvlRef.current?.deselectAll();
          }}
        />
      )}
    </div>
  );
}
