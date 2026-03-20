/**
 * LineageNodeDetail — 선택된 노드 상세 패널
 * 인바운드/아웃바운드 연결, 속성 목록을 보여준다.
 */

import { X, ArrowLeft, ArrowRight, ClipboardList } from 'lucide-react';
import { useLineageStore } from '../store/useLineageStore';
import { LINEAGE_NODE_STYLES, type LineageNode, type LineageEdge } from '../types/lineage';
import { useMemo } from 'react';

export function LineageNodeDetail() {
  const { selectedNode, nodes, edges, closeDetail } = useLineageStore();

  // 인바운드 연결 (이 노드로 들어오는 엣지)
  const inbound = useMemo(() => {
    if (!selectedNode) return [];
    return edges
      .filter((e) => e.target === selectedNode.id)
      .map((e) => ({ edge: e, node: nodes.find((n) => n.id === e.source) }))
      .filter((c): c is { edge: LineageEdge; node: LineageNode } => !!c.node);
  }, [selectedNode, edges, nodes]);

  // 아웃바운드 연결 (이 노드에서 나가는 엣지)
  const outbound = useMemo(() => {
    if (!selectedNode) return [];
    return edges
      .filter((e) => e.source === selectedNode.id)
      .map((e) => ({ edge: e, node: nodes.find((n) => n.id === e.target) }))
      .filter((c): c is { edge: LineageEdge; node: LineageNode } => !!c.node);
  }, [selectedNode, edges, nodes]);

  // 표시할 속성
  const displayProps = useMemo(() => {
    if (!selectedNode) return [];
    return Object.entries(selectedNode.properties || {}).map(([key, value]) => ({
      key,
      value: String(value),
    }));
  }, [selectedNode]);

  if (!selectedNode) return null;

  const style = LINEAGE_NODE_STYLES[selectedNode.type];

  return (
    <aside
      className="absolute top-0 right-0 z-50 flex h-full w-80 flex-col border-l border-border bg-card shadow-xl"
      role="complementary"
      aria-label="노드 상세 정보"
    >
      {/* ── 헤더 ── */}
      <header
        className="flex items-start justify-between gap-3 border-b border-border bg-muted/30 p-4"
        style={{ borderLeftWidth: 4, borderLeftColor: style.color }}
      >
        <div className="flex gap-3 min-w-0">
          {/* 타입 아이콘 */}
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm text-white"
            style={{ background: style.color }}
          >
            {selectedNode.type[0].toUpperCase()}
          </span>
          <div className="min-w-0">
            <h3 className="break-all text-sm font-semibold text-foreground">
              {selectedNode.name}
            </h3>
            <span className="text-[11px] font-medium uppercase tracking-wide" style={{ color: style.color }}>
              {style.label}
            </span>
          </div>
        </div>
        <button
          onClick={closeDetail}
          className="shrink-0 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="닫기"
        >
          <X className="h-4 w-4" />
        </button>
      </header>

      {/* ── 컨텐츠 (스크롤) ── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* 스키마/데이터소스 */}
        {(selectedNode.schema || selectedNode.datasource) && (
          <div className="text-xs text-muted-foreground">
            {selectedNode.schema && <span>Schema: {selectedNode.schema}</span>}
            {selectedNode.schema && selectedNode.datasource && <span> &middot; </span>}
            {selectedNode.datasource && <span>DS: {selectedNode.datasource}</span>}
          </div>
        )}

        {/* 설명 */}
        {selectedNode.description && (
          <p className="text-xs text-muted-foreground">{selectedNode.description}</p>
        )}

        {/* ── 인바운드 연결 ── */}
        {inbound.length > 0 && (
          <Section
            icon={<ArrowLeft className="h-3.5 w-3.5" />}
            title={`데이터 입력원 (${inbound.length})`}
          >
            <ConnectionList items={inbound} />
          </Section>
        )}

        {/* ── 아웃바운드 연결 ── */}
        {outbound.length > 0 && (
          <Section
            icon={<ArrowRight className="h-3.5 w-3.5" />}
            title={`데이터 출력 (${outbound.length})`}
          >
            <ConnectionList items={outbound} />
          </Section>
        )}

        {/* ── 속성 ── */}
        {displayProps.length > 0 && (
          <Section
            icon={<ClipboardList className="h-3.5 w-3.5" />}
            title="속성"
          >
            <div className="flex flex-col gap-1">
              {displayProps.map(({ key, value }) => (
                <div
                  key={key}
                  className="flex items-start justify-between gap-3 rounded-md bg-muted/40 px-2.5 py-2"
                >
                  <span className="shrink-0 text-[11px] font-medium text-muted-foreground">
                    {key}
                  </span>
                  <span className="break-all text-right text-xs text-foreground">{value}</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* 연결 없음 */}
        {inbound.length === 0 && outbound.length === 0 && displayProps.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <span className="text-3xl opacity-40 mb-3">&#128279;</span>
            <p className="text-sm text-muted-foreground">
              연결된 데이터 흐름이 없습니다.
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// 내부 서브 컴포넌트
// ---------------------------------------------------------------------------

/** 섹션 래퍼 */
function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h4 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {icon}
        {title}
      </h4>
      {children}
    </section>
  );
}

/** 연결 목록 */
function ConnectionList({
  items,
}: {
  items: { edge: LineageEdge; node: LineageNode }[];
}) {
  return (
    <div className="flex flex-col gap-1.5">
      {items.map(({ edge, node }) => {
        const nodeStyle = LINEAGE_NODE_STYLES[node.type];
        return (
          <div
            key={edge.id}
            className="flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 transition-colors hover:bg-muted/60 hover:border-primary/30"
          >
            <span
              className="h-3 w-3 shrink-0 rounded-sm"
              style={{ background: nodeStyle.color }}
            />
            <span className="flex-1 truncate text-[13px] font-medium text-foreground">
              {node.name}
            </span>
            <span className="shrink-0 rounded bg-card px-1.5 py-0.5 text-[9px] font-medium uppercase text-muted-foreground">
              {node.type}
            </span>
          </div>
        );
      })}
    </div>
  );
}
