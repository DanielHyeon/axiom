/**
 * Cytoscape.js 기반 인터랙티브 ERD 렌더러.
 *
 * 기존 Mermaid 정적 SVG를 대체하여 개별 테이블 노드를 자유롭게
 * 드래그할 수 있는 인터랙티브 ERD를 제공한다.
 *
 * 주요 기능:
 * - 개별 노드 드래그 (Cytoscape 기본 제공)
 * - 마우스 휠 줌 / 배경 드래그 팬
 * - 노드 클릭 시 연결된 엣지 하이라이트
 * - 줌 컨트롤 (확대/축소/리셋)
 * - PNG/SVG 내보내기 지원
 */

import { useRef, useEffect, useCallback, useState } from 'react';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import dagre from 'cytoscape-dagre';
import { useTranslation } from 'react-i18next';
import type { ERDTableInfo, ERDRelation } from '@/shared/types/schema';

// ─── Cytoscape 레이아웃 확장 등록 (전역 1회) ──────────────
let extensionsRegistered = false;
function ensureExtensions() {
  if (extensionsRegistered) return;
  cytoscape.use(coseBilkent);
  cytoscape.use(dagre);
  extensionsRegistered = true;
}

// ─── FK 추론 유틸 (mermaidCodeGen.ts 로직 재사용) ─────────

/** _id 접미사 기반 FK 추론 — 대상 테이블이 존재할 때만 FK로 판정 */
function inferForeignKey(
  colName: string,
  isPk: boolean,
  allTableNames: Set<string>,
): { isFk: boolean; referencedTable?: string } {
  if (isPk) return { isFk: false };
  const name = colName.toLowerCase();
  if (!name.endsWith('_id')) return { isFk: false };

  const baseName = name.slice(0, -3);
  const candidates = [
    baseName,
    baseName + 's',
    baseName + 'es',
    baseName.replace(/ie$/, 'y'),
    baseName + 'ations',
    baseName + 'izations',
  ];

  for (const candidate of candidates) {
    if (allTableNames.has(candidate)) {
      return { isFk: true, referencedTable: candidate };
    }
  }

  // 접두사 매칭: 유일 매치만 허용
  const prefixMatches = [...allTableNames].filter(
    (t) => t.startsWith(baseName) && t !== baseName,
  );
  if (prefixMatches.length === 1) {
    return { isFk: true, referencedTable: prefixMatches[0] };
  }

  return { isFk: false };
}

/** 테이블 데이터에서 FK 관계를 추출 */
function extractRelations(tables: ERDTableInfo[]): ERDRelation[] {
  const allTableNames = new Set(tables.map((t) => t.name.toLowerCase()));
  const relations: ERDRelation[] = [];
  const seen = new Set<string>();

  for (const table of tables) {
    for (const col of table.columns) {
      // 이미 FK 플래그가 있거나 추론으로 찾은 경우
      let isFk = col.isForeignKey;
      let refTable = col.referencedTable;

      if (!isFk) {
        const inferred = inferForeignKey(col.name, col.isPrimaryKey, allTableNames);
        isFk = inferred.isFk;
        refTable = inferred.referencedTable;
      }

      if (isFk && refTable) {
        const key = `${table.name}:${col.name}->${refTable}`;
        if (seen.has(key)) continue;
        seen.add(key);

        relations.push({
          fromTable: table.name,
          fromColumn: col.name,
          toTable: refTable,
          toColumn: 'id',
          type: 'many-to-one',
        });
      }
    }
  }

  return relations;
}

/**
 * ERD 관계 수 카운트 — 통계 표시용 헬퍼.
 * ERDiagramPanel에서 관계 수 통계에 사용.
 */
export function countERDRelations(tables: ERDTableInfo[]): number {
  return extractRelations(tables).length;
}

// ─── 노드 라벨 생성 ──────────────────────────────────────

