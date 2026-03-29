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

import { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import NVL from '@neo4j-nvl/base';
import type { Node as NvlNode, Relationship as NvlRelationship } from '@neo4j-nvl/base';
import {
  ClickInteraction,
  DragNodeInteraction,
  PanInteraction,
  ZoomInteraction,
} from '@neo4j-nvl/interaction-handlers';
import { X, Table2, Key, ArrowRight, Maximize, Maximize2, Minimize2 } from 'lucide-react';
import type { Layout } from '@neo4j-nvl/base';
import type { ERDTableInfo } from '@/shared/types/schema';

// ─── 레이아웃 스위처 설정 ─────────────────────────────────────
// NVL이 지원하는 5가지 레이아웃 모드 (free 제외 — 수동 배치 전용)
// NVL이 지원하는 6가지 레이아웃 모드 전체
const LAYOUT_OPTIONS: { key: Layout; label: string }[] = [
  { key: 'forceDirected', label: 'Force' },
  { key: 'hierarchical', label: 'Hierarchy' },
  { key: 'circular', label: 'Circular' },
  { key: 'grid', label: 'Grid' },
  { key: 'd3Force', label: 'D3' },
  { key: 'free', label: 'Free' },
];

// ─── 테이블 노드 컬러 팔레트 ─────────────────────────────────
// 주의: schemaColorMap은 아래 getTableColor 내부에서 useMemo를 통해 관리
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

/**
 * 테이블 목록에서 스키마별 색상 매핑을 생성하는 순수 함수.
 * useMemo에서 호출하여 컴포넌트 스코프에서 관리한다.
 */
function buildSchemaColorMap(tables: ERDTableInfo[]): Map<string, string> {
  const map = new Map<string, string>();
  let idx = 0;
  for (const table of tables) {
    const key = (table.schema || 'default').toLowerCase();
    if (!map.has(key)) {
      map.set(key, TABLE_COLORS[idx % TABLE_COLORS.length]);
      idx++;
    }
  }
  return map;
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
  /** 현재 그래프 레이아웃 모드 */
  const [currentLayout, setCurrentLayout] = useState<Layout>('forceDirected');
  /** 전체화면 모드 */
  const [isFullscreen, setIsFullscreen] = useState(false);

  // 스키마별 색상 매핑 (컴포넌트 스코프 — 모듈 싱글톤 방지)
  const schemaColorMap = useMemo(() => buildSchemaColorMap(tables), [tables]);

  // 엣지 데이터 계산 (테이블 변경 시 — useMemo로 중복 호출 방지)
  const edgesData = useMemo(() => extractEdges(tables), [tables]);

  // 선택된 테이블 정보 조회
  const selectedTable = selectedNodeId
    ? tables.find((t) => t.name === selectedNodeId) ?? null
    : null;

  // onNodeSelect 콜백을 ref로 안정화 — useEffect 의존성에서 제외하여
  // 콜백 변경만으로 NVL 인스턴스가 재생성되는 것을 방지
  const onNodeSelectRef = useRef(onNodeSelect);
  useEffect(() => {
    onNodeSelectRef.current = onNodeSelect;
  }, [onNodeSelect]);

  // ─── NVL: tables가 변경될 때마다 인스턴스를 재생성 ────────────
  // React 19 StrictMode 대응: 이전 인스턴스의 잔여 DOM 자식을 정리 후 재생성
  // ResizeObserver도 NVL 인스턴스와 같은 수명주기로 관리

  useEffect(() => {
    const container = containerRef.current;
    if (!container || tables.length === 0) return;

    // ── StrictMode 대응: 이전 NVL 인스턴스가 남긴 DOM 잔여물 제거 ──
    // React 19 StrictMode는 개발 모드에서 effect를 두 번 실행한다.
    // 첫 번째 destroy()가 컨테이너 내부 canvas를 제거하지만,
    // NVL이 설정한 인라인 style/속성이 남아 두 번째 초기화에 영향을 줄 수 있다.
    // 따라서 컨테이너 자식을 모두 제거하고 NVL이 추가한 속성을 초기화한다.
    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }
    container.removeAttribute('instanceId');
    container.removeAttribute('data-testid');
    container.removeAttribute('role');
    container.removeAttribute('aria-label');
    container.removeAttribute('aria-describedby');
    // NVL이 추가하는 인라인 style 초기화 (height, outline 등)
    container.style.removeProperty('height');
    container.style.removeProperty('outline');

    // ── 컨테이너 크기 확인 — 0이면 초기화 불가 ──
    // requestAnimationFrame으로 레이아웃 완료 후 측정하여 정확성 보장
    const rect = container.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) {
      console.warn('[NVLSchemaGraph] 컨테이너 크기 0 — NVL 초기화 건너뜀', rect);
      return;
    }

    // ── 취소 플래그 — StrictMode cleanup에서 비동기 콜백 무효화 ──
    let cancelled = false;

    // NVL 노드/엣지 생성 — edgesData/schemaColorMap은 useMemo로 안정화됨
    const nodes: NvlNode[] = tables.map((table) => ({
      id: table.name,
      caption: table.name,
      color: schemaColorMap.get((table.schema || 'default').toLowerCase()) || TABLE_COLORS[0],
      size: 25,
    }));
    const relationships: NvlRelationship[] = edgesData.map((edge) => ({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      caption: edge.caption,
      color: '#9CA3AB',
      width: 1,
      captionSize: 2,   // 관계 캡션 높이 (작을수록 글자 작음)
    }));

    // NVL 초기화 — 생성자 시그니처: new NVL(frame, nodes, rels, options, callbacks)
    // 참고: layoutDone은 cleanup 함수에서 false로 초기화됨 (effect 내 직접 setState 금지)

    // NVL 옵션 — KAIR 프로젝트와 동일한 설정
    // layoutOptions의 커스텀 속성(iterations, nodeRepulsion 등)은
    // NvlOptions 타입에 정의되지 않지만, 내부 CoseBilkent 레이아웃 엔진이
    // 실제로 소비한다. KAIR에서 검증된 값을 그대로 사용한다.
    // NVL 옵션 — KAIR 프로젝트와 100% 동일한 설정 (any 캐스트로 타입 문제 우회)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const nvlOptions: any = {
      disableTelemetry: true,
      disableWebWorkers: true,
      initialZoom: 1.0,
      renderer: 'canvas',
      relationshipLabelFontSize: 5,
      relationshipWidth: 1,
      nodeCaptionFontSize: 10,
      nodeCaptionColor: '#333333',
      panOnClick: false,
      zoomOnClick: false,
      layout: 'forceDirected',
      layoutOptions: {
        iterations: 150,
        animationDuration: 0,
        disableAnimation: true,
        updateLayoutOnChange: false,
        separateComponents: true,
        componentSpacing: 200,
        componentArrangement: 'grid',
        nodeRepulsion: 800,
        linkDistance: 80,
        gravity: 0.05,
        physics: { enabled: false },
        updateOnDrag: false,
        updateOnClick: false,
      },
    };

    // callbacks는 반드시 5번째 인자로 전달해야 동작함
    const nvlCallbacks = {
      onLayoutDone: () => {
        // StrictMode cleanup 이후 호출되면 무시
        if (cancelled) return;
        setLayoutDone(true);
        try {
          const allIds = nvl.getNodes().map((n: NvlNode) => n.id);
          if (allIds.length > 0) {
            nvl.fit(allIds, { animated: false });
          }
          setZoomLevel(Math.round(nvl.getScale() * 100));
        } catch {
          // destroy된 인스턴스에서 호출될 경우 무시
        }
      },
      onError: (err: Error) => console.error('[NVLSchemaGraph] NVL 오류:', err.message, err),
    };

    const nvl = new NVL(container, nodes, relationships, nvlOptions, nvlCallbacks);
    nvlRef.current = nvl;

    // 레이아웃 완료 후 fit 보장 (onLayoutDone 미호출 대비)
    setTimeout(() => {
      if (cancelled) return;
      const ids = nvl.getNodes().map(n => n.id);
      if (ids.length > 0) {
        try { nvl.fit(ids, { animated: false }); } catch { /* */ }
      }
    }, 500);

    // ── 인터랙션 핸들러 ──
    const click = new ClickInteraction(nvl, { selectOnClick: true });
    click.updateCallback('onNodeClick', (node) => {
      setSelectedNodeId((prev) => {
        const v = prev === node.id ? null : node.id;
        onNodeSelectRef.current?.(v);
        return v;
      });
    });
    click.updateCallback('onCanvasClick', () => {
      setSelectedNodeId(null);
      onNodeSelectRef.current?.(null);
      nvl.deselectAll();
    });
    click.updateCallback('onNodeDoubleClick', (node) => {
      const allN = nvl.getNodes();
      const allR = nvl.getRelationships();
      const connNodes = new Set<string>([node.id]);
      const connRels = new Set<string>();
      for (const r of allR) {
        if (r.from === node.id || r.to === node.id) {
          connRels.add(r.id);
          connNodes.add(r.from);
          connNodes.add(r.to);
        }
      }
      nvl.updateElementsInGraph(
        allN.map((n) => ({ ...n, disabled: !connNodes.has(n.id), activated: connNodes.has(n.id) })),
        allR.map((r) => ({ ...r, disabled: !connRels.has(r.id) })),
      );
    });
    click.updateCallback('onCanvasDoubleClick', () => {
      const allN = nvl.getNodes();
      const allR = nvl.getRelationships();
      nvl.updateElementsInGraph(
        allN.map((n) => ({ ...n, disabled: false, activated: false })),
        allR.map((r) => ({ ...r, disabled: false })),
      );
    });
    const drag = new DragNodeInteraction(nvl);
    const pan = new PanInteraction(nvl);
    const zoom = new ZoomInteraction(nvl);
    zoom.updateCallback('onZoom', (v) => setZoomLevel(Math.round(v * 100)));
    interactionsRef.current = [click, drag, pan, zoom];

    // ── 폴백 타이머 (onLayoutDone 미호출 대비) ──
    const fallback = setTimeout(() => {
      if (cancelled) return;
      setLayoutDone(true);
      try {
        const ids = nvl.getNodes().map((n) => n.id);
        if (ids.length > 0) nvl.fit(ids, { animated: false });
        setZoomLevel(Math.round(nvl.getScale() * 100));
      } catch { /* destroy 후 호출 방지 */ }
    }, 3000);

    // ── ResizeObserver — NVL 인스턴스와 동일 수명주기로 관리 ──
    // 별도 useEffect를 사용하면 StrictMode에서 stale 참조 문제 발생 가능
    const ro = new ResizeObserver(() => {
      if (cancelled) return;
      try {
        nvl.restart(undefined, true);
      } catch {
        // destroy된 인스턴스에서 호출될 경우 무시
      }
    });
    ro.observe(container);

    // ── 정리 함수 ──
    return () => {
      cancelled = true;
      clearTimeout(fallback);
      ro.disconnect();
      for (const i of interactionsRef.current) i.destroy();
      interactionsRef.current = [];
      nvl.destroy();
      nvlRef.current = null;
      setLayoutDone(false);
      setSelectedNodeId(null);
    };
    // onNodeSelect는 ref로 안정화, schemaColorMap/edgesData는 tables에서 파생 (useMemo)
  }, [tables, schemaColorMap, edgesData]);

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
    onNodeSelectRef.current?.(null);
  }, []);

  // ─── 레이아웃 변경 핸들러 ──────────────────────────────────

  const handleLayoutChange = useCallback((layout: Layout) => {
    const nvl = nvlRef.current;
    if (!nvl) return;
    setCurrentLayout(layout);
    // NVL 레이아웃 모드 전환 — 레이아웃 엔진이 노드 재배치 후 onLayoutDone 콜백 호출
    nvl.setLayout(layout);
    // 레이아웃 완료 대기 후 전체 노드가 보이도록 fit 실행
    setTimeout(() => {
      try {
        const ids = nvl.getNodes().map((n) => n.id);
        if (ids.length > 0) nvl.fit(ids, { animated: true });
        setZoomLevel(Math.round(nvl.getScale() * 100));
      } catch { /* destroy된 인스턴스 안전 처리 */ }
    }, 600);
  }, []);

  // ─── 전체 보기 (Fit All) 핸들러 ─────────────────────────────

  const handleFitAll = useCallback(() => {
    const nvl = nvlRef.current;
    if (!nvl) return;
    const allNodeIds = nvl.getNodes().map((n) => n.id);
    if (allNodeIds.length > 0) {
      nvl.fit(allNodeIds, { animated: true });
    }
    setZoomLevel(Math.round(nvl.getScale() * 100));
  }, []);

  // ─── 전체화면 토글 + ESC 키 ──────────────────────────────────
  const handleToggleFullscreen = useCallback(() => {
    setIsFullscreen((prev) => !prev);
    // 전체화면 전환 후 NVL 리사이즈 트리거
    setTimeout(() => {
      try { nvlRef.current?.restart(undefined, true); } catch { /* */ }
      setTimeout(() => {
        const ids = nvlRef.current?.getNodes().map(n => n.id) ?? [];
        if (ids.length > 0) try { nvlRef.current?.fit(ids, { animated: false }); } catch { /* */ }
      }, 300);
    }, 100);
  }, []);

  // ESC 키로 전체화면 종료 + NVL 리사이즈 트리거
  useEffect(() => {
    if (!isFullscreen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsFullscreen(false);
        // ESC로 종료 시에도 NVL 리사이즈 보장
        setTimeout(() => {
          try { nvlRef.current?.restart(undefined, true); } catch { /* */ }
          setTimeout(() => {
            const ids = nvlRef.current?.getNodes().map(n => n.id) ?? [];
            if (ids.length > 0) try { nvlRef.current?.fit(ids, { animated: false }); } catch { /* */ }
          }, 300);
        }, 100);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isFullscreen]);

  // ─── 빈 상태 처리 ──────────────────────────────────────────

  if (tables.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-foreground/60 text-sm h-full">
        {t('datasourcePage.whenDatasourceSelected', '데이터소스를 선택하면 그래프가 표시됩니다.')}
      </div>
    );
  }

  // ─── 렌더링 ────────────────────────────────────────────────

  const graphContent = (
    <div className={`flex flex-col ${isFullscreen ? 'fixed inset-0 z-[9999] w-screen h-screen bg-background' : 'h-full'}`}>
      {/* ─── 상단 툴바 (ERD 툴바와 동일한 구조) ─── */}
      <div className="flex items-center gap-3 p-3 border-b border-border bg-muted/50 shrink-0">
        {/* 통계 */}
        <div className="flex items-center gap-3 text-[10px] text-foreground/50 font-mono">
          <span>{t('datasource.graph.nodeCount', '노드')}: {tables.length}</span>
          <span>{t('datasource.graph.edgeCount', '관계')}: {edgesData.length}</span>
        </div>

        {/* 레이아웃 스위처 */}
        <div className="flex items-center gap-0.5 bg-card border border-border rounded-full px-1 py-0.5">
          {LAYOUT_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              type="button"
              onClick={() => handleLayoutChange(opt.key)}
              className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
                currentLayout === opt.key
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-transparent text-foreground/60 hover:text-foreground hover:bg-muted'
              }`}
              aria-pressed={currentLayout === opt.key}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* 우측 액션 버튼 */}
        <div className="ml-auto flex items-center gap-1">
          <button type="button" onClick={handleZoomIn} className="p-1.5 rounded text-foreground/60 hover:text-foreground hover:bg-muted transition-colors" title="확대">+</button>
          <span className="px-1 text-[10px] text-foreground/60 font-mono min-w-[32px] text-center">{zoomLevel}%</span>
          <button type="button" onClick={handleZoomOut} className="p-1.5 rounded text-foreground/60 hover:text-foreground hover:bg-muted transition-colors" title="축소">-</button>
          <button type="button" onClick={handleResetView} className="p-1.5 rounded text-foreground/60 hover:text-foreground hover:bg-muted transition-colors" title="초기화">Reset</button>
          <button type="button" onClick={handleFitAll} className="p-1.5 rounded text-foreground/60 hover:text-foreground hover:bg-muted transition-colors" title="전체 보기">
            <Maximize className="h-3.5 w-3.5" />
          </button>
          {/* 전체화면 토글 — ERDToolbar와 동일 위치 */}
          <button type="button" onClick={handleToggleFullscreen} className="p-1.5 rounded text-foreground/60 hover:text-foreground hover:bg-muted transition-colors" title={isFullscreen ? '전체화면 종료' : '전체화면'}>
            {isFullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* ─── NVL 렌더링 영역 ─── */}
      <div className="relative flex-1 min-h-0 overflow-hidden bg-card">
        <div
          ref={containerRef}
          className="relative w-full h-full"
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

  // CSS-only 전체화면: Portal 없이 같은 DOM에 fixed 스타일만 적용
  // NVL 캔버스가 containerRef에 바인딩되어 있으므로 DOM 이동하면 캔버스가 끊어짐
  return graphContent;
}
