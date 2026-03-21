/**
 * LineageGraphView — 데이터 리니지 Mermaid 그래프 뷰.
 *
 * OLAP Studio의 리니지 엔티티와 엣지를 Mermaid flowchart로 시각화한다.
 * 엔티티 타입별 색상 구분 + 엣지 타입별 라벨 표시.
 */
import { useMemo } from 'react';
import { MermaidERDRenderer } from '@/shared/components/MermaidERDRenderer';

// ─── 타입 정의 ─────────────────────────────────────────────

/** 리니지 그래프의 단일 엔티티 */
export interface LineageEntity {
  id: string;
  entity_type: string;
  display_name: string;
}

/** 리니지 그래프의 단일 엣지 (방향 있음) */
export interface LineageEdge {
  from_entity_id: string;
  to_entity_id: string;
  edge_type: string;
}

interface LineageGraphViewProps {
  entities: LineageEntity[];
  edges: LineageEdge[];
}

// ─── 엔티티 타입별 Mermaid 노드 형태 ───────────────────────

const ENTITY_SHAPES: Record<string, { prefix: string; suffix: string }> = {
  SOURCE_TABLE: { prefix: '[(', suffix: ')]' },   // 원통형 (DB)
  STAGING_TABLE: { prefix: '([', suffix: '])' },  // 경기장형
  FACT: { prefix: '[[', suffix: ']]' },           // 이중 사각형
  DIMENSION: { prefix: '[/', suffix: '/]' },       // 평행사변형
  CUBE: { prefix: '{', suffix: '}' },             // 다이아몬드
  MEASURE: { prefix: '((', suffix: '))' },         // 원형
  DAG: { prefix: '>', suffix: ']' },              // 비대칭
  REPORT: { prefix: '[', suffix: ']' },           // 사각형 (기본값)
};

// ─── 엣지 타입별 한글 라벨 ────────────────────────────────

const EDGE_LABELS: Record<string, string> = {
  DERIVES_TO: '파생',
  LOADS_TO: '적재',
  DEPENDS_ON: '의존',
  GENERATES: '생성',
  FEEDS: '공급',
};

// ─── 엔티티 타입별 색상 (Mermaid style) ────────────────────

const ENTITY_COLORS: Record<string, string> = {
  SOURCE_TABLE: '#60A5FA',   // blue-400
  STAGING_TABLE: '#A78BFA',  // purple-400
  FACT: '#34D399',           // emerald-400
  DIMENSION: '#FBBF24',      // amber-400
  CUBE: '#F87171',           // red-400
  MEASURE: '#2DD4BF',        // teal-400
};

// ─── 유틸리티 ──────────────────────────────────────────────

/** Mermaid ID로 사용할 수 있도록 특수문자를 제거한다 */
function sanitizeId(id: string): string {
  return id.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 20);
}

// ─── 컴포넌트 ──────────────────────────────────────────────

export function LineageGraphView({ entities, edges }: LineageGraphViewProps) {
  // Mermaid flowchart 코드 생성
  const mermaidCode = useMemo(() => {
    if (entities.length === 0) return '';

    const lines: string[] = ['flowchart LR'];

    // 엔티티 → Mermaid 노드 ID 맵핑
    const idMap = new Map<string, string>();

    entities.forEach((e, i) => {
      const safeId = `n${i}_${sanitizeId(e.display_name)}`;
      idMap.set(e.id, safeId);

      const shape = ENTITY_SHAPES[e.entity_type] || ENTITY_SHAPES.REPORT;
      lines.push(`    ${safeId}${shape.prefix}"${e.display_name}"${shape.suffix}`);
    });

    // 엣지 — 라벨 포함
    edges.forEach((edge) => {
      const from = idMap.get(edge.from_entity_id);
      const to = idMap.get(edge.to_entity_id);
      if (from && to) {
        const label = EDGE_LABELS[edge.edge_type] || edge.edge_type;
        lines.push(`    ${from} -->|${label}| ${to}`);
      }
    });

    // 엔티티 타입별 노드 색상 스타일
    entities.forEach((e) => {
      const safeId = idMap.get(e.id) || '';
      const color = ENTITY_COLORS[e.entity_type];
      if (color && safeId) {
        lines.push(`    style ${safeId} fill:${color},stroke:#333,color:#000`);
      }
    });

    return lines.join('\n');
  }, [entities, edges]);

  // 빈 상태
  if (!mermaidCode) {
    return (
      <div className="flex items-center justify-center h-full text-foreground/30 text-[11px] font-[IBM_Plex_Mono]">
        리니지 데이터가 없습니다
      </div>
    );
  }

  return <MermaidERDRenderer mermaidCode={mermaidCode} />;
}