/** 데이터 타입 약어 변환 — 라벨 너비 절약용 */
function shortType(rawType: string): string {
  const t = rawType.toLowerCase();
  if (t.includes('timestamp') || t.includes('datetime')) return 'timestamp';
  if (t.includes('varchar') || t.includes('character varying')) return 'varchar';
  if (t.includes('bigint')) return 'bigint';
  if (t.includes('integer') || t === 'int4' || t === 'int8') return 'int';
  if (t.includes('boolean') || t === 'bool') return 'bool';
  if (t.includes('numeric') || t.includes('decimal')) return 'numeric';
  if (t.includes('text')) return 'text';
  if (t.includes('json')) return 'json';
  if (t.includes('uuid')) return 'uuid';
  if (t.includes('bytea')) return 'bytea';
  if (t.includes('serial')) return 'serial';
  if (t.includes('float') || t.includes('double') || t.includes('real')) return 'float';
  if (t.includes('date')) return 'date';
  if (t.includes('time')) return 'time';
  return rawType.length > 12 ? rawType.slice(0, 10) + '..' : rawType;
}

/** 테이블의 멀티라인 라벨 생성 (테이블명 + 구분선 + 컬럼 목록) */
function buildNodeLabel(table: ERDTableInfo, maxCols: number = 12): string {
  const lines: string[] = [];

  // 테이블 헤더
  lines.push(table.name);
  lines.push('─'.repeat(Math.min(table.name.length + 4, 28)));

  // 컬럼 목록
  const displayCols = table.columns.slice(0, maxCols);
  for (const col of displayCols) {
    let prefix = '  ';
    if (col.isPrimaryKey) prefix = 'PK';
    else if (col.isForeignKey) prefix = 'FK';

    const type = shortType(col.dataType);
    lines.push(`${prefix} ${col.name}: ${type}`);
  }

  // 생략된 컬럼 수 표시
  const remaining = table.columns.length - displayCols.length;
  if (remaining > 0) {
    lines.push(`   ... +${remaining}`);
  }

  return lines.join('\n');
}

// ─── Cytoscape 스타일 정의 ────────────────────────────────

const CYTOSCAPE_STYLE: cytoscape.StylesheetStyle[] = [
  // 노드 기본 스타일 — 테이블 카드 형태
  {
    selector: 'node',
    style: {
      // 라벨
      label: 'data(label)',
      'text-wrap': 'wrap' as any,
      'text-max-width': '260px' as any,
      'text-valign': 'center',
      'text-halign': 'center',
      'font-family': 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
      'font-size': 10,
      color: '#333333',
      'text-justification': 'left' as any,

      // 배경 및 테두리
      'background-color': '#FFFFFF',
      'border-width': 1,
      'border-color': '#E5E5E5',
      shape: 'round-rectangle',

      // 크기 — 내용에 맞게 자동 조절
      width: 'label',
      height: 'label',
      'padding-top': '12px' as any,
      'padding-bottom': '12px' as any,
      'padding-left': '14px' as any,
      'padding-right': '14px' as any,

      // 상호작용
      'overlay-opacity': 0,
      'z-index': 1,
    },
  },
  // 엣지 기본 스타일
  {
    selector: 'edge',
    style: {
      width: 1.5,
      'line-color': '#CCCCCC',
      'target-arrow-color': '#CCCCCC',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 0.8,
      'curve-style': 'bezier',
      label: 'data(label)',
      'font-size': 8,
      'font-family': 'ui-monospace, SFMono-Regular, monospace',
      color: '#888888',
      'text-rotation': 'autorotate',
      'text-outline-width': 2,
      'text-outline-color': '#FFFFFF',
      'text-margin-y': -8,
      'overlay-opacity': 0,
    },
  },
  // 선택된 노드 — 오렌지 테두리 (#FF8400)
  {
    selector: 'node:selected',
    style: {
      'border-width': 2.5,
      'border-color': '#FF8400',
      'z-index': 20,
    },
  },
  // 하이라이트된 노드 (선택 노드의 이웃)
  {
    selector: 'node.highlighted',
    style: {
      'border-width': 2,
      'border-color': '#3B82F6',
      'background-color': '#F0F7FF',
      'z-index': 15,
    },
  },
  // 하이라이트된 엣지 (선택 노드의 연결선)
  {
    selector: 'edge.highlighted',
    style: {
      'line-color': '#3B82F6',
      'target-arrow-color': '#3B82F6',
      width: 2.5,
      'z-index': 15,
    },
  },
  // 희미해진 노드/엣지 (비연결 요소)
  {
    selector: 'node.dimmed',
    style: {
      opacity: 0.25,
    },
  },
  {
    selector: 'edge.dimmed',
    style: {
      opacity: 0.12,
    },
  },
  // 호버 — 테두리 강조
  {
    selector: 'node:active',
    style: {
      'overlay-opacity': 0.05,
      'overlay-color': '#3B82F6',
    },
  },
];

// ─── Props 타입 ───────────────────────────────────────────

interface CytoscapeERDRendererProps {
  /** ERD에 표시할 테이블 데이터 배열 */
  tables: ERDTableInfo[];
  /** 렌더링 상태 알림 */
  onRendered?: (hasDiagram: boolean) => void;
  /** 외부에서 Cytoscape 인스턴스 접근 (SVG 내보내기 등) */
  onCyInit?: (cy: cytoscape.Core) => void;
}

// ─── 컴포넌트 ─────────────────────────────────────────────

export function CytoscapeERDRenderer({
  tables,
  onRendered,
  onCyInit,
}: CytoscapeERDRendererProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [scale, setScale] = useState(100);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Cytoscape 인스턴스 초기화
  useEffect(() => {
    if (!containerRef.current) return;

    ensureExtensions();

    const cy = cytoscape({
      container: containerRef.current,
      style: CYTOSCAPE_STYLE,
      elements: [],
      // 줌/팬 기본 설정
      minZoom: 0.1,
      maxZoom: 5,
      wheelSensitivity: 0.3,
      // 박스 선택 비활성화 — 드래그가 팬으로 동작하도록
      boxSelectionEnabled: false,
    });

    cyRef.current = cy;
    onCyInit?.(cy);

    // 노드 클릭 → 연결된 엣지 하이라이트
    cy.on('tap', 'node', (evt) => {
      const nodeId = evt.target.id();
      const currentSelected = cyRef.current?.nodes(':selected').first()?.id();

      // 같은 노드 재클릭 → 선택 해제
      if (currentSelected === nodeId) {
        cy.elements().removeClass('highlighted dimmed');
        setSelectedNodeId(null);
        return;
      }

      setSelectedNodeId(nodeId);

      // 이웃 하이라이트 적용
      const node = evt.target;
      const neighborhood = node.closedNeighborhood();
      cy.elements().removeClass('highlighted dimmed');
      neighborhood.addClass('highlighted');
      cy.elements().not(neighborhood).addClass('dimmed');
    });

    // 배경 클릭 → 선택 해제
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass('highlighted dimmed');
        setSelectedNodeId(null);
      }
    });

    // 줌 레벨 변경 추적
    cy.on('zoom', () => {
      setScale(Math.round(cy.zoom() * 100));
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 테이블 데이터가 변경될 때 Cytoscape 요소 갱신
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    // 테이블이 없으면 요소 제거
    if (tables.length === 0) {
      cy.elements().remove();
      onRendered?.(false);
      return;
    }

    // FK 관계 추출
    const relations = extractRelations(tables);

    // 노드 생성 — 각 테이블이 하나의 노드
    const nodes: cytoscape.ElementDefinition[] = tables.map((table) => ({
      group: 'nodes' as const,
      data: {
        id: table.name.toLowerCase(),
        label: buildNodeLabel(table),
        tableName: table.name,
        schema: table.schema || '',
        columnCount: table.columns.length,
      },
    }));

    // 엣지 생성 — FK 관계
    const edges: cytoscape.ElementDefinition[] = relations.map((rel, idx) => ({
      group: 'edges' as const,
      data: {
        id: `e-${rel.fromTable.toLowerCase()}-${rel.toTable.toLowerCase()}-${idx}`,
        source: rel.fromTable.toLowerCase(),
        target: rel.toTable.toLowerCase(),
        label: rel.fromColumn,
        relationType: rel.type,
      },
    }));

    // 존재하지 않는 노드를 참조하는 엣지 필터링
    const nodeIds = new Set(nodes.map((n) => n.data.id));
    const validEdges = edges.filter(
      (e) => nodeIds.has(e.data.source as string) && nodeIds.has(e.data.target as string),
    );

    // 요소 업데이트
    cy.elements().remove();
    cy.add([...nodes, ...validEdges]);

    // 레이아웃 실행 — cose-bilkent (ERD에 적합한 힘 기반 레이아웃)
    const layout = cy.layout({
      name: 'cose-bilkent',
      animate: false,
      nodeDimensionsIncludeLabels: true,
      idealEdgeLength: 200,
      nodeRepulsion: 8000,
      gravity: 0.15,
      numIter: 3000,
      tile: true,
      // 노드 겹침 방지 간격
      tilingPaddingVertical: 30,
      tilingPaddingHorizontal: 30,
    } as any);

    layout.run();

    // 레이아웃 완료 후 뷰포트에 맞춤
    setTimeout(() => {
      cy.fit(undefined, 50);
      setScale(Math.round(cy.zoom() * 100));
      onRendered?.(true);
    }, 150);

    // 하이라이트 상태 초기화
    setSelectedNodeId(null);
  }, [tables, onRendered]);

  // 리사이즈 옵저버 — 컨테이너 크기 변경 시 Cytoscape 리사이즈
  useEffect(() => {
    const el = containerRef.current;
    const cy = cyRef.current;
    if (!el || !cy) return;

    const ro = new ResizeObserver(() => cy.resize());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ─── 줌 컨트롤 핸들러 ───────────────────────────────────

  const handleZoomIn = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({
      level: cy.zoom() * 1.3,
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
    });
  }, []);

  const handleZoomOut = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({
      level: cy.zoom() / 1.3,
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
    });
  }, []);

  const handleResetZoom = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.fit(undefined, 50);
    setScale(Math.round(cy.zoom() * 100));
    cy.elements().removeClass('highlighted dimmed');
    setSelectedNodeId(null);
  }, []);

  // ─── 빈 상태 처리 ───────────────────────────────────────

  if (tables.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-foreground/60 text-sm">
        {t('datasourcePage.whenDatasourceSelected')}
      </div>
    );
  }

  // ─── 렌더링 ─────────────────────────────────────────────

  return (
    <div className="relative w-full h-full overflow-hidden bg-card">
      {/* Cytoscape 컨테이너 */}
      <div
        ref={containerRef}
        className="w-full h-full"
        role="application"
        aria-label={`ERD 다이어그램. 테이블 ${tables.length}개 표시. 노드를 드래그하여 이동.`}
      />

      {/* 줌 컨트롤 — 우하단 고정 */}
      <div className="absolute bottom-4 right-4 flex items-center gap-1 bg-card border border-border rounded shadow-sm z-10">
        <button
          type="button"
          onClick={handleZoomIn}
          className="px-2 py-1 text-xs text-foreground/60 hover:text-foreground transition-colors"
          title={t('datasourceExt.zoomIn')}
          aria-label={t('workflowEditorExt.zoomIn')}
        >
          +
        </button>
        <span className="px-2 py-1 text-[10px] text-foreground/60 font-mono min-w-[40px] text-center">
          {scale}%
        </span>
        <button
          type="button"
          onClick={handleZoomOut}
          className="px-2 py-1 text-xs text-foreground/60 hover:text-foreground transition-colors"
          title={t('datasourceExt.zoomOut')}
          aria-label={t('workflowEditorExt.zoomOut')}
        >
          -
        </button>
        <button
          type="button"
          onClick={handleResetZoom}
          className="px-2 py-1 text-[10px] text-foreground/60 hover:text-foreground transition-colors border-l border-border"
          title={t('datasourceExt.resetZoom')}
          aria-label={t('datasourceExt.originalSize')}
        >
          Reset
        </button>
      </div>

      {/* 선택된 테이블 정보 표시 — 좌하단 */}
      {selectedNodeId && (
        <div className="absolute bottom-4 left-4 px-3 py-2 bg-card border border-border rounded shadow-sm z-10 text-[11px] font-mono text-foreground/70">
          <span className="text-foreground/40">{t('datasourceExt.selectedTable', '선택:')}</span>{' '}
          <span className="font-medium text-foreground/90">{selectedNodeId}</span>
        </div>
      )}
    </div>
  );
}
